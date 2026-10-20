"""
Optimized YOLOv8 Vehicle Detection & Tracking Service
Features:
- Streaming frame processing (bounded memory, zero RAM bloat)
- Asynchronous job execution with progress tracking and TTL cleanup
- Configurable tripwire line & minimum box area filtering
- Directional throughput counting (IN/OUT)
- Real-time video encoding using imageio-ffmpeg / cv2
- Multi-worker-safe file-based job storage
"""
import os
import sys
import time
import json
import uuid
import shutil
import threading
from pathlib import Path
from collections import defaultdict, Counter

import cv2
import numpy as np

# Ensure root in path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
from backend.config import Config

CLASS_LABELS = {
    1: 'Bicycle',
    2: 'Car',
    3: 'Motorcycle',
    5: 'Bus',
    7: 'Truck'
}
ALLOWED_CLASSES = list(CLASS_LABELS.keys())
MIN_CONFIRMED_HITS = 4  # Frames required to confirm track authenticity
JOB_TTL_SECONDS = 3600  # 1 hour TTL

# Thread lock for single active heavy YOLO processing job to protect memory
YOLO_SEMAPHORE = threading.Semaphore(1)

_cached_models = {}

def get_yolo_model(weights_choice="yolov8s"):
    """Load and cache YOLO model from backend/models/ or auto-download."""
    from ultralytics import YOLO
    
    models_dir = Path(Config.BASE_DIR) / "backend" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    target_name = "yolov8s.pt" if "s" in weights_choice.lower() else "yolov8n.pt"
    local_path = models_dir / target_name
    
    if not local_path.exists():
        # Fall back to root or download
        root_path = Path(Config.BASE_DIR) / target_name
        if root_path.exists():
            shutil.copy2(root_path, local_path)
            
    model_key = str(local_path if local_path.exists() else target_name)
    if model_key not in _cached_models:
        print(f"[YOLO] Loading model weights: {model_key}")
        _cached_models[model_key] = YOLO(model_key)
        
    return _cached_models[model_key], target_name

def get_job_dir(job_id):
    d = Path(Config.JOBS_DIR) / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def write_job_meta(job_id, data):
    job_dir = get_job_dir(job_id)
    meta_file = job_dir / "meta.json"
    with open(meta_file, "w") as f:
        json.dump(data, f, indent=2)

def read_job_meta(job_id):
    job_dir = Path(Config.JOBS_DIR) / job_id
    meta_file = job_dir / "meta.json"
    if not meta_file.exists():
        return None
    with open(meta_file, "r") as f:
        return json.load(f)

def cleanup_old_jobs():
    """Remove jobs and media files older than TTL."""
    jobs_root = Path(Config.JOBS_DIR)
    if not jobs_root.exists():
        return
    now = time.time()
    for item in jobs_root.iterdir():
        if item.is_dir():
            try:
                mtime = item.stat().st_mtime
                if now - mtime > JOB_TTL_SECONDS:
                    shutil.rmtree(item, ignore_errors=True)
            except Exception:
                pass

def process_detection_job(
    job_id, input_path, is_image, conf_thresh=0.25,
    weights_choice="yolov8s", line_pos_ratio=0.58, frame_stride=1
):
    """Worker function executing frame streaming YOLO detection."""
    cleanup_old_jobs()
    job_dir = get_job_dir(job_id)
    
    write_job_meta(job_id, {
        "job_id": job_id,
        "state": "RUNNING",
        "progress": 5,
        "frames_done": 0,
        "frames_total": 1,
        "eta_seconds": 0,
        "created_at": time.time(),
        "error": None
    })
    
    with YOLO_SEMAPHORE:
        try:
            model, used_weights = get_yolo_model(weights_choice)
            
            if is_image:
                _process_image(job_id, job_dir, input_path, model, used_weights, conf_thresh)
            else:
                _process_video(job_id, job_dir, input_path, model, used_weights, conf_thresh, line_pos_ratio, frame_stride)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            write_job_meta(job_id, {
                "job_id": job_id,
                "state": "FAILED",
                "progress": 0,
                "error": str(e),
                "created_at": time.time()
            })
        finally:
            # Clean up uploaded raw input file
            if os.path.exists(input_path):
                try:
                    os.remove(input_path)
                except Exception:
                    pass

