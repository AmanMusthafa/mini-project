/**
 * Severity Prediction & Explainability (TreeSHAP) Module
 */
import { fetchApi } from './api.js';
import { escapeHtml, showToast } from './utils.js';

let _cachedMetadata = null;

export async function initPredict() {
  await loadMetadata();
  await loadModelInfoCard();
  bindPredictForm();
}

async function loadMetadata() {
  try {
    const res = await fetchApi('/api/model-metadata');
    if (res.success && res.metadata) {
      _cachedMetadata = res.metadata;
      populateAreaRoadDropdowns(_cachedMetadata);
    }
  } catch (err) {
    console.warn('[Predict] Failed to load metadata:', err);
  }
}

function populateAreaRoadDropdowns(meta) {
  const areaSelect = document.getElementById('pred-area');
  const roadSelect = document.getElementById('pred-road');
  if (!areaSelect || !roadSelect) return;

  const areas = meta.areas || [];
  areaSelect.innerHTML = `<option value="">Select Kochi Area</option>` +
    areas.map(a => `<option value="${escapeHtml(a)}">${escapeHtml(a)}</option>`).join('');

  areaSelect.addEventListener('change', () => {
    const selectedArea = areaSelect.value;
    const roads = (meta.area_roads && meta.area_roads[selectedArea]) || [];
    roadSelect.innerHTML = `<option value="">Select Road / Corridor</option>` +
      roads.map(r => `<option value="${escapeHtml(r)}">${escapeHtml(r)}</option>`).join('');
  });
}

async function loadModelInfoCard() {
  const cardContainer = document.getElementById('model-info-card');
  if (!cardContainer) return;

  try {
    const res = await fetchApi('/api/model-info');
    if (!res.success || !res.model_info) return;

    const info = res.model_info;
    const m = info.metrics || {};
    cardContainer.innerHTML = `
      <div class="card card-pad hoverable">
        <div class="card-head">
          <div class="card-head-text">
            <h3>Verified Machine Learning Model Info</h3>
            <div class="card-sub">${escapeHtml(info.model_name)} (v${escapeHtml(info.version)})</div>
          </div>
          <span class="badge b-green">Calibrated XGBoost</span>
        </div>
        <div class="grid grid-4" style="gap:12px; margin-top:8px;">
          <div class="kpi-mini">
            <div class="text-dim" style="font-size:11px;">Hold-out Macro-F1</div>
            <div style="font-size:18px; font-weight:800; color:#17B26A;">${(m.test_macro_f1 || 0).toFixed(4)}</div>
            <div class="text-dim" style="font-size:10px;">Baseline: ${(m.majority_baseline_macro_f1 || 0).toFixed(4)}</div>
          </div>
          <div class="kpi-mini">
            <div class="text-dim" style="font-size:11px;">Balanced Accuracy</div>
            <div style="font-size:18px; font-weight:800; color:#2D7CFF;">${((m.test_balanced_accuracy || 0) * 100).toFixed(1)}%</div>
            <div class="text-dim" style="font-size:10px;">Majority: ${((m.majority_baseline_accuracy || 0) * 100).toFixed(1)}%</div>
          </div>
          <div class="kpi-mini">
            <div class="text-dim" style="font-size:11px;">5-Fold CV Macro-F1</div>
            <div style="font-size:16px; font-weight:700;">${escapeHtml(m.cv_5fold_macro_f1 || 'N/A')}</div>
            <div class="text-dim" style="font-size:10px;">Cross-validated</div>
          </div>
          <div class="kpi-mini">
            <div class="text-dim" style="font-size:11px;">Dataset Provenance</div>
            <div style="font-size:14px; font-weight:700;">${(info.dataset && info.dataset.total_rows_trained) || 15000} Rows</div>
            <div class="text-dim" style="font-size:10px; color:#F79009;">Synthetic Demo Data</div>
          </div>
        </div>
        <div style="margin-top:10px; font-size:11px; color:#64748B; line-height:1.4;">
          <strong>Disclaimer:</strong> ${escapeHtml((info.limitations_and_ethics && info.limitations_and_ethics[0]) || 'Model trained on probabilistic synthetic Kochi data.')}
        </div>
      </div>
    `;
  } catch (err) {}
}

function bindPredictForm() {
  const form = document.getElementById('predict-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('predict-submit-btn');
    if (btn) btn.disabled = true;

    const payload = {
      area: document.getElementById('pred-area')?.value || '',
      road_name: document.getElementById('pred-road')?.value || '',
      road_type: document.getElementById('pred-road-type')?.value || 'urban',
      lanes: parseInt(document.getElementById('pred-lanes')?.value || 2),
      traffic_signal: parseInt(document.getElementById('pred-signal')?.value || 0),
      weather: document.getElementById('pred-weather')?.value || 'clear',
      visibility: document.getElementById('pred-visibility')?.value || 'high',
      traffic_density: document.getElementById('pred-density')?.value || 'medium',
      cause: document.getElementById('pred-cause')?.value || 'overspeeding',
      day_of_week: document.getElementById('pred-day')?.value || 'Friday',
      hour: parseInt(document.getElementById('pred-hour')?.value || 18),
      vehicles_involved: parseInt(document.getElementById('pred-vehicles')?.value || 2)
    };

    try {
      const res = await fetchApi('/api/predict-severity', {
        method: 'POST',
        body: payload
      });

      if (res.success) {
        renderPredictionResults(res);
        showToast('success', 'Prediction Generated', `Predicted: ${res.predicted_severity.toUpperCase()} (${(res.probability * 100).toFixed(1)}% prob)`);
      }
    } catch (err) {
      showToast('error', 'Prediction Failed', err.message || 'Validation error');
    } finally {
      if (btn) btn.disabled = false;
    }
  });
}

