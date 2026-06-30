// Abre o side panel ao clicar no ícone da extensão
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

// Recebe mensagens do side panel
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'START_CAPTURE') {
    handleCapture(msg)
      .then(sendResponse)
      .catch(err => sendResponse({ error: err.message }));
    return true; // keepChannelOpen para resposta assíncrona
  }
});

async function handleCapture({ tabId, durationSec, backendUrl, videoId }) {
  // MV3: pega o streamId no service worker e passa para o offscreen document
  const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });

  await ensureOffscreenDocument();

  return new Promise((resolve) => {
    chrome.runtime.sendMessage(
      { type: 'CAPTURE_AUDIO', streamId, durationSec, backendUrl, videoId },
      resolve
    );
  });
}

async function ensureOffscreenDocument() {
  const exists = await chrome.offscreen.hasDocument();
  if (!exists) {
    await chrome.offscreen.createDocument({
      url: 'offscreen/offscreen.html',
      reasons: ['USER_MEDIA'],
      justification: 'Captura de áudio da aba para análise de acordes via IA.',
    });
  }
}
