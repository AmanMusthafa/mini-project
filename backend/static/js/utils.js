/**
 * Frontend Utilities & Security Helpers
 */

// XSS Prevention: Strict HTML escaping
export function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export function showToast(type, title, msg) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const el = document.createElement('div');
  el.className = `toast ${type}`;
  
  const iconMap = {
    success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`,
    error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/></svg>`,
    info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>`,
    warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4M12 17h.01"/></svg>`
  };

  el.innerHTML = `
    <div class="toast-icon">${iconMap[type] || iconMap.info}</div>
    <div class="toast-body">
      <div class="toast-title">${escapeHtml(title)}</div>
      <div class="toast-msg">${escapeHtml(msg)}</div>
    </div>
  `;

  container.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(10px)';
    el.style.transition = 'all 0.3s ease';
    setTimeout(() => el.remove(), 300);
  }, 4200);
}

// Chart Instance Registry to guarantee complete cleanup and prevent memory leaks
const _activeCharts = {};

export function registerChart(id, chart) {
  if (_activeCharts[id]) {
    try {
      _activeCharts[id].destroy();
    } catch (e) {
      console.warn(`[Chart] Error destroying chart ${id}:`, e);
    }
  }
  _activeCharts[id] = chart;
  return chart;
}

export function destroyChart(id) {
  if (_activeCharts[id]) {
    try {
      _activeCharts[id].destroy();
    } catch (e) {}
    delete _activeCharts[id];
  }
}

export const TIER_COLORS = {
  Critical: '#F04438',
  High: '#F79009',
  Moderate: '#EAB308',
  Low: '#17B26A'
};
