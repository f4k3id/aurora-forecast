from __future__ import annotations
from datetime import datetime

from flask import Flask, Response, jsonify

from ..config import WEB_HOST, WEB_PORT, APP_NAME, VERSION, POLL_INTERVAL_MINUTES
from ..scheduler import get_state, force_refresh, start_scheduler, get_activity_history_for_ui
from ..store import get_recent_kp_for_chart

app = Flask(__name__)

# In-memory for language (per process; browser localStorage will persist UI choice)
# We serve a self-contained HTML + JS app (Tailwind CDN + Chart.js)

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AurorA • Prévisions Aurores Boréales</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&amp;family=Space+Grotesk:wght@500;600&amp;display=swap');
    :root { --font-sans: 'Inter', system_ui, sans-serif; }
    body { font-family: 'Inter', system_ui, -apple-system, sans-serif; }
    .font-display { font-family: 'Space Grotesk', 'Inter', system_ui, sans-serif; }
    .aurora-bg {
      background: linear-gradient(135deg, #0f172a 0%, #1e1135 100%);
    }
    .status-card {
      transition: transform .2s cubic-bezier(0.4,0,0.2,1), box-shadow .2s;
    }
    .status-card:hover { transform: translateY(-2px); }
    .level-quiet { background-color: #166534; color: #86efac; }
    .level-unsettled { background-color: #854d0e; color: #fde047; }
    .level-active { background-color: #9a3412; color: #fdba74; }
    .level-stormy { background-color: #9f1239; color: #fda4af; animation: pulse 2s infinite; }
    .kp-value { font-variant-numeric: tabular-nums; }
    .section-title { letter-spacing: -.025em; }
    .data-table td { padding-top: .35rem; padding-bottom: .35rem; }
  </style>
</head>
<body class="aurora-bg text-slate-200">
  <div class="max-w-5xl mx-auto px-4 py-8">
    <!-- Header -->
    <div class="flex items-center justify-between mb-8">
      <div class="flex items-center gap-x-4">
        <div class="w-11 h-11 rounded-2xl bg-gradient-to-br from-violet-400 to-cyan-400 flex items-center justify-center text-slate-950 text-3xl shadow-inner">🌌</div>
        <div>
          <div class="font-display text-4xl font-semibold tracking-tighter">AurorA</div>
          <div class="text-xs text-slate-400 -mt-1">RNCan + NOAA • local</div>
        </div>
      </div>

      <div class="flex items-center gap-x-3">
        <!-- Language -->
        <div class="flex rounded-2xl bg-slate-800/60 p-1 text-sm">
          <button onclick="setLang('en')" id="btn-en"
                  class="px-4 py-1.5 rounded-[14px] font-medium transition active:scale-[0.985]">EN</button>
          <button onclick="setLang('fr')" id="btn-fr"
                  class="px-4 py-1.5 rounded-[14px] font-medium transition active:scale-[0.985]">FR</button>
        </div>

        <button onclick="manualRefresh()"
                class="flex items-center gap-x-2 px-4 py-2 rounded-2xl bg-white/10 hover:bg-white/15 active:bg-white/20 transition text-sm font-medium">
          <span>⟳</span>
          <span data-i18n="refresh">Refresh</span>
        </button>

        <div class="text-xs px-3 py-2 rounded-2xl bg-slate-800/70 font-mono text-emerald-400" id="last-updated">
          — 
        </div>
      </div>
    </div>

    <!-- Status Overview -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
      <!-- Kp Card -->
      <div class="status-card rounded-3xl bg-slate-900/70 border border-white/10 p-6">
        <div class="flex justify-between items-start">
          <div>
            <div class="text-sm text-slate-400 mb-1" data-i18n="current_kp">Current Kp Index (NOAA)</div>
            <div class="flex items-baseline gap-x-2">
              <div id="kp-value" class="text-6xl font-semibold kp-value tabular-nums tracking-tighter">—</div>
              <div id="kp-time" class="text-xs text-slate-500 font-mono"></div>
            </div>
          </div>
          <div id="kp-badge" 
               class="px-4 py-1.5 rounded-2xl text-sm font-semibold self-start bg-slate-800 text-slate-300">—</div>
        </div>
        <div class="mt-4 text-xs text-slate-400" data-i18n="kp_desc">
          Planetary geomagnetic activity (3-hourly). Higher = stronger auroral potential.
        </div>
      </div>

      <!-- Main RNCan Status -->
      <div class="status-card rounded-3xl bg-slate-900/70 border border-white/10 p-6">
        <div class="text-sm text-slate-400 mb-3" data-i18n="auroral_zone">Auroral Zone (RNCan)</div>
        
        <div class="flex items-center gap-x-3 mb-4">
          <div id="main-level-badge"
               class="px-5 py-1 rounded-2xl font-semibold text-lg inline-flex items-center">—</div>
          <div id="main-level-desc" class="text-slate-300 text-sm"></div>
        </div>

        <div class="grid grid-cols-3 gap-2 text-center text-xs">
          <div>
            <div class="text-[10px] text-slate-400" data-i18n="next_6h">Next 6h</div>
            <div id="aur-next6" class="font-semibold mt-0.5">—</div>
          </div>
          <div>
            <div class="text-[10px] text-slate-400" data-i18n="next_24h">Next 24h</div>
            <div id="aur-next24" class="font-semibold mt-0.5">—</div>
          </div>
          <div>
            <div class="text-[10px] text-slate-400" data-i18n="last_6h">Last 6h</div>
            <div id="aur-last6" class="font-semibold mt-0.5">—</div>
          </div>
        </div>
      </div>
    </div>

    <!-- All Zones -->
    <div class="mb-8">
      <div class="flex items-center justify-between mb-3 px-1">
        <div class="font-semibold text-sm tracking-tight section-title" data-i18n="zones_forecast">Zones Forecast (RNCan)</div>
        <div class="text-[10px] text-slate-400" id="rncan-issued"></div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3" id="zones-grid">
        <!-- Populated by JS -->
      </div>
    </div>

    <!-- KP INDEX — LAST 7 DAYS (NOAA) -->
    <div class="rounded-3xl bg-slate-900/70 border border-white/10 p-6 mb-8">
      <div class="flex items-center justify-between mb-4">
        <div>
          <div class="font-semibold text-sm tracking-tight section-title">KP INDEX — LAST 7 DAYS (NOAA)</div>
          <div class="text-xs text-slate-400">3-hourly planetary K-index (full recent history from NOAA SWPC)</div>
        </div>
        <div class="text-xs px-3 py-1 rounded-2xl bg-slate-800/80 text-slate-300">7-day view</div>
      </div>
      <div class="relative h-64">
        <canvas id="kp-7d-chart"></canvas>
      </div>
      <div class="flex justify-between text-[10px] text-slate-400 mt-2 px-1">
        <div>Quiet (Kp &lt; 4)</div>
        <div>Storm levels (Kp ≥ 5)</div>
      </div>
    </div>

    <!-- 24h Kp Chart -->
    <div class="rounded-3xl bg-slate-900/70 border border-white/10 p-6 mb-8">
      <div class="flex items-center justify-between mb-4">
        <div>
          <div class="font-semibold text-sm tracking-tight section-title" data-i18n="kp_history">Kp Index — Last 24h+</div>
          <div class="text-xs text-slate-400" data-i18n="kp_history_sub">3-hourly values from NOAA</div>
        </div>
        <div class="text-xs px-3 py-1 rounded-2xl bg-slate-800/80 text-slate-300">NOAA SWPC</div>
      </div>
      <div class="relative h-64">
        <canvas id="kp-chart"></canvas>
      </div>
      <div class="flex justify-between text-[10px] text-slate-400 mt-2 px-1">
        <div data-i18n="kp_low">Quiet (Kp &lt; 4)</div>
        <div data-i18n="kp_storm">Storm levels (Kp ≥ 5)</div>
      </div>
    </div>

    <!-- RNCan Official Maps -->
    <div id="maps-section" class="rounded-3xl bg-slate-900/70 border border-white/10 p-6 mb-8 hidden">
      <div class="font-semibold text-sm tracking-tight section-title mb-4" data-i18n="maps_title">Cartes officielles RNCan</div>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" id="maps-grid">
        <!-- populated by JS -->
      </div>
      <div class="text-[10px] text-slate-400 mt-3">Images directement depuis Space Weather Canada</div>
    </div>

    <!-- Footer / Info -->
    <div class="flex flex-wrap items-center gap-x-4 text-xs text-slate-400 px-1">
      <div>
        <span data-i18n="sync_every">Sync every</span> <span class="font-mono text-emerald-400">{{poll}} min</span>
      </div>
      <div class="hidden sm:block">•</div>
      <div>
        <a href="https://www.spaceweather.gc.ca/forecast-prevision/short-court/zone-en.php" target="_blank" class="hover:text-slate-200 underline decoration-dotted">RNCan source</a>
        <span class="mx-1">·</span>
        <a href="https://www.swpc.noaa.gov/products/planetary-k-index" target="_blank" class="hover:text-slate-200 underline decoration-dotted">NOAA Kp</a>
      </div>
      <div class="flex-1"></div>
      <div class="font-mono text-[10px] opacity-60">v{{version}} • local only</div>
    </div>
  </div>

<script>
const I18N = {
  en: {
    current_kp: "Current Kp Index (NOAA)",
    kp_desc: "Planetary geomagnetic activity (3-hourly). Higher = stronger auroral potential.",
    auroral_zone: "Auroral Zone (RNCan)",
    next_6h: "Next 6h",
    next_24h: "Next 24h",
    last_6h: "Last 6h",
    zones_forecast: "Zones Forecast (RNCan)",
    kp_history: "Kp Index — Last 24h+",
    kp_history_sub: "3-hourly values from NOAA",
    kp_low: "Quiet (Kp < 4)",
    kp_storm: "Storm levels (Kp ≥ 5)",
    maps_title: "Official RNCan Maps",
    sync_every: "Sync every",
    refresh: "Refresh",
    stormy: "Stormy",
    active: "Active",
    unsettled: "Unsettled",
    quiet: "Quiet",
    polar: "Polar",
    auroral: "Auroral",
    subauroral: "Sub-Auroral",
  },
  fr: {
    current_kp: "Indice Kp actuel (NOAA)",
    kp_desc: "Activité géomagnétique planétaire (toutes les 3h). Plus élevé = plus fortes aurores possibles.",
    auroral_zone: "Zone Aurorale (RNCan)",
    next_6h: "6h prochaines",
    next_24h: "24h prochaines",
    last_6h: "6h passées",
    zones_forecast: "Prévisions par zone (RNCan)",
    kp_history: "Indice Kp — 24h+",
    kp_history_sub: "Valeurs toutes les 3 heures (NOAA)",
    kp_low: "Calme (Kp < 4)",
    kp_storm: "Niveaux orageux (Kp ≥ 5)",
    maps_title: "Cartes officielles RNCan",
    sync_every: "Synchro toutes les",
    refresh: "Actualiser",
    stormy: "Orageuse",
    active: "Active",
    unsettled: "Agitée",
    quiet: "Calme",
    polar: "Polaire",
    auroral: "Aurorale",
    subauroral: "Sub-Aurorale",
  }
};

let currentLang = localStorage.getItem('aurora_lang') || 'en';
let chartInstance = null;

function t(key) {
  return I18N[currentLang][key] || key;
}

function setLang(lang) {
  currentLang = lang;
  localStorage.setItem('aurora_lang', lang);
  document.getElementById('btn-en').classList.toggle('bg-white/90', lang === 'en');
  document.getElementById('btn-en').classList.toggle('text-slate-950', lang === 'en');
  document.getElementById('btn-fr').classList.toggle('bg-white/90', lang === 'fr');
  document.getElementById('btn-fr').classList.toggle('text-slate-950', lang === 'fr');
  applyI18n();
  renderAll();
}

function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const txt = I18N[currentLang] && I18N[currentLang][key];
    if (txt) el.textContent = txt;
  });
}

function levelClass(level) {
  if (!level) return 'bg-slate-700 text-slate-300';
  const l = level.toLowerCase();
  if (l === 'stormy' || l.includes('orage')) return 'level-stormy';
  if (l === 'active') return 'level-active';
  if (l === 'unsettled' || l.includes('agit')) return 'level-unsettled';
  return 'level-quiet';
}

function levelText(level) {
  const map = { stormy: t('stormy'), active: t('active'), unsettled: t('unsettled'), quiet: t('quiet') };
  const key = (level || '').toLowerCase().replace(/[^a-z]/g,'');
  return map[key] || (level || '—');
}

function renderZones(rncan) {
  const container = document.getElementById('zones-grid');
  container.innerHTML = '';

  if (!rncan || !rncan.zones) {
    container.innerHTML = `<div class="col-span-3 text-slate-400 text-sm px-2">No data yet. Click Refresh.</div>`;
    return;
  }

  const order = ['subauroral', 'auroral', 'polar'];
  order.forEach(zkey => {
    const z = rncan.zones[zkey] || {};
    // Always render Sub-Auroral first, even with placeholder data

    const div = document.createElement('div');
    div.className = `rounded-3xl border border-white/10 p-4 bg-slate-950/50`;
    
    const zoneLabel = t(zkey);
    const n6 = z.next_6h || '—';
    const n24 = z.next_24h || '—';
    const l6 = z.last_6h || '—';

    div.innerHTML = `
      <div class="font-semibold mb-3 flex items-center justify-between">
        <span>${zoneLabel}</span>
        <span class="text-[10px] px-2 py-0.5 rounded-xl bg-white/5">${zkey}</span>
      </div>
      <div class="space-y-2 text-sm">
        <div class="flex justify-between items-center">
          <span class="text-xs text-slate-400 w-16">${t('next_6h')}</span>
          <span class="px-3 py-0.5 rounded-2xl font-medium ${levelClass(n6)}">${levelText(n6)}</span>
        </div>
        <div class="flex justify-between items-center">
          <span class="text-xs text-slate-400 w-16">${t('next_24h')}</span>
          <span class="px-3 py-0.5 rounded-2xl font-medium ${levelClass(n24)}">${levelText(n24)}</span>
        </div>
        <div class="flex justify-between items-center pt-1 border-t border-white/10">
          <span class="text-xs text-slate-400 w-16">${t('last_6h')}</span>
          <span class="text-slate-300 font-medium">${levelText(l6)}</span>
        </div>
      </div>
    `;
    container.appendChild(div);
  });
}

function renderMainAuroral(rncan) {
  const badge = document.getElementById('main-level-badge');
  const desc = document.getElementById('main-level-desc');

  if (!rncan || !rncan.zones || !rncan.zones.auroral) {
    badge.textContent = '—';
    badge.className = 'px-5 py-1 rounded-2xl font-semibold text-lg bg-slate-800 text-slate-300';
    desc.textContent = '';
    return;
  }

  const z = rncan.zones.auroral;
  const level = (z.next_6h || z.next_24h || '').toLowerCase();
  const cls = levelClass(level);
  badge.textContent = levelText(level);
  badge.className = `px-5 py-1 rounded-2xl font-semibold text-lg ${cls}`;

  const issued = rncan.issued_at || '';
  document.getElementById('rncan-issued').textContent = issued ? `Issued: ${issued}` : '';

  desc.textContent = `${t('next_6h')}: ${levelText(z.next_6h)}  •  ${t('next_24h')}: ${levelText(z.next_24h)}`;
}

function renderKp(latest, history) {
  const valEl = document.getElementById('kp-value');
  const timeEl = document.getElementById('kp-time');
  const badge = document.getElementById('kp-badge');

  if (!latest) {
    valEl.textContent = '—';
    timeEl.textContent = '';
    badge.textContent = '—';
    return;
  }

  valEl.textContent = latest.kp.toFixed(1);
  timeEl.textContent = latest.time_tag ? new Date(latest.time_tag).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '';

  let btext = 'Quiet', bcls = 'bg-emerald-900 text-emerald-300';
  if (latest.kp >= 5) { btext = 'Storm'; bcls = 'bg-rose-700 text-white'; }
  else if (latest.kp >= 4) { btext = 'Active'; bcls = 'bg-orange-800 text-orange-200'; }
  else if (latest.kp >= 3) { btext = 'Elevated'; bcls = 'bg-amber-800 text-amber-200'; }
  badge.textContent = btext;
  badge.className = `px-4 py-1.5 rounded-2xl text-sm font-semibold self-start ${bcls}`;
}

function renderChart(history) {
  const canvas = document.getElementById('kp-chart');
  if (!canvas) return;

  if (chartInstance) {
    chartInstance.destroy();
  }

  const labels = history.map(p => {
    const d = new Date(p.t);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  });
  const values = history.map(p => p.kp);

  chartInstance = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Kp',
        data: values,
        borderColor: '#a5b4fc',
        backgroundColor: 'rgba(165, 180, 252, 0.15)',
        borderWidth: 2.5,
        tension: 0.25,
        pointRadius: 2.5,
        pointHoverRadius: 4,
        fill: true,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
      scales: {
        y: {
          min: 0, max: 9,
          ticks: { stepSize: 1, color: '#64748b', font: {size: 10} },
          grid: { color: 'rgba(148,163,184,0.1)' }
        },
        x: {
          ticks: { color: '#64748b', font: {size: 10}, maxRotation: 0 },
          grid: { color: 'rgba(148,163,184,0.08)' }
        }
      }
    }
  });
}

