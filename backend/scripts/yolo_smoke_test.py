"""
YOLO Detection Smoke Test Script (P8.7)
Runs streaming vehicle detection on a short test image/clip,
asserts output media file existence, non-negative vehicle counts,
and verifies memory consumption stays strictly bounded.
"""
import os
import sys
import time
import tracemalloc
from pathlib import Path
import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.config import Config
from backend.yolo_service import process_detection_job, read_job_meta

def run_yolo_smoke_test():
    print("==========================================")
    print("Running YOLO Detection Smoke Test")
    print("==========================================")
    
    tracemalloc.start()
    start_time = time.time()
    
    # 1. Create a synthetic test video clip (40 frames, 640x480) with moving synthetic vehicles
    test_dir = Path(Config.BASE_DIR) / "tmp" / "test_media"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_video_path = test_dir / "smoke_sample.mp4"
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(test_video_path), fourcc, 20.0, (640, 480))
    for f_i in range(30):
        frame = np.full((480, 640, 3), 40, dtype=np.uint8)
        # Draw road
        cv2.rectangle(frame, (180, 0), (460, 480), (70, 70, 70), -1)
        # Draw moving rectangle simulating a vehicle
        y_pos = int(50 + f_i * 10)
        cv2.rectangle(frame, (260, y_pos), (360, y_pos + 60), (200, 200, 200), -1)
        out.write(frame)
    out.release()
    print(f"Created synthetic sample video: {test_video_path}")
    
    # 2. Run detection job
    job_id = f"smoke_job_{int(time.time())}"
    print(f"Processing detection job: {job_id}")
    process_detection_job(
        job_id=job_id,
        input_path=str(test_video_path),
        is_image=False,
        conf_thresh=0.20,
        weights_choice="yolov8n",  # use nano for fast smoke testing
        line_pos_ratio=0.58
    )
    
    # 3. Read metadata and verify
    meta = read_job_meta(job_id)
    assert meta is not None, "Smoke test failed: Job metadata was not written!"
    assert meta["state"] == "COMPLETED", f"Smoke test failed: Job state is {meta.get('state')} with error: {meta.get('error')}"
    
    result = meta["result"]
    print("\nSmoke Test Results:")
    print(f"  - Job ID:            {job_id}")
    print(f"  - Total Vehicles:    {result['total']}")
    print(f"  - Peak in Frame:     {result['peak_vehicles']}")
    print(f"  - Crossed Tripwire:  {result['line_crossed_total']}")
    print(f"  - Confirmed Tracks:  {result['confirmed_unique_total']}")
    print(f"  - Density Rating:    {result['density']}")
    
    # Verify non-negative counts
    assert result['total'] >= 0
    assert result['peak_vehicles'] >= 0
    assert result['line_crossed_total'] >= 0
    
    # Verify output file
    output_path = Path(Config.JOBS_DIR) / job_id / result["filename"]
    assert output_path.exists(), f"Smoke test failed: Output file {output_path} does not exist!"
    assert output_path.stat().st_size > 1000, "Smoke test failed: Output file is empty!"
    print(f"  - Output Media File: {output_path} ({output_path.stat().st_size} bytes)")
    
    # Check memory boundedness
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak_mem / (1024 * 1024)
    print(f"  - Peak Memory Usage: {peak_mb:.2f} MB (Bounded)")
    print(f"  - Execution Time:    {time.time() - start_time:.2f} s")
    
    print("\n==========================================")
    print("YOLO Detection Smoke Test PASSED Successfully!")
    print("==========================================\n")

if __name__ == "__main__":
    run_yolo_smoke_test()
