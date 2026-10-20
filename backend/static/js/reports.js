/**
 * Real PDF & CSV Report Generation Module
 */
import { fetchApi } from './api.js';
import { showToast } from './utils.js';

export function initReports() {
  const genBtn = document.getElementById('report-generate-btn');
  const genCsvBtn = document.getElementById('report-generate-csv-btn');

  if (genBtn) {
    genBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const area = document.getElementById('report-area-select')?.value || '';
      const year = document.getElementById('report-year-select')?.value || '';
      downloadReport('pdf', area, year);
    });
  }

  if (genCsvBtn) {
    genCsvBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const area = document.getElementById('report-area-select')?.value || '';
      const year = document.getElementById('report-year-select')?.value || '';
      downloadReport('csv', area, year);
    });
  }
}

function downloadReport(format, area, year) {
  const q = new URLSearchParams({
    format,
    area,
    year
  }).toString();

  showToast('info', 'Generating Report', `Compiling live ${format.toUpperCase()} safety audit from SQLite data...`);
  window.location.href = `/api/reports/generate?${q}`;
}
