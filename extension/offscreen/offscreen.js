// Recebe ordem de captura do service worker
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'CAPTURE_AUDIO') {
    captureAndSend(msg)
      .then(sendResponse)
      .catch(err => sendResponse({ error: err.message }));
    return true;
  }
});

async function captureAndSend({ streamId, durationSec, backendUrl, videoId }) {
  // Obtém o stream de áudio da aba via ID gerado pelo service worker
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: {
        chromeMediaSource: 'tab',
        chromeMediaSourceId: streamId,
      },
    },
    video: false,
  });

  const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? 'audio/webm;codecs=opus'
    : 'audio/webm';

  const chunks = [];
  const recorder = new MediaRecorder(stream, { mimeType });
  recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };

  return new Promise((resolve, reject) => {
    recorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());

      const blob = new Blob(chunks, { type: 'audio/webm' });
      try {
        resolve(await sendToBackend(blob, backendUrl, videoId));
      } catch (err) {
        reject(err);
      }
    };

    recorder.start(1000); // coleta chunks de 1s para não perder dados
    setTimeout(() => recorder.stop(), durationSec * 1000);
  });
}

async function sendToBackend(blob, backendUrl, videoId) {
  const formData = new FormData();
  formData.append('audio_file', blob, 'capture.webm');
  if (videoId) formData.append('video_id', videoId);

  const res = await fetch(`${backendUrl}/analyze`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Backend ${res.status}: ${text}`);
  }

  return res.json();
}