function renderKp7dChart(history) {
  const canvas = document.getElementById('kp-7d-chart');
  if (!canvas) return;

  if (window.kp7dChartInstance) {
    window.kp7dChartInstance.destroy();
  }

  if (!history || history.length === 0) {
    canvas.parentElement.innerHTML = '<div class="text-slate-400 text-sm p-4">No 7-day Kp data yet. Wait for more syncs or force refresh.</div>';
    return;
  }

  const labels = history.map(p => {
    const d = new Date(p.t);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' +
           d.toLocaleTimeString([], { hour: '2-digit' });
  });
  const values = history.map(p => p.kp);

  window.kp7dChartInstance = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Kp',
        data: values,
        backgroundColor: values.map(v => {
          if (v >= 5) return '#f43f5e';
          if (v >= 4) return '#fb923c';
          if (v >= 3) return '#facc15';
          return '#4ade80';
        }),
        borderRadius: 2,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { mode: 'index', intersect: false }
      },
      scales: {
        y: {
          min: 0,
          max: 9,
          ticks: { stepSize: 1, color: '#64748b', font: { size: 9 } },
          grid: { color: 'rgba(148,163,184,0.1)' }
        },
        x: {
          ticks: { color: '#64748b', font: { size: 8 }, maxRotation: 45, autoSkip: true, maxTicksLimit: 28 },
          grid: { color: 'rgba(148,163,184,0.06)' }
        }
      }
    }
  });
}

