let currentData = null;
let charts = {};

document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  setupFileLoader();
  setupFilters();
});

function setupNavigation() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const view = item.getAttribute('data-view');
      showView(view);
    });
  });
}

function showView(viewName) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.view').forEach(el => el.classList.remove('active'));

  const navEl = document.getElementById(`nav-${viewName}`);
  const viewEl = document.getElementById(`view-${viewName}`);

  if (navEl) navEl.classList.add('active');
  if (viewEl) viewEl.classList.add('active');

  const titleMap = {
    overview: 'Dashboard Overview',
    comparison: 'Provider Comparison',
    leaderboard: 'Model Leaderboard',
    categories: 'Category Analysis',
    heatmap: 'Failure Heatmap',
    timeline: 'Historical Trends',
    runs: 'Run Explorer',
    evidence: 'Evidence Chain',
    cost: 'Cost Analysis'
  };
  document.getElementById('page-title').innerText = titleMap[viewName] || 'Dashboard';
}

function setupFileLoader() {
  const fileInput = document.getElementById('file-input');
  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        currentData = JSON.parse(event.target.result);
        renderDashboard(currentData);
        document.getElementById('empty-state').style.display = 'none';
      } catch (err) {
        alert('Failed to parse JSON fixture: ' + err.message);
      }
    };
    reader.readAsText(file);
  });
}

function renderDashboard(data) {
  document.getElementById('run-badge').innerText = `Run ID: ${data.run_id}`;
  renderKPIs(data);
  renderRecentTable(data);
  renderLeaderboard(data);
  renderRunExplorer(data);
  renderCharts(data);
}

function renderKPIs(data) {
  const metrics = data.metrics || {};
  const verdicts = data.verdicts || [];

  const pass = verdicts.filter(v => v.status === 'pass').length;
  const fail = verdicts.filter(v => v.status === 'fail').length;
  const warn = verdicts.filter(v => v.status === 'warn').length;
  const total = verdicts.length;

  document.getElementById('chip-pass-count').innerText = pass;
  document.getElementById('chip-fail-count').innerText = fail;
  document.getElementById('chip-warn-count').innerText = warn;

  document.getElementById('kpi-runs').innerText = total;
  const passRate = total > 0 ? ((pass / total) * 100).toFixed(1) + '%' : '0%';
  document.getElementById('kpi-pass-rate').innerText = passRate;

  document.getElementById('kpi-tokens').innerText = (metrics.total_tokens || 0).toLocaleString();
  document.getElementById('kpi-cost').innerText = '$' + (metrics.total_cost_usd || 0).toFixed(4);
  document.getElementById('kpi-latency').innerText = (metrics.p50_latency_ms || 0) + ' ms';
}

