// Fase 2: overlay sincronizado com video.currentTime.
// Fase 3: transposição de acordes e controle de velocidade — tudo client-side,
// não reprocessa nada no servidor (ver transpose.js e seção 4.2/4.3 do plano).

let chordsTimeline = null;
let bpm = null;
let key = null;
let videoEl = null;
let rafId = null;
let panelEl = null;
let currentIndex = -1;
let transposeSemitones = 0;
let playbackRate = 1.0;

const SPEED_MIN = 0.5;
const SPEED_MAX = 2.0;
const SPEED_STEP = 0.25;

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "SHOW_CHORDS") {
    chordsTimeline = msg.chordsTimeline || [];
    bpm = msg.bpm;
    key = msg.key;
    currentIndex = -1;
    // Música nova: transposição e velocidade voltam ao padrão.
    transposeSemitones = 0;
    playbackRate = 1.0;
    startOverlay();
  }
});

function startOverlay() {
  findVideoElement((video) => {
    videoEl = video;
    applyPlaybackRate();
    ensurePanel();
    if (rafId) cancelAnimationFrame(rafId);
    tick();
  });
}

function findVideoElement(callback) {
  const existing = document.querySelector("video");
  if (existing) {
    callback(existing);
    return;
  }

  // O player do YouTube é montado de forma assíncrona (SPA) — espera aparecer.
  const observer = new MutationObserver(() => {
    const video = document.querySelector("video");
    if (video) {
      observer.disconnect();
      callback(video);
    }
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
}

function ensurePanel() {
  if (panelEl) {
    updateControlLabels();
    return;
  }

  panelEl = document.createElement("div");
  panelEl.id = "cifras-ai-overlay";
  panelEl.innerHTML = `
    <div class="cifras-ai-header">
      <span class="cifras-ai-key"></span>
      <span class="cifras-ai-bpm"></span>
    </div>
    <div class="cifras-ai-chord-current">—</div>
    <div class="cifras-ai-chord-next"></div>
    <div class="cifras-ai-controls">
      <div class="cifras-ai-control-group">
        <button class="cifras-ai-btn" data-action="transpose-down" title="Transpor 1 semitom abaixo">♭</button>
        <span class="cifras-ai-control-label" data-label="transpose"></span>
        <button class="cifras-ai-btn" data-action="transpose-up" title="Transpor 1 semitom acima">♯</button>
      </div>
      <div class="cifras-ai-control-group">
        <button class="cifras-ai-btn" data-action="speed-down" title="Diminuir velocidade">−</button>
        <span class="cifras-ai-control-label" data-label="speed"></span>
        <button class="cifras-ai-btn" data-action="speed-up" title="Aumentar velocidade">＋</button>
      </div>
    </div>
  `;
  panelEl.querySelector(".cifras-ai-controls").addEventListener("click", onControlClick);
  document.body.appendChild(panelEl);
  updateControlLabels();
}

function onControlClick(event) {
  const action = event.target?.dataset?.action;
  if (!action) return;

  if (action === "transpose-down") setTranspose(transposeSemitones - 1);
  else if (action === "transpose-up") setTranspose(transposeSemitones + 1);
  else if (action === "speed-down") setPlaybackRate(playbackRate - SPEED_STEP);
  else if (action === "speed-up") setPlaybackRate(playbackRate + SPEED_STEP);
}

function setTranspose(semitones) {
  // ±11 cobre todo o círculo cromático; além disso é só repetir uma nota já alcançável.
  transposeSemitones = Math.max(-11, Math.min(11, semitones));
  updateControlLabels();
  if (videoEl) updateChordDisplay(videoEl.currentTime);
}

function setPlaybackRate(rate) {
  playbackRate = Math.max(SPEED_MIN, Math.min(SPEED_MAX, Math.round(rate * 100) / 100));
  applyPlaybackRate();
  updateControlLabels();
}

function applyPlaybackRate() {
  if (!videoEl) return;
  videoEl.playbackRate = playbackRate;
  // Desacelerar sem mudar o tom só funciona com isso ligado; é o padrão em
  // navegadores modernos, mas fixamos explicitamente pra não depender disso.
  videoEl.preservesPitch = true;
  videoEl.mozPreservesPitch = true;
  videoEl.webkitPreservesPitch = true;
}

function updateControlLabels() {
  if (!panelEl) return;
  const transposeLabel = panelEl.querySelector('[data-label="transpose"]');
  transposeLabel.textContent =
    transposeSemitones === 0 ? "Tom original" : `${transposeSemitones > 0 ? "+" : ""}${transposeSemitones}`;

  const speedLabel = panelEl.querySelector('[data-label="speed"]');
  speedLabel.textContent = `${playbackRate.toFixed(2)}x`;
}

function tick() {
  if (!videoEl || !chordsTimeline) return;

  if (!videoEl.isConnected) {
    // Vídeo saiu do DOM (troca de página via SPA do YouTube) — para o loop.
    rafId = null;
    return;
  }

  updateChordDisplay(videoEl.currentTime);
  rafId = requestAnimationFrame(tick);
}

function updateChordDisplay(time) {
  if (currentIndex === -1 || time < (chordsTimeline[currentIndex]?.start ?? Infinity)) {
    // Sem posição conhecida, ou usuário voltou o vídeo (seek para trás): reprocura do zero.
    currentIndex = chordsTimeline.findIndex((c) => time >= c.start && time < c.end);
  } else {
    // Caminho comum: tempo avança — anda o ponteiro pra frente em vez de re-buscar.
    while (
      currentIndex + 1 < chordsTimeline.length &&
      time >= chordsTimeline[currentIndex + 1].start
    ) {
      currentIndex += 1;
    }
  }

  // O ponteiro pode ficar parado no último acorde conhecido mesmo depois que
  // o tempo passa do fim dele (ex.: vídeo continua além do trecho analisado)
  // — só exibe como "atual" se o tempo ainda está dentro do intervalo dele.
  const pointer = chordsTimeline[currentIndex];
  const current = pointer && time < pointer.end ? pointer : null;
  const next = chordsTimeline[currentIndex + 1];

  const displayKey = transposeKeyLabel(key, transposeSemitones);
  panelEl.querySelector(".cifras-ai-key").textContent = displayKey ? `Tom: ${displayKey}` : "";
  panelEl.querySelector(".cifras-ai-bpm").textContent = bpm ? `${Math.round(bpm)} BPM` : "";
  panelEl.querySelector(".cifras-ai-chord-current").textContent =
    current ? transposeChordSymbol(current.chord, transposeSemitones) : "—";
  panelEl.querySelector(".cifras-ai-chord-next").textContent =
    next ? `próximo: ${transposeChordSymbol(next.chord, transposeSemitones)}` : "";
}
