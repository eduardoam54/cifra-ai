// Desativa explicitamente o auto-open do painel: essa configuração é
// persistida pelo Chrome por extensão, então uma versão anterior deste
// arquivo que chamava `setPanelBehavior({ openPanelOnActionClick: true })`
// deixa esse comportamento "grudado" mesmo depois de remover a chamada.
// Sem isso, chrome.action.onClicked abaixo nunca dispara.
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }).catch(() => {});

// Estado da captura em andamento — permite que o side panel sincronize sua UI
// mesmo se abrir depois do clique no ícone (via mensagem GET_STATE).
let state = { status: "idle" };

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "GET_STATE") {
    sendResponse(state);
    return;
  }
  if (msg.type === "REANALYZE") {
    startCapture(msg.tabId, msg.videoId, msg.durationSec, msg.backendUrl)
      .catch(() => {}); // erros já são refletidos em `state` e via broadcast
    sendResponse({ ok: true });
    return;
  }
});

// Ponto de entrada real da captura: só o clique direto no ícone da extensão
// concede a permissão `activeTab` para a aba. Um botão dentro do side panel
// não conta como "invocação" da extensão para fins de tabCapture — por isso
// a captura começa aqui, não num handler de clique dentro do painel.
chrome.action.onClicked.addListener(async (tab) => {
  await chrome.sidePanel.open({ tabId: tab.id });

  const videoId = extractYouTubeId(tab.url);
  if (!videoId) {
    state = { status: "error", error: "Abra um vídeo do YouTube antes de clicar no ícone da extensão." };
    broadcastState();
    return;
  }

  const settings = await chrome.storage.local.get({
    durationSec: 60,
    backendUrl: "http://localhost:8000",
  });

  startCapture(tab.id, videoId, settings.durationSec, settings.backendUrl).catch(() => {});
});

function extractYouTubeId(url) {
  try {
    const u = new URL(url);
    if (u.hostname.includes("youtube.com")) return u.searchParams.get("v");
    if (u.hostname === "youtu.be") return u.pathname.slice(1);
  } catch {
    return null;
  }
  return null;
}

async function startCapture(tabId, videoId, durationSec, backendUrl) {
  state = { status: "recording", videoId, durationSec, startedAt: Date.now() };
  broadcastState();

  try {
    const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });
    await ensureOffscreenDocument();

    const result = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { type: "CAPTURE_AUDIO", streamId, durationSec, backendUrl, videoId },
        (response) => {
          if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
          if (response?.error) return reject(new Error(response.error));
          resolve(response);
        }
      );
    });

    state = { status: "done", videoId, result };
    broadcastState();

    chrome.tabs.sendMessage(tabId, {
      type: "SHOW_CHORDS",
      chordsTimeline: result.chords_timeline,
      bpm: result.bpm,
      key: result.key,
      videoId: result.video_id,
    }).catch(() => {
      // Content script pode não estar pronto ainda (ex.: aba acabou de carregar); ignora.
    });
  } catch (err) {
    state = { status: "error", videoId, error: err.message };
    broadcastState();
  }
}

function broadcastState() {
  chrome.runtime.sendMessage({ type: "STATE_UPDATE", state }).catch(() => {
    // Painel pode não estar aberto ainda; quem abrir depois consulta via GET_STATE.
  });
}

async function ensureOffscreenDocument() {
  const exists = await chrome.offscreen.hasDocument();
  if (!exists) {
    await chrome.offscreen.createDocument({
      url: "offscreen/offscreen.html",
      reasons: ["USER_MEDIA"],
      justification: "Captura de áudio da aba para análise de acordes via IA.",
    });
  }
}
