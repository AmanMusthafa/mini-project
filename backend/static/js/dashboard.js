/**
 * Dashboard & Analytics Module
 * Renders real-time statistics, monthly trends, diurnal distributions,
 * and verified incident records from SQLite.
 */
import { fetchApi } from './api.js';
import { escapeHtml, registerChart, showToast } from './utils.js';

let _currentFilters = {
  year: '',
  severity: '',
  area: '',
  data_source: ''
};

export async function loadDashboard() {
  await Promise.all([
    loadStats(),
    loadTrend(),
    loadTimeDistribution(),
    loadWeekdayDistribution(),
    loadCauseDistribution(),
    loadSeverityDoughnut(),
    loadTrafficDensity(),
    loadRecentRecords()
  ]);
}

export function bindDashboardFilters(onFilterChange) {
  const yearSelect = document.getElementById('filter-year') || document.getElementById('dash-filter-year');
  const sevSelect = document.getElementById('filter-severity') || document.getElementById('dash-filter-severity');
  const areaSelect = document.getElementById('filter-area') || document.getElementById('dash-filter-area');
  const applyBtn = document.getElementById('analytics-filter-btn') || document.getElementById('dash-apply-filter');

  if (applyBtn) {
    applyBtn.addEventListener('click', (e) => {
      e.preventDefault();
      _currentFilters.year = yearSelect ? yearSelect.value : '';
      _currentFilters.severity = sevSelect ? sevSelect.value : '';
      _currentFilters.area = areaSelect ? areaSelect.value : '';
      loadDashboard();
      if (onFilterChange) onFilterChange(_currentFilters);
    });
  }
}

function buildQueryString(params) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v) q.append(k, v);
  }
  return q.toString() ? `?${q.toString()}` : '';
}

async function loadStats() {
  try {
    const data = await fetchApi(`/api/dashboard/stats${buildQueryString(_currentFilters)}`);
    if (!data.success) return;

    // Update KPI Card values with animation
    updateKpiValue('kpi-total-accidents', data.total);
    updateKpiValue('kpi-fatal-accidents', data.fatal);
    updateKpiValue('kpi-major-accidents', data.major);
    updateKpiValue('kpi-minor-accidents', data.minor);
    updateKpiValue('kpi-casualties', data.casualties);
    
    // Severity Index
    const riskEl = document.getElementById('kpi-avg-risk');
    if (riskEl) {
      riskEl.textContent = data.historical_severity_index.toFixed(2);
    }

    // Provenance badge
    const badgeEl = document.getElementById('dataset-provenance-badge');
    if (badgeEl) {
      const srcText = Object.entries(data.source_mix || {}).map(([s, c]) => `${s}: ${c.toLocaleString()}`).join(' · ');
      badgeEl.innerHTML = `<span class="dot-status live"></span> Dataset: ${srcText || 'Synthetic Data'} (Kochi)`;
    }
  } catch (err) {
    console.warn('[Stats] Failed to fetch stats:', err);
  }
}

function updateKpiValue(elemId, targetValue) {
  const el = document.getElementById(elemId);
  if (!el) return;

  const startVal = parseInt(el.textContent.replace(/,/g, '')) || 0;
  const duration = 600;
  const startTime = performance.now();

  function animate(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const current = Math.floor(startVal + (targetValue - startVal) * progress);
    el.textContent = current.toLocaleString();
    if (progress < 1) requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
}

async function loadTrend() {
  const canvas = document.getElementById('chart-analytics-trend') || document.getElementById('chart-dashboard-trend');
  if (!canvas) return;

  try {
    const res = await fetchApi(`/api/dashboard/trend${buildQueryString(_currentFilters)}`);
    if (!res.success) return;

    registerChart('chart-trend', new Chart(canvas, {
      type: 'line',
      data: {
        labels: res.labels,
        datasets: [{
          label: 'Monthly Accidents',
          data: res.values,
          borderColor: '#17B26A',
          backgroundColor: 'rgba(23, 178, 106, 0.08)',
          fill: true,
          tension: 0.35,
          borderWidth: 2.2,
          pointRadius: 3
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: 'rgba(0,0,0,0.04)' } },
          y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' } }
        }
      }
    }));
  } catch (err) {
    console.warn('[Trend] Chart error:', err);
  }
}

