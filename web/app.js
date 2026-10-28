// app.js — Frontend interactive logic and API integration

let currentBundle = null;

// Page Navigation
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    item.classList.add('active');

    const page = item.getAttribute('data-page');
    document.querySelectorAll('.view-section').forEach(sec => sec.style.display = 'none');
    
    const target = document.getElementById(`view-${page}`);
    if (target) {
      target.style.display = 'block';
    }

    if (page === 'saved') {
      loadSavedDatasets();
    }
  });
});

function switchUploadTab(tabName) {
  document.querySelectorAll('#view-upload .tab-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');

  document.getElementById('tab-file').style.display = tabName === 'file' ? 'block' : 'none';
  document.getElementById('tab-url').style.display = tabName === 'url' ? 'block' : 'none';
  document.getElementById('tab-sample').style.display = tabName === 'sample' ? 'block' : 'none';
}

function showLoading(msg = "Processing...") {
  document.getElementById('loading-text').innerText = msg;
  document.getElementById('loading-spinner').style.display = 'flex';
}

function hideLoading() {
  document.getElementById('loading-spinner').style.display = 'none';
}

// Drag & Drop
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');

['dragenter', 'dragover'].forEach(eventName => {
  dropzone.addEventListener(eventName, e => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
});

['dragleave', 'drop'].forEach(eventName => {
  dropzone.addEventListener(eventName, e => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
  });
});

dropzone.addEventListener('drop', e => {
  if (e.dataTransfer.files.length) {
    handleFileUpload(e.dataTransfer.files[0]);
  }
});

fileInput.addEventListener('change', e => {
  if (e.target.files.length) {
    handleFileUpload(e.target.files[0]);
  }
});

async function handleFileUpload(file) {
  showLoading(`Analyzing ${file.name} through data pipeline...`);
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/analyze/file', {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Analysis failed");
    }
    const bundle = await res.json();
    onBundleLoaded(bundle);
  } catch (err) {
    alert("Pipeline Error: " + err.message);
  } finally {
    hideLoading();
  }
}

