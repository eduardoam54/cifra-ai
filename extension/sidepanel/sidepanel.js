let currentTab = null;
let hasVideo = false;
let progressTimer = null;

function extractYouTubeId(url) {
  try {
    const u = new URL(url);
    if (u.hostname.includes('youtube.com')) return u.searchParams.get('v');
    if (u.hostname === 'youtu.be') return u.pathname.slice(1);
  } catch {
    return null;
  }
  return null;
}

async function init() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentTab = tab;

  const videoId = tab?.url ? extractYouTubeId(tab.url) : null;
  hasVideo = Boolean(videoId);

  document.getElementById('video-title').textContent =
    videoId ? tab.title : 'Abra um vídeo no YouTube';
  document.getElementById('video-id').textContent =
    videoId ? `ID: ${videoId}` : '';

  const settings = await chrome.storage.local.get({ durationSec: 60, backendUrl: 'http://localhost:8000' });
  document.getElementById('duration').value = String(settings.durationSec);
  document.getElementById('backend-url').value = settings.backendUrl;
  document.getElementById('duration').addEventListener('change', saveSettings);
  document.getElementById('backend-url').addEventListener('change', saveSettings);

  document.getElementById('btn-analyze').disabled = !hasVideo;
  document.getElementById('btn-analyze').addEventListener('click', () => onAnalyzeClick(videoId));

  // Recebe atualizações de estado do service worker (captura disparada pelo
  // clique no ícone da extensão, que é o único gatilho que concede `activeTab`).
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === 'STATE_UPDATE') applyState(msg.state);
  });

  chrome.runtime.sendMessage({ type: 'GET_STATE' }, (state) => {
    if (state) applyState(state);
  });
}

function saveSettings() {
  chrome.storage.local.set({
    durationSec: parseInt(document.getElementById('duration').value, 10),
    backendUrl: document.getElementById('backend-url').value.trim().replace(/\/$/, ''),
  });
}

function onAnalyzeClick(videoId) {
  // Repete a captura na aba atual reaproveitando o `activeTab` concedido
  // quando o ícone foi clicado — só funciona se a aba não tiver navegado
  // para outra página desde então (nesse caso, clique no ícone de novo).
  saveSettings();
  const durationSec = parseInt(document.getElementById('duration').value, 10);
  const backendUrl = document.getElementById('backend-url').value.trim().replace(/\/$/, '');
  chrome.runtime.sendMessage({
    type: 'REANALYZE', tabId: currentTab.id, videoId, durationSec, backendUrl,
  });
}

function applyState(state) {
  const statusEl = document.getElementById('status');
  const resultsEl = document.getElementById('results');
  const errorEl = document.getElementById('error-box');
  const btn = document.getElementById('btn-analyze');

  clearInterval(progressTimer);

  if (state.status === 'recording') {
    btn.disabled = true;
    resultsEl.hidden = true;
    errorEl.hidden = true;
    statusEl.hidden = false;

    const fill = document.getElementById('progress-fill');
    const statusText = document.getElementById('status-text');

    const tick = () => {
      const elapsed = (Date.now() - state.startedAt) / 1000;
      const pct = Math.min(100, (elapsed / state.durationSec) * 100);
      fill.style.width = `${pct}%`;
      statusText.textContent = elapsed < state.durationSec
        ? `Gravando ${state.durationSec}s de áudio...`
        : 'Enviando para análise (pode levar 1-2 min)...';
    };
    tick();
    progressTimer = setInterval(tick, 500);
  } else if (state.status === 'done') {
    btn.disabled = !hasVideo;
    statusEl.hidden = true;
    errorEl.hidden = true;
    showResults(state.result);
  } else if (state.status === 'error') {
    btn.disabled = !hasVideo;
    statusEl.hidden = true;
    resultsEl.hidden = true;
    errorEl.hidden = false;
    document.getElementById('error-text').textContent = state.error;
  } else {
    statusEl.hidden = true;
  }
}

function showResults(data) {
  document.getElementById('bpm-badge').textContent = `♩ ${data.bpm} BPM`;
  document.getElementById('key-badge').textContent = `🎵 ${data.key}`;
  document.getElementById('time-badge').textContent = `processado em ${data.processing_time_s}s`;

  const list = document.getElementById('chord-list');
  list.innerHTML = '';

  for (const event of data.chords_timeline) {
    const div = document.createElement('div');
    div.className = 'chord-item';
    div.innerHTML = `<strong>${event.chord}</strong><span class="time">${event.start.toFixed(1)}s</span>`;
    list.appendChild(div);
  }

  document.getElementById('results').hidden = false;
}

init();