async function loadTimeDistribution() {
  const canvas = document.getElementById('chart-analytics-time');
  if (!canvas) return;

  try {
    const res = await fetchApi(`/api/dashboard/by_hour${buildQueryString(_currentFilters)}`);
    if (!res.success) return;

    registerChart('chart-time', new Chart(canvas, {
      type: 'bar',
      data: {
        labels: res.labels,
        datasets: [{
          label: 'Accidents',
          data: res.values,
          backgroundColor: 'rgba(45, 124, 255, 0.75)',
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' } }
        }
      }
    }));
  } catch (err) {
    console.warn('[Time] Chart error:', err);
  }
}

async function loadWeekdayDistribution() {
  const canvas = document.getElementById('chart-analytics-weekday');
  if (!canvas) return;

  try {
    const res = await fetchApi(`/api/dashboard/by_weekday${buildQueryString(_currentFilters)}`);
    if (!res.success) return;

    registerChart('chart-weekday', new Chart(canvas, {
      type: 'bar',
      data: {
        labels: res.labels,
        datasets: [{
          label: 'Accidents',
          data: res.values,
          backgroundColor: 'rgba(247, 144, 9, 0.75)',
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' } }
        }
      }
    }));
  } catch (err) {
    console.warn('[Weekday] Chart error:', err);
  }
}

async function loadCauseDistribution() {
  const canvas = document.getElementById('chart-analytics-cause');
  if (!canvas) return;

  try {
    const res = await fetchApi(`/api/dashboard/by_cause${buildQueryString(_currentFilters)}`);
    if (!res.success) return;

    registerChart('chart-cause', new Chart(canvas, {
      type: 'bar',
      data: {
        labels: res.labels,
        datasets: [{
          label: 'Incidents by Cause',
          data: res.values,
          backgroundColor: ['#F04438', '#F79009', '#2D7CFF', '#9E77ED', '#17B26A'],
          borderRadius: 4
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' } },
          y: { grid: { display: false } }
        }
      }
    }));
  } catch (err) {
    console.warn('[Cause] Chart error:', err);
  }
}

async function loadSeverityDoughnut() {
  const canvas = document.getElementById('chart-analytics-severity');
  if (!canvas) return;

  try {
    const res = await fetchApi(`/api/dashboard/by_severity${buildQueryString(_currentFilters)}`);
    if (!res.success) return;

    registerChart('chart-severity', new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: res.labels,
        datasets: [{
          data: res.values,
          backgroundColor: ['#17B26A', '#F79009', '#F04438'],
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }
        },
        cutout: '68%'
      }
    }));
  } catch (err) {
    console.warn('[Severity] Chart error:', err);
  }
}

async function loadTrafficDensity() {
  const canvas = document.getElementById('chart-analytics-density');
  if (!canvas) return;

  try {
    const res = await fetchApi(`/api/dashboard/by_traffic_density${buildQueryString(_currentFilters)}`);
    if (!res.success) return;

    registerChart('chart-density', new Chart(canvas, {
      type: 'pie',
      data: {
        labels: res.labels,
        datasets: [{
          data: res.values,
          backgroundColor: ['#17B26A', '#F79009', '#F04438']
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } }
      }
    }));
  } catch (err) {}
}

async function loadRecentRecords() {
  const tbody = document.getElementById('table-recent-records');
  if (!tbody) return;

  try {
    const res = await fetchApi('/api/dashboard/recent?limit=8');
    if (!res.success || !res.records) return;

    if (res.records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:18px;">No recent accident records available.</td></tr>`;
      return;
    }

    tbody.innerHTML = res.records.map(r => {
      const sevClass = r.severity === 'fatal' ? 'b-red' : (r.severity === 'major' ? 'b-orange' : 'b-green');
      return `
        <tr>
          <td class="mono">${escapeHtml(r.accident_uid)}</td>
          <td>${escapeHtml(r.occurred_at)}</td>
          <td><strong>${escapeHtml(r.road_name)}</strong> <span class="text-dim">(${escapeHtml(r.area)})</span></td>
          <td><span class="badge ${sevClass}">${escapeHtml(r.severity.toUpperCase())}</span></td>
          <td>${escapeHtml(r.cause.replace('_', ' ').toUpperCase())}</td>
          <td>${escapeHtml(r.casualties)}</td>
          <td><span class="badge b-neutral">${escapeHtml(r.data_source)}</span></td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.warn('[Recent] Table error:', err);
  }
}