function renderMaps(rncan) {
  const section = document.getElementById('maps-section');
  const grid = document.getElementById('maps-grid');
  if (!section || !grid) return;

  const imgs = (rncan && rncan.images) ? rncan.images : {};
  const entries = Object.entries(imgs);

  if (entries.length === 0) {
    section.classList.add('hidden');
    return;
  }
  section.classList.remove('hidden');
  grid.innerHTML = '';

  const labelMap = {
    current: 'Conditions actuelles',
    forecast_6: 'Prévision 6h',
    forecast_24: 'Prévision 24h',
    chart: 'Graphique zonal'
  };

  entries.forEach(([key, url]) => {
    const div = document.createElement('div');
    div.className = 'rounded-2xl overflow-hidden border border-white/10 bg-slate-950/60';
    div.innerHTML = `
      <img src="${url}" class="w-full block" alt="${key}" loading="lazy" />
      <div class="px-3 py-1.5 text-[10px] text-slate-400 text-center border-t border-white/10">
        ${labelMap[key] || key}
      </div>
    `;
    grid.appendChild(div);
  });
}

let lastData = null;

async function fetchData() {
  const res = await fetch('/api/state');
  const data = await res.json();
  lastData = data;
  return data;
}

function renderAll() {
  if (!lastData) return;

  const { rncan, latest_kp, kp_history, kp_7d_history, last_fetch } = lastData;

  // Kp
  renderKp(latest_kp, kp_history);

  // Main auroral
  renderMainAuroral(rncan);

  // All zones
  renderZones(rncan);

  // Issued
  if (rncan && rncan.issued_at) {
    document.getElementById('rncan-issued').textContent = `RNCan: ${rncan.issued_at}`;
  }

  // Last updated
  const lu = document.getElementById('last-updated');
  if (last_fetch) {
    const d = new Date(last_fetch);
    lu.textContent = d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
  } else {
    lu.textContent = '—';
  }

  // Charts
  renderChart(kp_history || []);
  if (typeof renderKp7dChart === 'function') {
    renderKp7dChart(kp_7d_history || []);
  }

  // RNCan maps
  renderMaps(rncan);
}

