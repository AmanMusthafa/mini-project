/**
 * Smart Traffic Signal Optimization (Webster's Method) Module
 */
import { fetchApi } from './api.js';
import { escapeHtml, registerChart, showToast } from './utils.js';

let _simInterval = null;
let _currentPhaseIndex = 0;

export function initSignal() {
  const optimizeBtn = document.getElementById('signal-optimize-btn');
  const importBtn = document.getElementById('signal-import-yolo');

  if (importBtn) {
    importBtn.addEventListener('click', () => {
      const stored = window.sessionStorage.getItem('kochi_yolo_counts');
      if (!stored) {
        showToast('info', 'No Saved Detection', 'Upload a video on the YOLO page to import live counts.');
        return;
      }
      try {
        const counts = JSON.parse(stored);
        document.getElementById('sig-n-cars').value = counts.Car || 15;
        document.getElementById('sig-n-bus').value = counts.Bus || 2;
        document.getElementById('sig-n-truck').value = counts.Truck || 1;
        document.getElementById('sig-n-moto').value = counts.Motorcycle || 8;
        showToast('success', 'YOLO Data Imported', 'Loaded vehicle class counts into North Approach.');
      } catch (e) {}
    });
  }

  if (optimizeBtn) {
    optimizeBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      await runSignalOptimizer();
    });
  }

  // Run initial default optimization
  runSignalOptimizer();
}

async function runSignalOptimizer() {
  const approaches = [
    {
      name: 'North (MG Road)',
      vehicle_counts: {
        Car: parseInt(document.getElementById('sig-n-cars')?.value || 25),
        Bus: parseInt(document.getElementById('sig-n-bus')?.value || 4),
        Truck: parseInt(document.getElementById('sig-n-truck')?.value || 2),
        Motorcycle: parseInt(document.getElementById('sig-n-moto')?.value || 14),
        Bicycle: 2
      },
      lanes: parseInt(document.getElementById('sig-n-lanes')?.value || 2)
    },
    {
      name: 'South (Kadavanthra Jn)',
      vehicle_counts: {
        Car: parseInt(document.getElementById('sig-s-cars')?.value || 20),
        Bus: parseInt(document.getElementById('sig-s-bus')?.value || 3),
        Truck: 1,
        Motorcycle: parseInt(document.getElementById('sig-s-moto')?.value || 12),
        Bicycle: 1
      },
      lanes: parseInt(document.getElementById('sig-s-lanes')?.value || 2)
    },
    {
      name: 'East (SA Road)',
      vehicle_counts: {
        Car: parseInt(document.getElementById('sig-e-cars')?.value || 12),
        Bus: 1,
        Truck: 0,
        Motorcycle: parseInt(document.getElementById('sig-e-moto')?.value || 8),
        Bicycle: 3
      },
      lanes: parseInt(document.getElementById('sig-e-lanes')?.value || 1)
    },
    {
      name: 'West (Chittoor Road)',
      vehicle_counts: {
        Car: parseInt(document.getElementById('sig-w-cars')?.value || 8),
        Bus: 0,
        Truck: 0,
        Motorcycle: parseInt(document.getElementById('sig-w-moto')?.value || 6),
        Bicycle: 4
      },
      lanes: parseInt(document.getElementById('sig-w-lanes')?.value || 1)
    }
  ];

  try {
    const res = await fetchApi('/api/signal/optimize', {
      method: 'POST',
      body: { approaches }
    });

    if (res.success) {
      renderSignalResults(res);
      startJunctionSimulation(res.phases);
      showToast('success', 'Signals Optimized', `Computed optimal Webster cycle: ${res.cycle_length}s (-${res.comparison.estimated_delay_reduction_pct}% delay)`);
    }
  } catch (err) {
    showToast('error', 'Optimization Error', err.message || 'Calculation error');
  }
}

function renderSignalResults(data) {
  // Cycle length
  const cycleEl = document.getElementById('signal-cycle-display');
  const delayRedEl = document.getElementById('signal-delay-reduction');
  const rationaleEl = document.getElementById('signal-rationale-text');

  if (cycleEl) cycleEl.textContent = `${data.cycle_length}s`;
  if (delayRedEl) delayRedEl.textContent = `-${data.comparison.estimated_delay_reduction_pct}%`;
  if (rationaleEl) rationaleEl.textContent = data.rationale;

  // Render doughnut chart of phase green times
  const canvas = document.getElementById('chart-signal-phases');
  if (canvas) {
    const labels = data.phases.map(p => p.approach_name);
    const greens = data.phases.map(p => p.green_seconds);

    registerChart('chart-signals', new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: greens,
          backgroundColor: ['#17B26A', '#2D7CFF', '#F79009', '#9E77ED'],
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => ` Green Time: ${ctx.parsed}s`
            }
          }
        },
        cutout: '65%'
      }
    }));
  }

  // Phase comparison table
  const tbody = document.getElementById('signal-phase-tbody');
  if (tbody) {
    tbody.innerHTML = data.phases.map((p, i) => {
      const bGreen = data.comparison.baseline_phases[i] || 20;
      const diff = p.green_seconds - bGreen;
      const diffLabel = diff > 0 ? `+${diff}s` : (diff < 0 ? `${diff}s` : 'Equal');
      return `
        <tr>
          <td><strong>${escapeHtml(p.approach_name)}</strong></td>
          <td>${p.pcu_count} PCU</td>
          <td>${bGreen}s</td>
          <td><strong style="color:#17B26A;">${p.green_seconds}s</strong> <span class="badge ${diff > 0 ? 'b-green' : (diff < 0 ? 'b-orange' : 'b-neutral')}">${diffLabel}</span></td>
          <td>${p.estimated_delay_seconds}s</td>
        </tr>
      `;
    }).join('');
  }
}

function startJunctionSimulation(phases) {
  if (_simInterval) clearInterval(_simInterval);
  if (!phases || phases.length === 0) return;

  _currentPhaseIndex = 0;
  const lights = {
    North: document.getElementById('sim-light-north'),
    South: document.getElementById('sim-light-south'),
    East: document.getElementById('sim-light-east'),
    West: document.getElementById('sim-light-west')
  };

  const simStatus = document.getElementById('sim-active-phase-text');

  function tick() {
    const curPhase = phases[_currentPhaseIndex];
    if (simStatus) {
      simStatus.textContent = `Active Phase: ${curPhase.approach_name} (Green: ${curPhase.green_seconds}s)`;
    }

    // Set active green
    for (const [k, el] of Object.entries(lights)) {
      if (!el) continue;
      if (curPhase.approach_name.includes(k)) {
        el.style.backgroundColor = '#17B26A';
        el.style.boxShadow = '0 0 14px #17B26A';
      } else {
        el.style.backgroundColor = '#F04438';
        el.style.boxShadow = 'none';
      }
    }

    _currentPhaseIndex = (_currentPhaseIndex + 1) % phases.length;
  }

  tick();
  _simInterval = setInterval(tick, 4500); // 4.5s simulation loop tick
}
