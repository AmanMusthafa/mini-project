/**
 * Hotspot Map & Spatial Analysis Module
 */
import { fetchApi } from './api.js';
import { escapeHtml, TIER_COLORS } from './utils.js';

let _mapInstance = null;
let _markersLayer = null;

export async function initHotspots() {
  initMap();
  await loadHotspots();
  bindHotspotFilters();
}

function initMap() {
  const mapContainer = document.getElementById('map-hotspot');
  if (!mapContainer || _mapInstance) return;

  // Center on Kochi, Kerala (9.9671, 76.3217)
  _mapInstance = L.map('map-hotspot').setView([9.9850, 76.3050], 12);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(_mapInstance);

  _markersLayer = L.layerGroup().addTo(_mapInstance);
}

export async function loadHotspots(filters = {}) {
  const q = new URLSearchParams(filters).toString();
  try {
    const res = await fetchApi(`/api/hotspots${q ? '?' + q : ''}`);
    if (!res.success || !res.hotspots) return;

    renderMapMarkers(res.hotspots);
    renderHotspotsTable(res.hotspots);
  } catch (err) {
    console.warn('[Hotspots] Error loading hotspots:', err);
  }
}

function renderMapMarkers(hotspots) {
  if (!_markersLayer) return;
  _markersLayer.clearLayers();

  hotspots.forEach(h => {
    if (!h.latitude || !h.longitude) return;

    const color = TIER_COLORS[h.tier] || '#17B26A';
    const radius = Math.min(Math.max(h.total_accidents / 25, 8), 24);

    const circle = L.circleMarker([h.latitude, h.longitude], {
      radius: radius,
      fillColor: color,
      color: '#ffffff',
      weight: 1.5,
      opacity: 0.9,
      fillOpacity: 0.65
    });

    const popupHtml = `
      <div style="font-family:inherit; min-width:180px;">
        <h4 style="margin:0 0 4px; font-size:13px;">${escapeHtml(h.road_name)}</h4>
        <div style="font-size:11px; color:#64748B; margin-bottom:6px;">${escapeHtml(h.area)} · <span style="font-weight:700; color:${color};">${escapeHtml(h.tier)} Risk</span></div>
        <div style="font-size:11.5px; line-height:1.4;">
          <div>Total Crashes: <strong>${h.total_accidents}</strong></div>
          <div>Fatal: <strong>${h.fatal_count}</strong> | Major: <strong>${h.major_count}</strong></div>
          <div>Primary Cause: <strong>${escapeHtml(h.primary_cause || 'N/A')}</strong></div>
          <div style="margin-top:4px; font-weight:700;">Danger Score: ${h.danger_score} / 100</div>
        </div>
      </div>
    `;

    circle.bindPopup(popupHtml);
    _markersLayer.addLayer(circle);
  });
}

function renderHotspotsTable(hotspots) {
  const tbody = document.getElementById('table-hotspots');
  if (!tbody) return;

  if (hotspots.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:18px;">No hotspots found matching selected criteria.</td></tr>`;
    return;
  }

  tbody.innerHTML = hotspots.slice(0, 15).map((h, i) => {
    const badgeClass = h.tier === 'Critical' ? 'b-red' : (h.tier === 'High' ? 'b-orange' : (h.tier === 'Moderate' ? 'b-yellow' : 'b-green'));
    return `
      <tr>
        <td class="mono">#${i + 1}</td>
        <td><strong>${escapeHtml(h.road_name)}</strong></td>
        <td>${escapeHtml(h.area)}</td>
        <td><span class="badge ${badgeClass}">${escapeHtml(h.tier)}</span></td>
        <td><strong>${h.total_accidents}</strong> <span class="text-dim">(${h.fatal_count}F · ${h.major_count}M)</span></td>
        <td>${escapeHtml((h.primary_cause || 'N/A').toUpperCase())}</td>
        <td><strong>${h.danger_score}</strong></td>
      </tr>
    `;
  }).join('');
}

function bindHotspotFilters() {
  const areaSelect = document.getElementById('hotspot-filter-area');
  const yearSelect = document.getElementById('hotspot-filter-year');

  if (areaSelect) {
    areaSelect.addEventListener('change', () => {
      loadHotspots({
        area: areaSelect.value,
        year: yearSelect ? yearSelect.value : ''
      });
    });
  }

  if (yearSelect) {
    yearSelect.addEventListener('change', () => {
      loadHotspots({
        area: areaSelect ? areaSelect.value : '',
        year: yearSelect.value
      });
    });
  }
}