async function manualRefresh() {
  const lu = document.getElementById('last-updated');
  lu.textContent = '...';
  try {
    const res = await fetch('/api/refresh', { method: 'POST' });
    const data = await res.json();
    lastData = data.state;
    renderAll();
  } catch (e) {
    console.error(e);
    lu.textContent = 'err';
  }
}

async function init() {
  // Language buttons state
  document.getElementById('btn-en').classList.toggle('bg-white/90', currentLang === 'en');
  document.getElementById('btn-en').classList.toggle('text-slate-950', currentLang === 'en');
  document.getElementById('btn-fr').classList.toggle('bg-white/90', currentLang === 'fr');
  document.getElementById('btn-fr').classList.toggle('text-slate-950', currentLang === 'fr');

  applyI18n();

  // Initial data
  try {
    lastData = await fetchData();
  } catch (e) {
    console.warn('Initial fetch failed, will retry on refresh');
  }
  renderAll();

  // Auto refresh UI every 60s (data itself refreshes every 5min server-side)
  setInterval(async () => {
    try {
      lastData = await fetchData();
      renderAll();
    } catch (_) {}
  }, 60000);

  // Keyboard shortcut
  document.addEventListener('keydown', (e) => {
    if (e.key.toLowerCase() === 'r' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      manualRefresh();
    }
  });
}

