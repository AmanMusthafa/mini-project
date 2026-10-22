'use strict';

/* ================================================================
   STATIC / LOCAL DATA — map markers, road-scene only
   All real analytics come from the SQLite API
   ================================================================ */
const LOCATIONS = [
  {name:'Edappally Toll Junction', lat:10.0261, lng:76.3083, tier:'veryhigh', accidents:41, risk:92},
  {name:'Vyttila Mobility Hub',    lat:9.9671,  lng:76.3217, tier:'veryhigh', accidents:37, risk:88},
  {name:'Palarivattom Junction',   lat:10.0024, lng:76.3118, tier:'high',     accidents:34, risk:81},
  {name:'Kadavanthra Junction',    lat:9.9710,  lng:76.2951, tier:'high',     accidents:29, risk:77},
  {name:'Infopark Expressway',     lat:10.0159, lng:76.3419, tier:'moderate', accidents:22, risk:62},
  {name:'MG Road Kadavanthra',     lat:9.9685,  lng:76.2850, tier:'moderate', accidents:19, risk:58},
  {name:'Beach Road Fort Kochi',   lat:9.9638,  lng:76.2424, tier:'moderate', accidents:17, risk:55},
  {name:'Jew Town Road',           lat:9.9563,  lng:76.2603, tier:'low',      accidents:11, risk:38},
  {name:'NH 66 Bypass',            lat:10.0300, lng:76.3150, tier:'veryhigh', accidents:48, risk:95},
  {name:'Seaport Airport Road',    lat:10.0250, lng:76.3350, tier:'high',     accidents:31, risk:79}
];

/* Geographic centres of Kochi areas — lat / lng */
const KOCHI_AREA_GEO = {
  'Edappally':    {lat:10.0261, lng:76.3083},
  'Kakkanad':     {lat:10.0159, lng:76.3419},
  'Vyttila':      {lat:9.9671,  lng:76.3217},
  'Palarivattom': {lat:10.0024, lng:76.3118},
  'Fort Kochi':   {lat:9.9638,  lng:76.2424},
  'Mattancherry': {lat:9.9563,  lng:76.2603},
  'Kadavanthra':  {lat:9.9710,  lng:76.2951},
};

const TIER_COLOR = {veryhigh:'#F04438', high:'#F79009', moderate:'#EAB308', low:'#17B26A', verylow:'#2D7CFF'};
const TIER_LABEL = {veryhigh:'Very High', high:'High', moderate:'Moderate', low:'Low', verylow:'Very Low'};

function rnd(min,max){ return Math.floor(Math.random()*(max-min+1))+min; }

