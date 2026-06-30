// Fase 1: apenas recebe a mensagem e loga — overlay sincronizado vem na Fase 2
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'SHOW_CHORDS') {
    console.log('[CifrasAI] acordes recebidos:', msg.chordsTimeline?.length,
      '| tom:', msg.key, '| BPM:', msg.bpm);
    // TODO Fase 2: renderizar overlay sincronizado com video.currentTime
  }
});