async function ingestFromUrl() {
  const url = document.getElementById('url-input').value.trim();
  if (!url) return alert("Please enter a URL.");

  showLoading(`Fetching & ingesting data from URL...`);
  const formData = new FormData();
  formData.append('url', url);

  try {
    const res = await fetch('/api/analyze/url', {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to fetch URL");
    }
    const bundle = await res.json();
    onBundleLoaded(bundle);
  } catch (err) {
    alert("URL Ingestion Error: " + err.message);
  } finally {
    hideLoading();
  }
}

async function loadSample(samplePath) {
  showLoading(`Loading benchmark dataset: ${samplePath}...`);
  try {
    const response = await fetch(samplePath);
    const blob = await response.blob();
    const filename = samplePath.split('/').pop();
    const file = new File([blob], filename);
    await handleFileUpload(file);
  } catch (err) {
    alert("Failed to load sample: " + err.message);
    hideLoading();
  }
}

// When bundle completes
function onBundleLoaded(bundle) {
  currentBundle = bundle;

  // Update Status
  document.getElementById('session-status').innerText = `${bundle.source.filename} (${bundle.clean.n_rows_clean.toLocaleString()} rows)`;

  // Fill Profile Metrics
  document.getElementById('stat-rows').innerText = bundle.clean.n_rows_clean.toLocaleString();
  document.getElementById('stat-cols').innerText = bundle.clean.n_cols_clean;
  document.getElementById('stat-dups').innerText = bundle.profile.n_duplicates.toLocaleString();
  document.getElementById('stat-date').innerText = bundle.profile.date_column || 'None Detected';

  // Fill Profile Table
  const tbody = document.querySelector('#profile-table tbody');
  tbody.innerHTML = '';
  bundle.profile.columns.forEach(col => {
    let stats = '-';
    if (col.numeric_stats) {
      stats = `Min: ${col.numeric_stats.min} | Max: ${col.numeric_stats.max} | Mean: ${col.numeric_stats.mean}`;
    } else if (col.top_categories && col.top_categories.length) {
      stats = col.top_categories.slice(0, 3).map(c => `${c.value} (${c.count})`).join(', ');
    }

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${col.name}</strong></td>
      <td><span style="display:inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; background: rgba(99,102,241,0.15); color: #818cf8;">${col.kind}</span></td>
      <td><code>${col.inferred_dtype}</code></td>
      <td>${col.null_count} (${col.null_pct}%)</td>
      <td>${col.distinct_count}</td>
      <td style="color: var(--text-muted); font-size: 0.8rem;">${stats}</td>
    `;
    tbody.appendChild(tr);
  });

  // Fill Cleaned Data Preview Table
  const previewHead = document.querySelector('#clean-preview-table thead');
  const previewBody = document.querySelector('#clean-preview-table tbody');
  previewHead.innerHTML = `<tr>${bundle.clean.columns.map(c => `<th>${c}</th>`).join('')}</tr>`;
  previewBody.innerHTML = '';
  bundle.clean.data_preview.slice(0, 50).forEach(row => {
    const tr = document.createElement('tr');
    tr.innerHTML = bundle.clean.columns.map(c => `<td>${row[c] !== null && row[c] !== undefined ? row[c] : ''}</td>`).join('');
    previewBody.appendChild(tr);
  });

  // Render Charts
  const chartsContainer = document.getElementById('charts-container');
  chartsContainer.innerHTML = '';
  bundle.charts.forEach((chart, idx) => {
    const card = document.createElement('div');
    card.className = 'chart-card';
    card.innerHTML = `
      <div style="font-weight: 600; margin-bottom: 12px; font-size: 0.95rem;">${chart.title}</div>
      <div id="chart-plot-${idx}" style="flex: 1; min-height: 360px;"></div>
    `;
    chartsContainer.appendChild(card);

    const fig = JSON.parse(chart.figure_json);
    fig.layout.template = 'plotly_dark';
    fig.layout.paper_bgcolor = 'rgba(0,0,0,0)';
    fig.layout.plot_bgcolor = 'rgba(0,0,0,0)';
    fig.layout.autosize = true;
    Plotly.newPlot(`chart-plot-${idx}`, fig.data, fig.layout, { responsive: true, displayModeBar: false });
  });

  // Configure Forecast Dropdowns
  const dateSelect = document.getElementById('fc-date-col');
  const targetSelect = document.getElementById('fc-target-col');
  dateSelect.innerHTML = '';
  targetSelect.innerHTML = '';

  bundle.profile.columns.forEach(c => {
    if (c.kind === 'numeric') {
      const opt = document.createElement('option');
      opt.value = c.name;
      opt.innerText = c.name;
      targetSelect.appendChild(opt);
    }
    if (c.kind === 'date' || c.inferred_dtype.includes('datetime')) {
      const opt = document.createElement('option');
      opt.value = c.name;
      opt.innerText = c.name;
      dateSelect.appendChild(opt);
    }
  });

  if (bundle.profile.date_column) {
    dateSelect.value = bundle.profile.date_column;
  }

  // Render Forecast Charts
  renderForecastCharts(bundle.forecast_charts);

  // Insights List
  const insightsList = document.getElementById('insights-list');
  insightsList.innerHTML = '';
  bundle.insights.forEach(text => {
    const div = document.createElement('div');
    div.className = 'insight-item';
    div.innerHTML = `
      <div class="insight-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
      </div>
      <div>${text}</div>
    `;
    insightsList.appendChild(div);
  });

  // Refresh Report Preview iframe
  document.getElementById('report-frame').src = '/api/report/preview?' + new Date().getTime();

  // Navigate to Data Profile automatically
  document.querySelector('.nav-item[data-page="profile"]').click();
}

function renderForecastCharts(forecastCharts) {
  const container = document.getElementById('forecast-charts-container');
  container.innerHTML = '';
  forecastCharts.forEach((chart, idx) => {
    const card = document.createElement('div');
    card.className = 'chart-card';
    card.innerHTML = `
      <div style="font-weight: 600; margin-bottom: 12px; font-size: 0.95rem;">${chart.title}</div>
      <div id="fc-plot-${idx}" style="flex: 1; min-height: 360px;"></div>
    `;
    container.appendChild(card);

    const fig = JSON.parse(chart.figure_json);
    fig.layout.template = 'plotly_dark';
    fig.layout.paper_bgcolor = 'rgba(0,0,0,0)';
    fig.layout.plot_bgcolor = 'rgba(0,0,0,0)';
    fig.layout.autosize = true;
    Plotly.newPlot(`fc-plot-${idx}`, fig.data, fig.layout, { responsive: true, displayModeBar: false });
  });
}

async function triggerRecalculateForecast() {
  const dateCol = document.getElementById('fc-date-col').value;
  const targetCol = document.getElementById('fc-target-col').value;
  const horizon = document.getElementById('fc-horizon').value;

  if (!dateCol || !targetCol) {
    return alert("Please select a date column and a numeric target column.");
  }

  showLoading("Recalculating ARIMA time-series models...");
  const formData = new FormData();
  formData.append('date_col', dateCol);
  formData.append('target_col', targetCol);
  formData.append('horizon', horizon);

  try {
    const res = await fetch('/api/forecast/recalculate', {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Forecasting failed");
    }
    const bundle = await res.json();
    currentBundle = bundle;
    renderForecastCharts(bundle.forecast_charts);
    alert("Forecast updated successfully!");
  } catch (err) {
    alert("Forecast error: " + err.message);
  } finally {
    hideLoading();
  }
}

async function showSaveModal() {
  if (!currentBundle) return alert("No active dataset loaded.");
  const name = prompt("Enter a label or title for saving this dataset in SQLite:", currentBundle.source.filename);
  if (!name) return;

  showLoading("Saving dataset and clean table to SQLite...");
  const formData = new FormData();
  formData.append('dataset_name', name);

  try {
    const res = await fetch('/api/save', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    alert(`Dataset successfully saved! Record ID: ${data.dataset_id}`);
  } catch (err) {
    alert("Save failed: " + err.message);
  } finally {
    hideLoading();
  }
}

async function loadSavedDatasets() {
  try {
    const res = await fetch('/api/saved');
    const datasets = await res.json();
    const tbody = document.querySelector('#saved-datasets-table tbody');
    tbody.innerHTML = '';

    datasets.forEach(ds => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>#${ds.id}</td>
        <td><strong>${ds.name}</strong></td>
        <td><span style="padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; background: rgba(99,102,241,0.15); color: #818cf8;">${ds.source_format}</span></td>
        <td>${ds.n_rows_clean.toLocaleString()}</td>
        <td>${ds.n_cols_clean}</td>
        <td style="color: var(--text-muted); font-size: 0.8rem;">${new Date(ds.created_at).toLocaleString()}</td>
        <td>
          <button class="btn btn-danger" style="padding: 4px 10px; font-size: 0.75rem;" onclick="deleteSavedDataset(${ds.id})">Delete</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Could not fetch saved datasets", err);
  }
}

async function deleteSavedDataset(id) {
  if (!confirm(`Are you sure you want to delete dataset #${id}?`)) return;
  showLoading("Deleting dataset...");
  try {
    await fetch(`/api/saved/${id}`, { method: 'DELETE' });
    loadSavedDatasets();
  } catch (err) {
    alert("Delete error: " + err.message);
  } finally {
    hideLoading();
  }
}