/* Escape HTML to prevent XSS and DOM injection */
function escapeHtml(str){
  if(str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
window.escapeHtml = escapeHtml;

/* ================================================================
   TOAST NOTIFICATIONS
   ================================================================ */
function showToast(type, title, msg){
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  const icons = {
    success:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 4.5-5"/></svg>',
    error:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></svg>',
    info:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>'
  };
  el.innerHTML = `<span class="toast-icon">${icons[type]||icons.info}</span>
    <div><div class="toast-title">${title}</div><div class="toast-msg">${msg}</div></div>
    <span class="toast-close" role="button">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>
    </span>`;
  container.appendChild(el);
  const remove = ()=>{ el.classList.add('leaving'); setTimeout(()=>el.remove(), 280); };
  el.querySelector('.toast-close').addEventListener('click', remove);
  setTimeout(remove, 6000);
}
window.showToast = showToast;

/* ================================================================
   RIPPLE EFFECT
   ================================================================ */
document.addEventListener('click', function(e){
  const btn = e.target.closest('.ripple-surface');
  if(!btn) return;
  const rect = btn.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height);
  const span = document.createElement('span');
  span.className = 'ripple';
  span.style.width = span.style.height = size+'px';
  span.style.left = (e.clientX-rect.left-size/2)+'px';
  span.style.top  = (e.clientY-rect.top -size/2)+'px';
  btn.appendChild(span);
  setTimeout(()=>span.remove(), 620);
});

/* ================================================================
   LOGIN
   ================================================================ */
const loginForm   = document.getElementById('login-form');
const loginScreen = document.getElementById('login-screen');
const appShell    = document.getElementById('app-shell');

let currentUser = {username:'admin', name:'Admin', role:'Admin', email:'', department:''};

document.getElementById('eye-toggle').addEventListener('click', function(){
  const p = document.getElementById('login-pass');
  p.type = p.type === 'password' ? 'text' : 'password';
});

loginForm.addEventListener('submit', async function(e){
  e.preventDefault();
  const username = document.getElementById('login-user').value;
  const password = document.getElementById('login-pass').value;
  const spinner  = document.getElementById('login-spinner');
  const btnText  = document.getElementById('login-btn-text');
  const arrow    = document.getElementById('login-arrow');

  spinner.style.display = 'inline-block';
  arrow.style.display   = 'none';
  btnText.textContent   = 'Authenticating…';

  try {
    const res    = await fetch('/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username, password})});
    const result = await res.json();
    spinner.style.display = 'none';
    arrow.style.display   = 'inline';
    btnText.textContent   = 'Login to Dashboard';

    if(result.success){
      const u = result.user || result;
      currentUser = {
        username: u.username || 'admin',
        name: u.name || 'Admin',
        role: u.role || 'Admin',
        email: u.email || '',
        department: u.department || ''
      };
      sessionStorage.setItem('kochi_session_user', JSON.stringify(currentUser));
      sessionStorage.setItem('kochi_active_page', 'dashboard');
      document.documentElement.classList.add('logged-in-session');
      updateTopbarProfile(currentUser);
      loginScreen.style.transition = 'opacity .4s ease';
      loginScreen.style.opacity    = '0';
      setTimeout(()=>{
        loginScreen.style.display = 'none';
        appShell.classList.add('active');
        initAppOnce();
        navigateTo('dashboard');
      }, 400);
    } else {
      showToast('error', 'Login Failed', result.error || result.message || 'Invalid username or password.');
    }
  } catch(err){
    spinner.style.display = 'none';
    arrow.style.display   = 'inline';
    btnText.textContent   = 'Login to Dashboard';
    showToast('error', 'Server Error', 'Cannot connect to Flask server.');
    console.error(err);
  }
});

function updateTopbarProfile(user){
  const name     = user.name || 'Admin';
  const initials = name.split(' ').map(n=>n[0]).join('').toUpperCase().slice(0,2) || 'AD';
  document.querySelectorAll('.avatar').forEach(a=>a.textContent = initials);
  const who = document.querySelector('.who');
  if(who) who.textContent = name;
  const pdName = document.querySelector('.pd-name');
  if(pdName) pdName.textContent = name;
  const pdRole = document.querySelector('.pd-role');
  if(pdRole) pdRole.textContent = user.role || 'Admin';
}

function restoreUserSession(){
  try {
    const stored = sessionStorage.getItem('kochi_session_user');
    if(stored){
      currentUser = JSON.parse(stored);
      updateTopbarProfile(currentUser);
      document.documentElement.classList.add('logged-in-session');
      if(loginScreen){
        loginScreen.style.display = 'none';
        loginScreen.style.opacity = '0';
      }
      if(appShell){
        appShell.classList.add('active');
      }
      initAppOnce();
      const savedPage = sessionStorage.getItem('kochi_active_page') || 'dashboard';
      navigateTo(savedPage);
      return true;
    }
  } catch(e){
    console.error('Session restore error:', e);
    sessionStorage.removeItem('kochi_session_user');
    sessionStorage.removeItem('kochi_active_page');
  }
  return false;
}

/* ================================================================
   NAVIGATION
   ================================================================ */
const PAGE_META = {
  dashboard:{title:'Dashboard',         sub:'Kochi Road Accident Analytics · 2022–2026'},
  analytics: {title:'Accident Analytics', sub:'Statistical breakdown of road incidents'},
  risk:      {title:'Risk Prediction',   sub:'Explainable AI risk engine'},
  hotspot:   {title:'Hotspot Map',       sub:'City-wide accident intensity'},
  traffic:   {title:'Traffic Management',sub:'Adaptive signal optimization'},
  yolo:      {title:'YOLOv8 Detection',  sub:'Real-time vehicle detection'},
  emergency: {title:'Emergency Priority',sub:'Signal preemption control'},
  reports:   {title:'Reports',           sub:'Generated analytics reports'},
  data:      {title:'Data Management',   sub:'Accident records dataset'},
  settings:  {title:'Settings',          sub:'Account & system preferences'}
};

function navigateTo(pageId){
  if(sessionStorage.getItem('kochi_session_user')){
    sessionStorage.setItem('kochi_active_page', pageId);
  }
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  const target = document.getElementById('page-'+pageId);
  if(target) target.classList.add('active');
  document.querySelectorAll('.nav-item[data-page]').forEach(n=>n.classList.toggle('active', n.dataset.page===pageId));
  const meta = PAGE_META[pageId]||{title:'Dashboard',sub:''};
  document.getElementById('topbar-title-text').textContent = meta.title;
  document.getElementById('topbar-title-sub').innerHTML   = meta.sub;
  document.getElementById('sidebar').classList.remove('mobile-open');
  const overlay = document.getElementById('sidebar-overlay');
  if(overlay) overlay.classList.remove('active');
  requestAnimationFrame(()=>{
    initPageContent(pageId);
    if(pageId === 'hotspot' && typeof hotspotMapInstance !== 'undefined' && hotspotMapInstance){
      setTimeout(() => hotspotMapInstance.invalidateSize(), 200);
    }
  });
}

document.querySelectorAll('.nav-item[data-page]').forEach(item=>{
  item.addEventListener('click', ()=>navigateTo(item.dataset.page));
});

document.getElementById('hamburger-btn').addEventListener('click', function(){
  if(window.innerWidth <= 1024){
    document.getElementById('sidebar').classList.toggle('mobile-open');
    document.getElementById('sidebar-overlay').classList.toggle('active');
  } else {
    document.getElementById('sidebar').classList.toggle('collapsed');
    document.body.classList.toggle('sidebar-collapsed');
  }
});
document.getElementById('sidebar-overlay').addEventListener('click', function(){
  document.getElementById('sidebar').classList.remove('mobile-open');
  this.classList.remove('active');
});

document.getElementById('logout-btn').addEventListener('click', function(){
  sessionStorage.removeItem('kochi_session_user');
  sessionStorage.removeItem('kochi_active_page');
  document.documentElement.classList.remove('logged-in-session');
  appShell.classList.remove('active');
  loginScreen.style.display = 'flex';
  requestAnimationFrame(()=>{ loginScreen.style.opacity = '1'; });
  loginForm.reset();
  document.getElementById('login-spinner').style.display = 'none';
  document.getElementById('login-arrow').style.display   = 'inline';
  document.getElementById('login-btn-text').textContent  = 'Login to Dashboard';
  // Reset init state so data reloads on next login
  Object.keys(PAGE_INIT_DONE).forEach(k=>delete PAGE_INIT_DONE[k]);
  dashMapBuilt = false;
});

const profBtn = document.getElementById('profile-btn');
const profileWrap = profBtn ? profBtn.closest('.profile-menu-wrap') : null;
if(profBtn && profileWrap){
  profBtn.addEventListener('click', function(e){
    e.stopPropagation();
    profileWrap.classList.toggle('open');
  });
  document.addEventListener('click', function(e){
    if(profileWrap.classList.contains('open') && !profileWrap.contains(e.target))
      profileWrap.classList.remove('open');
  });
}
const pViewBtn = document.getElementById('profile-view-btn');
if(pViewBtn){
  pViewBtn.addEventListener('click', function(){
    if(profileWrap) profileWrap.classList.remove('open');
    showToast('info','Profile', `${currentUser.name} · ${currentUser.role||'Admin'}`);
  });
}
const pLogoutBtn = document.getElementById('profile-logout-btn');
if(pLogoutBtn){
  pLogoutBtn.addEventListener('click', function(){
    if(profileWrap) profileWrap.classList.remove('open');
    const lBtn = document.getElementById('logout-btn');
    if(lBtn) lBtn.click();
  });
}
const notifBtn = document.getElementById('notif-btn');
if(notifBtn){
  notifBtn.addEventListener('click', function(){
    showToast('info','Alerts','Traffic notifications active.');
  });
}

function setDarkTheme(on){
  document.body.classList.toggle('dark-theme', on);
  const t = document.getElementById('dark-mode-toggle');
  if(t) t.checked = on;
}
const themeBtn = document.getElementById('theme-btn');
if(themeBtn){
  themeBtn.addEventListener('click', function(){
    setDarkTheme(!document.body.classList.contains('dark-theme'));
    showToast('info','Theme updated', document.body.classList.contains('dark-theme') ? 'Dark mode enabled.' : 'Light mode enabled.');
  });
}

/* ================================================================
   COUNTER ANIMATION
   ================================================================ */
function animateCounters(scope){
  const root = scope || document;
  root.querySelectorAll('[data-count]').forEach(el=>{
    if(el.dataset.done) return;
    el.dataset.done = '1';
    const target   = parseInt(el.dataset.count, 10);
    const duration = 1200;
    const start    = performance.now();
    function step(now){
      const p     = Math.min(1, (now-start)/duration);
      const eased = 1 - Math.pow(1-p, 3);
      el.textContent = Math.round(eased*target).toLocaleString('en-IN');
      if(p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
}

/* ================================================================
   CHART.JS DEFAULTS
   ================================================================ */
if(window.Chart){
  Chart.defaults.font.family  = "'Inter', sans-serif";
  Chart.defaults.font.size    = 11.5;
  Chart.defaults.color        = '#5B6B8C';
  Chart.defaults.plugins.legend.display           = false;
  Chart.defaults.plugins.tooltip.backgroundColor  = '#0B1526';
  Chart.defaults.plugins.tooltip.titleFont        = {family:"'Manrope',sans-serif", weight:'700', size:12};
  Chart.defaults.plugins.tooltip.bodyFont         = {family:"'Inter',sans-serif", size:11.5};
  Chart.defaults.plugins.tooltip.padding          = 10;
  Chart.defaults.plugins.tooltip.cornerRadius     = 8;
  Chart.defaults.plugins.tooltip.displayColors    = false;
}
function gridOpt(){ return {color:'#EEF1F7', drawTicks:false}; }

const CHART_REGISTRY = {};
function mkChart(id, config){
  if(!window.Chart) return null;
  const canvas = document.getElementById(id);
  if(!canvas) return null;
  if(CHART_REGISTRY[id]){ CHART_REGISTRY[id].destroy(); delete CHART_REGISTRY[id]; }
  const chart = new Chart(canvas.getContext('2d'), config);
  CHART_REGISTRY[id] = chart;
  return chart;
}

/* ================================================================
   COLOUR HELPERS
   ================================================================ */
function hexAlpha(hex, a){
  const c = hex.replace('#','');
  const r = parseInt(c.substring(0,2),16), g = parseInt(c.substring(2,4),16), b = parseInt(c.substring(4,6),16);
  return `rgba(${r},${g},${b},${a})`;
}
function colorHex(n){ return {red:'#F04438',orange:'#F79009',green:'#17B26A',blue:'#2D7CFF',purple:'#9E77ED'}[n]||'#2D7CFF'; }
function sevColor(sev){
  if(!sev) return 'blue';
  const s = sev.toLowerCase();
  if(s==='fatal') return 'red';
  if(s==='major') return 'orange';
  return 'green';
}

/* ================================================================
   API HELPER — leverages api.js with fallback
   ================================================================ */
async function apiFetch(endpoint){
  try {
    if(window.apiGet){
      return await window.apiGet(endpoint);
    }
    const r = await fetch(endpoint, { cache: 'no-store' });
    if(!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } catch(e){
    console.error('API error:', endpoint, e.message);
    return null;
  }
}

/* Helper returning consistent Chart.js options for the Accidents Trend line chart */
function trendChartOptions(isMultiYear = true){
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false
    },
    plugins: {
      legend: {
        display: isMultiYear,
        position: 'top',
        align: 'end',
        labels: {
          color: '#cbd5e1',
          font: { family: "'Inter', sans-serif", size: 11.5, weight: '600' },
          boxWidth: 10,
          boxHeight: 10,
          usePointStyle: true,
          pointStyle: 'circle',
          padding: 12
        }
      },
      tooltip: {
        backgroundColor: '#0c1b33',
        titleColor: '#ffffff',
        bodyColor: '#93c5fd',
        borderColor: 'rgba(192,230,253,0.25)',
        borderWidth: 1,
        padding: 10,
        boxPadding: 4,
        callbacks: {
          label: function(context){
            const label = context.dataset.label || '';
            const val = context.parsed.y;
            return val !== null && val !== undefined
              ? `  ${label}: ${val.toLocaleString('en-IN')} accidents`
              : `  ${label}: No data`;
          }
        }
      }
    },
    scales: {
      x: {
        grid: {
          color: 'rgba(255, 255, 255, 0.05)',
          borderColor: 'rgba(255, 255, 255, 0.1)'
        },
        ticks: {
          color: '#94a3b8',
          font: { family: "'Inter', sans-serif", size: 11 }
        }
      },
      y: {
        beginAtZero: true,
        grid: {
          color: 'rgba(255, 255, 255, 0.05)',
          borderColor: 'rgba(255, 255, 255, 0.1)'
        },
        ticks: {
          color: '#94a3b8',
          font: { family: "'Inter', sans-serif", size: 11 },
          callback: function(v){ return v.toLocaleString('en-IN'); }
        }
      }
    }
  };
}
window.trendChartOptions = trendChartOptions;

/* Dash Leaflet mini-map is defined below with real hotspot markers */

/* ================================================================
   DASHBOARD — initDashboardCharts(year)
   year = '' → All 2022-2026 (comparison)
   year = '2022' … '2026' → Filtered single year
   ================================================================ */
async function initDashboardCharts(year=''){
  const q  = year ? ('?year='+year) : '';
  const q2 = year ? ('&year='+year) : '';

  // Destroy existing trend chart if already registered
  if(CHART_REGISTRY['chart-dash-trend']){
    CHART_REGISTRY['chart-dash-trend'].destroy();
    delete CHART_REGISTRY['chart-dash-trend'];
  }

  // Fetch in parallel: filtered stats + trend + causes + hotspots + recent (8)
  const [stats, trendData, byCause, hotspotsData, recentRes] = await Promise.all([
    apiFetch('/api/dashboard/stats'    + q),
    apiFetch('/api/dashboard/trend'    + q),
    apiFetch('/api/dashboard/by_cause' + q),
    apiFetch('/api/hotspots?limit=10'),
    apiFetch('/api/dashboard/recent?limit=8' + q2)
  ]);

  /* ── KPI Cards ───────────────────────────────────────────── */
  if(stats){
    // Card 1 – Total Accidents
    const el1 = document.getElementById('totalAccidents');
    if(el1){ el1.dataset.count = stats.total; el1.dataset.done = ''; el1.textContent = '0'; }

    // Card 2 – Fatal Accidents  (re-uses #highRiskZones)
    const el2 = document.getElementById('highRiskZones');
    if(el2){
      el2.dataset.count = stats.fatal; el2.dataset.done = ''; el2.textContent = '0';
      const lbl = el2.nextElementSibling;
      if(lbl) lbl.textContent = 'Fatal Accidents';
      const trend = el2.closest('.kpi-card')?.querySelector('.kpi-trend');
      if(trend) trend.textContent = stats.fatal.toLocaleString('en-IN')+' recorded';
    }

    // Card 3 – Fatality Rate (R4)
    const elFatality = document.getElementById('dash-fatality-rate');
    if(elFatality){
      const fRate = stats.fatality_rate !== undefined ? stats.fatality_rate : (stats.fatal_pct !== undefined ? stats.fatal_pct : ((stats.fatal / Math.max(stats.total, 1)) * 100).toFixed(1));
      elFatality.textContent = fRate + '%';
      const trendEl = document.getElementById('dash-fatality-trend');
      if(trendEl) trendEl.textContent = `${stats.fatal} of ${stats.total}`;
    }

    // Card 4 – Total Casualties
    const el4 = document.getElementById('totalCasualties');
    if(el4){ el4.dataset.count = stats.casualties; el4.dataset.done = ''; el4.textContent = '0'; }
    const trendEl = document.getElementById('dash-casualties-trend');
    if(trendEl) trendEl.textContent = year ? year+' data' : '2022–2026 data';

    // Animate all counters on dashboard page
    animateCounters(document.getElementById('page-dashboard'));
  }

  /* ── Trend Chart ─────────────────────────────────────────── */
  requestAnimationFrame(()=>{
    requestAnimationFrame(()=>{
      const cv  = document.getElementById('chart-dash-trend');
      const box = document.getElementById('trend-chart-box');
      if(!cv || !box) return;

      const sub = document.getElementById('trend-chart-sub');
      const YEAR_COLORS = {2022:'#8BA7CC', 2023:'#2D7CFF', 2024:'#9E77ED', 2025:'#17B26A', 2026:'#F04438'};

      let chartObj = null;
      if(year && trendData && trendData.labels){
        if(sub) sub.textContent = year + ' Monthly Breakdown · Kochi';
        const vals = (trendData.datasets && trendData.datasets[year]) || trendData.values || (trendData.series && trendData.series[0]?.data) || [];
        chartObj = mkChart('chart-dash-trend', {
          type:'line',
          data:{
            labels: trendData.labels,
            datasets:[{
              label: year,
              data:  vals,
              borderColor: YEAR_COLORS[year] || '#2D7CFF',
              backgroundColor:'rgba(45,124,255,0.12)',
              borderWidth:2.5, tension:0.35, fill:true,
              pointRadius:3, pointBackgroundColor: YEAR_COLORS[year] || '#2D7CFF', pointHoverRadius:6
            }]
          },
          options: trendChartOptions(false)
        });
      } else if(trendData && trendData.labels){
        if(sub) sub.textContent = 'Monthly accidents by year · Kochi (2026 to date)';
        const years = ['2022','2023','2024','2025','2026'];
        const datasets = years.map(yr => {
          let yData = [];
          if(trendData.datasets && trendData.datasets[yr]) {
            yData = trendData.datasets[yr];
          } else if(trendData.series) {
            const found = trendData.series.find(s => String(s.year) === yr);
            if(found) yData = found.data;
          }
          return {
            label: yr === '2026' ? '2026 (to date)' : yr,
            data: yData,
            borderColor: YEAR_COLORS[yr] || '#2D7CFF',
            backgroundColor: yr === '2024' ? 'rgba(45,124,255,0.08)' : 'transparent',
            fill: yr === '2024',
            borderWidth: yr === '2024' ? 2.5 : 2,
            borderDash: ['2025','2026'].includes(yr) ? [5,4] : [],
            tension: 0.35,
            pointRadius: 3,
            pointBackgroundColor: YEAR_COLORS[yr] || '#2D7CFF',
            pointHoverRadius: 5
          };
        });
        chartObj = mkChart('chart-dash-trend', {
          type:'line',
          data:{ labels: trendData.labels, datasets },
          options: trendChartOptions(true)
        });
      }
      if(chartObj) requestAnimationFrame(()=>chartObj.resize());
    });
  });

  /* ── Contributing Factors ────────────────────────────────── */
  if(byCause && byCause.labels && byCause.labels.length){
    renderDashFactors(byCause);
  }

  /* ── Recent Accidents & Critical Feed ────────────────────── */
  const records = Array.isArray(recentRes) ? recentRes : (recentRes?.records || []);
  renderDashRecentAccidents(records);
  renderDashCriticalFeed(records);

  /* ── Real Leaflet Mini-Map (R3) ──────────────────────────── */
  buildDashMap(hotspotsData?.hotspots || []);
}

/* ── Leaflet Mini-Map for Dashboard (R3) ───────────────────── */
let dashMapInstance = null;
function buildDashMap(hotspots){
  const el = document.getElementById('dash-map');
  if(!el) return;

  if(!window.L){
    setTimeout(()=>buildDashMap(hotspots), 200);
    return;
  }

  if(dashMapInstance){
    dashMapInstance.invalidateSize();
    return;
  }

  dashMapInstance = L.map(el, {
    zoomControl: true,
    attributionControl: false
  }).setView([9.985, 76.295], 11);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18
  }).addTo(dashMapInstance);

  if(hotspots && hotspots.length > 0){
    hotspots.slice(0, 10).forEach((h, idx) => {
      const lat = parseFloat(h.latitude || 9.98);
      const lon = parseFloat(h.longitude || 76.29);
      const isCritical = (h.tier === 'Critical' || (h.danger_score || 0) >= 70);
      const color = isCritical ? '#F04438' : '#F79009';

      const circle = L.circleMarker([lat, lon], {
        radius: isCritical ? 9 : 7,
        fillColor: color,
        color: '#ffffff',
        weight: 1.5,
        opacity: 0.9,
        fillOpacity: 0.85
      }).addTo(dashMapInstance);

      circle.bindPopup(`
        <div style="font-size:12px;color:#0f172a;padding:4px;">
          <strong style="color:${color};">#${idx+1} Hotspot</strong><br>
          <b>${h.name || h.road_name}</b><br>
          <span style="color:#64748b;">${h.area} &middot; Score: ${h.danger_score}/100</span><br>
          <span>Accidents: ${h.total_accidents || 0} (${h.fatal_accidents || 0} Fatal)</span>
        </div>
      `);
    });
  }

  setTimeout(() => dashMapInstance?.invalidateSize(), 300);
}

/* ── Top Contributing Factors on Dashboard ────────────────── */
function renderDashFactors(byCause){
  const el = document.getElementById('dash-factors');
  if(!el || !byCause || !byCause.labels) return;
  const total = (byCause.values || []).reduce((a, b) => a + b, 0) || 1;
  el.innerHTML = byCause.labels.slice(0, 4).map((label, i) => {
    const val = byCause.values[i] || 0;
    const pct = Math.round((val / total) * 100);
    const cleanLabel = (label || '').replace(/_/g, ' ');
    return `
      <div style="margin-bottom:8px;">
        <div class="flex justify-between" style="font-size:12px;margin-bottom:3px;">
          <span style="color:#ffffff;font-weight:600;">${cleanLabel}</span>
          <span style="color:#94a3b8;">${val.toLocaleString()} (${pct}%)</span>
        </div>
        <div style="background:rgba(255,255,255,0.08);height:6px;border-radius:3px;overflow:hidden;">
          <div style="background:#2D7CFF;height:100%;width:${pct}%;border-radius:3px;"></div>
        </div>
      </div>
    `;
  }).join('');
}

/* ── Recent collisions feed (Latest 8) ─────────────────────── */
function renderDashRecentAccidents(records){
  const el = document.getElementById('dash-recent-accidents');
  if(!el) return;

  if(!records || records.length === 0){
    el.innerHTML = '<div style="padding:24px;text-align:center;color:#94a3b8;font-size:12.5px;">No recent collision records found.</div>';
    return;
  }

  el.innerHTML = records.slice(0, 8).map(a=>{
    const location = a.road_name ? `${a.road_name}, ${a.area||a.city}` : `${a.area||a.city}, Kochi`;
    const dateFormatted = a.occurred_at ? a.occurred_at.slice(0,16) : (a.date || 'Recent');
    const causeClean = (a.cause || 'Unknown').replace(/_/g, ' ');

    return `
    <div class="flex items-center gap-12 cursor-pointer" onclick="openViewRecordModal('${a.id || a.accident_uid}')" style="padding:9px 0; border-bottom:1px solid var(--border); transition:background .15s;" title="Click to view details">
      <div class="kpi-icon ${sevColor(a.severity)}" style="width:34px;height:34px;border-radius:9px;flex-shrink:0;">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4M12 17h.01"/></svg>
      </div>
      <div style="flex:1;min-width:0;">
        <div style="font-size:12.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#ffffff;">${location}</div>
        <div class="text-faint" style="font-size:11px;">${dateFormatted} &middot; ${causeClean}</div>
      </div>
      <span class="badge b-${sevColor(a.severity)}" style="font-size:11px;">${a.severity ? a.severity.charAt(0).toUpperCase()+a.severity.slice(1) : '—'}</span>
    </div>`;
  }).join('');
}

/* ── Critical & Fatal Collisions Feed (R1, R2 replacement) ─── */
function renderDashCriticalFeed(records){
  const el = document.getElementById('dash-critical-feed');
  if(!el) return;

  const criticals = (records || []).filter(r => ['fatal', 'major'].includes((r.severity || '').toLowerCase()));

  if(criticals.length === 0){
    el.innerHTML = '<div style="padding:24px;text-align:center;color:#17B26A;font-size:12.5px;">No critical or fatal incidents reported recently.</div>';
    return;
  }

  el.innerHTML = criticals.slice(0, 6).map(c=>{
    const isFatal = (c.severity || '').toLowerCase() === 'fatal';
    const color = isFatal ? 'red' : 'orange';
    const location = c.road_name ? `${c.road_name}, ${c.area}` : `${c.area}, Kochi`;
    const casualtiesText = c.casualties ? `${c.casualties} casualties reported` : 'Casualties recorded';

    return `
    <div class="flex items-center gap-12" style="padding:10px 0; border-bottom:1px solid var(--border);">
      <div class="kpi-icon ${color}" style="width:34px;height:34px;border-radius:9px;flex-shrink:0;">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>
      </div>
      <div style="flex:1;min-width:0;">
        <div style="font-size:12.5px;font-weight:700;color:#ffffff;">${isFatal ? 'FATAL CRASH' : 'SEVERE COLLISION'}: ${location}</div>
        <div class="text-faint" style="font-size:11px;">${casualtiesText} &middot; Cause: ${(c.cause||'Unknown').replace(/_/g,' ')}</div>
      </div>
      <span class="badge b-${color}" style="font-size:10.5px;">${c.severity ? c.severity.toUpperCase() : 'ALERT'}</span>
    </div>`;
  }).join('');
}

/* ================================================================
   DASHBOARD FILTER — year selector in page header
   ================================================================ */
async function applyDashboardFilter(){
  const year = document.getElementById('dash-year-filter')?.value || '';
  const btn  = document.getElementById('dash-filter-btn');
  if(btn){ btn.disabled=true; btn.innerHTML='<span class="spinner" style="display:inline-block;"></span> Applying…'; }

  // Destroy existing trend chart so it re-renders properly
  if(CHART_REGISTRY['chart-dash-trend']){
    CHART_REGISTRY['chart-dash-trend'].destroy();
    delete CHART_REGISTRY['chart-dash-trend'];
  }

  // Reset counter animations so they re-trigger
  document.querySelectorAll('#page-dashboard [data-count]').forEach(el=>delete el.dataset.done);

  await initDashboardCharts(year);

  if(btn){
    btn.disabled = false;
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 3H2l8 9.5V19l4 2v-8.5z"/></svg> Apply Filter';
  }

  const label = year ? `${year} data loaded` : 'Showing all 2022–2024 data';
  showToast('success', 'Dashboard updated', label);
}
window.applyDashboardFilter = applyDashboardFilter;

/* ================================================================
   ACCIDENT ANALYTICS — with year / severity / area filter
   Unified /api/analytics endpoint guarantees:
   sum(by_hour) == sum(by_weekday) == kpis.total == records_count
   ================================================================ */
let _analyticsActiveFilters = {};

async function initAnalyticsCharts(filters = {}){
  _analyticsActiveFilters = { ...filters };
  const qs = new URLSearchParams(filters).toString();
  const q  = qs ? '?' + qs : '';

  try {
    const data = await apiFetch('/api/analytics' + q);
    if(!data) throw new Error('No analytics data received from server');

    const kpis = data.kpis || { total: 0, fatal: 0, major: 0, minor: 0, casualties: 0 };
    const hasFilters = Object.keys(filters).length > 0 && Object.values(filters).some(v => v !== '');

    // ── Update Subtitle & Badges ─────────────────────────────
    const subEl = document.getElementById('analytics-page-subtitle') || document.getElementById('analytics-filter-subtitle');
    if(subEl && data.subtitle){
      subEl.textContent = data.subtitle;
    }

    // ── Update Filter Info Line & Active Chips ───────────────
    const infoEl = document.getElementById('analytics-filter-count');
    if(infoEl){
      infoEl.textContent = hasFilters
        ? `Showing ${data.records_count.toLocaleString('en-IN')} of ${kpis.total.toLocaleString('en-IN')} accidents (filtered)`
        : `Showing all ${kpis.total.toLocaleString('en-IN')} recorded accidents`;
    }
    const chipsEl = document.getElementById('analytics-active-chips');
    if(chipsEl){
      const chips = [];
      if(filters.year) chips.push(`Year: ${filters.year}`);
      if(filters.severity) chips.push(`Severity: ${filters.severity.charAt(0).toUpperCase() + filters.severity.slice(1)}`);
      if(filters.area) chips.push(`Area: ${filters.area}`);
      if(chips.length > 0){
        chipsEl.innerHTML = chips.map(c => `<span class="badge b-blue" style="font-size:11px;padding:3px 10px;">${escapeHtml(c)}</span>`).join(' ');
      } else {
        chipsEl.innerHTML = '<span class="badge b-blue" style="font-size:11px;">All Records</span>';
      }
    }

    // ── KPI Cards ────────────────────────────────────────────
    const totalEl = document.getElementById('analytics-kpi-total');
    if(totalEl){ totalEl.dataset.count = kpis.total; totalEl.dataset.done = ''; totalEl.textContent = kpis.total.toLocaleString('en-IN'); }
    const fatalEl = document.getElementById('analytics-kpi-fatal');
    if(fatalEl){ fatalEl.dataset.count = kpis.fatal; fatalEl.dataset.done = ''; fatalEl.textContent = kpis.fatal.toLocaleString('en-IN'); }
    const casEl = document.getElementById('analytics-kpi-casualties');
    if(casEl){ casEl.dataset.count = kpis.casualties; casEl.dataset.done = ''; casEl.textContent = kpis.casualties.toLocaleString('en-IN'); }
    const majorEl = document.getElementById('analytics-kpi-major');
    if(majorEl){ majorEl.dataset.count = kpis.major; majorEl.dataset.done = ''; majorEl.textContent = kpis.major.toLocaleString('en-IN'); }

    // Update labels to reflect filter
    const lblTotal = document.getElementById('analytics-label-total');
    if(lblTotal) lblTotal.textContent = hasFilters ? 'Total Accidents (filtered)' : 'Total Accidents';
    const lblFatal = document.getElementById('analytics-label-fatal');
    if(lblFatal) lblFatal.textContent = hasFilters ? 'Fatal Accidents (filtered)' : 'Fatal Accidents';
    const lblCas = document.getElementById('analytics-label-casualties');
    if(lblCas) lblCas.textContent = hasFilters ? 'Total Casualties (filtered)' : 'Total Casualties';
    const lblMajor = document.getElementById('analytics-label-major');
    if(lblMajor) lblMajor.textContent = hasFilters ? 'Major Accidents (filtered)' : 'Major Accidents';

    // Real dynamic badges (no hardcoded percentages)
    const fatalPct = kpis.total > 0 ? ((kpis.fatal / kpis.total) * 100).toFixed(1) : '0.0';
    const majorPct = kpis.total > 0 ? ((kpis.major / kpis.total) * 100).toFixed(1) : '0.0';
    const trendFatal = document.getElementById('analytics-trend-fatal');
    if(trendFatal) trendFatal.textContent = `${fatalPct}% fatal`;
    const trendMajor = document.getElementById('analytics-trend-major');
    if(trendMajor) trendMajor.textContent = `${majorPct}% major`;
    const trendCas = document.getElementById('analytics-trend-casualties');
    if(trendCas) trendCas.textContent = `${kpis.casualties.toLocaleString('en-IN')} victims`;
    const trendTot = document.getElementById('analytics-trend-total');
    if(trendTot) trendTot.textContent = hasFilters ? `${kpis.total.toLocaleString('en-IN')} matching` : '100% of dataset';

    // ── Hourly bar chart (12 2-hour buckets) ─────────────────
    const byHour = data.by_hour || { values: [] };
    const bucketLabels = ['12AM','2AM','4AM','6AM','8AM','10AM','12PM','2PM','4PM','6PM','8PM','10PM'];
    const bucketData   = [];
    for(let i=0; i<24; i+=2){
      bucketData.push((byHour.values[i]||0) + (byHour.values[i+1]||0));
    }
    const timeTotal = bucketData.reduce((a, b) => a + b, 0);

    // Dynamically highlight top 3 buckets
    const sortedIndices = bucketData
      .map((val, idx) => ({ val, idx }))
      .sort((a, b) => b.val - a.val)
      .slice(0, 3)
      .filter(item => item.val > 0)
      .map(item => item.idx);
    const timeColors = bucketData.map((_, i) => sortedIndices.includes(i) ? '#F04438' : '#2D7CFF');

    const exTime = CHART_REGISTRY['chart-analytics-time'];
    if(exTime){
      exTime.data.datasets[0].data = bucketData;
      exTime.data.datasets[0].backgroundColor = timeColors;
      exTime.update();
    } else {
      mkChart('chart-analytics-time', {
        type: 'bar',
        data: {
          labels: bucketLabels,
          datasets: [{
            data: bucketData,
            backgroundColor: timeColors,
            borderRadius: 6,
            maxBarThickness: 24
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: i => i[0].label + ' hrs',
                label: i => {
                  const pct = timeTotal > 0 ? ((i.raw / timeTotal) * 100).toFixed(1) : '0';
                  return `  Accidents: ${i.raw.toLocaleString('en-IN')} (${pct}%)`;
                }
              }
            }
          },
          scales: {
            y: {
              grid: { color: 'rgba(255,255,255,0.06)' },
              ticks: { color: '#94a3b8' }
            },
            x: {
              grid: { display: false },
              ticks: { color: '#94a3b8' }
            }
          }
        }
      });
    }

    // ── Weekday doughnut chart ───────────────────────────────
    const byWeekday = data.by_weekday || { labels: ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'], values: [0,0,0,0,0,0,0] };
    const wTotal = byWeekday.values.reduce((a, b) => a + b, 0);
    const exWeekday = CHART_REGISTRY['chart-analytics-weekday'];
    if(exWeekday){
      exWeekday.data.labels = byWeekday.labels;
      exWeekday.data.datasets[0].data = byWeekday.values;
      exWeekday.update();
    } else {
      mkChart('chart-analytics-weekday', {
        type: 'doughnut',
        data: {
          labels: byWeekday.labels,
          datasets: [{
            data: byWeekday.values,
            backgroundColor: ['#2D7CFF','#17B26A','#F79009','#F04438','#9E77ED','#06AED4','#EAB308'],
            borderWidth: 2,
            borderColor: '#0f172a'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '62%',
          plugins: {
            legend: {
              display: true,
              position: 'right',
              labels: {
                color: '#cbd5e1',
                boxWidth: 9,
                boxHeight: 9,
                usePointStyle: true,
                pointStyle: 'circle',
                padding: 10,
                font: { family: "'Inter', sans-serif", size: 11, weight: '600' },
                generateLabels: function(chart) {
                  const d = chart.data;
                  if(!d.labels.length || !d.datasets.length) return [];
                  const ds = d.datasets[0];
                  const sum = ds.data.reduce((a, b) => a + b, 0);
                  return d.labels.map((lbl, i) => {
                    const v = ds.data[i] || 0;
                    const pct = sum > 0 ? ((v / sum) * 100).toFixed(1) : '0';
                    return {
                      text: `${lbl} · ${v.toLocaleString('en-IN')} (${pct}%)`,
                      fillStyle: ds.backgroundColor[i],
                      strokeStyle: ds.borderColor,
                      lineWidth: ds.borderWidth,
                      hidden: false,
                      index: i
                    };
                  });
                }
              }
            },
            tooltip: {
              callbacks: {
                label: item => {
                  const pct = wTotal > 0 ? ((item.raw / wTotal) * 100).toFixed(1) : '0';
                  return `  ${item.label}: ${item.raw.toLocaleString('en-IN')} accidents (${pct}%)`;
                }
              }
            }
          }
        }
      });
    }

  } catch(err){
    console.error('[Analytics Error]', err);
    showToast('error', 'Analytics Load Failed', err.message || 'Could not fetch analytics data.');
  }
}


/* ================================================================
   ANALYTICS FILTER CONTROLS
   ================================================================ */
async function applyAnalyticsFilter(){
  const year     = document.getElementById('filter-year')?.value     || '';
  const severity = document.getElementById('filter-severity')?.value || '';
  const area     = document.getElementById('filter-area')?.value     || '';
  const btn      = document.getElementById('analytics-filter-btn');

  if(btn){
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner" style="display:inline-block;"></span> Applying…';
  }

  const filters = {};
  if(year)     filters.year     = year;
  if(severity) filters.severity = severity;
  if(area)     filters.area     = area;

  await initAnalyticsCharts(filters);

  if(btn){
    btn.disabled = false;
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><path d="M22 3H2l8 9.5V19l4 2v-8.5z"/></svg>Apply Filter';
  }

  const parts = [];
  if(year)     parts.push(`Year: ${year}`);
  if(severity) parts.push(`Severity: ${severity.charAt(0).toUpperCase() + severity.slice(1)}`);
  if(area)     parts.push(`Area: ${area}`);
  showToast('success', 'Filter Applied', parts.length ? parts.join(' · ') : 'All Kochi accident records');
}
window.applyAnalyticsFilter = applyAnalyticsFilter;

async function resetAnalyticsFilter(){
  const yEl = document.getElementById('filter-year');
  const sEl = document.getElementById('filter-severity');
  const aEl = document.getElementById('filter-area');
  if(yEl) yEl.value = '';
  if(sEl) sEl.value = '';
  if(aEl) aEl.value = '';

  await initAnalyticsCharts({});
  showToast('info', 'Filters Reset', 'All filters cleared.');
}
window.resetAnalyticsFilter = resetAnalyticsFilter;

function exportAnalyticsCSV(){
  const qs = new URLSearchParams(_analyticsActiveFilters).toString();
  window.location.href = '/api/analytics/export' + (qs ? '?' + qs : '');
}
window.exportAnalyticsCSV = exportAnalyticsCSV;

/* ================================================================
   DATA MANAGEMENT
   ================================================================ */
async function initDataPage(){
  const recent = await apiFetch('/api/dashboard/recent?limit=20');
  renderDataTable(recent || []);
}

/* ================================================================
   DATA MANAGEMENT — Full CRUD, Real API, Pagination, Import/Export
   ================================================================ */
const KOCHI_AREA_ROADS = {
  "Edappally": ["Rajagiri Road", "LuLu Mall Access Road", "Konthuruthy Road", "Edappally Junction", "Edappally Toll Junction", "NH 66 Bypass", "Seaport Airport Road", "Edappally North"],
  "Fort Kochi": ["KB Jacob Road", "Calvathy Road", "Bazaar Road", "Tower Road", "River Road", "Peter Celli Street"],
  "Kadavanthra": ["Kadavanthra Junction", "KP Vallon Road", "Sahodaran Ayyappan Road", "Gandhinagar Road", "Subhash Chandra Bose Road"],
  "Kakkanad": ["Seaport Airport Road", "Infopark Expressway", "Kakkanad Junction", "Vazhakkala Road", "Civil Station Road"],
  "Mattancherry": ["Palace Road", "Jew Town Road", "Pandit Karuppan Road", "New Road", "Cheralai Road"],
  "Palarivattom": ["Palarivattom Junction", "Palarivattom Bypass", "Pipeline Road", "Janatha Road", "St. Martin Road"],
  "Vyttila": ["Vyttila Mobility Hub Access Road", "Vyttila Junction", "SA Road", "Subhash Bose Road", "Kaniyampuzha Road"]
};

let currentDataPage = 1;
const DATA_PAGE_SIZE = 25;
let dataSearchTimeout = null;
let cachedDataRecords = [];

function openModal(modalId){
  const el = document.getElementById(modalId);
  if(el){
    el.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }
}
window.openModal = openModal;

function closeModal(modalId){
  const el = document.getElementById(modalId);
  if(el){
    el.style.display = 'none';
    document.body.style.overflow = '';
  }
}
window.closeModal = closeModal;

function populateRecordRoads(area, selectedRoad=''){
  const select = document.getElementById('rec-road-name');
  if(!select) return;
  const roads = KOCHI_AREA_ROADS[area] || [];
  select.innerHTML = roads.map(r => `<option value="${r}" ${r===selectedRoad?'selected':''}>${r}</option>`).join('');
}
window.populateRecordRoads = populateRecordRoads;

async function initDataPage(){
  await loadDataRecords(1);
}

async function loadDataRecords(page=1){
  currentDataPage = page;
  const tbody = document.getElementById('data-table-body');
  const countEl = document.getElementById('data-table-count');
  if(!tbody) return;

  tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:24px;color:#94a3b8;"><span class="spinner" style="display:inline-block;margin-right:8px;"></span> Loading records from database...</td></tr>';

  const q = document.getElementById('data-search-input')?.value?.trim() || '';
  const severity = document.getElementById('data-filter-severity')?.value || '';
  const area = document.getElementById('data-filter-area')?.value || '';
  const source = document.getElementById('data-filter-source')?.value || '';

  const params = new URLSearchParams({
    page: page,
    page_size: DATA_PAGE_SIZE,
    q: q,
    severity: severity,
    area: area,
    source: source
  });

  try {
    const res = await apiFetch('/api/records?' + params.toString());
    if(!res || !res.success){
      tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;padding:24px;color:#F04438;">Error loading records: ${res?.error || 'Database unavailable'}. <button class="btn btn-secondary" onclick="loadDataRecords(${page})" style="margin-left:8px;padding:3px 10px;font-size:11px;">Retry</button></td></tr>`;
      return;
    }

    cachedDataRecords = res.items || [];
    const total = res.total || 0;
    const totalPages = res.total_pages || 1;

    if(countEl){
      const startIdx = total > 0 ? (page - 1) * DATA_PAGE_SIZE + 1 : 0;
      const endIdx = Math.min(page * DATA_PAGE_SIZE, total);
      countEl.textContent = `Showing ${startIdx}–${endIdx} of ${total.toLocaleString('en-IN')} records`;
    }

    if(cachedDataRecords.length === 0){
      tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:32px;color:#94a3b8;">No records matched your search filters.</td></tr>';
      renderDataPagination(page, totalPages, total);
      return;
    }

    tbody.innerHTML = cachedDataRecords.map(r => {
      const dateText = r.occurred_at ? r.occurred_at.slice(0, 16).replace('T', ' ') : '—';
      const causeText = (r.cause || 'Unknown').replace(/_/g, ' ');
      const srcBadge = r.data_source === 'real' ? 'b-green' : (r.data_source === 'synthetic' ? 'b-purple' : 'b-blue');

      return `
        <tr>
          <td class="mono" style="font-weight:700;color:#93c5fd;">${r.accident_uid}</td>
          <td class="mono" style="font-size:12px;">${dateText}</td>
          <td>${r.area}</td>
          <td style="font-weight:600;color:#ffffff;">${r.road_name}</td>
          <td><span class="badge b-${sevColor(r.severity)}">${r.severity.toUpperCase()}</span></td>
          <td style="font-size:12px;">${causeText}</td>
          <td style="font-size:12px;text-transform:capitalize;">${r.weather}</td>
          <td style="text-align:center;">${r.vehicles_involved}</td>
          <td style="text-align:center;font-weight:700;color:${r.casualties>0?'#ff7675':'inherit'};">${r.casualties}</td>
          <td><span class="badge ${srcBadge}" style="font-size:10px;">${(r.data_source||'sample').toUpperCase()}</span></td>
          <td>
            <div class="table-actions">
              <button class="icon-btn-sm" onclick="openViewRecordModal('${r.accident_uid}')" title="View Details">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
              <button class="icon-btn-sm" onclick="openEditRecordModal('${r.accident_uid}')" title="Edit Record">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
              </button>
              <button class="icon-btn-sm danger" onclick="deleteRecord('${r.accident_uid}')" title="Delete Record">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    renderDataPagination(page, totalPages, total);

  } catch(err){
    console.error('Error loading records:', err);
    tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;padding:24px;color:#F04438;">Network error loading records. <button class="btn btn-secondary" onclick="loadDataRecords(${page})" style="margin-left:8px;padding:3px 10px;font-size:11px;">Retry</button></td></tr>`;
  }
}
window.loadDataRecords = loadDataRecords;

function renderDataPagination(page, totalPages, total){
  const el = document.getElementById('data-pagination');
  if(!el) return;

  el.innerHTML = `
    <div>Page <strong>${page}</strong> of <strong>${totalPages}</strong> &middot; Total <strong>${total.toLocaleString('en-IN')}</strong> entries</div>
    <div class="page-btns">
      <button class="page-btn" ${page <= 1 ? 'disabled' : ''} onclick="loadDataRecords(${page - 1})">Previous</button>
      <button class="page-btn" ${page >= totalPages ? 'disabled' : ''} onclick="loadDataRecords(${page + 1})">Next</button>
    </div>
  `;
}

function onDataSearchInput(val){
  clearTimeout(dataSearchTimeout);
  dataSearchTimeout = setTimeout(() => {
    loadDataRecords(1);
  }, 300);
}
window.onDataSearchInput = onDataSearchInput;

function openAddRecordModal(){
  document.getElementById('record-form').reset();
  document.getElementById('rec-id').value = '';
  document.getElementById('record-modal-title').textContent = 'Add Accident Record';

  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const mins = String(now.getMinutes()).padStart(2, '0');
  document.getElementById('rec-occurred-at').value = `${year}-${month}-${day}T${hours}:${mins}`;

  const area = document.getElementById('rec-area').value || 'Edappally';
  populateRecordRoads(area);
  openModal('record-modal');
}
window.openAddRecordModal = openAddRecordModal;

function openEditRecordModal(id){
  const r = cachedDataRecords.find(item => item.accident_uid === id || item.id === id);
  if(!r) return;

  document.getElementById('rec-id').value = r.accident_uid;
  document.getElementById('record-modal-title').textContent = `Edit Record — ${r.accident_uid}`;

  if(r.occurred_at){
    document.getElementById('rec-occurred-at').value = r.occurred_at.slice(0, 16);
  }
  document.getElementById('rec-area').value = r.area;
  populateRecordRoads(r.area, r.road_name);
  document.getElementById('rec-road-type').value = r.road_type || 'urban';
  document.getElementById('rec-severity').value = (r.severity || 'minor').toLowerCase();
  document.getElementById('rec-cause').value = r.cause || 'overspeeding';
  document.getElementById('rec-weather').value = r.weather || 'clear';
  document.getElementById('rec-density').value = r.traffic_density || 'medium';
  document.getElementById('rec-vehicles').value = r.vehicles_involved || 1;
  document.getElementById('rec-casualties').value = r.casualties || 0;

  openModal('record-modal');
}
window.openEditRecordModal = openEditRecordModal;

async function submitRecordForm(e){
  e.preventDefault();
  const submitBtn = document.getElementById('rec-submit-btn');
  submitBtn.disabled = true;
  submitBtn.textContent = 'Saving...';

  const id = document.getElementById('rec-id').value;
  const isEdit = Boolean(id);

  const payload = {
    occurred_at: document.getElementById('rec-occurred-at').value.replace('T', ' ') + ':00',
    area: document.getElementById('rec-area').value,
    road_name: document.getElementById('rec-road-name').value,
    road_type: document.getElementById('rec-road-type').value,
    severity: document.getElementById('rec-severity').value,
    cause: document.getElementById('rec-cause').value,
    weather: document.getElementById('rec-weather').value,
    traffic_density: document.getElementById('rec-density').value,
    vehicles_involved: parseInt(document.getElementById('rec-vehicles').value, 10),
    casualties: parseInt(document.getElementById('rec-casualties').value, 10)
  };

  try {
    const url = isEdit ? `/api/records/${id}` : '/api/records';
    const method = isEdit ? 'PUT' : 'POST';

    const res = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if(!res.ok || !data.success){
      throw new Error(data.error || 'Failed to save record.');
    }

    closeModal('record-modal');
    showToast('success', isEdit ? 'Record Updated' : 'Record Created', data.message);
    loadDataRecords(currentDataPage);

  } catch(err){
    console.error('Save error:', err);
    showToast('error', 'Error', err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Save Record';
  }
}
window.submitRecordForm = submitRecordForm;

function openViewRecordModal(id){
  const r = cachedDataRecords.find(item => item.accident_uid === id || item.id === id);
  if(!r) return;

  const titleEl = document.getElementById('record-view-title');
  const bodyEl = document.getElementById('record-view-body');
  if(!bodyEl) return;

  if(titleEl) titleEl.textContent = `Accident Record: ${r.accident_uid}`;

  bodyEl.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:13px;">
      <div style="padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;">
        <span class="text-dim">Occurred At:</span> <strong>${r.occurred_at || '—'}</strong>
      </div>
      <div style="padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;">
        <span class="text-dim">Severity:</span> <span class="badge b-${sevColor(r.severity)}">${(r.severity||'').toUpperCase()}</span>
      </div>
      <div style="padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;">
        <span class="text-dim">Location:</span> <strong>${r.road_name}, ${r.area}</strong>
      </div>
      <div style="padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;">
        <span class="text-dim">Coordinates:</span> <strong>${r.latitude}, ${r.longitude}</strong>
      </div>
      <div style="padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;">
        <span class="text-dim">Primary Cause:</span> <strong>${(r.cause||'').replace(/_/g, ' ')}</strong>
      </div>
      <div style="padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;">
        <span class="text-dim">Weather &amp; Traffic:</span> <strong>${r.weather} &middot; ${r.traffic_density} density</strong>
      </div>
      <div style="padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;">
        <span class="text-dim">Vehicles Involved:</span> <strong>${r.vehicles_involved}</strong>
      </div>
      <div style="padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;">
        <span class="text-dim">Casualties:</span> <strong>${r.casualties}</strong>
      </div>
      <div style="padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;grid-column:span 2;">
        <span class="text-dim">Data Source:</span> <span class="badge b-purple">${(r.data_source||'sample').toUpperCase()}</span>
      </div>
    </div>
  `;

  openModal('record-view-modal');
}
window.openViewRecordModal = openViewRecordModal;

async function deleteRecord(id){
  if(!confirm(`Are you sure you want to permanently delete record ${id}? This action is logged in audit trail.`)){
    return;
  }

  try {
    const res = await fetch(`/api/records/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if(!res.ok || !data.success){
      throw new Error(data.error || 'Failed to delete record.');
    }
    showToast('success', 'Deleted', data.message);
    loadDataRecords(currentDataPage);
  } catch(err){
    console.error('Delete error:', err);
    showToast('error', 'Delete Failed', err.message);
  }
}
window.deleteRecord = deleteRecord;

function openImportModal(){
  document.getElementById('import-csv-file').value = '';
  document.getElementById('import-result-wrap').style.display = 'none';
  openModal('record-import-modal');
}
window.openImportModal = openImportModal;

async function submitImportCSV(){
  const fileInput = document.getElementById('import-csv-file');
  const btn = document.getElementById('import-submit-btn');
  const resultWrap = document.getElementById('import-result-wrap');

  if(!fileInput.files || fileInput.files.length === 0){
    alert('Please select a CSV file to upload.');
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  btn.disabled = true;
  btn.textContent = 'Importing...';
  resultWrap.style.display = 'block';
  resultWrap.innerHTML = '<span class="spinner" style="display:inline-block;margin-right:8px;"></span> Validating and importing rows...';

  try {
    const res = await fetch('/api/records/import', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if(!res.ok || !data.success){
      throw new Error(data.error || 'Import failed.');
    }

    resultWrap.innerHTML = `
      <div style="color:#17B26A;font-weight:700;margin-bottom:6px;">Import Complete!</div>
      <div style="font-size:12.5px;">
        &bull; Accepted rows: <strong>${data.accepted}</strong><br>
        &bull; Rejected rows: <strong>${data.rejected}</strong>
      </div>
      ${data.errors && data.errors.length ? `<div style="margin-top:8px;font-size:11.5px;color:#ff7675;max-height:100px;overflow:auto;">${data.errors.map(e => `Row ${e.row}: ${e.reason}`).join('<br>')}</div>` : ''}
    `;

    showToast('success', 'Import Finished', `Imported ${data.accepted} records successfully.`);
    loadDataRecords(1);

  } catch(err){
    resultWrap.innerHTML = `<div style="color:#F04438;">Error: ${err.message}</div>`;
    showToast('error', 'Import Failed', err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Start Import';
  }
}
window.submitImportCSV = submitImportCSV;

function exportDataRecords(){
  const q = document.getElementById('data-search-input')?.value?.trim() || '';
  const severity = document.getElementById('data-filter-severity')?.value || '';
  const area = document.getElementById('data-filter-area')?.value || '';
  const source = document.getElementById('data-filter-source')?.value || '';

  const params = new URLSearchParams({ q, severity, area, source });
  window.location.href = '/api/records/export?' + params.toString();
  showToast('info', 'Export Started', 'Streaming filtered records to CSV...');
}
window.exportDataRecords = exportDataRecords;

/* ================================================================
   SETTINGS — load from DB on page open, save back to DB
   ================================================================ */
async function initSettingsPage(){
  const profile = await apiFetch('/api/profile?username='+(currentUser.username||'admin'));
  if(profile && !profile.error){
    const set = (id,val)=>{ const el=document.getElementById(id); if(el) el.value=val||''; };
    set('settings-name',  profile.name);
    set('settings-email', profile.email);
    set('settings-dept',  profile.department);
    set('settings-phone', profile.phone);
    const roleEl = document.getElementById('settings-role');
    if(roleEl && profile.role){
      const opt = Array.from(roleEl.options).find(o=>o.value===profile.role||o.text===profile.role);
      if(opt) roleEl.value = opt.value;
    }
  }

  const saveBtn = document.getElementById('settings-save-btn');
  if(saveBtn && !saveBtn.dataset.wired){
    saveBtn.dataset.wired = '1';
    saveBtn.addEventListener('click', saveSettings);
  }

  // Sync dark-mode toggle
  const darkToggle = document.getElementById('dark-mode-toggle');
  if(darkToggle && !darkToggle.dataset.wired){
    darkToggle.dataset.wired = '1';
    darkToggle.checked = document.body.classList.contains('dark-theme');
    darkToggle.addEventListener('change', function(){
      setDarkTheme(this.checked);
      showToast('info','Theme', this.checked?'Dark mode enabled.':'Light mode enabled.');
    });
  }
}

async function saveSettings(){
  const btn  = document.getElementById('settings-save-btn');
  const name = document.getElementById('settings-name')?.value?.trim()  || '';
  const email= document.getElementById('settings-email')?.value?.trim() || '';
  const dept = document.getElementById('settings-dept')?.value?.trim()  || '';
  const phone= document.getElementById('settings-phone')?.value?.trim() || '';
  const role = document.getElementById('settings-role')?.value           || '';

  if(!name){ showToast('error','Validation','Name cannot be empty.'); return; }
  if(btn) btn.disabled = true;

  try {
    const res  = await fetch('/api/profile/update', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({username:currentUser.username||'admin', name, email, department:dept, phone, role})
    });
    const data = await res.json();
    if(data.success){
      currentUser = {...currentUser, name, role, email, department:dept};
      sessionStorage.setItem('kochi_session_user', JSON.stringify(currentUser));
      updateTopbarProfile(currentUser);
      const initials = name.split(' ').map(n=>n[0]).join('').toUpperCase().slice(0,2);
      const settingsAvatar = document.querySelector('#page-settings .flex .avatar');
      if(settingsAvatar) settingsAvatar.textContent = initials;
      showToast('success','Profile saved', `${name}'s profile has been updated.`);
    } else {
      showToast('error','Save failed', data.message || 'Something went wrong.');
    }
  } catch(err){
    showToast('error','Error','Could not reach the server.');
    console.error(err);
  }
  if(btn) btn.disabled = false;
}

/* ================================================================
   RISK PREDICTION
   ================================================================ */
/* ================================================================
   SEVERITY PREDICTION & EXPLAINABILITY (PB-06, Phases B1-B4)
   ================================================================ */
async function initRiskCharts(){
  const area = document.getElementById('risk-area')?.value || 'Edappally';
  const road = document.getElementById('risk-road-name')?.value || 'Rajagiri Road';
  await loadLocationHistory(area, road);

  const btn = document.getElementById('predict-risk-btn');
  if(btn && !btn.dataset.wired){
    btn.dataset.wired = '1';
    btn.addEventListener('click', runRiskPrediction);
  }
}

window.onRoadSelectionChanged = function(){
  const area = document.getElementById('risk-area')?.value || 'Edappally';
  const road = document.getElementById('risk-road-name')?.value || 'Rajagiri Road';
  loadLocationHistory(area, road);
};

window.onKeralaAreaChanged = function(area){
  const roadSelect = document.getElementById('risk-road-name');
  if(!roadSelect) return;
  const roads = KOCHI_AREA_ROADS[area] || [];
  roadSelect.innerHTML = roads.map(r => `<option value="${r}">${r}</option>`).join('');
  const firstRoad = roads[0] || '';
  loadLocationHistory(area, firstRoad);
};

/* ── Location Historical Record (Phase B2) ─────────────────── */
async function loadLocationHistory(area, roadName){
  const titleEl = document.getElementById('hist-record-title');
  const statsEl = document.getElementById('hist-location-stats');
  if(!statsEl) return;

  if(titleEl) titleEl.textContent = `Historical Record — ${roadName}, ${area}`;

  try {
    const res = await apiFetch(`/api/location-history?area=${encodeURIComponent(area)}&road_name=${encodeURIComponent(roadName)}`);
    if(!res || !res.success){
      statsEl.innerHTML = '<div style="color:#F04438;font-size:12px;padding:8px;">Location historical data not available for this selection.</div>';
      return;
    }

    const data = res.history || res;

    // Render 12-month mini chart
    requestAnimationFrame(()=>{
      const cv = document.getElementById('chart-risk-history');
      if(!cv) return;

      if(CHART_REGISTRY['chart-risk-history']){
        CHART_REGISTRY['chart-risk-history'].destroy();
        delete CHART_REGISTRY['chart-risk-history'];
      }

      const mLabels = Array.isArray(data.monthly_counts)
        ? data.monthly_counts.map(m => m.month.slice(5))
        : (data.monthly_counts?.labels || []).map(l => l.slice(5));
      const mData = Array.isArray(data.monthly_counts)
        ? data.monthly_counts.map(m => m.count)
        : (data.monthly_counts?.values || []);

      mkChart('chart-risk-history', {
        type: 'bar',
        data: {
          labels: mLabels,
          datasets: [{
            label: 'Monthly Accidents',
            data: mData,
            backgroundColor: '#2D7CFF',
            borderRadius: 4
          }]
        },
        options: {
          responsive: false,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: c => ` ${c.raw} recorded accidents` } }
          },
          scales: {
            y: { grid: gridOpt(), border: { display: false } },
            x: { grid: { display: false }, border: { display: false } }
          }
        }
      });
    });

    // Render Location Stats
    const topCausesStr = (data.top_causes || []).slice(0, 3).map(c => `${(c.cause || '').replace(/_/g, ' ')} (${c.pct || 0}%)`).join(' &middot; ');

    const minorInfo = data.severity_split?.minor || {count: 0, pct: 0};
    const majorInfo = data.severity_split?.major || {count: 0, pct: 0};
    const fatalInfo = data.severity_split?.fatal || {count: 0, pct: 0};

    statsEl.innerHTML = `
      <div style="font-size:12px;background:rgba(255,255,255,0.03);padding:10px 12px;border-radius:8px;border:1px solid rgba(192,230,253,0.12);">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
          <span style="color:#93c5fd;font-weight:700;">Hotspot Rank #${data.hotspot_rank || 1} of ${data.total_roads || 57} roads</span>
          <span class="badge b-orange">Danger Score: ${data.danger_score || 0}/100</span>
        </div>
        <div style="color:#cbd5e1;margin-bottom:6px;">
          Total Accidents: <strong>${data.total_accidents || 0}</strong> &middot;
          Minor: <span style="color:#17B26A;">${minorInfo.count} (${minorInfo.pct}%)</span> &middot;
          Major: <span style="color:#F79009;">${majorInfo.count} (${majorInfo.pct}%)</span> &middot;
          Fatal: <span style="color:#F04438;">${fatalInfo.count} (${fatalInfo.pct}%)</span>
        </div>
        <div style="color:#94a3b8;font-size:11px;">
          Top Collision Drivers: ${topCausesStr || 'None recorded'}
        </div>
      </div>
    `;

  } catch(err){
    console.error('Location history error:', err);
    statsEl.innerHTML = '<div style="color:#F04438;font-size:12px;">Error retrieving location record.</div>';
  }
}

/* ── Top Contributing Factors Table (Phase B1) ─────────────── */
function renderShapFactorsTable(features, predictedSeverity){
  const container = document.getElementById('risk-factors');
  if(!container) return;

  if(!features || features.length === 0){
    container.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-dim);font-size:12px;">SHAP factors not available for this prediction.</div>';
    return;
  }

  container.innerHTML = `
    <div class="risk-factor-header-row">
      <div class="risk-col-num">#</div>
      <div class="risk-col-feat">Factor</div>
      <div class="risk-col-pct">Share</div>
      <div class="risk-col-eff">Effect</div>
    </div>
  ` + features.slice(0, 5).map((f, i) => {
    const isSup = f.direction === 'supports';
    const dirClass = isSup ? 'supports' : 'opposes';
    const badgeText = isSup ? 'Supports' : 'Opposes';
    const fillWidth = Math.min(Math.max(f.share_pct * 2, 2), 100);

    return `
      <div class="risk-factor">
        <div class="risk-col-num">${i + 1}</div>
        <div class="risk-col-feat" title="${escapeHtml(f.value_label)}">${escapeHtml(f.value_label)}</div>
        <div class="risk-col-pct">${f.share_pct}%</div>
        <div class="risk-col-eff">
          <span class="risk-factor-direction ${dirClass}">${badgeText}</span>
        </div>
        <div class="risk-col-bar" title="Impact: ${f.share_pct}%">
          <div class="risk-factor-bar">
            <div class="risk-factor-fill ${dirClass}" style="width:${fillWidth}%;"></div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}
/* ── Feature → Recommendation lookup ── */
const SHAP_REC_MAP = {
  'area':                      {icon:'M12 2 4 5v6c0 5.2 3.4 9.6 8 11 4.6-1.4 8-5.8 8-11V5l-8-3Z',                                                      title:'Zonal Police Deployment',   desc:'Deploy dedicated traffic wardens and mobile enforcement in this Kochi zone.', color:'blue'},
  'road_name':                 {icon:'M3 12h18M3 6h18M3 18h18',                                                                                           title:'Corridor Patrol',            desc:'High-frequency patrolling along this specific corridor during high-incidence windows.', color:'purple'},
  'cause':                     {icon:'M13 2 3 14h7l-1 8 10-12h-7z',                                                                                     title:'Targeted Hazard Prevention', desc:'Implement focused interventions addressing the primary cause identified by the AI model.', color:'red'},
  'lanes':                     {icon:'M3 12h18M3 6h18M3 18h18',                                                                                           title:'Lane Discipline Enforcement', desc:'Enforce lane discipline markings, median barriers, and designated turning bays.', color:'blue'},
  'traffic_density':           {icon:'M23 7 16 12l7 5V7ZM1 5h15v14H1z',                                                                                  title:'Traffic Congestion Management', desc:'Dynamic traffic rerouting, signal phasing adjustments, and bottleneck easing.', color:'orange'},
  'traffic_signal':            {icon:'M12 2 4 5v6c0 5.2 3.4 9.6 8 11 4.6-1.4 8-5.8 8-11V5l-8-3Z',                                                      title:'Signal Control Optimization', desc:'Install or recalibrate smart traffic signals to safely manage intersection conflicting movements.', color:'green'},
  'weather':                   {icon:'M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2 7 7 0 0 1 4.9-6.65A5 5 0 1 1 19 13h1a3 3 0 0 1 3 3z',      title:'Monsoon Weather Protocol',   desc:'Deploy wet-weather electronic warning signs and reduce operational corridor speed limits.', color:'blue'},
  'visibility':                {icon:'M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41',  title:'Visibility & Illumination Upgrade', desc:'Upgrade street lighting with high-lumen anti-glare fixtures and reflective delineators.', color:'orange'},
  'vehicles_involved':         {icon:'M8.5 12.5h7l1 3.2h-9z',                                                                                            title:'Multi-Vehicle Buffer Separation', desc:'Maintain safe following distances and install median barriers to prevent pileups.', color:'red'},
  'Weather_Conditions':       {icon:'M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2 7 7 0 0 1 4.9-6.65A5 5 0 1 1 19 13h1a3 3 0 0 1 3 3z',      title:'Weather Advisory',           desc:'Increase driver caution and reduce speed during adverse weather. Deploy variable message signs when visibility drops.',           color:'blue'},
  'Speed_Limit':              {icon:'M13 2 3 14h7l-1 8 10-12h-7z',                                                                                     title:'Speed Limit Enforcement',    desc:'Strengthen speed-limit monitoring in the identified zone. Deploy speed cameras and enforce lower limits during high-risk periods.', color:'red'},
  'Light_Conditions':         {icon:'M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41',  title:'Lighting Improvement',       desc:'Improve street lighting at accident-prone segments. Schedule lighting inspections and prioritise poorly-lit junctions.',         color:'orange'},
  'Road_Surface_Conditions':  {icon:'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z',                                                     title:'Road Surface Maintenance',   desc:'Inspect and repair road surface defects. Schedule urgent resurfacing and pothole-filling on the affected carriageway.',           color:'blue'},
  'Junction_Detail':          {icon:'M22 12H2M12 2v20M17 7l5 5-5 5M7 7 2 12l5 5',                                                                       title:'Junction Redesign',          desc:'Review junction layout and sightlines. Consider adding merge lanes, better signage, or road markings to improve traffic flow.',   color:'purple'},
  'Junction_Control':         {icon:'M12 2 4 5v6c0 5.2 3.4 9.6 8 11 4.6-1.4 8-5.8 8-11V5l-8-3Z',                                                      title:'Junction Signal Review',     desc:'Audit traffic-signal phasing and priorities at the junction. Update timings to match current traffic patterns.',                  color:'green'},
  'Policing_Area':            {icon:'M12 2 4 5v6c0 5.2 3.4 9.6 8 11 4.6-1.4 8-5.8 8-11V5l-8-3Z',                                                      title:'Police Deployment',          desc:'Increase traffic police presence in this policing area, especially during identified peak-risk hours.',                           color:'green'},
  'Hour_of_Collision':        {icon:'M23 7 16 12l7 5V7ZM1 5h15v14H1z',                                                                                  title:'Peak-Hour Monitoring',       desc:'Deploy additional surveillance and traffic officers during the identified high-risk hours to deter violations and assist road users.', color:'purple'},
  'default':                  {icon:'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z',                                                    title:'General Safety Review',      desc:'Conduct a thorough road-safety audit for this scenario and implement recommended preventive measures.',                           color:'orange'}
};

/* ── Kerala Area to Roads Mapping ── */
const KERALA_AREA_ROADS = {
  "Edappally": [
    "Rajagiri Road", "LuLu Mall Access Road", "Konthuruthy Road",
    "Edappally Junction", "Edappally Toll Junction", "NH 66 Bypass",
    "Seaport Airport Road", "Edappally North"
  ],
  "Fort Kochi": [
    "Beach Road Fort Kochi", "Calvathy Road", "Fort Kochi Ferry Road",
    "Napier Street", "Princess Street", "Ridsdale Road",
    "Tower Road", "Willingdon Island Road"
  ],
  "Kadavanthra": [
    "Bristow Road", "Chittoor Road", "Convent Road", "Judges Avenue",
    "Kadavanthra Junction", "Kasturi Ranga Rd", "MG Road Kadavanthra",
    "Ravipuram Road", "Sahodaran Ayyappan Road", "Shanmugham Road"
  ],
  "Kakkanad": [
    "CSEZ Road", "High Court Road Kakkanad", "Infopark Expressway",
    "Infopark Road Phase 1", "Infopark Road Phase 2", "Kakkanad Main Road",
    "Kolenchery Road", "Thrippunithura Road"
  ],
  "Mattancherry": [
    "Bazaar Road", "Dutch Cemetery Road", "Harbour Road", "Jew Town Road",
    "Mattancherry Palace Road", "Mattancherry Road", "Pallipuram Road",
    "Thoppumpady Road"
  ],
  "Palarivattom": [
    "Banerji Road", "Elamkulam Road", "Kaloor Palarivattom Rd",
    "NH 85 Palarivattom", "Palarivattom Junction", "Pullepady Road",
    "Vyttila Palarivattom Rd"
  ],
  "Vyttila": [
    "Aroor Bypass", "Chilavannoor Road", "Kundannoor Bridge Road",
    "NH 66 Vyttila", "Pachalam Road", "SA Road Vyttila",
    "Vyttila Junction", "Vyttila Mobility Hub Road"
  ]
};

window.onKeralaAreaChanged = function(area) {
  const roadSelect = document.getElementById('risk-road-name');
  if (!roadSelect) return;
  const roads = KERALA_AREA_ROADS[area] || [];
  roadSelect.innerHTML = roads.map(r => `<option value="${r}">${r}</option>`).join('');
};

function getBaseFeatureName(rawName) {
  return rawName
    .replace(/^(cat|num)__/i, '')   // strip sklearn pipeline prefix
    .trim()
    .replace(/\s+/g, '_')           // normalise spaces → underscores
    .replace(/_[\d.]+$/, '');       // strip trailing numeric one-hot suffix
}

/* ── Defensive AI Recommendations (Phase B3) ───────────────── */
function renderRiskRecommendations(recs){
  const el = document.getElementById('risk-recommendations');
  if(!el) return;

  if(!recs || recs.length === 0){
    el.innerHTML = '<div style="grid-column:span 3;padding:24px;text-align:center;color:#94a3b8;">No safety alerts identified. All parameters appear within normal baseline.</div>';
    return;
  }

  el.innerHTML = recs.map((r, i) => {
    const title = r.title || 'Safety Guideline';
    const desc = r.description || r.desc || 'Standard road safety precaution.';
    const prio = (r.priority || 'medium').toLowerCase();
    const trigger = r.triggered_by ? `Triggered by: ${r.triggered_by}` : '';

    let color = '#2D7CFF';
    let icon = 'M12 2 4 5v6c0 5.2 3.4 9.6 8 11 4.6-1.4 8-5.8 8-11V5l-8-3Z';
    if(prio === 'high' || prio === 'critical'){
      color = '#F04438';
      icon = 'M13 2 3 14h7l-1 8 10-12h-7z';
    } else if(prio === 'medium'){
      color = '#F79009';
      icon = 'M12 2v2M12 20v2M4 12H2M22 12h-2';
    }

    return `
      <div class="card hoverable" style="padding:16px;display:flex;flex-direction:column;gap:8px;background:rgba(13,34,64,0.65);">
        <div style="display:flex;align-items:flex-start;gap:12px;">
          <div class="kpi-icon" style="width:36px;height:36px;border-radius:10px;flex-shrink:0;background:${color}20;color:${color};display:flex;align-items:center;justify-content:center;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${icon}"/></svg>
          </div>
          <div style="flex:1;min-width:0;">
            <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:3px;">
              <span style="font-size:13px;font-weight:700;color:#ffffff;">${i+1}. ${title}</span>
              <span class="badge" style="background:${color}25;color:${color};font-size:10px;font-weight:800;border:1px solid ${color}40;">${prio.toUpperCase()}</span>
            </div>
            <div style="font-size:12px;color:#cbd5e1;line-height:1.55;margin-bottom:4px;">${desc}</div>
            ${trigger ? `<div style="font-size:10.5px;color:#93c5fd;font-weight:600;">${trigger}</div>` : ''}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

/* ── Severity Prediction Execution ─────────────────────────── */
async function runRiskPrediction(){
  const btn = document.getElementById('predict-risk-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="display:inline-block;"></span> Analyzing Scenario…';

  try {
    const area = (document.getElementById('risk-area')?.value || 'Edappally').trim();
    const roadName = (document.getElementById('risk-road-name')?.value || 'Rajagiri Road').trim();
    const roadType = document.getElementById('risk-road-type')?.value || 'urban';
    const lanes = Number(document.getElementById('risk-lanes')?.value || 2);
    const trafficDensity = document.getElementById('risk-density')?.value || 'high';
    const trafficSignal = Number(document.getElementById('risk-signal')?.value || 0);
    const hour = Number(document.getElementById('risk-hour')?.value || 18);
    const dayOfWeek = document.getElementById('risk-day')?.value || 'Wednesday';
    const weather = document.getElementById('risk-weather')?.value || 'clear';
    const visibility = document.getElementById('risk-visibility')?.value || 'good';
    const cause = document.getElementById('risk-cause')?.value || 'overspeeding';
    const vehiclesInvolved = Number(document.getElementById('risk-vehicles')?.value || 2);

    const predictionData = {
      area: area,
      road_name: roadName,
      road_type: roadType,
      lanes: lanes,
      traffic_density: trafficDensity,
      traffic_signal: trafficSignal,
      hour: hour,
      day_of_week: dayOfWeek,
      weather: weather,
      visibility: visibility,
      cause: cause,
      vehicles_involved: vehiclesInvolved
    };

    const response = await fetch('/api/predict-severity', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(predictionData)
    });

    const result = await response.json();
    if(!response.ok || !result.success){
      throw new Error(result.error || 'Prediction calculation failed.');
    }

    const severity = result.predicted_severity || 'Minor';
    const confidence = Number(result.confidence || 0);
    const sevIndex = Math.round(result.severity_index !== undefined ? result.severity_index : 25);

    let riskColor = '#17B26A';
    let riskClass = 'b-green';
    if(severity.toLowerCase() === 'major'){
      riskColor = '#F79009';
      riskClass = 'b-orange';
    } else if(severity.toLowerCase() === 'fatal'){
      riskColor = '#F04438';
      riskClass = 'b-red';
    }

    // 1. Update Severity Index Gauge (0–100)
    const gauge = document.getElementById('risk-gauge-fill');
    if(gauge){
      gauge.setAttribute('stroke', riskColor);
      gauge.style.strokeDashoffset = 283 - (283 * sevIndex / 100);
    }
    const gaugePct = document.getElementById('risk-gauge-pct');
    if(gaugePct){
      gaugePct.textContent = sevIndex;
      gaugePct.style.color = riskColor;
    }
    const gaugeLabel = document.getElementById('risk-gauge-label');
    if(gaugeLabel){
      gaugeLabel.className = 'glabel badge ' + riskClass;
      gaugeLabel.textContent = `Severity Index: ${sevIndex}/100`;
    }
    const gaugeDesc = document.getElementById('risk-gauge-desc');
    if(gaugeDesc){
      gaugeDesc.textContent = `Predicted class: ${severity.toUpperCase()} (${roadName}, ${area}). Model probability: ${confidence.toFixed(1)}%.`;
    }

    // 2. Update 3 Probability Bars (Minor / Major / Fatal)
    const probs = result.probabilities || { minor: 70, major: 25, fatal: 5 };
    const pMinor = Number(probs.minor || 0);
    const pMajor = Number(probs.major || 0);
    const pFatal = Number(probs.fatal || 0);

    const valMinor = document.getElementById('prob-minor-val');
    const barMinor = document.getElementById('prob-minor-bar');
    if(valMinor) valMinor.textContent = pMinor.toFixed(1) + '%';
    if(barMinor) barMinor.style.width = pMinor + '%';

    const valMajor = document.getElementById('prob-major-val');
    const barMajor = document.getElementById('prob-major-bar');
    if(valMajor) valMajor.textContent = pMajor.toFixed(1) + '%';
    if(barMajor) barMajor.style.width = pMajor + '%';

    const valFatal = document.getElementById('prob-fatal-val');
    const barFatal = document.getElementById('prob-fatal-bar');
    if(valFatal) valFatal.textContent = pFatal.toFixed(1) + '%';
    if(barFatal) barFatal.style.width = pFatal + '%';

    // 3. Update Prediction Details
    const confEl = document.getElementById('risk-confidence');
    if(confEl) confEl.textContent = confidence.toFixed(1) + '%';

    const statusBadge = document.getElementById('risk-status-badge');
    if(statusBadge){
      statusBadge.className = 'badge ' + riskClass;
      statusBadge.textContent = `${severity.toUpperCase()} CONFIRMED`;
    }

    const timeEl = document.getElementById('risk-pred-time');
    if(timeEl){
      const now = new Date();
      timeEl.textContent = now.toLocaleDateString('en-IN') + ', ' + now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    }

    // 4. Update SHAP Chart & Top Contributing Factors Table
    const shapData = result.shap;
    if(shapData && shapData.features && shapData.features.length > 0){
      renderShapChart(shapData, severity, confidence);
      renderShapFactorsTable(shapData.features, severity);
    }

    // 5. Update AI Recommendations
    renderRiskRecommendations(result.recommendations || []);

    // 6. Reload Location Historical Record
    loadLocationHistory(area, roadName);

    showToast('success', 'Inference Complete', `${severity} predicted (${confidence.toFixed(1)}%) for ${roadName}.`);

  } catch(error){
    console.error('Severity prediction error:', error);
    showToast('error', 'Prediction Failed', error.message || 'Unable to execute inference.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M13 2 3 14h7l-1 8 10-12h-7z"/>
      </svg>
      Predict Severity
    `;
  }
}

/* ── SHAP Horizontal Diverging Bar Chart (Phase B1) ────────── */
function renderShapChart(shapData, predictedSeverity, confidence){
  const features = (shapData.features || []).slice(0, 8);
  const labels = features.map(f => f.value_label || f.feature);
  const values = features.map(f => parseFloat(f.shap_value));
  const colors = features.map(f => f.direction === 'supports' ? '#17B26A' : '#F04438');

  // Auto-summary above chart
  const summaryEl = document.getElementById('shap-auto-summary');
  if(summaryEl){
    const supporting = features.filter(f => f.direction === 'supports').slice(0, 2).map(f => f.value_label);
    const opposing = features.filter(f => f.direction === 'opposes').slice(0, 1).map(f => f.value_label);
    const supText = supporting.length ? supporting.join(', ') : 'Standard road baseline';
    const oppText = opposing.length ? opposing.join(', ') : 'None';
    summaryEl.innerHTML = `Predicted <strong>${predictedSeverity}</strong> (${confidence.toFixed(1)}%). Main drivers: <span style="color:#17B26A;">${supText}</span>; main opposing: <span style="color:#F04438;">${oppText}</span>.`;
  }

  // Subtitle
  const subEl = document.getElementById('shap-card-sub');
  if(subEl) subEl.textContent = `Feature contribution to predicted severity: ${predictedSeverity}`;

  if(CHART_REGISTRY['chart-shap']){
    CHART_REGISTRY['chart-shap'].destroy();
    delete CHART_REGISTRY['chart-shap'];
  }

  requestAnimationFrame(() => {
    mkChart('chart-shap', {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderRadius: 4,
          barThickness: 16
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (c) => {
                const item = features[c.dataIndex];
                const sign = item.shap_value >= 0 ? '+' : '';
                const dirLabel = item.direction === 'supports' ? 'Supports' : 'Opposes';
                return ` ${dirLabel} predicted severity: ${sign}${item.shap_value.toFixed(4)} (${item.share_pct}% share)`;
              }
            }
          }
        },
        scales: {
          x: {
            grid: gridOpt(),
            border: { display: false },
            title: { display: true, text: `SHAP Value &middot; Class: ${predictedSeverity}`, font: { size: 11, weight: '600' }, color: '#93c5fd' }
          },
          y: {
            grid: { display: false },
            border: { display: false },
            ticks: { font: { size: 11, weight: '600' }, color: '#cbd5e1' }
          }
        }
      }
    });
  });
}

/* ================================================================
   HOTSPOT MAP PAGE (PB-07: Interactive Accident Hotspots & Danger Zones)
   ================================================================ */
let hotspotMapInstance = null;
let hotspotMarkersLayer = null;
let currentHotspots = [];
let activeMarkerMap = {};
let topDangerHotspot = null;
let activeTierFilter = 'all';

function initHotspotPage(){
  buildHotspotMap();
  loadHotspotsFromAPI();
}

function buildHotspotMap(){
  if(hotspotMapInstance) {
    setTimeout(() => hotspotMapInstance.invalidateSize(), 150);
    return;
  }
  if(!window.L) {
    setTimeout(buildHotspotMap, 250);
    return;
  }
  const el = document.getElementById('hotspot-map');
  if(!el) return;

  // Center around Kochi City (lat 9.98, lng 76.29)
  hotspotMapInstance = L.map(el, {
    zoomControl: false,
    attributionControl: false
  }).setView([9.985, 76.295], 12);

  // Clean, high-performance OpenStreetMap tiles
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19
  }).addTo(hotspotMapInstance);

  L.control.zoom({ position: 'topleft' }).addTo(hotspotMapInstance);

  hotspotMarkersLayer = L.layerGroup().addTo(hotspotMapInstance);

  setTimeout(() => hotspotMapInstance.invalidateSize(), 200);
}

async function loadHotspotsFromAPI(filters = {}){
  try {
    const params = new URLSearchParams();
    if(filters.year) params.append('year', filters.year);
    if(filters.severity) params.append('severity', filters.severity);
    if(filters.road_type) params.append('road_type', filters.road_type);
    if(filters.area) params.append('area', filters.area);

    const res = await fetch(`/api/hotspots?${params.toString()}`);
    if(!res.ok) throw new Error('Failed to fetch hotspot data');

    const data = await res.json();
    currentHotspots = data.hotspots || [];
    const stats = data.stats || {
      total_hotspots: currentHotspots.length,
      total_accidents: currentHotspots.reduce((acc, h) => acc + (h.total_accidents || 0), 0),
      very_high_count: currentHotspots.filter(h => h.tier === 'Critical' || h.tier === 'veryhigh').length,
      high_count: currentHotspots.filter(h => h.tier === 'High' || h.tier === 'high').length,
      moderate_count: currentHotspots.filter(h => h.tier === 'Moderate' || h.tier === 'moderate').length,
      low_count: currentHotspots.filter(h => h.tier === 'Low' || h.tier === 'low').length,
      top_danger_zone: currentHotspots[0] || null
    };
    topDangerHotspot = stats.top_danger_zone || currentHotspots[0] || null;

    // Update Header Badges
    const headerDangerEl = document.getElementById('header-danger-count');
    if(headerDangerEl){
      headerDangerEl.innerHTML = `<span class="dot-status live" style="background:#F04438;"></span>${stats.very_high_count || 0} Critical Zones`;
    }
    const headerCountEl = document.getElementById('header-hotspot-count');
    if(headerCountEl){
      headerCountEl.textContent = `${stats.total_hotspots || 0} Monitored Hotspots`;
    }

    // Update Top Danger Zone Alert Banner
    const topAlertEl = document.getElementById('hotspot-top-alert');
    if(topAlertEl && topDangerHotspot){
      topAlertEl.style.display = 'block';
      const nameEl = document.getElementById('top-alert-name');
      const fatalEl = document.getElementById('top-alert-fatal');
      const descEl = document.getElementById('top-alert-desc');
      if(nameEl) nameEl.textContent = topDangerHotspot.name || topDangerHotspot.road_name;
      if(fatalEl) fatalEl.textContent = `${topDangerHotspot.fatal_accidents || topDangerHotspot.fatal_count || 0} Fatal`;
      if(descEl) descEl.textContent = `${topDangerHotspot.area} · Score: ${topDangerHotspot.danger_score}/100 · Primary Cause: ${topDangerHotspot.top_cause || topDangerHotspot.primary_cause}`;
    } else if(topAlertEl){
      topAlertEl.style.display = 'none';
    }

    // Render Stats
    renderHotspotStats(stats);

    // Apply tier filter to view
    renderFilteredHotspotView();

  } catch(err){
    console.error('Error loading hotspots:', err);
    showToast('error', 'Hotspot Error', 'Could not load live hotspot data from server.');
  }
}

function renderHotspotStats(stats){
  const el = document.getElementById('hotspot-stats');
  if(!el || !stats) return;

  const total = stats.total_hotspots || 0;
  const tiers = [
    { label: 'Critical Danger Zone', count: stats.very_high_count || 0, color: '#F04438' },
    { label: 'High Danger Zone',     count: stats.high_count || 0,      color: '#F79009' },
    { label: 'Moderate Risk Zone',   count: stats.moderate_count || 0,  color: '#EAB308' },
    { label: 'Low Risk Zone',        count: stats.low_count || 0,       color: '#17B26A' }
  ];

  let html = `
    <div class="flex justify-between items-center" style="padding:10px 0; border-bottom:1px solid var(--border); margin-bottom:4px;">
      <span style="font-size:12.5px; font-weight:700;">Total Monitored Hotspots</span>
      <span style="font-size:18px; font-weight:800; color:var(--text);">${total}</span>
    </div>
    <div class="flex justify-between items-center" style="padding:8px 0; border-bottom:1px solid var(--border); margin-bottom:6px;">
      <span style="font-size:12px; font-weight:600; color:var(--text-dim);">Total Collisions Recorded</span>
      <span style="font-size:13px; font-weight:700; color:var(--text);">${(stats.total_accidents || 0).toLocaleString()}</span>
    </div>
  `;

  html += tiers.map(t => `
    <div class="flex justify-between items-center" style="padding:8px 0; border-bottom:1px solid rgba(192,230,253,0.06);">
      <span class="flex items-center gap-8" style="font-size:12px; font-weight:600;">
        <span class="dot-status" style="background:${t.color}; width:8px; height:8px;"></span>
        ${t.label}
      </span>
      <span class="badge" style="background:${hexAlpha(t.color, 0.15)}; color:${t.color}; font-weight:800; font-size:12px;">
        ${t.count}
      </span>
    </div>
  `).join('');

  el.innerHTML = html;
}

function renderFilteredHotspotView(){
  let displayList = currentHotspots;
  if(activeTierFilter === 'veryhigh' || activeTierFilter === 'Critical'){
    displayList = currentHotspots.filter(h => h.tier === 'veryhigh' || h.tier === 'Critical' || h.tier_code === 'veryhigh');
  }

  renderHotspotMarkers(displayList);
  renderHotspotList(displayList);

  if(hotspotMapInstance) {
    setTimeout(() => hotspotMapInstance.invalidateSize(), 150);
  }
}

function renderHotspotMarkers(hotspots){
  if(!hotspotMapInstance || !hotspotMarkersLayer) return;
  hotspotMarkersLayer.clearLayers();
  activeMarkerMap = {};

  if(!hotspots || hotspots.length === 0){
    return;
  }

  const bounds = [];

  hotspots.forEach(loc => {
    const color = loc.color || '#F04438';
    bounds.push([loc.lat, loc.lng]);

    // 1. Semi-transparent danger zone halo circle indicating affected perimeter
    const circle = L.circle([loc.lat, loc.lng], {
      radius: loc.radius || 250,
      fillColor: color,
      fillOpacity: loc.tier === 'veryhigh' ? 0.28 : 0.18,
      color: color,
      weight: loc.tier === 'veryhigh' ? 2 : 1.2,
      opacity: 0.65
    }).addTo(hotspotMarkersLayer);

    // 2. High-contrast danger marker pin with glowing pulse for critical zones
    const isCritical = loc.tier === 'veryhigh';
    const pinHtml = `
      <div style="position:relative; width:28px; height:28px; display:flex; align-items:center; justify-content:center;">
        ${isCritical ? `<div class="danger-halo" style="position:absolute; width:44px; height:44px; background:${hexAlpha(color, 0.35)}; border:2px solid ${color};"></div>` : ''}
        <div style="width:24px; height:24px; border-radius:50%; background:${color}; border:2.5px solid #0d2240; box-shadow:0 2px 8px rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; color:#fff; font-size:11px; font-weight:800;">
          ${loc.id}
        </div>
      </div>
    `;

    const marker = L.marker([loc.lat, loc.lng], {
      icon: L.divIcon({
        className: '',
        html: pinHtml,
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      })
    }).addTo(hotspotMarkersLayer);

    // 3. Rich interactive popup with full collision intelligence
    const popupHtml = `
      <div style="font-family:'Inter',sans-serif; min-width:240px; color:#c0e6fd;">
        <div class="flex items-center justify-between gap-8" style="margin-bottom:6px;">
          <span class="badge" style="background:${hexAlpha(color, 0.18)}; color:${color}; font-weight:800; font-size:10.5px; border:1px solid ${hexAlpha(color, 0.35)};">
            ${loc.danger_level}
          </span>
          <span style="font-family:'JetBrains Mono',monospace; font-size:11.5px; font-weight:700; color:#fff;">
            Danger: ${loc.danger_score}/100
          </span>
        </div>
        <div style="font-weight:800; font-size:14px; color:#fff; margin-bottom:2px;">${loc.name}</div>
        <div style="font-size:11.5px; color:#80aad3; margin-bottom:10px;">Area: <b style="color:#c0e6fd;">${loc.area}</b> · Road: <b style="color:#c0e6fd;">${loc.road_type}</b></div>

        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; margin-bottom:10px; background:rgba(0,15,34,0.35); padding:8px; border-radius:8px; text-align:center;">
          <div>
            <div style="font-size:10px; color:#F04438; font-weight:700;">FATAL</div>
            <div style="font-size:14px; font-weight:800; color:#fff;">${loc.fatal_accidents}</div>
          </div>
          <div>
            <div style="font-size:10px; color:#F79009; font-weight:700;">MAJOR</div>
            <div style="font-size:14px; font-weight:800; color:#fff;">${loc.major_accidents}</div>
          </div>
          <div>
            <div style="font-size:10px; color:#80aad3; font-weight:700;">TOTAL</div>
            <div style="font-size:14px; font-weight:800; color:#fff;">${loc.total_accidents}</div>
          </div>
        </div>

        <div style="font-size:11px; color:#80aad3; margin-bottom:10px;">
          Primary Cause: <b style="color:#c0e6fd;">${loc.top_cause}</b>
        </div>

        <button onclick="focusHotspot(${loc.id})" style="width:100%; padding:6px 0; background:rgba(91,134,182,0.25); border:1px solid rgba(192,230,253,0.3); border-radius:6px; color:#c0e6fd; font-size:11px; font-weight:700; cursor:pointer;">
          Inspect Zone Perimeter
        </button>
      </div>
    `;

    marker.bindPopup(popupHtml);
    circle.bindPopup(popupHtml);

    activeMarkerMap[loc.id] = marker;
  });

  if(bounds.length > 0){
    hotspotMapInstance.fitBounds(bounds, { padding: [35, 35], maxZoom: 14 });
  }
}

function renderHotspotList(hotspots){
  const el = document.getElementById('hotspot-list');
  if(!el) return;

  if(!hotspots || hotspots.length === 0){
    el.innerHTML = '<div style="text-align:center; padding:24px 10px; color:var(--text-dim); font-size:12px;">No hotspots match the selected filters.</div>';
    return;
  }

  el.innerHTML = hotspots.slice(0, 20).map((h, i) => `
    <div class="hotspot-card-item flex items-center gap-10" id="hotspot-item-${h.id}" onclick="focusHotspot(${h.id})">
      <div style="width:26px; height:26px; border-radius:7px; background:${hexAlpha(h.color, 0.15)}; color:${h.color}; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:11px; flex-shrink:0;">
        ${i + 1}
      </div>
      <div style="flex:1; min-width:0;">
        <div style="font-size:12px; font-weight:700; color:var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
          ${h.name}
        </div>
        <div class="flex items-center gap-8" style="font-size:10.5px; color:var(--text-dim);">
          <span>${h.area}</span>
          <span>·</span>
          <span style="color:#F04438; font-weight:700;">${h.fatal_accidents} Fatal</span>
          <span>·</span>
          <span>${h.total_accidents} Total</span>
        </div>
      </div>
      <span class="badge" style="background:${hexAlpha(h.color, 0.14)}; color:${h.color}; font-size:9.5px; font-weight:700; flex-shrink:0;">
        ${h.tier === 'veryhigh' ? 'Critical' : h.tier === 'high' ? 'High' : 'Moderate'}
      </span>
    </div>
  `).join('');
}

function focusHotspot(id){
  const loc = currentHotspots.find(h => h.id === Number(id));
  if(!loc || !hotspotMapInstance) return;

  // Highlight list item
  document.querySelectorAll('.hotspot-card-item').forEach(el => el.classList.remove('active'));
  const activeEl = document.getElementById(`hotspot-item-${id}`);
  if(activeEl){
    activeEl.classList.add('active');
    activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // Smoothly fly to hotspot location on map
  hotspotMapInstance.flyTo([loc.lat, loc.lng], 15, {
    animate: true,
    duration: 1.2
  });

  // Open marker popup
  setTimeout(() => {
    const marker = activeMarkerMap[loc.id];
    if(marker){
      marker.openPopup();
    }
  }, 1250);
}

function focusTopDangerZone(){
  if(topDangerHotspot){
    focusHotspot(topDangerHotspot.id);
  }
}

function applyHotspotFilters(){
  const year = document.getElementById('hotspot-filter-year')?.value || '';
  const severity = document.getElementById('hotspot-filter-severity')?.value || '';
  const road_type = document.getElementById('hotspot-filter-road')?.value || '';
  const area = document.getElementById('hotspot-filter-area')?.value || '';

  loadHotspotsFromAPI({ year, severity, road_type, area });
  showToast('info', 'Filters Applied', 'Hotspot geospatial intelligence updated.');
}

function resetHotspotFilters(){
  const yearEl = document.getElementById('hotspot-filter-year');
  const sevEl = document.getElementById('hotspot-filter-severity');
  const roadEl = document.getElementById('hotspot-filter-road');
  const areaEl = document.getElementById('hotspot-filter-area');

  if(yearEl) yearEl.value = '';
  if(sevEl) sevEl.value = '';
  if(roadEl) roadEl.value = '';
  if(areaEl) areaEl.value = '';

  activeTierFilter = 'all';
  updateTierFilterButtons();

  loadHotspotsFromAPI();
  showToast('info', 'Filters Reset', 'Displaying all 57 monitored danger zones.');
}

function filterHotspotTiers(tier){
  activeTierFilter = tier;
  updateTierFilterButtons();
  renderFilteredHotspotView();
  if(tier === 'veryhigh'){
    showToast('info', 'Critical Zones', 'Displaying top critical danger zones (fatal incidents ≥ 60).');
  }
}

function updateTierFilterButtons(){
  const allBtn = document.getElementById('btn-filter-all');
  const critBtn = document.getElementById('btn-filter-critical');
  if(allBtn && critBtn){
    if(activeTierFilter === 'all'){
      allBtn.className = 'btn btn-sm btn-primary';
      critBtn.className = 'btn btn-sm btn-secondary';
      critBtn.style.color = '#F04438';
    } else {
      allBtn.className = 'btn btn-sm btn-secondary';
      critBtn.className = 'btn btn-sm btn-primary';
      critBtn.style.color = '#fff';
    }
  }
}

function resetHotspotMapView(){
  if(hotspotMapInstance && currentHotspots.length > 0){
    const bounds = currentHotspots.map(h => [h.lat, h.lng]);
    hotspotMapInstance.fitBounds(bounds, { padding: [35, 35], maxZoom: 14 });
    showToast('info', 'Map Centered', 'Zoomed to city-wide overview.');
  }
}

// Expose functions globally for HTML event handlers
window.initHotspotPage = initHotspotPage;
window.applyHotspotFilters = applyHotspotFilters;
window.resetHotspotFilters = resetHotspotFilters;
window.filterHotspotTiers = filterHotspotTiers;
window.resetHotspotMapView = resetHotspotMapView;
window.focusHotspot = focusHotspot;
window.focusTopDangerZone = focusTopDangerZone;

/* ================================================================
   TRAFFIC MANAGEMENT
   ================================================================ */
function initTrafficCharts(){
  mkChart('chart-traffic-density',{type:'line',data:{labels:['12AM','4AM','8AM','12PM','4PM','8PM'],datasets:[{data:[15,10,55,62,88,50],borderColor:'#2D7CFF',backgroundColor:'rgba(45,124,255,0.12)',fill:true,tension:.4,borderWidth:2.5,pointRadius:0}]},options:{responsive:true,maintainAspectRatio:false,scales:{y:{grid:gridOpt(),border:{display:false}},x:{grid:{display:false},border:{display:false}}}}});
  mkChart('chart-signal-timing',{type:'doughnut',data:{labels:['Phase 1 (N-S)','Phase 2 (E-W)','Phase 3 (NS-Left)','Phase 4 (EW-Left)'],datasets:[{data:[25,30,20,15],backgroundColor:['#17B26A','#F04438','#F79009','#2D7CFF'],borderWidth:3,borderColor:'#fff'}]},options:{responsive:true,maintainAspectRatio:false,cutout:'60%',plugins:{legend:{display:true,position:'bottom',labels:{boxWidth:8,boxHeight:8,usePointStyle:true,pointStyle:'circle',padding:8,font:{size:10}}}}}});
  mkChart('chart-congestion',{type:'bar',data:{labels:['Mon','Tue','Wed','Thu','Fri','Sat'],datasets:[{label:'Before',data:[68,72,65,70,75,60],backgroundColor:'#EEF1F7',borderRadius:5,maxBarThickness:14},{label:'After',data:[38,42,35,40,45,32],backgroundColor:'#2D7CFF',borderRadius:5,maxBarThickness:14}]},options:{responsive:true,maintainAspectRatio:false,scales:{y:{grid:gridOpt(),border:{display:false}},x:{grid:{display:false},border:{display:false}}},plugins:{legend:{display:true,position:'bottom',labels:{boxWidth:8,boxHeight:8,usePointStyle:true,pointStyle:'circle',font:{size:10.5,weight:'600'}}}}}});
  const evEl=document.getElementById('traffic-ev-table');
  if(evEl) evEl.innerHTML=[
    {id:'EV-102',type:'Ambulance',loc:'Edappally Toll Jn.',eta:'2 mins'},
    {id:'EV-103',type:'Fire Truck',loc:'MG Road Kadavanthra',eta:'4 mins'},
    {id:'EV-104',type:'Ambulance',loc:'Palarivattom Bypass',eta:'3 mins'},
    {id:'EV-105',type:'Police Escort',loc:'Vyttila Mobility Hub',eta:'6 mins'}
  ].map(r=>`<tr><td class="mono">${r.id}</td><td>${r.type}</td><td>${r.loc}</td><td>${r.eta}</td><td><span class="badge b-green"><span class="dot-status live"></span>Active</span></td></tr>`).join('');
  buildRoadSceneInto('traffic-detect-stage',trafficVehicles(),true);
}

/* ================================================================
   EMERGENCY PRIORITY
   ================================================================ */
async function initEmergencyPage(){
  const emEl=document.getElementById('emergency-table');
  const tlEl=document.getElementById('emergency-timeline');

  try {
    const res = await apiFetch('/api/emergency/events');
    if (res && res.success && res.events && res.events.length > 0) {
      if(emEl) {
        emEl.innerHTML = res.events.map(ev => `
          <tr>
            <td class="mono">EV-${ev.id || '901'}</td>
            <td>${ev.vehicle_type || 'Ambulance'}</td>
            <td>${ev.approach ? ev.approach + ' Approach' : 'Edappally Toll'}</td>
            <td>${ev.eta_seconds ? Math.round(ev.eta_seconds / 60) + ' min' : '2 min'}</td>
            <td><span class="badge b-green"><span class="dot-status live"></span>${ev.decision || 'Preempted'}</span></td>
          </tr>
        `).join('');
      }
      if(tlEl) {
        tlEl.innerHTML = res.events.slice(0, 5).map(ev => `
          <div class="tl-item">
            <div class="tl-dot" style="background:rgba(23,178,106,0.16);color:#17B26A;">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/></svg>
            </div>
            <div>
              <div class="tl-time">${ev.timestamp ? ev.timestamp.slice(11, 16) : 'Just Now'}</div>
              <div class="tl-text">Signal preempted for ${ev.vehicle_type} on ${ev.approach} Approach (${ev.decision})</div>
            </div>
          </div>
        `).join('');
      }
      buildRoadSceneInto('emergency-detect-stage',emergencyVehicles(),true);
      return;
    }
  } catch (e) {
    console.warn('Could not fetch emergency events, using live defaults', e);
  }

  if(emEl) emEl.innerHTML=[
    {v:'KL-07-AB-1234',type:'Ambulance',loc:'Edappally Toll Junction',eta:'1 min'},
    {v:'KL-07-CD-5678',type:'Fire Truck',loc:'Palarivattom Bypass',eta:'2 min'},
    {v:'KL-07-EF-9012',type:'Ambulance',loc:'Vyttila Mobility Hub',eta:'3 min'},
    {v:'KL-07-GH-3345',type:'Police',loc:'MG Road Kadavanthra',eta:'5 min'}
  ].map(r=>`<tr><td class="mono">${r.v}</td><td>${r.type}</td><td>${r.loc}</td><td>${r.eta}</td><td><span class="badge b-green"><span class="dot-status live"></span>Active</span></td></tr>`).join('');
  
  if(tlEl) tlEl.innerHTML=[
    {time:'05:28 PM',text:'Signal preempted at Edappally Toll Junction for Ambulance KL-07-AB-1234',color:'red'},
    {time:'05:22 PM',text:'Signal preempted at Palarivattom Bypass for Fire Truck KL-07-CD-5678',color:'orange'},
    {time:'05:15 PM',text:'Green corridor created for Ambulance KL-07-EF-9012 at Vyttila',color:'green'},
    {time:'05:04 PM',text:'Traffic diverted at MG Road Kadavanthra for Police escort',color:'blue'}
  ].map(i=>`<div class="tl-item"><div class="tl-dot" style="background:${hexAlpha(colorHex(i.color),0.16)};color:${colorHex(i.color)};"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/></svg></div><div><div class="tl-time">${i.time}</div><div class="tl-text">${i.text}</div></div></div>`).join('');
  buildRoadSceneInto('emergency-detect-stage',emergencyVehicles(),true);
}

/* ================================================================
   REPORTS
   ================================================================ */
async function initReportsCharts(){
  await Promise.all([
    loadReportsStats(),
    loadReportsTrends(),
    loadReportsTable()
  ]);
}
window.initReportsCharts = initReportsCharts;

async function loadReportsStats(){
  try {
    const stats = await apiFetch('/api/reports/stats');
    if(!stats) return;
    const tEl = document.getElementById('reports-stat-today');
    if(tEl) tEl.textContent = stats.today_reports !== undefined ? stats.today_reports : 0;
    const mEl = document.getElementById('reports-stat-month');
    if(mEl) mEl.textContent = stats.month_reports !== undefined ? stats.month_reports : 0;
    const dEl = document.getElementById('reports-stat-downloads');
    if(dEl) dEl.textContent = stats.total_downloads !== undefined ? stats.total_downloads : 0;
  } catch(e) {
    console.error('Failed to load report stats:', e);
  }
}
window.loadReportsStats = loadReportsStats;

async function loadReportsTrends(){
  try {
    const trends = await apiFetch('/api/reports/trends');
    if(!trends) return;

    // Accident Trends: 6-month summary
    if(trends.accident_trends && trends.accident_trends.labels){
      mkChart('chart-reports-accidents', {
        type: 'line',
        data: {
          labels: trends.accident_trends.labels,
          datasets: [{
            label: 'Accidents',
            data: trends.accident_trends.values,
            borderColor: '#2D7CFF',
            backgroundColor: 'rgba(45,124,255,0.12)',
            fill: true,
            tension: 0.35,
            borderWidth: 2.5,
            pointRadius: 4,
            pointBackgroundColor: '#2D7CFF'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: i => ` Accidents: ${i.raw.toLocaleString('en-IN')}` } }
          },
          scales: {
            y: { grid: gridOpt(), border: { display: false } },
            x: { grid: { display: false }, border: { display: false } }
          }
        }
      });
    }

    // Hotspot Trends: Risk zone evolution (top 5 areas)
    if(trends.hotspot_trends && trends.hotspot_trends.labels && trends.hotspot_trends.datasets){
      const datasets = trends.hotspot_trends.datasets.map(ds => ({
        label: ds.label,
        data: ds.data,
        backgroundColor: ds.backgroundColor,
        borderRadius: 4,
        maxBarThickness: 16
      }));

      mkChart('chart-reports-hotspots', {
        type: 'bar',
        data: {
          labels: trends.hotspot_trends.labels,
          datasets: datasets
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { grid: gridOpt(), border: { display: false }, stacked: true },
            x: { grid: { display: false }, border: { display: false }, stacked: true }
          },
          plugins: {
            legend: {
              display: true,
              position: 'bottom',
              labels: { boxWidth: 8, boxHeight: 8, usePointStyle: true, pointStyle: 'circle', font: { size: 10.5, weight: '600' } }
            }
          }
        }
      });
    }
  } catch(e) {
    console.error('Failed to load report trends:', e);
  }
}
window.loadReportsTrends = loadReportsTrends;

async function loadReportsTable(){
  const el = document.getElementById('reports-table');
  if(!el) return;
  try {
    const res = await apiFetch('/api/reports');
    if(!res || !res.reports || res.reports.length === 0){
      el.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:32px;color:#94a3b8;">No reports generated yet. Click "Generate New Report" to create an audit report.</td></tr>';
      return;
    }

    el.innerHTML = res.reports.map(r => {
      let format = 'PDF';
      if(r.type && r.type.includes('csv')) format = 'CSV';
      else if(r.file_path && r.file_path.endsWith('.csv')) format = 'CSV';
      else if(r.params_json){
        try { const p = JSON.parse(r.params_json); if(p.format === 'csv') format = 'CSV'; }catch(e){}
      }

      const sizeKb = r.file_size ? (r.file_size / 1024).toFixed(1) + ' KB' : '—';
      const dateStr = r.created_at ? r.created_at.slice(0, 16) : '—';
      const statusClass = (r.status || 'Ready').toLowerCase() === 'ready' ? 'b-green' : 'b-orange';

      return `
        <tr>
          <td style="font-weight:700;color:#ffffff;">${escapeHtml(r.name || 'Safety Report')}</td>
          <td><span class="badge ${format === 'PDF' ? 'b-purple' : 'b-blue'}">${format}</span></td>
          <td>${escapeHtml(r.generated_by || 'Admin')}</td>
          <td class="text-faint">${dateStr}</td>
          <td class="mono">${sizeKb}</td>
          <td>${r.download_count || 0}</td>
          <td><span class="badge ${statusClass}">${escapeHtml(r.status || 'Ready')}</span></td>
          <td>
            <div class="table-actions">
              <button class="icon-btn-sm" onclick="previewReport(${r.id})" title="Preview in browser">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
              <button class="icon-btn-sm" onclick="downloadReport(${r.id})" title="Download">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M12 18v-6M9 15l3 3 3-3"/></svg>
              </button>
              <button class="icon-btn-sm" onclick="deleteReport(${r.id})" title="Delete" style="color:#f87171;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  } catch(e) {
    console.error('Failed to load reports table:', e);
    el.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:24px;color:#f87171;">Failed to load reports. <button class="btn btn-secondary btn-sm" onclick="loadReportsTable()">Retry</button></td></tr>';
  }
}
window.loadReportsTable = loadReportsTable;

function openReportModal(){
  const f = document.getElementById('report-gen-form');
  if(f) f.reset();
  const now = new Date();
  const dTo = now.toISOString().slice(0, 10);
  const dFrom = new Date(now.getFullYear(), 0, 1).toISOString().slice(0, 10);
  const fromEl = document.getElementById('rep-gen-date-from');
  const toEl = document.getElementById('rep-gen-date-to');
  if(fromEl && !fromEl.value) fromEl.value = dFrom;
  if(toEl && !toEl.value) toEl.value = dTo;
  openModal('report-generate-modal');
}
window.openReportModal = openReportModal;

async function submitGenerateReport(e){
  e.preventDefault();
  const btn = document.getElementById('rep-gen-submit-btn');
  const origHtml = btn ? btn.innerHTML : '';
  if(btn){
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Generating...';
  }

  const payload = {
    type: document.getElementById('rep-gen-type')?.value || 'monthly_summary',
    date_from: document.getElementById('rep-gen-date-from')?.value || '',
    date_to: document.getElementById('rep-gen-date-to')?.value || '',
    area: document.getElementById('rep-gen-area')?.value || '',
    format: document.getElementById('rep-gen-format')?.value || 'pdf'
  };

  try {
    const res = await fetch('/api/reports/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if(res.ok && data.success){
      showToast('success', 'Report Generated', data.report?.name || 'Report successfully created.');
      closeModal('report-generate-modal');
      await Promise.all([loadReportsStats(), loadReportsTable()]);
    } else {
      showToast('error', 'Generation Failed', data.error || 'Server could not generate report');
    }
  } catch(err){
    console.error('Error generating report:', err);
    showToast('error', 'Network Error', 'Could not reach server to generate report');
  } finally {
    if(btn){
      btn.disabled = false;
      btn.innerHTML = origHtml;
    }
  }
}
window.submitGenerateReport = submitGenerateReport;

async function previewReport(id){
  try {
    const res = await apiFetch(`/api/reports/${id}/preview`);
    if(res && res.html){
      const titleEl = document.getElementById('preview-modal-title');
      const bodyEl = document.getElementById('preview-modal-body');
      if(titleEl) titleEl.textContent = res.report_name || 'Report Preview';
      if(bodyEl) bodyEl.innerHTML = res.html;
      openModal('report-preview-modal');
    } else {
      showToast('error', 'Preview Error', res?.error || 'Could not load preview');
    }
  } catch(e){
    console.error('Preview error:', e);
    showToast('error', 'Error', 'Failed to preview report');
  }
}
window.previewReport = previewReport;

function downloadReport(id){
  window.open(`/api/reports/${id}/download`, '_blank');
  setTimeout(() => {
    loadReportsStats();
    loadReportsTable();
  }, 1200);
}
window.downloadReport = downloadReport;

async function deleteReport(id){
  if(!confirm('Are you sure you want to delete this report? This cannot be undone.')) return;
  try {
    const res = await fetch(`/api/reports/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if(res.ok && data.success){
      showToast('success', 'Deleted', 'Report removed successfully.');
      await Promise.all([loadReportsStats(), loadReportsTable()]);
    } else {
      showToast('error', 'Delete Failed', data.error || 'Could not delete report');
    }
  } catch(e){
    console.error('Delete error:', e);
    showToast('error', 'Error', 'Failed to delete report');
  }
}
window.deleteReport = deleteReport;


/* ================================================================
   ROAD SCENE — YOLOv8 illustration
   ================================================================ */
function trafficVehicles(){ return [{label:'Car',color:'#17B26A',conf:0.94,top:58,left:20,w:13,h:10},{label:'Bus',color:'#2D7CFF',conf:0.91,top:52,left:58,w:16,h:12},{label:'Truck',color:'#F79009',conf:0.88,top:40,left:44,w:10,h:8},{label:'Bike',color:'#F04438',conf:0.85,top:66,left:70,w:7,h:6},{label:'Car',color:'#17B26A',conf:0.90,top:34,left:48,w:7,h:5.5}]; }
function yoloVehicles(){ return [{label:'Car',color:'#17B26A',conf:0.96,top:60,left:10,w:14,h:11},{label:'Car',color:'#17B26A',conf:0.93,top:62,left:76,w:13,h:10},{label:'Bus',color:'#2D7CFF',conf:0.91,top:48,left:38,w:17,h:13},{label:'Truck',color:'#F79009',conf:0.89,top:38,left:56,w:11,h:9},{label:'Bike',color:'#F04438',conf:0.83,top:70,left:32,w:6.5,h:5.5},{label:'Bike',color:'#F04438',conf:0.81,top:68,left:60,w:6.5,h:5.5},{label:'Auto',color:'#EAB308',conf:0.87,top:56,left:52,w:9,h:7.5},{label:'Car',color:'#17B26A',conf:0.90,top:32,left:46,w:7,h:5.5},{label:'Truck',color:'#F79009',conf:0.85,top:44,left:20,w:9,h:7}]; }
function emergencyVehicles(){ return [{label:'Ambulance',color:'#17B26A',conf:0.97,top:44,left:36,w:22,h:17,thick:true},{label:'Car',color:'#17B26A',conf:0.88,top:66,left:14,w:11,h:9},{label:'Bike',color:'#F04438',conf:0.82,top:70,left:70,w:6.5,h:5.5}]; }
function roadSceneMarkup(vehicles){
  let html=`<div class="road-glow"></div><div class="road-surface"></div><div class="road-lane l1"></div><div class="road-lane l2"></div><div class="road-lane l3"></div>`;
  vehicles.forEach(v=>{
    html+=`<div class="bbox" style="top:${v.top}%;left:${v.left}%;width:${v.w}%;height:${v.h}%;border-color:${v.color};${v.thick?'border-width:3px;box-shadow:0 0 0 3px '+hexAlpha(v.color,0.25)+';':''}"><div class="bbox-tag" style="background:${v.color};">${v.label} ${v.conf.toFixed(2)}</div><div class="veh-glyph" style="background:${hexAlpha(v.color,0.85)};"></div></div>`;
  });
  return html;
}
function buildRoadSceneInto(containerId, vehicles, keepLiveBadge){
  const el=document.getElementById(containerId);
  if(!el||el.dataset.built) return;
  el.dataset.built='1';
  const lb=keepLiveBadge?el.querySelector('.live-badge').outerHTML:'';
  el.innerHTML=lb+roadSceneMarkup(vehicles);
}

/* ================================================================
   YOLO VEHICLE DETECTION & COUNT (Robust Async Jobs + ByteTrack)
   ================================================================ */

let _yoloFile = null;
let _currentYoloJobId = null;
let _yoloPollTimer = null;

async function initYoloCharts(){
  // Fetch real model info dynamically from backend
  try {
    const info = await apiFetch('/api/yolo/info');
    if(info){
      const badgeText = document.getElementById('yolo-model-badge-text');
      if(badgeText) badgeText.textContent = `${info.model_name || 'YOLOv8s'} · ${info.weights_loaded ? 'Online' : 'Standby'}`;
      const infoModel = document.getElementById('yolo-info-model');
      if(infoModel) infoModel.textContent = info.model_name || 'YOLOv8s (Enhanced)';
      const infoDevice = document.getElementById('yolo-info-device');
      if(infoDevice) infoDevice.textContent = info.device || 'CPU';
      const infoTracker = document.getElementById('yolo-info-tracker');
      if(infoTracker) infoTracker.textContent = info.tracker || 'ByteTrack Multi-Object';
      const infoClasses = document.getElementById('yolo-info-classes');
      if(infoClasses && info.classes) infoClasses.textContent = info.classes.join(', ');
      const infoStatus = document.getElementById('yolo-info-status');
      if(infoStatus){
        infoStatus.innerHTML = info.weights_loaded
          ? '<span class="dot-status live"></span>Online'
          : '<span class="dot-status"></span>Standby';
      }
    }
  } catch(e){
    console.warn('[YOLO Info Error]', e);
  }
}
window.initYoloCharts = initYoloCharts;

function onYoloFileSelected(input){
  const file = input.files && input.files[0];
  if(!file) return;
  setYoloFile(file);
}
window.onYoloFileSelected = onYoloFileSelected;

function handleYoloDrop(e){
  e.preventDefault();
  const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
  if(!file) return;
  setYoloFile(file);
}
window.handleYoloDrop = handleYoloDrop;

function setYoloFile(file){
  // Client-side validation: 200 MB maximum
  const maxBytes = 200 * 1024 * 1024;
  if(file.size > maxBytes){
    showToast('error', 'File Too Large', `Selected file is ${(file.size / (1024 * 1024)).toFixed(1)} MB. Maximum allowed is 200 MB.`);
    return;
  }
  _yoloFile = file;
  const nameEl = document.getElementById('yolo-file-name');
  if(nameEl) nameEl.textContent = `${file.name} (${(file.size / (1024 * 1024)).toFixed(1)} MB)`;
  const btn = document.getElementById('yolo-detect-btn');
  if(btn) btn.disabled = false;
  const dlBtn = document.getElementById('yolo-download-btn');
  if(dlBtn) dlBtn.style.display = 'none';

  // Reset any error box
  const errWrap = document.getElementById('yolo-error-wrap');
  if(errWrap) errWrap.style.display = 'none';
  const statusEl = document.getElementById('yolo-kpi-status');
  if(statusEl){ statusEl.textContent = 'Ready'; statusEl.style.color = 'var(--green)'; }

  // Update empty state text
  const stageTitle = document.getElementById('yolo-stage-title');
  if(stageTitle) stageTitle.textContent = `${file.name} Selected`;
  const stageSub = document.getElementById('yolo-stage-sub');
  if(stageSub) stageSub.textContent = `Click "Run YOLOv8 Detection" to process with YOLOv8s + ByteTrack`;

  showToast('info', 'File Selected', `${file.name} is ready for detection.`);
}

async function runYoloDetection(){
  if(!_yoloFile){
    showToast('error', 'No file', 'Please select a traffic video or image first.');
    return;
  }

  const btn     = document.getElementById('yolo-detect-btn');
  const btnText = document.getElementById('yolo-detect-btn-text');
  const spinner = document.getElementById('yolo-spinner');
  btn.disabled  = true;
  btnText.textContent = 'Uploading…';
  spinner.style.display = 'inline-block';

  const dlBtn = document.getElementById('yolo-download-btn');
  if(dlBtn) dlBtn.style.display = 'none';

  const statusEl = document.getElementById('yolo-kpi-status');
  if(statusEl){ statusEl.textContent = 'Uploading…'; statusEl.style.color = 'var(--blue)'; }

  const errWrap = document.getElementById('yolo-error-wrap');
  if(errWrap) errWrap.style.display = 'none';

  const progWrap = document.getElementById('yolo-progress-wrap');
  const progBar  = document.getElementById('yolo-progress-bar');
  const progPct  = document.getElementById('yolo-progress-pct');
  const progLbl  = document.getElementById('yolo-progress-label');
  const progDet  = document.getElementById('yolo-progress-detail');
  if(progWrap){
    progWrap.style.display = 'block';
    progBar.style.width = '0%';
    progPct.textContent = '0%';
    progLbl.textContent = 'Uploading media to server...';
    progDet.textContent = 'Starting upload stream';
  }

  try {
    const formData = new FormData();
    formData.append('video', _yoloFile);
    const confSlider = document.getElementById('yolo-conf-slider');
    const confVal = confSlider ? parseFloat(confSlider.value).toFixed(2) : '0.35';
    formData.append('conf', confVal);

    // Upload with progress tracking via apiUpload or XMLHttpRequest
    let uploadResp;
    if(window.apiUpload){
      uploadResp = await window.apiUpload('/api/yolo/detect', formData, (pct) => {
        if(progBar) progBar.style.width = Math.min(pct, 100) + '%';
        if(progPct) progPct.textContent = Math.round(pct) + '%';
        if(progDet) progDet.textContent = `Uploaded ${Math.round(pct)}% of ${_yoloFile.name}`;
      });
    } else {
      const res = await fetch('/api/yolo/detect', { method: 'POST', body: formData });
      uploadResp = await res.json();
    }

    if(!uploadResp || !uploadResp.success){
      throw new Error((uploadResp && uploadResp.error) || 'Upload failed');
    }

    const jobId = uploadResp.job_id;
    _currentYoloJobId = jobId;

    btnText.textContent = 'Processing…';
    if(statusEl){ statusEl.textContent = 'Processing…'; statusEl.style.color = 'var(--orange)'; }
    if(progLbl) progLbl.textContent = 'YOLOv8 + ByteTrack analysis in progress...';

    // Poll status until completion
    await pollYoloJob(jobId);

  } catch(err){
    console.error('[YOLO Detect Error]', err);
    if(statusEl){ statusEl.textContent = 'Error'; statusEl.style.color = 'var(--red)'; }
    if(progWrap) progWrap.style.display = 'none';
    if(errWrap){
      errWrap.style.display = 'block';
      const msgEl = document.getElementById('yolo-error-msg');
      if(msgEl) msgEl.textContent = err.message || 'Detection failed. Please check server logs.';
    }
    showToast('error', 'Detection Failed', err.message || 'Unexpected server response');
  } finally {
    btn.disabled = false;
    btnText.textContent = 'Run YOLOv8 Detection';
    spinner.style.display = 'none';
  }
}
window.runYoloDetection = runYoloDetection;

function retryYoloDetection(){
  const errWrap = document.getElementById('yolo-error-wrap');
  if(errWrap) errWrap.style.display = 'none';
  runYoloDetection();
}
window.retryYoloDetection = retryYoloDetection;

async function cancelYoloDetection(){
  if(_yoloPollTimer) clearTimeout(_yoloPollTimer);
  if(_currentYoloJobId){
    try {
      await fetch(`/api/yolo/job/${_currentYoloJobId}`, { method: 'DELETE' });
    } catch(e){}
    _currentYoloJobId = null;
  }
  const progWrap = document.getElementById('yolo-progress-wrap');
  if(progWrap) progWrap.style.display = 'none';
  const statusEl = document.getElementById('yolo-kpi-status');
  if(statusEl){ statusEl.textContent = 'Ready'; statusEl.style.color = 'var(--green)'; }
  const btn = document.getElementById('yolo-detect-btn');
  const btnText = document.getElementById('yolo-detect-btn-text');
  const spinner = document.getElementById('yolo-spinner');
  if(btn) btn.disabled = false;
  if(btnText) btnText.textContent = 'Run YOLOv8 Detection';
  if(spinner) spinner.style.display = 'none';
  showToast('info', 'Detection Cancelled', 'Detection job was cancelled.');
}
window.cancelYoloDetection = cancelYoloDetection;

async function pollYoloJob(jobId){
  return new Promise((resolve, reject) => {
    async function check(){
      try {
        const stat = await apiFetch(`/api/yolo/status/${jobId}`);
        if(!stat){
          _yoloPollTimer = setTimeout(check, 1000);
          return;
        }

        const progBar = document.getElementById('yolo-progress-bar');
        const progPct = document.getElementById('yolo-progress-pct');
        const progLbl = document.getElementById('yolo-progress-label');
        const progDet = document.getElementById('yolo-progress-detail');

        const pct = stat.progress || 0;
        if(progBar) progBar.style.width = pct + '%';
        if(progPct) progPct.textContent = pct + '%';
        if(progLbl) progLbl.textContent = stat.state === 'running'
          ? `Processing frame ${stat.frames_done || 0} / ${stat.frames_total || '?'}`
          : (stat.state === 'queued' ? 'Job queued in background...' : 'Finalizing output...');
        if(progDet){
          progDet.textContent = stat.eta_s !== undefined
            ? `Estimated time remaining: ${Math.round(stat.eta_s)}s`
            : `State: ${stat.state}`;
        }

        const sState = (stat.state || '').toLowerCase();
        if(sState === 'completed' || sState === 'done'){
          const pWrap = document.getElementById('yolo-progress-wrap');
          if(pWrap) pWrap.style.display = 'none';
          await handleYoloJobComplete(jobId);
          resolve();
        } else if(sState === 'failed' || sState === 'error' || sState === 'cancelled'){
          const pWrap = document.getElementById('yolo-progress-wrap');
          if(pWrap) pWrap.style.display = 'none';
          reject(new Error(stat.error || 'YOLO worker processing failed'));
        } else {
          _yoloPollTimer = setTimeout(check, 1000);
        }
      } catch(e){
        reject(e);
      }
    }
    check();
  });
}

async function handleYoloJobComplete(jobId){
  const data = await apiFetch(`/api/yolo/result/${jobId}`);
  if(!data) throw new Error('Could not retrieve detection results');

  const statusEl = document.getElementById('yolo-kpi-status');
  if(statusEl){ statusEl.textContent = 'Done ✓'; statusEl.style.color = 'var(--green)'; }

  // ── Show Annotated Result Output ─────────────────────────
  const frameWrap = document.getElementById('yolo-frame-wrap');
  const stageWrap = document.getElementById('yolo-detect-stage');
  const videoEl   = document.getElementById('yolo-annotated-video');
  const imgEl     = document.getElementById('yolo-annotated-img');
  const liveBadge = document.getElementById('yolo-live-badge');
  const dlBtn     = document.getElementById('yolo-download-btn');

  if(data.is_image){
    if(imgEl){
      imgEl.src = data.annotated_frame ? 'data:image/jpeg;base64,' + data.annotated_frame : `/api/yolo/thumbnail/${jobId}`;
      imgEl.style.display = 'block';
    }
    if(videoEl) videoEl.style.display = 'none';
  } else {
    if(videoEl){
      videoEl.src = `/api/yolo/video/${jobId}`;
      videoEl.style.display = 'block';
      videoEl.load();
    }
    if(imgEl) imgEl.style.display = 'none';
  }

  if(frameWrap) frameWrap.style.display = 'block';
  if(stageWrap) stageWrap.style.display = 'none';
  if(liveBadge) liveBadge.style.display = '';

  if(dlBtn){
    dlBtn.href = `/api/yolo/video/${jobId}?download=1`;
    dlBtn.setAttribute('download', data.is_image ? 'annotated_traffic.jpg' : 'annotated_traffic.mp4');
    dlBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Download Annotated ${data.is_image ? 'Image' : 'H.264 Video'}`;
    dlBtn.style.display = 'flex';
  }

  // ── KPI Cards ────────────────────────────────────────────
  const totalVehicles = data.line_crossed_total !== undefined ? data.line_crossed_total : (data.total || 0);
  const totalEl = document.getElementById('yolo-kpi-total');
  if(totalEl){
    totalEl.dataset.count = totalVehicles;
    totalEl.dataset.done = '';
    totalEl.textContent = totalVehicles.toLocaleString('en-IN');
  }
  const totalLbl = document.getElementById('yolo-kpi-total-label');
  if(totalLbl){
    totalLbl.textContent = data.is_image ? 'Total Vehicles' : `Total Vehicles (Tripwire · ${data.unique_tracks || totalVehicles} unique)`;
  }

  const densityEl = document.getElementById('yolo-kpi-density');
  const dColors = { High: 'var(--red)', Medium: 'var(--orange)', Low: 'var(--green)' };
  if(densityEl){
    densityEl.textContent = data.density || 'Low';
    densityEl.style.color = dColors[data.density] || 'var(--text)';
  }

  const framesEl = document.getElementById('yolo-kpi-frames');
  if(framesEl){
    framesEl.textContent = `${data.total_frames_sampled || data.frames_analysed || 0} / ${data.video_total_frames || '—'}`;
  }

  // ── Vehicle Count Breakdown ──────────────────────────────
  const VCOL = { Car: '#17B26A', Bus: '#2D7CFF', Truck: '#F79009', Motorcycle: '#F04438', Bicycle: '#EAB308' };
  const counts = data.all_counts || {};
  const inOut = data.line_crossing_in_out || {};
  const totalCount = Object.values(counts).reduce((a, b) => a + b, 0);
  const summaryEl = document.getElementById('yolo-summary');
  if(summaryEl){
    if(totalCount > 0){
      summaryEl.innerHTML = Object.entries(counts).map(([label, count]) => {
        const pct   = totalCount > 0 ? Math.round((count / totalCount) * 100) : 0;
        const color = VCOL[label] || '#5B6B8C';
        const io = inOut[label] ? ` (${inOut[label].in || 0} IN / ${inOut[label].out || 0} OUT)` : '';
        return `<div style="margin-bottom:12px;">
          <div class="flex justify-between items-center" style="font-size:12px;font-weight:700;margin-bottom:6px;">
            <span class="flex items-center gap-8"><span class="legend-swatch" style="background:${color};"></span>${label}${io}</span>
            <span class="text-dim">${count} · ${pct}%</span>
          </div>
          <div class="pbar-track" style="margin-bottom:0;height:6px;">
            <div class="pbar-fill" style="background:${color};width:${pct}%;"></div>
          </div></div>`;
      }).join('');
      const sepEl   = document.getElementById('yolo-total-sep');
      const totRow  = document.getElementById('yolo-total-row');
      const totDisp = document.getElementById('yolo-total-display');
      if(sepEl)   sepEl.style.display  = '';
      if(totRow)  totRow.style.removeProperty('display');
      if(totDisp) totDisp.textContent  = `${totalVehicles} vehicles crossed tripwire`;
    } else {
      summaryEl.innerHTML = '<div class="text-dim" style="font-size:12px;text-align:center;padding:20px 0;">No vehicles detected in footage.</div>';
    }
  }

  // ── Priority Decision Card ───────────────────────────────
  renderYoloPriorityCard(data);

  // ── Per-Frame / Per-Second Detection Trend Chart ─────────
  if(data.frame_results && data.frame_results.length){
    const ex = CHART_REGISTRY['chart-yolo-trend'];
    if(ex){
      ex.data.labels = data.frame_labels;
      ex.data.datasets[0].data  = data.frame_results;
      ex.data.datasets[0].label = 'Vehicles detected';
      ex.update();
    } else {
      mkChart('chart-yolo-trend', {
        type: 'line',
        data: {
          labels: data.frame_labels,
          datasets: [{
            label: 'Vehicles detected',
            data: data.frame_results,
            borderColor: '#2D7CFF',
            backgroundColor: 'rgba(45,124,255,0.10)',
            fill: true,
            tension: 0.35,
            borderWidth: 2,
            pointRadius: 2,
            pointBackgroundColor: '#2D7CFF'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            tooltip: {
              callbacks: {
                label: i => `  Vehicles in frame: ${i.raw}`
              }
            }
          },
          scales: {
            y: { min: 0, grid: { color: 'rgba(255,255,255,0.06)' }, ticks: { color: '#94a3b8' } },
            x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
          }
        }
      });
    }
  }

  showToast('success', 'Detection Complete', `${totalVehicles} vehicles counted · Traffic density: ${data.density || 'Low'}`);
}
window.handleYoloJobComplete = handleYoloJobComplete;

function renderYoloPriorityCard(data){
  const el = document.getElementById('yolo-priority-output');
  if(!el) return;
  const counts = data.all_counts || {};
  const total  = data.total || 0;
  const busCount   = counts['Bus']   || 0;
  const truckCount = counts['Truck'] || 0;
  let priority = 'NORMAL — Standard Flow';
  let prColor  = 'green';
  let prDesc   = 'Traffic flow is normal. No special signal priority needed.';
  let action   = 'Maintain standard signal cycle.';
  if(data.emergency_detected || busCount >= 3){
    priority = 'HIGH — Heavy Vehicle Priority';
    prColor  = 'red';
    prDesc   = `${busCount} buses · ${truckCount} trucks detected in corridor.`;
    action   = 'Extend green phase +25 sec for heavy vehicle lane.';
  } else if(data.density === 'High'){
    priority = 'MEDIUM — Congestion Alert';
    prColor  = 'orange';
    prDesc   = `High vehicle density (${total} total). Congestion likely.`;
    action   = 'Adaptive signal extension + traffic warden alert.';
  } else if(data.density === 'Medium'){
    priority = 'LOW — Moderate Traffic';
    prColor  = 'blue';
    prDesc   = `Moderate traffic detected (${total} total).`;
    action   = 'Standard adaptive signal timing.';
  }
  el.innerHTML = `
    <div style="margin-bottom:12px;">
      <span class="badge b-${prColor}" style="font-size:11.5px;padding:5px 12px;">${priority}</span>
    </div>
    <div class="text-dim" style="font-size:12px;line-height:1.6;margin-bottom:12px;">${prDesc}</div>
    <div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:10px 14px;font-size:12px;">
      <span style="font-weight:700;">Recommended Action:</span>
      <span class="text-dim" style="margin-left:6px;">${action}</span>
    </div>
    <div style="margin-top:14px;padding-top:14px;border-top:1px solid var(--border);">
      ${Object.entries(counts).map(([lbl,cnt])=>`
        <div class="flex justify-between" style="font-size:12px;padding:3px 0;">
          <span class="text-dim font-600">${lbl}</span><span style="font-weight:700;">${cnt}</span>
        </div>`).join('')}
      <div class="flex justify-between" style="font-size:12px;padding:6px 0 0;border-top:1px solid var(--border);margin-top:4px;">
        <span style="font-weight:800;">Total</span>
        <span style="font-weight:800;color:var(--primary);">${total}</span>
      </div>
    </div>`;
}
window.renderYoloPriorityCard = renderYoloPriorityCard;

/* ================================================================
   PAGE INIT DISPATCHER
   ================================================================ */

const PAGE_INIT_DONE = {};
function initPageContent(pageId){
  if(PAGE_INIT_DONE[pageId]){
    if(pageId==='hotspot' && hotspotMapInstance) setTimeout(()=>hotspotMapInstance.invalidateSize(),150);
    return;
  }
  PAGE_INIT_DONE[pageId] = true;
  switch(pageId){
    case 'dashboard': initDashboardCharts();  break;
    case 'analytics': initAnalyticsCharts();  break;
    case 'risk':      initRiskCharts();        break;
    case 'hotspot':   initHotspotPage();       break;
    case 'traffic':   initTrafficCharts();     break;
    case 'yolo':      initYoloCharts();        break;
    case 'emergency': initEmergencyPage();     break;
    case 'reports':   initReportsCharts();     break;
    case 'data':      initDataPage();          break;
    case 'settings':  initSettingsPage();      break;
  }
}

/* ================================================================
   ONE-TIME APP BOOTSTRAP
   ================================================================ */
let appBooted = false;
function initAppOnce(){ appBooted = true; }

window.addEventListener('resize', function(){
  if(window.innerWidth > 1024){
    document.getElementById('sidebar').classList.remove('mobile-open');
    document.getElementById('sidebar-overlay').classList.remove('active');
  }
});

// Restore login session if available
restoreUserSession();
