/**
 * Emergency Vehicle Signal Preemption Simulation Module
 */
import { fetchApi } from './api.js';
import { escapeHtml, showToast } from './utils.js';

export async function initEmergency() {
  const triggerBtn = document.getElementById('em-trigger-btn');
  const simBadge = document.getElementById('em-sim-badge');

  if (simBadge) {
    simBadge.innerHTML = `<span class="badge b-orange"><span class="dot-status warning"></span> SIMULATED EVENT MODE</span>`;
  }

  if (triggerBtn) {
    triggerBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      await triggerSimulation();
    });
  }

  await loadEmergencyEventHistory();
}

async function triggerSimulation() {
  const approach = document.getElementById('em-approach-select')?.value || 'North';
  const vehicleType = document.getElementById('em-vehicle-type')?.value || 'Ambulance';
  const etaSec = parseInt(document.getElementById('em-eta-input')?.value || 25);
  const currentPhase = document.getElementById('em-current-phase')?.value || 'East';

  try {
    const res = await fetchApi('/api/signal/emergency', {
      method: 'POST',
      body: {
        approach,
        vehicle_type: vehicleType,
        eta_seconds: etaSec,
        current_active_phase: currentPhase
      }
    });

    if (res.success) {
      renderPreemptionPlan(res);
      await loadEmergencyEventHistory();
      showToast('success', 'Preemption Planned', `Clearance-compliant preemption sequence activated for ${vehicleType}.`);
    }
  } catch (err) {
    showToast('error', 'Preemption Error', err.message || 'Simulation error');
  }
}

function renderPreemptionPlan(plan) {
  const decisionEl = document.getElementById('em-decision-display');
  const rationaleEl = document.getElementById('em-rationale-display');
  const timelineEl = document.getElementById('em-timeline-container');

  if (decisionEl) decisionEl.textContent = plan.decision;
  if (rationaleEl) rationaleEl.textContent = plan.rationale;

  if (timelineEl && plan.timeline) {
    timelineEl.innerHTML = plan.timeline.map(step => {
      let dotColor = '#17B26A';
      if (step.state.includes('YELLOW')) dotColor = '#F79009';
      if (step.state.includes('ALL_RED')) dotColor = '#F04438';
      if (step.state.includes('PREEMPTION')) dotColor = '#17B26A';
      if (step.state.includes('RESTORE')) dotColor = '#2D7CFF';

      return `
        <div class="tl-item" style="display:flex; gap:12px; margin-bottom:12px;">
          <div style="width:12px; height:12px; border-radius:6px; background:${dotColor}; margin-top:4px; flex-shrink:0;"></div>
          <div>
            <div style="font-weight:700; font-size:12.5px; color:${dotColor};">
              T+${step.t_offset}s · ${escapeHtml(step.state)} (${step.duration}s)
            </div>
            <div style="font-size:12px; color:#334155; margin-top:2px;">
              ${escapeHtml(step.description)}
            </div>
          </div>
        </div>
      `;
    }).join('');
  }
}

async function loadEmergencyEventHistory() {
  const tbody = document.getElementById('em-events-tbody');
  if (!tbody) return;

  try {
    const res = await fetchApi('/api/emergency/events');
    if (!res.success || !res.events) return;

    if (res.events.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:18px;">No emergency events logged yet. Trigger a simulation above.</td></tr>`;
      return;
    }

    tbody.innerHTML = res.events.map(ev => `
      <tr>
        <td class="mono">#${ev.id}</td>
        <td>${escapeHtml(ev.timestamp)}</td>
        <td><strong>${escapeHtml(ev.vehicle_type)}</strong></td>
        <td>${escapeHtml(ev.approach)} (ETA: ${ev.eta_seconds}s)</td>
        <td><span class="badge b-blue">${escapeHtml(ev.decision)}</span></td>
        <td><span class="badge b-orange">${escapeHtml(ev.source.toUpperCase())}</span></td>
      </tr>
    `).join('');
  } catch (err) {
    console.warn('[Emergency] History error:', err);
  }
}
