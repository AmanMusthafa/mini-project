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
  setTimeout(remove, 4200);
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
      currentUser = {username:result.username, name:result.name||'Admin', role:result.role||'Admin', email:result.email||'', department:result.department||''};
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
      showToast('error', 'Login Failed', result.message);
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
  document.getElementById('sidebar-overlay').classList.remove('active');
  requestAnimationFrame(()=>initPageContent(pageId));
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

const profileWrap = document.getElementById('profile-btn').closest('.profile-menu-wrap');
document.getElementById('profile-btn').addEventListener('click', function(e){
  e.stopPropagation();
  profileWrap.classList.toggle('open');
});
document.addEventListener('click', function(e){
  if(profileWrap.classList.contains('open') && !profileWrap.contains(e.target))
    profileWrap.classList.remove('open');
});
document.getElementById('profile-view-btn').addEventListener('click', function(){
  profileWrap.classList.remove('open');
  showToast('info','Profile', `${currentUser.name} · ${currentUser.role||'Admin'}`);
});
document.getElementById('profile-logout-btn').addEventListener('click', function(){
  profileWrap.classList.remove('open');
  document.getElementById('logout-btn').click();
});
document.getElementById('notif-btn').addEventListener('click', function(){
  showToast('info','3 new alerts','High risk at Ayyanthole junction · 2 emergency vehicles dispatched.');
});

function setDarkTheme(on){
  document.body.classList.toggle('dark-theme', on);
  const t = document.getElementById('dark-mode-toggle');
  if(t) t.checked = on;
}
document.getElementById('theme-btn').addEventListener('click', function(){
  setDarkTheme(!document.body.classList.contains('dark-theme'));
  showToast('info','Theme updated', document.body.classList.contains('dark-theme') ? 'Dark mode enabled.' : 'Light mode enabled.');
});

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
   API HELPER
   ================================================================ */
async function apiFetch(endpoint){
  try {
    const r = await fetch(endpoint);
    if(!r.ok) throw new Error('HTTP '+r.status);
    return await r.json();
  } catch(e){
    console.error('API error:', endpoint, e.message);
    return null;
  }
}

/* ================================================================
   INDIA ACCIDENT DENSITY MAP — Chart.js bubble chart
   (no internet needed, no Leaflet tiles, always renders)
   ================================================================ */
let dashMapBuilt = false;

function buildDashMap(areaData){
  const container = document.getElementById('dash-map');
  if(!container || dashMapBuilt) return;
  dashMapBuilt = true;

  Object.assign(container.style, {
    background:'linear-gradient(135deg,#0B1526 0%,#0D2040 100%)',
    position:'relative', overflow:'hidden', borderRadius:'12px'
  });

  if(!areaData || !areaData.labels) return;

  const palette  = ['#F04438','#F79009','#9E77ED','#2D7CFF','#17B26A','#06AED4','#EAB308'];
  const maxCount = Math.max(...areaData.values, 1);

  // Kochi bounding box: lng 76.22–76.36, lat 9.94–10.05
  // Map to percentage: x = (lng-76.22)/(76.36-76.22)*90+5, y = (10.05-lat)/(10.05-9.94)*80+5
  function toPercent(lat, lng){
    const x = Math.round((lng - 76.22) / (76.36 - 76.22) * 84 + 6);
    const y = Math.round((10.05 - lat) / (10.05 - 9.94) * 76 + 8);
    return {x, y};
  }

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" style="position:absolute;top:0;left:0;z-index:2;">`;
  // Grid lines
  for(let i=1;i<5;i++){
    svg += `<line x1="${i*20}%" y1="0" x2="${i*20}%" y2="100%" stroke="rgba(45,124,255,0.07)" stroke-width="1"/>`;
    svg += `<line x1="0" y1="${i*20}%" x2="100%" y2="${i*20}%" stroke="rgba(45,124,255,0.07)" stroke-width="1"/>`;
  }

  areaData.labels.forEach((area, i)=>{
    const geo   = KOCHI_AREA_GEO[area];
    if(!geo) return;
    const pos   = toPercent(geo.lat, geo.lng);
    const color = palette[i % palette.length];
    const count = areaData.values[i] || 0;
    const r     = 14 + Math.round((count / maxCount) * 24); // 14–38px
    // Glow
    svg += `<circle cx="${pos.x}%" cy="${pos.y}%" r="${r*1.7}" fill="${hexAlpha(color,0.13)}"/>`;
    // Main bubble
    svg += `<circle cx="${pos.x}%" cy="${pos.y}%" r="${r}" fill="${hexAlpha(color,0.58)}" stroke="${color}" stroke-width="2"><title>${area}: ${count.toLocaleString('en-IN')} records</title></circle>`;
    // Area label
    svg += `<text x="${pos.x}%" y="${pos.y-r/20-1.5}%" text-anchor="middle" fill="white" font-size="9.5" font-family="Inter,sans-serif" font-weight="700" style="pointer-events:none;">${area}</text>`;
    // Count
    svg += `<text x="${pos.x}%" y="${pos.y+r/20+2.5}%" text-anchor="middle" fill="rgba(255,255,255,0.75)" font-size="8" font-family="Inter,sans-serif" style="pointer-events:none;">${count >= 1000 ? (count/1000).toFixed(1)+'k' : count}</text>`;
  });
  svg += `</svg>`;

  const title = document.createElement('div');
  title.style.cssText = 'position:absolute;top:10px;left:12px;color:rgba(255,255,255,0.35);font-size:10px;font-weight:700;font-family:Inter,sans-serif;letter-spacing:0.08em;z-index:3;pointer-events:none;';
  title.textContent = 'KOCHI · ACCIDENT HOTSPOT MAP · 2022–2026';
  container.appendChild(title);
  container.insertAdjacentHTML('beforeend', svg);
}

/* ================================================================
   DASHBOARD — initDashboardCharts(year)
   year = '' → All 2022-2026 (5-line trend comparison)
   year = '2022' … '2026' → Filter everything
   ================================================================ */
