/**
 * YOLOv8 Vehicle Detection & Streaming Analytics Module
 */
import { fetchApi } from './api.js';
import { escapeHtml, showToast } from './utils.js';

let _activePollInterval = null;
let _lastDetectionResult = null;

export function initYolo() {
  const uploadForm = document.getElementById('yolo-upload-form');
  const fileInput = document.getElementById('yolo-file-input');
  const lineSlider = document.getElementById('yolo-line-slider');
  const lineVal = document.getElementById('yolo-line-val');
  const planSignalBtn = document.getElementById('yolo-plan-signal-btn');

  if (lineSlider && lineVal) {
    lineSlider.addEventListener('input', () => {
      lineVal.textContent = `${lineSlider.value}%`;
    });
  }

  if (uploadForm) {
    uploadForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        showToast('warning', 'No File Selected', 'Please choose a video or image file.');
        return;
      }

      const file = fileInput.files[0];
      const formData = new FormData();
      formData.append('file', file);
      formData.append('confidence', document.getElementById('yolo-conf-slider')?.value || 0.25);
      formData.append('weights', document.getElementById('yolo-model-select')?.value || 'yolov8s');
      formData.append('line_position', (parseInt(lineSlider?.value || 58) / 100.0));

      const submitBtn = document.getElementById('yolo-submit-btn');
      if (submitBtn) submitBtn.disabled = true;

      try {
        showProgressUI(true);
        const res = await fetchApi('/api/yolo/detect', {
          method: 'POST',
          body: formData
        });

        if (res.success && res.job_id) {
          showToast('info', 'Processing Queued', 'Running streaming detection and vehicle tracking...');
          pollJobStatus(res.job_id);
        }
      } catch (err) {
        showToast('error', 'Detection Failed', err.message || 'Upload error');
        showProgressUI(false);
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }

  if (planSignalBtn) {
    planSignalBtn.addEventListener('click', () => {
      if (!_lastDetectionResult) {
        showToast('warning', 'No Counts Available', 'Run a vehicle detection first.');
        return;
      }
      // Export counts to Signal page
      window.sessionStorage.setItem('kochi_yolo_counts', JSON.stringify(_lastDetectionResult.counts));
      showToast('success', 'Counts Exported', 'Transferred vehicle class counts to Traffic Signal Optimizer.');
      // Switch to traffic management page
      const navTraffic = document.querySelector('[data-page="traffic"]');
      if (navTraffic) navTraffic.click();
    });
  }
}

function showProgressUI(show) {
  const pBox = document.getElementById('yolo-progress-box');
  const pBar = document.getElementById('yolo-progress-bar');
  const pText = document.getElementById('yolo-progress-text');

  if (pBox) pBox.style.display = show ? 'block' : 'none';
  if (pBar) pBar.style.width = '5%';
  if (pText) pText.textContent = 'Initializing detection pipeline...';
}

function pollJobStatus(jobId) {
  if (_activePollInterval) clearInterval(_activePollInterval);

  const pBar = document.getElementById('yolo-progress-bar');
  const pText = document.getElementById('yolo-progress-text');
  const submitBtn = document.getElementById('yolo-submit-btn');

  _activePollInterval = setInterval(async () => {
    try {
      const statusRes = await fetchApi(`/api/yolo/status/${jobId}`);
      if (!statusRes.success) return;

      if (statusRes.state === 'RUNNING') {
        const pct = statusRes.progress || 10;
        if (pBar) pBar.style.width = `${pct}%`;
        if (pText) pText.textContent = `Processing frames (${statusRes.frames_done}/${statusRes.frames_total}) · ETA: ${statusRes.eta_seconds}s`;
      } else if (statusRes.state === 'COMPLETED') {
        clearInterval(_activePollInterval);
        showProgressUI(false);
        if (submitBtn) submitBtn.disabled = false;

        // Fetch final result
        const resultRes = await fetchApi(`/api/yolo/result/${jobId}`);
        if (resultRes.success) {
          _lastDetectionResult = resultRes;
          renderYoloResults(resultRes);
          showToast('success', 'Detection Complete', `Throughput: ${resultRes.total} vehicles · Density: ${resultRes.density}`);
        }
      } else if (statusRes.state === 'FAILED') {
        clearInterval(_activePollInterval);
        showProgressUI(false);
        if (submitBtn) submitBtn.disabled = false;
        showToast('error', 'Detection Error', statusRes.error || 'Processing failed');
      }
    } catch (e) {
      clearInterval(_activePollInterval);
      showProgressUI(false);
      if (submitBtn) submitBtn.disabled = false;
    }
  }, 1200);
}

function renderYoloResults(data) {
  // Update Video / Image Preview
  const playerWrap = document.getElementById('yolo-player-wrap');
  if (playerWrap) {
    if (data.is_image) {
      playerWrap.innerHTML = `
        <img src="${data.download_url}" style="width:100%; max-height:480px; object-fit:contain; border-radius:8px; border:1px solid #E2E8F0;" alt="Annotated Vehicle Detection" />
      `;
    } else {
      playerWrap.innerHTML = `
        <video controls autoplay loop muted style="width:100%; max-height:480px; object-fit:contain; border-radius:8px; border:1px solid #E2E8F0;">
          <source src="${data.download_url}" type="video/mp4">
          Your browser does not support HTML5 video streaming.
        </video>
      `;
    }
  }

  // Update counts
  const totDisp = document.getElementById('yolo-total-display');
  const lineDisp = document.getElementById('yolo-line-display');
  const peakDisp = document.getElementById('yolo-peak-display');
  const densityBadge = document.getElementById('yolo-density-badge');
  const countsTbody = document.getElementById('yolo-class-tbody');

  if (totDisp) totDisp.textContent = data.total;
  if (lineDisp) lineDisp.textContent = data.line_crossed_total;
  if (peakDisp) peakDisp.textContent = data.peak_vehicles;

  if (densityBadge) {
    densityBadge.textContent = `Traffic Density: ${data.density}`;
    densityBadge.className = `badge ${data.density === 'High' ? 'b-red' : (data.density === 'Medium' ? 'b-orange' : 'b-green')}`;
  }

  if (countsTbody && data.counts) {
    countsTbody.innerHTML = Object.entries(data.counts).map(([cls, cnt]) => `
      <tr>
        <td><strong>${escapeHtml(cls)}</strong></td>
        <td style="text-align:right; font-weight:700;">${cnt}</td>
      </tr>
    `).join('');
  }

  // Heavy vehicle alert
  const heavyBanner = document.getElementById('yolo-heavy-banner');
  if (heavyBanner) {
    if (data.heavy_vehicle_detected) {
      heavyBanner.style.display = 'block';
      heavyBanner.innerHTML = `
        <div class="toast-body" style="padding:10px 14px; background:#FEF3F2; border-left:4px solid #F04438; border-radius:6px; margin-top:10px;">
          <strong>Heavy Vehicle Tracked:</strong> Bus or large commercial vehicle detected in corridor. Automatic PCU weighting applied for signal optimization.
        </div>
      `;
    } else {
      heavyBanner.style.display = 'none';
    }
  }
}
