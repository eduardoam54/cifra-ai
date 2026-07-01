// Fase 2: overlay sincronizado com video.currentTime.
// Recebe a timeline de acordes do service worker (após a análise) e desenha
// um painel flutuante sobre o vídeo, atualizado a cada frame.

let chordsTimeline = null;
let bpm = null;
let key = null;
let videoEl = null;
let rafId = null;
let panelEl = null;
let currentIndex = -1;

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "SHOW_CHORDS") {
    chordsTimeline = msg.chordsTimeline || [];
    bpm = msg.bpm;
    key = msg.key;
    currentIndex = -1;
    startOverlay();
  }
});

function startOverlay() {
  findVideoElement((video) => {
    videoEl = video;
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
  if (panelEl) return;

  panelEl = document.createElement("div");
  panelEl.id = "cifras-ai-overlay";
  panelEl.innerHTML = `
    <div class="cifras-ai-header">
      <span class="cifras-ai-key"></span>
      <span class="cifras-ai-bpm"></span>
    </div>
    <div class="cifras-ai-chord-current">—</div>
    <div class="cifras-ai-chord-next"></div>
  `;
  document.body.appendChild(panelEl);
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

  const current = chordsTimeline[currentIndex];
  const next = chordsTimeline[currentIndex + 1];

  panelEl.querySelector(".cifras-ai-key").textContent = key ? `Tom: ${key}` : "";
  panelEl.querySelector(".cifras-ai-bpm").textContent = bpm ? `${Math.round(bpm)} BPM` : "";
  panelEl.querySelector(".cifras-ai-chord-current").textContent = current ? current.chord : "—";
  panelEl.querySelector(".cifras-ai-chord-next").textContent = next ? `próximo: ${next.chord}` : "";
}