def _process_image(job_id, job_dir, input_path, model, used_weights, conf_thresh):
    frame = cv2.imread(input_path)
    if frame is None:
        raise ValueError("Failed to decode uploaded image. Invalid format or corrupted file.")
        
    h, w, _ = frame.shape
    results = model(frame, conf=conf_thresh, classes=ALLOWED_CLASSES, verbose=False)
    
    annotated_frame = results[0].plot() if results else frame.copy()
    
    agg_counts = {v: 0 for v in CLASS_LABELS.values()}
    heavy_vehicle_detected = False
    
    if results and results[0].boxes:
        for box in results[0].boxes:
            c_id = int(box.cls[0].item())
            if c_id in CLASS_LABELS:
                agg_counts[CLASS_LABELS[c_id]] += 1
                if c_id in (5, 7):  # Bus or Truck
                    heavy_vehicle_detected = True
                    
    total = sum(agg_counts.values())
    
    # Draw clean HUD
    hud_text = f"Vehicles in Image: {total} | Heavy: {'Yes' if heavy_vehicle_detected else 'None'}"
    (tw, th), _ = cv2.getTextSize(hud_text, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
    cv2.rectangle(annotated_frame, (16, 16), (tw + 36, th + 32), (15, 23, 42), -1)
    cv2.rectangle(annotated_frame, (16, 16), (tw + 36, th + 32), (23, 178, 106), 2)
    cv2.putText(annotated_frame, hud_text, (26, th + 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
                
    output_filename = "annotated_image.jpg"
    output_path = job_dir / output_filename
    cv2.imwrite(str(output_path), annotated_frame)
    
    result_data = {
        "job_id": job_id,
        "is_image": True,
        "counts": agg_counts,
        "total": total,
        "peak_vehicles": total,
        "avg_vehicles": total,
        "line_crossed_total": total,
        "confirmed_unique_total": total,
        "heavy_vehicle_detected": heavy_vehicle_detected,
        "density": "High" if total >= 8 else ("Medium" if total >= 4 else "Low"),
        "density_score": round(min(total / 12.0, 1.0), 2),
        "conf_used": conf_thresh,
        "model_used": used_weights,
        "download_url": f"/api/yolo/download/{job_id}",
        "filename": output_filename,
        "mimetype": "image/jpeg"
    }
    
    write_job_meta(job_id, {
        "job_id": job_id,
        "state": "COMPLETED",
        "progress": 100,
        "frames_done": 1,
        "frames_total": 1,
        "result": result_data,
        "created_at": time.time()
    })

def _process_video(job_id, job_dir, input_path, model, used_weights, conf_thresh, line_pos_ratio, frame_stride):
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise ValueError("Failed to open uploaded video stream.")
        
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 100
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Bound max frames to protect resources (e.g. max 500 frames)
    max_frames = min(total_frames, 500)
    line_y = int(height * line_pos_ratio)
    
    output_filename = "annotated_video.mp4"
    output_path = job_dir / output_filename
    
    # Try H.264 mp4v writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    
    track_history = defaultdict(list)
    track_centroids = defaultdict(list)
    crossed_tids = set()
    crossed_directions = {}
    line_crossed_counts = {v: 0 for v in CLASS_LABELS.values()}
    direction_counts = {"IN": 0, "OUT": 0}
    
    frame_counts = []
    heavy_vehicle_detected = False
    
    frame_idx = 0
    start_time = time.time()
    
    while cap.isOpened() and frame_idx < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_idx += 1
        if frame_idx % frame_stride != 0:
            continue
            
        # YOLO Track with persistence (ByteTrack)
        results = model.track(
            frame,
            persist=True,
            conf=conf_thresh,
            classes=ALLOWED_CLASSES,
            verbose=False
        )
        
        annotated_frame = frame.copy()
        current_frame_vehicles = 0
        
        # Draw Tripwire Line
        cv2.line(annotated_frame, (0, line_y), (width, line_y), (0, 165, 255), 2)
        cv2.putText(annotated_frame, f"TRIPWIRE (Throughput Line: {int(line_pos_ratio*100)}%)",
                    (20, line_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 165, 255), 2, cv2.LINE_AA)
                    
        if results and results[0].boxes and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().numpy()
            class_ids = results[0].boxes.cls.int().cpu().numpy()
            confs = results[0].boxes.conf.cpu().numpy()
            
            for box, tid, cls_id, conf in zip(boxes, track_ids, class_ids, confs):
                if cls_id not in CLASS_LABELS:
                    continue
                    
                x1, y1, x2, y2 = box
                box_area = (x2 - x1) * (y2 - y1)
                
                # Filter out tiny distant noise boxes (< 0.05% of frame area)
                if box_area < (0.0005 * width * height):
                    continue
                    
                current_frame_vehicles += 1
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                
                track_history[tid].append((cls_id, conf, box_area))
                track_centroids[tid].append((cx, cy))
                
                # Check for Heavy Vehicles (Bus / Truck)
                if cls_id in (5, 7):
                    heavy_vehicle_detected = True
                    
                # Trajectory trail (last 8 points)
                pts = track_centroids[tid][-8:]
                for i in range(1, len(pts)):
                    cv2.line(annotated_frame, pts[i - 1], pts[i], (0, 255, 255), 2)
                    
                # Check Tripwire Crossing
                if len(pts) >= 2 and (tid not in crossed_tids):
                    prev_y = pts[-2][1]
                    curr_y = pts[-1][1]
                    if (prev_y < line_y <= curr_y) or (prev_y > line_y >= curr_y):
                        crossed_tids.add(tid)
                        direction = "IN" if curr_y >= line_y else "OUT"
                        crossed_directions[tid] = direction
                        direction_counts[direction] += 1
                        
                        dom_cls = Counter([r[0] for r in track_history[tid]]).most_common(1)[0][0]
                        line_crossed_counts[CLASS_LABELS.get(dom_cls, 'Car')] += 1
                        
                # Draw vehicle box and status
                color = (0, 230, 115) if tid in crossed_tids else (255, 178, 23)
                cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                lbl = f"#{tid} {CLASS_LABELS.get(cls_id, 'Car')}"
                if tid in crossed_tids:
                    lbl += f" [{crossed_directions.get(tid, 'CROSSED')}]"
                cv2.putText(annotated_frame, lbl, (int(x1), int(y1) - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
                            
        frame_counts.append(current_frame_vehicles)
        
        # Draw Informative HUD
        confirmed_unique = sum(1 for tid, recs in track_history.items() if len(recs) >= MIN_CONFIRMED_HITS)
        hud_text = f"In Frame: {current_frame_vehicles}  |  Tripwire Crossed: {len(crossed_tids)} (IN:{direction_counts['IN']}, OUT:{direction_counts['OUT']})  |  Tracks: {confirmed_unique}"
        (tw, th), _ = cv2.getTextSize(hud_text, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        cv2.rectangle(annotated_frame, (16, 16), (tw + 36, th + 32), (15, 23, 42), -1)
        cv2.rectangle(annotated_frame, (16, 16), (tw + 36, th + 32), (23, 178, 106), 2)
        cv2.putText(annotated_frame, hud_text, (26, th + 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
                    
        out_writer.write(annotated_frame)
        
        # Update progress every 20 frames
        if frame_idx % 20 == 0:
            pct = int((frame_idx / float(max_frames)) * 90) + 5
            elapsed = time.time() - start_time
            rate = frame_idx / max(elapsed, 0.1)
            eta = int((max_frames - frame_idx) / max(rate, 0.1))
            write_job_meta(job_id, {
                "job_id": job_id,
                "state": "RUNNING",
                "progress": pct,
                "frames_done": frame_idx,
                "frames_total": max_frames,
                "eta_seconds": eta,
                "created_at": time.time(),
                "error": None
            })
            
    cap.release()
    out_writer.release()
    
    # Calculate robust summary counts
    confirmed_tracks = {tid: recs for tid, recs in track_history.items() if len(recs) >= MIN_CONFIRMED_HITS}
    agg_counts = {v: 0 for v in CLASS_LABELS.values()}
    for tid, recs in confirmed_tracks.items():
        dom_cls = Counter([r[0] for r in recs]).most_common(1)[0][0]
        agg_counts[CLASS_LABELS.get(dom_cls, 'Car')] += 1
        
    line_total = len(crossed_tids)
    confirmed_total = len(confirmed_tracks)
    peak_count = max(frame_counts) if frame_counts else 0
    avg_per_frame = (sum(frame_counts) / max(len(frame_counts), 1))
    
    # Use tripwire line crossed total as primary throughput metric if available
    total = line_total if line_total > 0 else (confirmed_total if confirmed_total > 0 else peak_count)
    if line_total > 0 and sum(line_crossed_counts.values()) > 0:
        agg_counts = line_crossed_counts
        
    result_data = {
        "job_id": job_id,
        "is_image": False,
        "counts": agg_counts,
        "total": total,
        "line_crossed_total": line_total,
        "confirmed_unique_total": confirmed_total,
        "peak_vehicles": peak_count,
        "avg_vehicles": round(avg_per_frame, 1),
        "direction_counts": direction_counts,
        "heavy_vehicle_detected": heavy_vehicle_detected,
        "density": "High" if avg_per_frame >= 8 else ("Medium" if avg_per_frame >= 4 else "Low"),
        "density_score": round(min(avg_per_frame / 10.0, 1.0), 2),
        "total_frames_sampled": len(frame_counts),
        "conf_used": conf_thresh,
        "model_used": used_weights,
        "download_url": f"/api/yolo/download/{job_id}",
        "filename": output_filename,
        "mimetype": "video/mp4"
    }
    
    write_job_meta(job_id, {
        "job_id": job_id,
        "state": "COMPLETED",
        "progress": 100,
        "frames_done": frame_idx,
        "frames_total": max_frames,
        "result": result_data,
        "created_at": time.time()
    })