async function initDashboardCharts(year=''){
  const q  = year ? ('?year='+year) : '';
  const q2 = year ? ('&year='+year) : '';

  // Fetch in parallel: filtered stats + trend + causes + state + recent
  const [stats, trendData, byCause, byArea, recent] = await Promise.all([
    apiFetch('/api/dashboard/stats'    + q),
    year
      ? apiFetch('/api/dashboard/trend' + q)           // single-year monthly line
      : apiFetch('/api/dashboard/trend_by_year'),       // 5-year comparison
    apiFetch('/api/dashboard/by_cause' + q),
    apiFetch('/api/dashboard/by_area'),                // Kochi area map always all areas
    apiFetch('/api/dashboard/recent?limit=4' + q2)
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

    // Card 3 – Avg Risk Score (no id, pick by index)
    const cards = document.querySelectorAll('#page-dashboard .kpi-card');
    if(cards[2]){
      const v = cards[2].querySelector('.kpi-value');
      if(v){ v.textContent = stats.avg_risk+'%'; }
      const l = cards[2].querySelector('.kpi-label');
      if(l) l.textContent = 'Avg Risk Score';
    }

    // Card 4 – Total Casualties (new #totalCasualties id)
    const el4 = document.getElementById('totalCasualties');
    if(el4){ el4.dataset.count = stats.casualties; el4.dataset.done = ''; el4.textContent = '0'; }
    const trendEl = document.getElementById('dash-casualties-trend');
    if(trendEl) trendEl.textContent = year ? year+' data' : '2022–2024 data';

    // Animate all counters on dashboard page
    animateCounters(document.getElementById('page-dashboard'));
  }

  /* ── Trend Chart ─────────────────────────────────────────── */
  // Delay chart creation to ensure DOM is laid out and canvas has proper dimensions
  requestAnimationFrame(()=>{
    requestAnimationFrame(()=>{
      const cv  = document.getElementById('chart-dash-trend');
      const box = document.getElementById('trend-chart-box');
      if(!cv || !box) return;

      const bw = box.offsetWidth  > 50 ? box.offsetWidth  : 560;
      const bh = box.offsetHeight > 50 ? box.offsetHeight : 220;
      cv.width  = bw;
      cv.height = bh;
      cv.style.width  = bw + 'px';
      cv.style.height = bh + 'px';

      const sub = document.getElementById('trend-chart-sub');
      const YEAR_COLORS = {2022:'#8BA7CC',2023:'#2D7CFF',2024:'#9E77ED',2025:'#17B26A',2026:'#F04438'};

      let chartObj = null;
      if(year && trendData && trendData.labels){
        if(sub) sub.textContent = year + ' Monthly Breakdown · Kochi';
        chartObj = mkChart('chart-dash-trend', {
          type:'line',
          data:{
            labels: trendData.labels,
            datasets:[{
              label: year,
              data:  trendData.values,
              borderColor:'#2D7CFF',
              backgroundColor:'rgba(45,124,255,0.12)',
              borderWidth:2.5, tension:0.4, fill:true,
              pointRadius:3, pointBackgroundColor:'#2D7CFF', pointHoverRadius:6
            }]
          },
          options: trendChartOptions(false)
        });
      } else if(!year && trendData && trendData.labels){
        if(sub) sub.textContent = '2022–2026 · Monthly comparison · Kochi';
        // Build 5 datasets
        const datasets = ['2022','2023','2024','2025','2026'].map(yr => ({
          label: yr,
          data: trendData.datasets[yr]||[],
          borderColor: YEAR_COLORS[yr]||'#2D7CFF',
          backgroundColor: yr==='2023' ? 'rgba(45,124,255,0.10)' : 'transparent',
          fill: yr==='2023',
          borderWidth: yr==='2023' ? 2.5 : 2,
          borderDash: ['2025','2026'].includes(yr) ? [5,4] : [],
          tension: 0.4,
          pointRadius: yr==='2023' ? 3 : 2,
          pointBackgroundColor: YEAR_COLORS[yr]||'#2D7CFF',
          pointHoverRadius: yr==='2023' ? 6 : 4
        }));
        chartObj = mkChart('chart-dash-trend', {
          type:'line',
          data:{ labels: trendData.labels, datasets },
          options: trendChartOptions(true)
        });
      }
      if(chartObj) requestAnimationFrame(()=>chartObj.resize());
    });
  });


  /* ── Contributing Factors (from real DB causes) ──────────── */
  if(byCause && byCause.labels && byCause.labels.length){
    renderDashFactors(byCause);
  }

  /* ── Recent Accidents ────────────────────────────────────── */
  if(recent && recent.length) renderDashRecentAccidents(recent);
  renderDashEmergencyAlerts();
  renderDashTrafficStatus();

  /* ── India map (only when no year filter so we don't confuse) */
  buildDashMap(byArea);
}

function trendChartOptions(showLegend){
  return {
    responsive: false,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: showLegend,
        position:'top', align:'end',
        labels:{boxWidth:10, boxHeight:10, usePointStyle:true, pointStyle:'circle', font:{size:11, weight:'600'}, padding:12}
      },
      tooltip:{
        mode:'index', intersect:false,
        callbacks:{
          title: items => items[0].label,
          label: item  => `  ${item.dataset.label}: ${(item.raw||0).toLocaleString('en-IN')} accidents`
        }
      }
    },
    scales:{
      y:{grid:gridOpt(), border:{display:false}},
      x:{grid:{display:false}, border:{display:false}}
    },
    interaction:{intersect:false, mode:'index'}
  };
}

/* ── Contributing Factors renderer ── */
function renderDashFactors(byCause){
  const palette = ['#F04438','#F79009','#9E77ED','#2D7CFF','#17B26A'];
  const total   = byCause.values.reduce((s,v)=>s+v, 0);
  const el      = document.getElementById('dash-factors');
  if(!el) return;

  el.innerHTML = byCause.labels.map((lbl, i)=>{
    const pct   = total > 0 ? Math.round(byCause.values[i]/total*100) : 0;
    const color = palette[i] || '#5B6B8C';
    return `
      <div class="pbar-row">
        <span class="flex items-center gap-8">
          <span class="legend-swatch" style="background:${color};"></span>${lbl}
        </span>
        <span>${pct}%</span>
      </div>
      <div class="pbar-track">
        <div class="pbar-fill" style="background:${color}; width:0; transition:width .8s ease;" data-w="${pct}%"></div>
      </div>`;
  }).join('');

  // Animate bars after a frame
  requestAnimationFrame(()=>{
    el.querySelectorAll('.pbar-fill').forEach(f=>{
      f.style.width = f.dataset.w;
    });
  });
}

/* ── Recent accidents feed ── */
function renderDashRecentAccidents(records){
  const el = document.getElementById('dash-recent-accidents');
  if(!el) return;
  el.innerHTML = records.slice(0,4).map(a=>{
    const location = a.road_name ? `${a.road_name}, ${a.area||a.city}` : `${a.area||a.city}, Kochi`;
    return `
    <div class="flex items-center gap-12" style="padding:11px 0; border-bottom:1px solid var(--border);">
      <div class="kpi-icon ${sevColor(a.severity)}" style="width:36px;height:36px;border-radius:10px;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4M12 17h.01"/></svg>
      </div>
      <div style="flex:1;min-width:0;">
        <div style="font-size:12.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${location}</div>
        <div class="text-faint" style="font-size:11px;">${a.date||''} · ${(a.cause||'').replace(/_/g,' ')}</div>
      </div>
      <span class="badge b-${sevColor(a.severity)}">${a.severity ? a.severity.charAt(0).toUpperCase()+a.severity.slice(1) : '—'}</span>
    </div>`;
  }).join('');
}