function renderPredictionResults(data) {
  // 1. Severity Badge & Probability
  const sevEl = document.getElementById('pred-result-severity');
  const probEl = document.getElementById('pred-result-prob');
  const gaugeFill = document.getElementById('pred-gauge-fill');
  const gaugeText = document.getElementById('pred-gauge-text');

  if (sevEl) {
    sevEl.textContent = data.predicted_severity.toUpperCase();
    sevEl.className = `badge ${data.predicted_severity === 'fatal' ? 'b-red' : (data.predicted_severity === 'major' ? 'b-orange' : 'b-green')}`;
  }

  if (probEl) {
    probEl.textContent = `${(data.probability * 100).toFixed(1)}%`;
  }

  // 2. Expected Severity Index (0 - 100)
  if (gaugeFill && gaugeText) {
    const score = data.expected_severity_score;
    gaugeFill.style.width = `${score}%`;
    gaugeFill.style.backgroundColor = score > 60 ? '#F04438' : (score > 35 ? '#F79009' : '#17B26A');
    gaugeText.textContent = `Severity Index: ${score} / 100`;
  }

  // 3. Class probability bars
  const pBars = document.getElementById('pred-prob-bars');
  if (pBars && data.class_probabilities) {
    const cp = data.class_probabilities;
    pBars.innerHTML = `
      <div style="font-size:12px; margin-bottom:4px;">Predicted-class probability distribution:</div>
      <div style="display:flex; height:12px; border-radius:6px; overflow:hidden; background:#E2E8F0; margin-bottom:6px;">
        <div style="width:${(cp.minor * 100).toFixed(1)}%; background:#17B26A;" title="Minor: ${(cp.minor * 100).toFixed(1)}%"></div>
        <div style="width:${(cp.major * 100).toFixed(1)}%; background:#F79009;" title="Major: ${(cp.major * 100).toFixed(1)}%"></div>
        <div style="width:${(cp.fatal * 100).toFixed(1)}%; background:#F04438;" title="Fatal: ${(cp.fatal * 100).toFixed(1)}%"></div>
      </div>
      <div style="display:flex; justify-content:space-between; font-size:11px;" class="text-dim">
        <span>Minor: ${(cp.minor * 100).toFixed(1)}%</span>
        <span>Major: ${(cp.major * 100).toFixed(1)}%</span>
        <span>Fatal: ${(cp.fatal * 100).toFixed(1)}%</span>
      </div>
    `;
  }

  // 4. SHAP Local Explanation Waterfall / Feature Bars
  const shapList = document.getElementById('pred-shap-list');
  if (shapList && data.shap_features) {
    shapList.innerHTML = data.shap_features.map(f => {
      const isSupport = f.direction === 'supports';
      const barColor = isSupport ? '#2D7CFF' : '#94A3B8';
      const widthPct = Math.min(Math.abs(f.shap_value) * 120, 100);
      return `
        <div style="margin-bottom:10px;">
          <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:2px;">
            <span><strong>${escapeHtml(f.original_feature.replace('_', ' ').toUpperCase())}</strong>: ${escapeHtml(f.value)}</span>
            <span style="color:${barColor}; font-weight:700;">${escapeHtml(f.label)} (${f.shap_value > 0 ? '+' : ''}${f.shap_value})</span>
          </div>
          <div style="height:6px; background:#F1F5F9; border-radius:3px; overflow:hidden;">
            <div style="width:${widthPct}%; height:100%; background:${barColor}; border-radius:3px;"></div>
          </div>
        </div>
      `;
    }).join('');
  }

  // 5. SHAP-Derived Recommendations
  const recsContainer = document.getElementById('pred-recs-container');
  if (recsContainer && data.recommendations) {
    recsContainer.innerHTML = data.recommendations.map(r => `
      <div class="card card-pad mb-12 hoverable" style="border-left: 4px solid ${r.priority === 'Critical' ? '#F04438' : '#2D7CFF'};">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:4px;">
          <h4 style="margin:0; font-size:14px;">${escapeHtml(r.title)}</h4>
          <span class="badge ${r.priority === 'Critical' ? 'b-red' : 'b-blue'}">${escapeHtml(r.priority)}</span>
        </div>
        <div class="text-dim" style="font-size:12px; margin-bottom:6px;">${escapeHtml(r.description)}</div>
        <div style="font-size:11.5px; color:#0F172A; background:#F8FAFC; padding:6px 10px; border-radius:6px; margin-bottom:4px;">
          <strong>Action:</strong> ${escapeHtml(r.action)}
        </div>
        <div style="font-size:10.5px; color:#64748B;">
          <em>${escapeHtml(r.trigger)}</em> · <span class="text-dim">${escapeHtml(r.disclaimer || '')}</span>
        </div>
      </div>
    `).join('');
  }
}