init();
</script>
</body>
</html>
""".replace("{{poll}}", str(POLL_INTERVAL_MINUTES)).replace("{{version}}", VERSION)


@app.route("/", methods=["GET"])
def dashboard():
    return Response(DASHBOARD_HTML, mimetype="text/html")


@app.route("/api/state", methods=["GET"])
def api_state():
    state = get_state()
    kp_chart = get_recent_kp_for_chart(state, hours=72)      # short-term chart
    kp_7d_chart = get_recent_kp_for_chart(state, hours=200)   # full ~7 days for dedicated chart

    return jsonify({
        "rncan": state.rncan.to_dict() if state.rncan else None,
        "latest_kp": state.latest_kp.to_dict() if state.latest_kp else None,
        "kp_history": kp_chart,
        "kp_7d_history": kp_7d_chart,
        "activity_history": get_activity_history_for_ui(state),
        "last_fetch": state.last_fetch,
        "poll_interval": POLL_INTERVAL_MINUTES,
    })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    new_state = force_refresh()
    kp_chart = get_recent_kp_for_chart(new_state, hours=72)
    kp_7d_chart = get_recent_kp_for_chart(new_state, hours=200)
    return jsonify({
        "ok": True,
        "state": {
            "rncan": new_state.rncan.to_dict() if new_state.rncan else None,
            "latest_kp": new_state.latest_kp.to_dict() if new_state.latest_kp else None,
            "kp_history": kp_chart,
            "kp_7d_history": kp_7d_chart,
            "activity_history": get_activity_history_for_ui(new_state),
            "last_fetch": new_state.last_fetch,
        }
    })


def run_server():
    """Start the web server (blocking)."""
    # Start scheduler when web server boots (ensures data is fresh)
    start_scheduler()
    print(f"🌌 AurorA web dashboard → http://{WEB_HOST}:{WEB_PORT}")
    # threaded=True so the UI can poll while other requests (manual refresh) come in.
    # use_reloader=False is mandatory when running inside a thread / frozen app.
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    run_server()