function renderDashEmergencyAlerts(){
  const alerts = [
    {text:'Ambulance dispatched to Edappally Toll Jn.', time:'2 min ago',  color:'red'},
    {text:'Signal preempted at Palarivattom Bypass',   time:'8 min ago',  color:'blue'},
    {text:'Green corridor activated — MG Road Kadavanthra', time:'15 min ago', color:'green'},
    {text:'High risk alert — Vyttila Mobility Hub',     time:'22 min ago', color:'orange'}
  ];
  const el = document.getElementById('dash-emergency-alerts');
  if(!el) return;
  el.innerHTML = alerts.map(a=>`
    <div class="flex items-center gap-12" style="padding:11px 0; border-bottom:1px solid var(--border);">
      <div class="kpi-icon ${a.color}" style="width:36px;height:36px;border-radius:10px;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>
      </div>
      <div style="flex:1;min-width:0;">
        <div style="font-size:12.5px;font-weight:700;line-height:1.4;">${a.text}</div>
        <div class="text-faint" style="font-size:11px;margin-top:2px;">${a.time}</div>
      </div>
    </div>`).join('');
}

function renderDashTrafficStatus(){
  const rows = [
    {name:'Edappally Toll Junction', density:'High',     color:'red'},
    {name:'MG Road Kadavanthra',     density:'Moderate', color:'orange'},
    {name:'Marine Drive / Menaka',    density:'Low',      color:'green'},
    {name:'Vyttila Mobility Hub',    density:'High',     color:'red'}
  ];
  const el = document.getElementById('dash-traffic-status');
  if(!el) return;
  el.innerHTML = rows.map(r=>`
    <div class="flex items-center justify-between" style="padding:11px 0; border-bottom:1px solid var(--border);">
      <div class="flex items-center gap-8"><span class="dot-status live"></span><span style="font-size:12.5px;font-weight:700;">${r.name}</span></div>
      <span class="badge b-${r.color}">${r.density}</span>
    </div>`).join('');
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
   ACCIDENT ANALYTICS — with year / severity / state filter
   ================================================================ */
async function initAnalyticsCharts(filters={}){
  const qs = new URLSearchParams(filters).toString();
  const q  = qs ? '?'+qs : '';

  const [byHour, byWeekday, stats, recent] = await Promise.all([
    apiFetch('/api/dashboard/by_hour'+q),
    apiFetch('/api/dashboard/by_weekday'+q),
    apiFetch('/api/dashboard/stats'+q),
    apiFetch('/api/dashboard/recent?limit=12'+(qs?'&'+qs:''))
  ]);

  // KPI cards
  if(stats){
    const vals = [stats.total, stats.fatal, stats.casualties, stats.major];
    const lbls = ['Total Accidents','Fatal Accidents','Total Casualties','Major Accidents'];
    document.querySelectorAll('#page-analytics .kpi-card').forEach((card, i)=>{
      if(vals[i] === undefined) return;
      const v = card.querySelector('.kpi-value');
      const l = card.querySelector('.kpi-label');
      if(v){ v.dataset.count = vals[i]; v.dataset.done=''; v.textContent='0'; }
      if(l) l.textContent = lbls[i];
    });
    animateCounters(document.querySelector('#page-analytics .grid.grid-4') || document.getElementById('page-analytics'));
    // Update badge
    const badge = document.querySelector('#page-analytics .card-head .badge');
    if(badge) badge.textContent = stats.total.toLocaleString('en-IN')+' records';
  }

  // Hourly bar chart (group into 2-hour buckets for readability)
  if(byHour && byHour.values){
    const bucketLabels = ['12AM','2AM','4AM','6AM','8AM','10AM','12PM','2PM','4PM','6PM','8PM','10PM'];
    const bucketData   = [];
    for(let i=0; i<24; i+=2) bucketData.push((byHour.values[i]||0)+(byHour.values[i+1]||0));
    const peak = [4,8,9,10]; // 8AM, 4PM, 6PM, 8PM buckets

    const ex = CHART_REGISTRY['chart-analytics-time'];
    if(ex){
      ex.data.datasets[0].data            = bucketData;
      ex.data.datasets[0].backgroundColor = bucketData.map((_,i)=>peak.includes(i)?'#F04438':'#2D7CFF');
      ex.update();
    } else {
      mkChart('chart-analytics-time', {
        type:'bar',
        data:{
          labels:bucketLabels,
          datasets:[{
            data:bucketData,
            backgroundColor:bucketData.map((_,i)=>peak.includes(i)?'#F04438':'#2D7CFF'),
            borderRadius:6, maxBarThickness:24
          }]
        },
        options:{
          responsive:true, maintainAspectRatio:false,
          plugins:{
            legend:{display:false},
            tooltip:{callbacks:{title:i=>i[0].label+' hrs', label:i=>`  Accidents: ${i.raw.toLocaleString('en-IN')}`}}
          },
          scales:{y:{grid:gridOpt(),border:{display:false}}, x:{grid:{display:false},border:{display:false}}}
        }
      });
    }
  }

  // Weekday doughnut
  if(byWeekday && byWeekday.values){
    const ex = CHART_REGISTRY['chart-analytics-weekday'];
    if(ex){ ex.data.datasets[0].data = byWeekday.values; ex.update(); }
    else {
      mkChart('chart-analytics-weekday', {
        type:'doughnut',
        data:{
          labels:byWeekday.labels||['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],
          datasets:[{
            data:byWeekday.values,
            backgroundColor:['#2D7CFF','#17B26A','#F79009','#F04438','#9E77ED','#06AED4','#EAB308'],
            borderWidth:3, borderColor:'#fff'
          }]
        },
        options:{
          responsive:true, maintainAspectRatio:false, cutout:'62%',
          plugins:{
            legend:{display:true, position:'right', labels:{boxWidth:9,boxHeight:9,usePointStyle:true,pointStyle:'circle',padding:12,font:{size:11.5,weight:'600'}}},
            tooltip:{callbacks:{label:item=>`  ${item.label}: ${item.raw.toLocaleString('en-IN')} accidents`}}
          }
        }
      });
    }
  }

  if(recent && recent.length) renderAnalyticsTable(recent);
}

function renderAnalyticsTable(records){
  const tbody = document.getElementById('analytics-table-body');
  if(!tbody) return;
  tbody.innerHTML = records.map(a=>`
    <tr>
      <td>${a.date||'—'} ${a.time||''}</td>
      <td>${a.city||'—'}, ${a.state||'—'}</td>
      <td><span class="badge b-${sevColor(a.severity)}">${a.severity?a.severity.charAt(0).toUpperCase()+a.severity.slice(1):'—'}</span></td>
      <td>${a.vehicles||'—'}</td>
      <td>${a.casualties||'0'}</td>
      <td>${a.road_type?a.road_type.charAt(0).toUpperCase()+a.road_type.slice(1):'—'}</td>
    </tr>`).join('');
}

/* ================================================================
   ANALYTICS FILTER — called from HTML button
   ================================================================ */
async function applyAnalyticsFilter(){
  const year     = document.getElementById('filter-year')?.value     || '';
  const severity = document.getElementById('filter-severity')?.value || '';
  const state    = document.getElementById('filter-state')?.value    || '';
  const btn      = document.getElementById('analytics-filter-btn');

  if(btn){ btn.disabled=true; btn.innerHTML='<span class="spinner" style="display:inline-block;"></span> Applying…'; }

  const filters = {};
  if(year)     filters.year     = year;
  if(severity) filters.severity = severity;
  if(state)    filters.state    = state;

  await initAnalyticsCharts(filters);

  if(btn){
    btn.disabled = false;
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 3H2l8 9.5V19l4 2v-8.5z"/></svg>Apply Filter';
  }

  const parts = [];
  if(year)     parts.push(year);
  if(severity) parts.push(severity.charAt(0).toUpperCase()+severity.slice(1));
  if(state)    parts.push(state);
  showToast('success','Filter applied', parts.length ? parts.join(' · ') : 'Showing all 2022–2024 data');
}
window.applyAnalyticsFilter = applyAnalyticsFilter;

/* ================================================================
   DATA MANAGEMENT
   ================================================================ */
async function initDataPage(){
  const recent = await apiFetch('/api/dashboard/recent?limit=20');
  renderDataTable(recent || []);
}

function renderDataTable(rows){
  const tbody = document.getElementById('data-table-body');
  if(!tbody) return;
  tbody.innerHTML = rows.map(a=>`
    <tr>
      <td class="mono">${a.id}</td>
      <td>${a.city||'—'}, ${a.state||'—'}</td>
      <td class="mono">${a.date||'—'}</td>
      <td class="mono">${a.time||'—'}</td>
      <td>${a.weather?a.weather.charAt(0).toUpperCase()+a.weather.slice(1):'—'}</td>
      <td><span class="badge b-${sevColor(a.severity)}">${a.severity?a.severity.charAt(0).toUpperCase()+a.severity.slice(1):'—'}</span></td>
      <td style="font-weight:700;">${a.risk_score?(parseFloat(a.risk_score)*100).toFixed(0)+'%':'—'}</td>
      <td><div class="table-actions">
        <button class="icon-btn-sm" onclick="showToast('info','Record','${a.id} — ${a.city}, ${a.state}')" title="View"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"/><circle cx="12" cy="12" r="3"/></svg></button>
        <button class="icon-btn-sm" onclick="showToast('success','Updated','${a.id} saved.')" title="Edit"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></button>
        <button class="icon-btn-sm danger" onclick="showToast('error','Deleted','${a.id} removed (demo).')" title="Delete"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg></button>
      </div></td>
    </tr>`).join('');
}

function filterDataTable(q){
  apiFetch('/api/dashboard/recent?limit=50').then(rows=>{
    if(!rows) return;
    const lq = q.toLowerCase();
    renderDataTable(rows.filter(r=>
      (r.id+'').toLowerCase().includes(lq) ||
      (r.city||'').toLowerCase().includes(lq) ||
      (r.state||'').toLowerCase().includes(lq) ||
      (r.cause||'').toLowerCase().includes(lq)
    ));
  });
}
window.filterDataTable = filterDataTable;

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
function initRiskCharts(){
  // Canvas dimensions are pre-set in HTML attributes (width/height).
  // A short timeout just yields the event loop so the page is active.
  setTimeout(() => {

    // ── SHAP Explainability chart ────────────────────────────────
    const shapChart = mkChart('chart-shap',{
      type:'bar',
      data:{
        labels:['Weather Conditions','Speed Limit','Light Conditions','Road Surface','Junction Detail'],
        datasets:[{
          data:[0.42,0.31,0.25,-0.18,0.12],
          backgroundColor:[0.42,0.31,0.25,-0.18,0.12].map(v=>v>=0?'#F04438':'#2D7CFF'),
          borderRadius:5, barThickness:20
        }]
      },
      options:{
        indexAxis:'y', responsive:false, maintainAspectRatio:false,
        animation:{ duration:500 },
        scales:{
          x:{ grid:gridOpt(), border:{display:false},
              title:{display:true, text:'SHAP value — contribution to predicted severity',
                     font:{size:10.5,weight:'600'}} },
          y:{ grid:{display:false}, border:{display:false} }
        },
        plugins:{
          legend:{display:false},
          tooltip:{callbacks:{label:c=>(c.raw>=0?'↑ Increases severity: +':'↓ Decreases severity: ')+Math.abs(c.raw).toFixed(4)}}
        }
      }
    });
    if(shapChart) setTimeout(()=>shapChart.resize(), 60);

    // ── Historical Risk chart ───────────────────────────────────
    const histChart = mkChart('chart-risk-history',{
      type:'line',
      data:{
        labels:['6 ago','5','4','3','2','Latest'],
        datasets:[{data:[62,58,71,65,74,78],
          borderColor:'#9E77ED', backgroundColor:'rgba(158,119,237,0.12)',
          fill:true, tension:.4, borderWidth:2.5, pointRadius:3, pointBackgroundColor:'#9E77ED'}]
      },
      options:{
        responsive:false, maintainAspectRatio:false,
        scales:{
          y:{min:0,max:100, grid:gridOpt(), border:{display:false}},
          x:{grid:{display:false}, border:{display:false}}
        }
      }
    });
    if(histChart) setTimeout(()=>histChart.resize(), 60);

  }, 50); // short yield — canvas is pre-sized in HTML

  // Default placeholder recommendations (replaced after real prediction)
  renderRiskRecommendations([]);
  document.getElementById('predict-risk-btn').addEventListener('click', runRiskPrediction);
}

function renderRiskFactors(data) {

    // Find the factors container
    const container = document.getElementById("risk-factors");

    // Stop if the container does not exist
    if (!container) return;

    // Clear previous factors
    container.innerHTML = "";

    // Get real SHAP factors from the API
    const factors = data?.top_factors || [];

    // Show message when no factors are available
    if (factors.length === 0) {
        container.innerHTML = `
            <div class="risk-factor-empty">
                SHAP factors are not available for this prediction.
            </div>
        `;
        return;
    }

    // Find the largest SHAP value for percentage scaling
    const maxValue = Math.max(
        ...factors.map(factor =>
            Math.abs(Number(factor.shap_value))
        )
    );

    // Create the table header
    const header = document.createElement("div");
    header.className = "risk-factor-header-row";
    header.innerHTML = `
        <div class="risk-col-num">#</div>
        <div class="risk-col-feat">Feature</div>
        <div class="risk-col-bar">Impact</div>
        <div class="risk-col-pct">Contrib</div>
        <div class="risk-col-eff">Effect</div>
    `;
    container.appendChild(header);

    // Display each SHAP factor
    factors.slice(0, 5).forEach((factor, index) => {
        const shapValue = Number(factor.shap_value);
        const percentage = maxValue > 0
            ? Math.round((Math.abs(shapValue) / maxValue) * 100)
            : 0;
        const increases = shapValue >= 0;
        const cleanName = (factor.feature || "").replace(/_/g, " ");

        const row = document.createElement("div");
        row.className = "risk-factor";

        row.innerHTML = `
            <div class="risk-col-num">${index + 1}</div>
            <div class="risk-col-feat" title="${factor.feature}">${cleanName}</div>
            <div class="risk-col-bar">
                <div class="risk-factor-bar">
                    <div
                        class="risk-factor-fill ${increases ? "increase" : "decrease"}"
                        style="width: ${percentage}%"
                    ></div>
                </div>
            </div>
            <div class="risk-col-pct">${percentage}%</div>
            <div class="risk-col-eff">
                <span class="risk-factor-direction ${increases ? "increase" : "decrease"}">
                    ${increases ? "↑ Increases" : "↓ Decreases"}
                </span>
            </div>
        `;
        container.appendChild(row);
    });
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

function renderRiskRecommendations(topFactors, customRecs){
  const el = document.getElementById('risk-recommendations');
  if(!el) return;

  if (customRecs && customRecs.length > 0) {
    el.innerHTML = customRecs.map((r, i) => `
    <div class="card hoverable" style="padding:16px;display:flex;flex-direction:column;gap:10px;">
      <div style="display:flex;gap:12px;align-items:flex-start;">
        <div class="kpi-icon blue" style="width:38px;height:38px;border-radius:11px;flex-shrink:0;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 4 5v6c0 5.2 3.4 9.6 8 11 4.6-1.4 8-5.8 8-11V5l-8-3Z"/></svg>
        </div>
        <div style="flex:1;min-width:0;">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:3px;">
            <div style="font-size:12.5px;font-weight:700;">${i+1}. ${r.title}</div>
            <span class="badge b-blue">${r.badge || 'Preventive Action'}</span>
          </div>
          <div class="text-dim" style="font-size:11.5px;line-height:1.55;">${r.desc}</div>
        </div>
      </div>
    </div>`).join('');
    return;
  }

  let recs = [];

  if(topFactors && topFactors.length > 0){
    const seen = new Map();
    topFactors.forEach(f => {
      const baseKey = getBaseFeatureName(f.feature);
      const abs = Math.abs(Number(f.shap_value));
      if (!seen.has(baseKey) || abs > Math.abs(Number(seen.get(baseKey).shap_value))) {
        seen.set(baseKey, f);
      }
    });

    const deduped = [...seen.values()]
      .filter(f => Math.abs(Number(f.shap_value)) > 0)
      .sort((a,b) => Math.abs(Number(b.shap_value)) - Math.abs(Number(a.shap_value)))
      .slice(0, 6);

    recs = deduped.map(f => {
      const baseKey = getBaseFeatureName(f.feature);
      const lookup =
        SHAP_REC_MAP[baseKey] ||
        Object.entries(SHAP_REC_MAP).find(([k]) =>
          k.toLowerCase().includes(baseKey.toLowerCase()) ||
          baseKey.toLowerCase().includes(k.toLowerCase())
        )?.[1] ||
        SHAP_REC_MAP['default'];

      const shapVal  = Number(f.shap_value);
      const increase = shapVal >= 0;
      const badge    = increase
        ? `<span style="font-size:10px;font-weight:700;color:#F04438;background:rgba(240,68,56,0.1);border-radius:4px;padding:1px 5px;">↑ Increases Risk</span>`
        : `<span style="font-size:10px;font-weight:700;color:#17B26A;background:rgba(23,178,106,0.1);border-radius:4px;padding:1px 5px;">↓ Reduces Risk</span>`;
      const shapDisplay = (shapVal >= 0 ? '+' : '') + shapVal.toFixed(4);
      const displayName = baseKey.replace(/_/g, ' ');

      return { ...lookup, badge, shapDisplay, featureName: displayName };
    });
  } else {
    recs = [
      {icon:'M13 2 3 14h7l-1 8 10-12h-7z',      title:'Reduce Speed',         desc:'Maintain safe speed limits. Excessive speed is a leading factor in collision severity.',                                    color:'red',    badge:'', shapDisplay:'', featureName:''},
      {icon:'M12 2v2M12 20v2M4 12H2M22 12h-2',   title:'Improve Lighting',     desc:'Ensure adequate street lighting on accident-prone segments, especially at night.',                                      color:'orange', badge:'', shapDisplay:'', featureName:''},
      {icon:'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z', title:'Road Maintenance', desc:'Repair surface defects and resurface deteriorated carriageways to reduce loss-of-control accidents.', color:'blue',   badge:'', shapDisplay:'', featureName:''}
    ];
  }

  el.innerHTML = recs.map((r, i) => `
    <div class="card hoverable" style="padding:16px;display:flex;flex-direction:column;gap:10px;">
      <div style="display:flex;gap:12px;align-items:flex-start;">
        <div class="kpi-icon ${r.color}" style="width:38px;height:38px;border-radius:11px;flex-shrink:0;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${r.icon}"/></svg>
        </div>
        <div style="flex:1;min-width:0;">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:3px;">
            <div style="font-size:12.5px;font-weight:700;">${i+1}. ${r.title}</div>
            ${r.badge}
          </div>
          ${r.featureName ? `<div style="font-size:10.5px;font-weight:600;color:var(--text-faint);margin-bottom:4px;">Feature: <span style="color:var(--primary)">${r.featureName}</span>${r.shapDisplay ? ' · SHAP: <span style="font-family:monospace">' + r.shapDisplay + '</span>' : ''}</div>` : ''}
          <div class="text-dim" style="font-size:11.5px;line-height:1.55;">${r.desc}</div>
        </div>
      </div>
    </div>`).join('');
}

async function runRiskPrediction(){
  const btn = document.getElementById('predict-risk-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="display:inline-block;"></span> Analyzing…';

  try {
    const area = (document.getElementById('risk-area')?.value || 'Edappally').trim();
    const roadName = (document.getElementById('risk-road-name')?.value || 'Rajagiri Road').trim();
    const dateValue = document.getElementById('risk-date')?.value || '2026-05-24';
    const timeValue = document.getElementById('risk-time')?.value || '18:30';
    const roadType = document.getElementById('risk-road-type')?.value || 'urban';
    const lanes = Number(document.getElementById('risk-lanes')?.value || 2);
    const trafficDensity = document.getElementById('risk-traffic-density')?.value || 'high';
    const trafficSignal = Number(document.getElementById('risk-traffic-signal')?.value || 0);
    const weather = document.getElementById('risk-weather')?.value || 'clear';
    const visibility = document.getElementById('risk-visibility')?.value || 'high';
    const cause = document.getElementById('risk-cause')?.value || 'overspeeding';
    const vehiclesInvolved = Number(document.getElementById('risk-vehicles')?.value || 2);

    const predictionData = {
      area: area,
      road_name: roadName,
      date: dateValue,
      time: timeValue,
      road_type: roadType,
      lanes: lanes,
      traffic_density: trafficDensity,
      traffic_signal: trafficSignal,
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
      throw new Error(result.error || 'Prediction failed.');
    }

    const severity = result.predicted_severity || 'Minor Severity';
    const confidence = Number(result.confidence || 0);

    let riskLevel = 'Low';
    let riskColor = '#17B26A';
    let riskClass = 'b-green';

    if(severity.includes('Major') || severity.includes('Serious')){
      riskLevel = 'Moderate';
      riskColor = '#F79009';
      riskClass = 'b-orange';
    }

    if(severity.includes('Fatal')){
      riskLevel = 'High';
      riskColor = '#F04438';
      riskClass = 'b-red';
    }

    const gauge = document.getElementById('risk-gauge-fill');
    if(gauge){
      gauge.setAttribute('stroke', riskColor);
      gauge.style.strokeDashoffset = 283 - (283 * confidence / 100);
    }

    const gaugePct = document.getElementById('risk-gauge-pct');
    if(gaugePct){
      gaugePct.textContent = Math.round(confidence) + '%';
      gaugePct.style.color = riskColor;
    }

    const gaugeLabel = document.getElementById('risk-gauge-label');
    if(gaugeLabel){
      gaugeLabel.className = 'glabel badge ' + riskClass;
      gaugeLabel.textContent = severity;
    }

    const gaugeDesc = document.getElementById('risk-gauge-desc');
    if(gaugeDesc){
      gaugeDesc.textContent =
        `Predicted severity: ${severity} (${area}, ${roadName}). Model confidence: ${confidence.toFixed(2)}%.`;
    }

    const confidenceEl = document.getElementById('risk-confidence');
    if(confidenceEl){
      confidenceEl.textContent = confidence.toFixed(2) + '%';
    }

    const predictionTime = document.getElementById('risk-pred-time');
    if(predictionTime){
      const now = new Date();
      predictionTime.textContent =
        now.toLocaleDateString('en-IN') + ', ' +
        now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    }

    // Update the real-time SHAP explainability chart with actual prediction values
    if (result.top_factors && result.top_factors.length > 0) {
      renderRiskFactors(result);

      const shapLabels = result.top_factors.map(f => (f.feature || '').replace(/_/g, ' '));
      const shapValues = result.top_factors.map(f => parseFloat(f.shap_value));
      const shapColors = shapValues.map(v => v >= 0 ? '#F04438' : '#2D7CFF');

      const existingShap = CHART_REGISTRY['chart-shap'];
      if (existingShap) {
        existingShap.data.labels = shapLabels;
        existingShap.data.datasets[0].data = shapValues;
        existingShap.data.datasets[0].backgroundColor = shapColors;
        existingShap.update('active');
      } else {
        requestAnimationFrame(() => requestAnimationFrame(() => {
          mkChart('chart-shap', {
            type: 'bar',
            data: {
              labels: shapLabels,
              datasets: [{ data: shapValues, backgroundColor: shapColors, borderRadius: 5, barThickness: 20 }]
            },
            options: {
              indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: { duration: 600 },
              scales: {
                x: { grid: gridOpt(), border: { display: false }, title: { display: true, text: 'SHAP value — contribution to predicted severity', font: { size: 10.5, weight: '600' } } },
                y: { grid: { display: false }, border: { display: false } }
              },
              plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: c => (c.raw >= 0 ? '↑ Increases severity: +' : '↓ Decreases severity: ') + Math.abs(c.raw).toFixed(4) } }
              }
            }
          });
        }));
      }

      renderRiskRecommendations(result.top_factors, result.recommendations);
    }

    showToast(
      'success',
      'Prediction Complete',
      `${severity} predicted with ${confidence.toFixed(2)}% confidence for ${area}.`
    );

  } catch(error){

    // # Show prediction error
    console.error('Severity prediction error:', error);

    showToast(
      'error',
      'Prediction failed',
      error.message || 'Unable to connect to the prediction service.'
    );

  } finally{

    // # Restore prediction button
    btn.disabled = false;

    btn.innerHTML = `
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M13 2 3 14h7l-1 8 10-12h-7z"/>
      </svg>
      Predict Severity
    `;
  }
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
  if(hotspotMapInstance || !window.L) return;
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
    topDangerHotspot = data.stats?.top_danger_zone || currentHotspots[0] || null;

    // Update Header Badges
    const headerDangerEl = document.getElementById('header-danger-count');
    if(headerDangerEl){
      headerDangerEl.innerHTML = `<span class="dot-status live" style="background:#F04438;"></span>${data.stats.very_high_count} Critical Zones`;
    }
    const headerCountEl = document.getElementById('header-hotspot-count');
    if(headerCountEl){
      headerCountEl.textContent = `${data.stats.total_hotspots} Monitored Hotspots`;
    }

    // Update Top Danger Zone Alert Banner
    const topAlertEl = document.getElementById('hotspot-top-alert');
    if(topAlertEl && topDangerHotspot){
      topAlertEl.style.display = 'block';
      const nameEl = document.getElementById('top-alert-name');
      const fatalEl = document.getElementById('top-alert-fatal');
      const descEl = document.getElementById('top-alert-desc');
      if(nameEl) nameEl.textContent = topDangerHotspot.name;
      if(fatalEl) fatalEl.textContent = `${topDangerHotspot.fatal_accidents} Fatal`;
      if(descEl) descEl.textContent = `${topDangerHotspot.area} · Score: ${topDangerHotspot.danger_score}/100 · Primary Cause: ${topDangerHotspot.top_cause}`;
    } else if(topAlertEl){
      topAlertEl.style.display = 'none';
    }

    // Render Stats
    renderHotspotStats(data.stats);

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
  if(activeTierFilter === 'veryhigh'){
    displayList = currentHotspots.filter(h => h.tier === 'veryhigh');
  }

  renderHotspotMarkers(displayList);
  renderHotspotList(displayList);
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
  const trend = await apiFetch('/api/dashboard/trend');
  if(trend && trend.labels){
    const last6Labels = trend.labels.slice(-6);
    const last6Values = trend.values.slice(-6);
    mkChart('chart-reports-accidents',{type:'line',data:{labels:last6Labels,datasets:[{data:last6Values,borderColor:'#2D7CFF',backgroundColor:'rgba(45,124,255,0.1)',fill:true,tension:.4,borderWidth:2.5,pointRadius:3,pointBackgroundColor:'#2D7CFF'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{tooltip:{callbacks:{label:i=>`  Accidents: ${i.raw.toLocaleString('en-IN')}`}}},scales:{y:{grid:gridOpt(),border:{display:false}},x:{grid:{display:false},border:{display:false}}}}});
  } else {
    mkChart('chart-reports-accidents',{type:'line',data:{labels:['Dec','Jan','Feb','Mar','Apr','May'],datasets:[{data:[210,198,225,240,215,260],borderColor:'#2D7CFF',backgroundColor:'rgba(45,124,255,0.1)',fill:true,tension:.4,borderWidth:2.5,pointRadius:3,pointBackgroundColor:'#2D7CFF'}]},options:{responsive:true,maintainAspectRatio:false,scales:{y:{grid:gridOpt(),border:{display:false}},x:{grid:{display:false},border:{display:false}}}}});
  }
  mkChart('chart-reports-hotspots',{type:'bar',data:{labels:['Dec','Jan','Feb','Mar','Apr','May'],datasets:[{label:'Very High',data:[4,4,5,5,6,5],backgroundColor:'#F04438',borderRadius:4,maxBarThickness:14,stack:'s'},{label:'High',data:[6,7,7,8,7,8],backgroundColor:'#F79009',borderRadius:4,maxBarThickness:14,stack:'s'},{label:'Moderate',data:[5,6,6,5,6,6],backgroundColor:'#EAB308',borderRadius:4,maxBarThickness:14,stack:'s'}]},options:{responsive:true,maintainAspectRatio:false,scales:{y:{grid:gridOpt(),border:{display:false},stacked:true},x:{grid:{display:false},border:{display:false},stacked:true}},plugins:{legend:{display:true,position:'bottom',labels:{boxWidth:8,boxHeight:8,usePointStyle:true,pointStyle:'circle',font:{size:10.5,weight:'600'}}}}}});
  const el=document.getElementById('reports-table');
  if(el) el.innerHTML=[{name:'Monthly Accident Summary — Jan 2024',by:'System',date:'31 Jan 2024',status:'Ready'},{name:'Hotspot Analysis Report — 2023',by:'Admin',date:'01 Jan 2024',status:'Ready'},{name:'Traffic Signal Optimization Report',by:'System',date:'15 Dec 2023',status:'Ready'},{name:'Emergency Response Performance',by:'Admin',date:'01 Dec 2023',status:'Processing'},{name:'Risk Prediction Accuracy Report',by:'System',date:'01 Nov 2023',status:'Ready'},{name:'Annual Incident Log — 2022',by:'Admin',date:'31 Dec 2022',status:'Ready'}].map(r=>`<tr><td style="font-weight:700;">${r.name}</td><td>${r.by}</td><td>${r.date}</td><td><span class="badge ${r.status==='Ready'?'b-green':'b-orange'}">${r.status}</span></td><td><div class="table-actions"><button class="icon-btn-sm" onclick="showToast('info','Report','${r.name}')" title="View"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"/><circle cx="12" cy="12" r="3"/></svg></button><button class="icon-btn-sm" onclick="showToast('success','Download','${r.name}.pdf')" title="PDF"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg></button></div></td></tr>`).join('');
}

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
   YOLO VEHICLE DETECTION & COUNT
   Modelled after: github.com/RayanAIX/vehicle-detection-and-counting-yolov8
   Backend uses results[0].plot() annotation + per-frame vehicle count overlay
   + saves annotated output video downloadable as output.mp4
   ================================================================ */

let _yoloFile = null;

function initYoloCharts(){
  buildRoadSceneInto('yolo-detect-stage', yoloVehicles(), true);
}
window.initYoloCharts = initYoloCharts;

function onYoloFileSelected(input){
  const file = input.files && input.files[0];
  if(!file) return;
  _yoloFile = file;
  const nameEl = document.getElementById('yolo-file-name');
  if(nameEl) nameEl.textContent = file.name;
  const btn = document.getElementById('yolo-detect-btn');
  if(btn) btn.disabled = false;
  const dlBtn = document.getElementById('yolo-download-btn');
  if(dlBtn) dlBtn.style.display = 'none';
  showToast('success', 'File loaded', file.name + ' ready for detection.');
}
window.onYoloFileSelected = onYoloFileSelected;

function handleYoloDrop(e){
  e.preventDefault();
  const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
  if(!file) return;
  _yoloFile = file;
  const nameEl = document.getElementById('yolo-file-name');
  if(nameEl) nameEl.textContent = file.name;
  const btn = document.getElementById('yolo-detect-btn');
  if(btn) btn.disabled = false;
  const dlBtn = document.getElementById('yolo-download-btn');
  if(dlBtn) dlBtn.style.display = 'none';
  showToast('success', 'File dropped', file.name + ' ready.');
}
window.handleYoloDrop = handleYoloDrop;

async function runYoloDetection(){
  if(!_yoloFile){
    showToast('error', 'No file', 'Please select a video or image first.');
    return;
  }
  const btn     = document.getElementById('yolo-detect-btn');
  const btnText = document.getElementById('yolo-detect-btn-text');
  const spinner = document.getElementById('yolo-spinner');
  btn.disabled  = true;
  btnText.textContent = 'Detecting…';
  spinner.style.display = 'inline-block';

  const dlBtn = document.getElementById('yolo-download-btn');
  if(dlBtn) dlBtn.style.display = 'none';

  const statusEl = document.getElementById('yolo-kpi-status');
  if(statusEl){ statusEl.textContent = 'Processing…'; statusEl.style.color = 'var(--orange)'; }

  try {
    const formData = new FormData();
    formData.append('video', _yoloFile);
    // Confidence threshold — matches reference repo Streamlit sidebar slider
    const confSlider = document.getElementById('yolo-conf-slider');
    const confVal = confSlider ? parseFloat(confSlider.value).toFixed(2) : '0.40';
    formData.append('conf', confVal);

    const res  = await fetch('/api/yolo/detect', { method: 'POST', body: formData });
    const data = await res.json();
    if(!data.success) throw new Error(data.error || 'Detection failed');

    // ── Annotated frame (backend used results[0].plot()) ──────────────
    const frameWrap = document.getElementById('yolo-frame-wrap');
    const stageWrap = document.getElementById('yolo-detect-stage');
    const imgEl     = document.getElementById('yolo-annotated-img');
    if(data.annotated_frame && imgEl){
      imgEl.src = 'data:image/jpeg;base64,' + data.annotated_frame;
      if(frameWrap) frameWrap.style.display = 'block';
      if(stageWrap) stageWrap.style.display = 'none';
      const liveBadge = document.getElementById('yolo-live-badge');
      if(liveBadge) liveBadge.style.display = '';
    }

    // ── Download annotated output (mirrors reference repo output) ─────
    if(data.download_token && dlBtn){
      const dlName = data.download_filename || (data.is_image ? 'annotated_traffic.jpg' : 'vehicle_detection_output.mp4');
      dlBtn.href = '/api/yolo/download/' + data.download_token;
      dlBtn.setAttribute('download', dlName);
      dlBtn.innerHTML = data.is_image ? '⬇ Download Annotated Image' : '⬇ Download Annotated Video';
      Object.assign(dlBtn.style, {
        display:'flex', alignItems:'center', gap:'8px', justifyContent:'center',
        marginBottom:'18px', background:'rgba(23,178,106,0.12)',
        border:'1px solid var(--green)', color:'var(--green)', borderRadius:'10px',
        padding:'10px 16px', fontWeight:'700', fontSize:'13px', textDecoration:'none'
      });
    }

    // ── KPI cards ──────────────────────────────────────────────────────
    if(statusEl){ statusEl.textContent = 'Done ✓'; statusEl.style.color = 'var(--green)'; }
    const totalEl = document.getElementById('yolo-kpi-total');
    if(totalEl){ totalEl.dataset.count = data.total; totalEl.dataset.done = ''; totalEl.textContent = '0'; }
    const dColors = { High:'var(--red)', Medium:'var(--orange)', Low:'var(--green)' };
    const densityEl = document.getElementById('yolo-kpi-density');
    if(densityEl){ densityEl.textContent = data.density; densityEl.style.color = dColors[data.density]||'var(--text)'; }
    const framesEl = document.getElementById('yolo-kpi-frames');
    if(framesEl) framesEl.textContent = data.total_frames_sampled + ' / ' + data.video_total_frames;
    animateCounters(document.getElementById('page-yolo'));

    // ── Emergency banner ───────────────────────────────────────────────
    const emergBanner = document.getElementById('yolo-emergency-banner');
    if(emergBanner) emergBanner.style.display = data.emergency_detected ? 'block' : 'none';
    if(data.emergency_detected)
      showToast('error', '⚠️ Priority Vehicle', 'Large bus/truck detected — recommend green-phase extension.');

    // ── Vehicle count breakdown ────────────────────────────────────────
    const VCOL = { Car:'#17B26A', Bus:'#2D7CFF', Truck:'#F79009', Motorcycle:'#F04438', Bicycle:'#EAB308' };
    const counts = data.all_counts || {};
    const total  = data.total || 0;
    const summaryEl = document.getElementById('yolo-summary');
    if(summaryEl){
      if(total > 0){
        summaryEl.innerHTML = Object.entries(counts).map(([label, count]) => {
          const pct   = total > 0 ? Math.round(count / total * 100) : 0;
          const color = VCOL[label] || '#5B6B8C';
          return `<div style="margin-bottom:12px;">
            <div class="flex justify-between items-center" style="font-size:12px;font-weight:700;margin-bottom:6px;">
              <span class="flex items-center gap-8"><span class="legend-swatch" style="background:${color};"></span>${label}</span>
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
        if(totDisp) totDisp.textContent  = (!data.is_image && data.line_crossed_total > 0) ? `${total} vehicles crossed tripwire` : `${total} vehicles`;
      } else {
        summaryEl.innerHTML = '<div class="text-dim" style="font-size:12px;text-align:center;padding:20px 0;">No vehicles detected — try lowering confidence threshold.</div>';
      }
    }

    // ── Traffic priority card ──────────────────────────────────────────
    renderYoloPriorityCard(data);

    // ── Per-frame trend chart ──────────────────────────────────────────
    if(data.frame_results && data.frame_results.length){
      const ex = CHART_REGISTRY['chart-yolo-trend'];
      if(ex){
        ex.data.labels = data.frame_labels;
        ex.data.datasets[0].data  = data.frame_results;
        ex.data.datasets[0].label = 'Vehicles detected';
        ex.update();
      } else {
        mkChart('chart-yolo-trend',{
          type:'line',
          data:{ labels:data.frame_labels, datasets:[{
            label:'Vehicles detected', data:data.frame_results,
            borderColor:'#2D7CFF', backgroundColor:'rgba(45,124,255,0.10)',
            fill:true, tension:0.4, borderWidth:2.5, pointRadius:3, pointBackgroundColor:'#2D7CFF'
          }]},
          options:{ responsive:true, maintainAspectRatio:false,
            plugins:{tooltip:{callbacks:{label:i=>`  Vehicles: ${i.raw}`}}},
            scales:{ y:{min:0,grid:gridOpt(),border:{display:false}}, x:{grid:{display:false},border:{display:false}} }
          }
        });
      }
    }

    const toastMsg = (!data.is_image && data.line_crossed_total > 0) 
      ? `${total} vehicles crossed line · Peak in frame: ${data.peak_vehicles} · Density: ${data.density}`
      : `${total} vehicles · Density: ${data.density} · Conf: ${data.conf_used}`;
    showToast('success', 'Detection complete', toastMsg);

  } catch(err){
    console.error('[YOLO]', err);
    showToast('error', 'Detection failed', err.message || 'Server error');
    if(statusEl){ statusEl.textContent = 'Error'; statusEl.style.color = 'var(--red)'; }
  } finally {
    btn.disabled = false;
    btnText.textContent = 'Run YOLOv8 Detection';
    spinner.style.display = 'none';
  }
}
window.runYoloDetection = runYoloDetection;

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
    priority = 'HIGH — Bus/Truck Priority';
    prColor  = 'red';
    prDesc   = `${busCount} buses · ${truckCount} trucks detected in frame.`;
    action   = 'Extend green phase +25 sec for heavy vehicle lane.';
  } else if(data.density === 'High'){
    priority = 'MEDIUM — Congestion Alert';
    prColor  = 'orange';
    prDesc   = `High vehicle density (${total} total). Congestion likely.`;
    action   = 'Adaptive signal extension + traffic warden deployment.';
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
