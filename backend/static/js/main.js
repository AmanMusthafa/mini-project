/**
 * Main Application Orchestrator
 * Connects modular controllers, navigation routing, and responsive events.
 */
import { initAuth, checkSession } from './auth.js';
import { loadDashboard, bindDashboardFilters } from './dashboard.js';
import { initPredict } from './predict.js';
import { initHotspots } from './hotspots.js';
import { initYolo } from './yolo.js';
import { initSignal } from './signal.js';
import { initEmergency } from './emergency.js';
import { initRecords } from './records.js';
import { initReports } from './reports.js';

document.addEventListener('DOMContentLoaded', async () => {
  // 1. Initialize Auth
  initAuth((user) => {
    loadDashboard();
  });

  // 2. Setup Sidebar Page Navigation
  setupNavigation();

  // 3. Setup Theme & Mobile Menu
  setupUIInteractions();

  // 4. Verify Active Session
  const activeUser = await checkSession();
  if (activeUser) {
    loadDashboard();
  }

  // 5. Initialize Sub-modules
  bindDashboardFilters();
  initPredict();
  initHotspots();
  initYolo();
  initSignal();
  initEmergency();
  initRecords();
  initReports();
});

function setupNavigation() {
  const navItems = document.querySelectorAll('.sidebar-nav .nav-item[data-page]');
  const pages = document.querySelectorAll('.page');
  const titleText = document.getElementById('topbar-title-text');
  const titleSub = document.getElementById('topbar-title-sub');

  const pageMeta = {
    dashboard: { title: 'Dashboard', sub: 'Kochi Road Safety Monitoring & Analytics · 2023–2026' },
    analytics: { title: 'Accident Analytics', sub: 'Historical Multi-Factor Crash Distribution & Trend Analysis' },
    risk: { title: 'Severity Prediction', sub: 'Post-Incident Incident Scenario Severity Classifier & TreeSHAP Local Attribution' },
    hotspot: { title: 'Hotspot Map', sub: 'Spatial Crash Concentration & Quantile Risk Ranking (Kochi)' },
    traffic: { title: 'Smart Signal Optimization', sub: 'Webster Method PCU-Weighted Adaptive Phase Allocation (Simulation Mode)' },
    yolo: { title: 'YOLOv8 Detection', sub: 'High-Throughput Streaming Tripwire Vehicle Counting & Classification' },
    emergency: { title: 'Emergency Priority', sub: 'Clearance-Compliant Signal Preemption Planning (Simulation Mode)' },
    reports: { title: 'Audit Reports', sub: 'Downloadable Live PDF & CSV Road Safety Documentation' },
    data: { title: 'Data Management', sub: 'Incident Records CRUD, Schema Verification & SQLite Management' }
  };

  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const targetPageId = item.getAttribute('data-page');

      // Update active nav
      navItems.forEach(n => n.classList.remove('active'));
      item.classList.add('active');

      // Update visible page
      pages.forEach(p => p.classList.remove('active'));
      const targetPage = document.getElementById(`page-${targetPageId}`);
      if (targetPage) {
        targetPage.classList.add('active');
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }

      // Update topbar header
      const meta = pageMeta[targetPageId] || { title: 'Dashboard', sub: 'Kochi Road Safety System' };
      if (titleText) titleText.textContent = meta.title;
      if (titleSub) titleSub.textContent = meta.sub;

      // Close mobile sidebar if open
      const sidebar = document.getElementById('sidebar');
      const overlay = document.getElementById('sidebar-overlay');
      if (sidebar && sidebar.classList.contains('open')) {
        sidebar.classList.remove('open');
        if (overlay) overlay.style.display = 'none';
      }
    });
  });
}

function setupUIInteractions() {
  const hamburger = document.getElementById('hamburger-btn');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const profileBtn = document.getElementById('profile-btn');
  const profileDropdown = document.getElementById('profile-dropdown');

  if (hamburger && sidebar) {
    hamburger.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      if (overlay) overlay.style.display = sidebar.classList.contains('open') ? 'block' : 'none';
    });
  }

  if (overlay) {
    overlay.addEventListener('click', () => {
      if (sidebar) sidebar.classList.remove('open');
      overlay.style.display = 'none';
    });
  }

  if (profileBtn && profileDropdown) {
    profileBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      profileDropdown.classList.toggle('show');
    });

    document.addEventListener('click', () => {
      profileDropdown.classList.remove('show');
    });
  }
}
