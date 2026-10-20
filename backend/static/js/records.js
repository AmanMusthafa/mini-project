/**
 * Incident Records Management (CRUD) Module
 */
import { fetchApi } from './api.js';
import { escapeHtml, showToast } from './utils.js';

let _page = 1;
const _pageSize = 15;

export async function initRecords() {
  const searchInput = document.getElementById('records-search-input');
  const addBtn = document.getElementById('records-add-btn');
  const exportBtn = document.getElementById('records-export-csv-btn');
  const prevBtn = document.getElementById('records-prev-page');
  const nextBtn = document.getElementById('records-next-page');

  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        _page = 1;
        loadRecords(searchInput.value.trim());
      }, 350);
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (_page > 1) {
        _page--;
        loadRecords(searchInput ? searchInput.value.trim() : '');
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      _page++;
      loadRecords(searchInput ? searchInput.value.trim() : '');
    });
  }

  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      window.location.href = '/api/records/export';
      showToast('success', 'Exporting CSV', 'Downloading verified incident records.');
    });
  }

  if (addBtn) {
    addBtn.addEventListener('click', () => {
      showAddRecordModal();
    });
  }

  await loadRecords();
}

async function loadRecords(search = '') {
  const tbody = document.getElementById('records-table-tbody');
  const pageLabel = document.getElementById('records-page-indicator');
  if (!tbody) return;

  const q = new URLSearchParams({
    page: _page,
    page_size: _pageSize,
    search: search
  }).toString();

  try {
    const res = await fetchApi(`/api/records?${q}`);
    if (!res.success) return;

    if (pageLabel) {
      pageLabel.textContent = `Page ${res.page} of ${res.total_pages || 1} (${res.total.toLocaleString()} records)`;
    }

    if (res.records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:24px;">No records match your search.</td></tr>`;
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
          <td>${escapeHtml(r.cause.toUpperCase())}</td>
          <td>${escapeHtml(r.casualties)}</td>
          <td><span class="badge b-neutral">${escapeHtml(r.data_source)}</span></td>
          <td>
            <button class="btn btn-sm btn-secondary edit-rec-btn" data-id="${r.id}" data-uid="${r.accident_uid}" data-sev="${r.severity}" data-cause="${r.cause}" style="padding:3px 8px; font-size:11px;">Edit</button>
            <button class="btn btn-sm btn-secondary delete-rec-btn" data-id="${r.id}" style="padding:3px 8px; font-size:11px; color:#F04438;">Del</button>
          </td>
        </tr>
      `;
    }).join('');

    // Bind action buttons
    document.querySelectorAll('.edit-rec-btn').forEach(b => {
      b.addEventListener('click', () => {
        showEditRecordModal(b.dataset.id, b.dataset.uid, b.dataset.sev, b.dataset.cause);
      });
    });

    document.querySelectorAll('.delete-rec-btn').forEach(b => {
      b.addEventListener('click', async () => {
        if (confirm(`Are you sure you want to delete incident record #${b.dataset.id}?`)) {
          try {
            const delRes = await fetchApi(`/api/records/${b.dataset.id}`, { method: 'DELETE' });
            if (delRes.success) {
              showToast('success', 'Record Deleted', `Record #${b.dataset.id} removed from database.`);
              loadRecords(search);
            }
          } catch (err) {
            showToast('error', 'Delete Failed', err.message);
          }
        }
      });
    });

  } catch (err) {
    console.warn('[Records] Load error:', err);
  }
}

function showAddRecordModal() {
  const modal = document.getElementById('record-crud-modal');
  if (!modal) return;

  modal.style.display = 'flex';
  const form = document.getElementById('record-crud-form');
  if (form) {
    form.reset();
    form.onsubmit = async (e) => {
      e.preventDefault();
      const payload = {
        area: document.getElementById('modal-rec-area')?.value || 'Edappally',
        road_name: document.getElementById('modal-rec-road')?.value || 'NH 66 Bypass',
        severity: document.getElementById('modal-rec-sev')?.value || 'minor',
        cause: document.getElementById('modal-rec-cause')?.value || 'distraction',
        casualties: parseInt(document.getElementById('modal-rec-cas')?.value || 0),
        vehicles_involved: parseInt(document.getElementById('modal-rec-veh')?.value || 1)
      };

      try {
        const res = await fetchApi('/api/records', {
          method: 'POST',
          body: payload
        });
        if (res.success) {
          modal.style.display = 'none';
          showToast('success', 'Incident Created', `Recorded ${res.accident_uid} successfully.`);
          loadRecords();
        }
      } catch (err) {
        showToast('error', 'Creation Failed', err.message);
      }
    };
  }
}

function showEditRecordModal(id, uid, currSev, currCause) {
  const modal = document.getElementById('record-crud-modal');
  if (!modal) return;

  modal.style.display = 'flex';
  document.getElementById('modal-rec-sev').value = currSev;
  document.getElementById('modal-rec-cause').value = currCause;

  const form = document.getElementById('record-crud-form');
  if (form) {
    form.onsubmit = async (e) => {
      e.preventDefault();
      const payload = {
        severity: document.getElementById('modal-rec-sev')?.value || 'minor',
        cause: document.getElementById('modal-rec-cause')?.value || 'distraction',
        casualties: parseInt(document.getElementById('modal-rec-cas')?.value || 0),
        vehicles_involved: parseInt(document.getElementById('modal-rec-veh')?.value || 1)
      };

      try {
        const res = await fetchApi(`/api/records/${id}`, {
          method: 'PUT',
          body: payload
        });
        if (res.success) {
          modal.style.display = 'none';
          showToast('success', 'Incident Updated', `Record ${uid} updated.`);
          loadRecords();
        }
      } catch (err) {
        showToast('error', 'Update Failed', err.message);
      }
    };
  }
}
