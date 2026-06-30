let currentTab = null;
let progressInterval = null;

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

  document.getElementById('video-title').textContent =
    videoId ? tab.title : 'Abra um vídeo no YouTube';
  document.getElementById('video-id').textContent =
    videoId ? `ID: ${videoId}` : '';

  document.getElementById('btn-analyze').disabled = !videoId;
  document.getElementById('btn-analyze').addEventListener('click', () => onAnalyze(videoId));
}

async function onAnalyze(videoId) {
  const btn = document.getElementById('btn-analyze');
  const statusEl = document.getElementById('status');
  const resultsEl = document.getElementById('results');
  const errorEl = document.getElementById('error-box');
  const durationSec = parseInt(document.getElementById('duration').value, 10);
  const backendUrl = document.getElementById('backend-url').value.trim().replace(/\/$/, '');

  btn.disabled = true;
  resultsEl.hidden = true;
  errorEl.hidden = true;
  statusEl.hidden = false;

  const fill = document.getElementById('progress-fill');
  const statusText = document.getElementById('status-text');
  fill.style.width = '0%';
  statusText.textContent = `Gravando ${durationSec}s de áudio...`;

  let elapsed = 0;
  progressInterval = setInterval(() => {
    elapsed += 0.5;
    const pct = Math.min(100, (elapsed / durationSec) * 100);
    fill.style.width = `${pct}%`;
    if (elapsed >= durationSec) {
      statusText.textContent = 'Enviando para análise (pode levar 1-2 min)...';
      clearInterval(progressInterval);
    }
  }, 500);

  try {
    const result = await chrome.runtime.sendMessage({
      type: 'START_CAPTURE',
      tabId: currentTab.id,
      durationSec,
      backendUrl,
      videoId,
    });

    clearInterval(progressInterval);
    if (result?.error) throw new Error(result.error);

    showResults(result);
  } catch (err) {
    errorEl.hidden = false;
    document.getElementById('error-text').textContent = err.message;
  } finally {
    clearInterval(progressInterval);
    btn.disabled = false;
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