function renderRecentTable(data) {
  const tbody = document.getElementById('tbody-recent');
  tbody.innerHTML = '';

  const executions = (data.executions || []).slice(0, 10);
  const verdictsMap = {};
  (data.verdicts || []).forEach(v => verdictsMap[v.execution_id] = v);

  executions.forEach(exec => {
    const tr = document.createElement('tr');
    const v = verdictsMap[exec.execution_id] || { status: 'unknown' };
    tr.innerHTML = `
      <td><code>${exec.test_case_id}</code></td>
      <td>${exec.category}</td>
      <td>${exec.provider || '-'}</td>
      <td>${exec.model || '-'}</td>
      <td>${exec.latency_ms ? exec.latency_ms + ' ms' : '-'}</td>
      <td><span class="badge-verdict badge-${v.status}">${v.status}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderLeaderboard(data) {
  const tbody = document.getElementById('tbody-leaderboard');
  tbody.innerHTML = '';

  const modelStats = {};
  const verdictsMap = {};
  (data.verdicts || []).forEach(v => verdictsMap[v.execution_id] = v);

  (data.executions || []).forEach(exec => {
    if (!exec.model) return;
    if (!modelStats[exec.model]) {
      modelStats[exec.model] = {
        model: exec.model,
        provider: exec.provider,
        pass: 0,
        fail: 0,
        total: 0,
        latencies: [],
        tokens: 0
      };
    }
    const stats = modelStats[exec.model];
    stats.total++;
    const v = verdictsMap[exec.execution_id];
    if (v && v.status === 'pass') stats.pass++;
    else stats.fail++;

    if (exec.latency_ms) stats.latencies.push(exec.latency_ms);
    if (exec.input_tokens) stats.tokens += (exec.input_tokens + (exec.output_tokens || 0));
  });

  const sorted = Object.values(modelStats).sort((a, b) => (b.pass / b.total) - (a.pass / a.total));

  sorted.forEach((stat, idx) => {
    const passRate = ((stat.pass / stat.total) * 100).toFixed(1) + '%';
    const avgLat = stat.latencies.length > 0
      ? Math.round(stat.latencies.reduce((a, b) => a + b, 0) / stat.latencies.length) + ' ms'
      : '-';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>#${idx + 1}</td>
      <td><strong>${stat.model}</strong></td>
      <td>${stat.provider}</td>
      <td>${stat.pass}</td>
      <td>${stat.fail}</td>
      <td>${passRate}</td>
      <td>${avgLat}</td>
      <td>${stat.tokens.toLocaleString()}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderRunExplorer(data) {
  const tbody = document.getElementById('tbody-runs');
  tbody.innerHTML = '';

  const verdictsMap = {};
  (data.verdicts || []).forEach(v => verdictsMap[v.execution_id] = v);

  (data.executions || []).forEach(exec => {
    const v = verdictsMap[exec.execution_id] || { status: 'unknown' };
    const tr = document.createElement('tr');
    tr.setAttribute('data-category', exec.category);
    tr.setAttribute('data-verdict', v.status);
    tr.setAttribute('data-provider', exec.provider || '');

    tr.innerHTML = `
      <td><code>${exec.test_case_id}</code></td>
      <td>${exec.category}</td>
      <td>${exec.provider || '-'}</td>
      <td>${exec.model || '-'}</td>
      <td>${exec.status}</td>
      <td>${exec.latency_ms ? exec.latency_ms + ' ms' : '-'}</td>
      <td>${(exec.input_tokens || 0) + (exec.output_tokens || 0)}</td>
      <td><span class="badge-verdict badge-${v.status}">${v.status}</span></td>
      <td><button onclick="viewDetail('${exec.execution_id}')" style="background:none;border:none;color:var(--accent-cyan);cursor:pointer;">View</button></td>
    `;
    tbody.appendChild(tr);
  });
}

function setupFilters() {
  const searchInput = document.getElementById('filter-runs');
  const verdictSelect = document.getElementById('filter-verdict');
  const providerSelect = document.getElementById('filter-provider');

  const filterFn = () => {
    const text = searchInput.value.toLowerCase();
    const verdict = verdictSelect.value;
    const provider = providerSelect.value;

    document.querySelectorAll('#tbody-runs tr').forEach(row => {
      const matchText = row.innerText.toLowerCase().includes(text);
      const matchVerdict = !verdict || row.getAttribute('data-verdict') === verdict;
      const matchProvider = !provider || row.getAttribute('data-provider') === provider;

      row.style.display = (matchText && matchVerdict && matchProvider) ? '' : 'none';
    });
  };

  searchInput.addEventListener('input', filterFn);
  verdictSelect.addEventListener('change', filterFn);
  providerSelect.addEventListener('change', filterFn);
}

function renderCharts(data) {
  const verdicts = data.verdicts || [];
  const pass = verdicts.filter(v => v.status === 'pass').length;
  const fail = verdicts.filter(v => v.status === 'fail').length;
  const warn = verdicts.filter(v => v.status === 'warn').length;

  if (charts.donut) charts.donut.destroy();
  const ctxDonut = document.getElementById('chart-donut').getContext('2d');
  charts.donut = new Chart(ctxDonut, {
    type: 'doughnut',
    data: {
      labels: ['Pass', 'Fail', 'Warn'],
      datasets: [{
        data: [pass, fail, warn],
        backgroundColor: ['#4ade80', '#f87171', '#fbbf24']
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { position: 'bottom', labels: { color: '#f8fafc' } } }
    }
  });
}
