# Extensão de Cifras com IA — Plano Completo

> Extensão de navegador que reconhece acordes de músicas/vídeos em tempo real, detecta BPM e tonalidade, e permite transpor os acordes e controlar a velocidade do vídeo. **Todo o núcleo de análise é feito por IA.**

---

## 1. Visão geral

A extensão captura o áudio de uma aba (YouTube/vídeo), envia para um backend de IA que separa instrumentos, reconhece a progressão harmônica, detecta andamento e tonalidade, e devolve uma *timeline* de acordes. A extensão exibe esses acordes em overlay sincronizado com o vídeo e oferece transposição e controle de velocidade — ambos client-side e instantâneos.

**Princípio central:** processa cada vídeo **uma vez**, guarda o resultado em cache e serve instantâneo nas próximas vezes. Isso resolve latência e custo de uma só vez.

### As quatro funções
1. **Reconhecimento de acordes** (simples e complexos) — IA, no servidor.
2. **Detecção de tonalidade + transposição** — detecção no servidor, transposição no cliente.
3. **Detecção de BPM + controle de velocidade** — detecção no servidor, controle no cliente.
4. **Overlay sincronizado** com o tempo do vídeo — no cliente.

---

## 2. Restrições que definem o projeto

Ler isto **antes** de começar. Essas duas restrições determinam o que é possível.

### 2.1 DRM — define o público-alvo
Uma extensão captura áudio de aba via `chrome.tabCapture`, mas **só de fontes sem DRM**:

| Fonte | Captável? |
|---|---|
| YouTube, SoundCloud, `<video>` comuns | ✅ Sim |
| Spotify, Apple Music, Netflix | ❌ Não (áudio protegido por EME/DRM) |

**Alvo realista: YouTube / vídeos abertos.**

### 2.2 Peso computacional — define a arquitetura
Separação de fontes (Demucs) + modelo de acordes é **pesado demais para rodar em tempo real no navegador**. Por isso a análise pesada vai para um backend, e o resultado é cacheado. O navegador só faz o que é leve (overlay, transposição, controle de velocidade).

---

## 3. Arquitetura (híbrida + cache)

```
[Extensão no navegador]
   captura áudio da aba (offscreen document)
   identifica o vídeo (URL/ID; fallback: hash do áudio)
        │
        ▼
   consulta cache (Supabase): já analisamos esse vídeo?
        │
   ┌────┴────┐
  SIM        NÃO
   │          │
   │          ▼
   │     [Backend IA] (Railway/Render)
   │       Demucs → separa stems
   │       baixo → fundamental | outros → qualidade
   │       fusão de features → modelo ACR (IA)
   │       + BPM + tonalidade
   │       devolve timeline e salva no cache
   │          │
   └────┬─────┘
        ▼
   [Overlay na extensão] sincroniza acordes com video.currentTime
   transposição e velocidade tratadas localmente, na hora
```

---

## 4. Como cada função funciona

### 4.1 Reconhecimento de acordes (IA — servidor)
Pipeline de separação + fusão de features (a chave para acordes complexos):

1. **Separação de fontes** — Demucs (htdemucs) ou Spleeter → baixo / bateria / voz / outros.
2. **Descartar a bateria** — percussão é ruído para harmonia.
3. **Stem do baixo** — pitch tracking monofônico (CREPE / basic-pitch) ou chroma do baixo → dá a *fundamental* e a nota do baixo (inversões / slash chords).
4. **Voz + outros** — chroma harmônico → dá a *qualidade* do acorde (terças, sétimas, tensões).
5. **Fusão de features** — combina baixo + harmonia e alimenta o modelo ACR (transformer/conformer, ex.: BTC/Chordformer, exportado em ONNX ou rodando em PyTorch).

**Por que o baixo importa tanto:** se o teclado toca C–E–G mas o baixo toca A, o acorde real é **Am7** (A–C–E–G), não C maior. Sem o baixo, o modelo erra; com ele, desambigua. É assim que se pegam os padrões complexos.

**Saída:** lista de `{ inicio, fim, acorde }`.

> ⚠️ **O gargalo real:** acordes estendidos/alterados (7M(9), m7(b5), tensões) aparecem pouco nos dados de treino (desbalanceamento de classes), então a precisão neles é menor. É a parte que mais exige iteração com dados.

### 4.2 Tonalidade + transposição
- **Detecção (servidor):** usa o chroma já extraído + perfis Krumhansl-Schmuckler. Leve, sai de graça do mesmo pipeline.
- **Transposição (cliente):** matemática pura e instantânea. Detectado o tom, transpor é só deslocar todos os símbolos pelo mesmo intervalo (tabela de 12 semitons + parser de cifra). **Não reprocessa áudio.**

> Detectar é o trabalho; transpor é de graça.

### 4.3 Velocidade / BPM
- **Detecção de BPM (servidor ou cliente):** beat tracking via Essentia.js (cliente) ou aubio/librosa (servidor).
- **Controle de velocidade (cliente):** ajustar `video.playbackRate`. Navegadores modernos têm `preservesPitch = true` por padrão → desacelerar **mantém o tom**, ideal para estudar trechos difíceis.
- Mudar a velocidade **não exige reanálise**: acordes e tom continuam os mesmos, só a régua de tempo do overlay estica/encolhe.

### 4.4 Overlay sincronizado (cliente)
A extensão lê `video.currentTime` e destaca o acorde atual sobre o vídeo, estilo player de cifra.

---

## 5. Stack concreta

| Camada | Tecnologia |
|---|---|
| Extensão | Manifest V3 + **offscreen document** (obrigatório no MV3 para processar áudio; o service worker não acessa mídia direto) |
| Captura | `chrome.tabCapture` → stream de áudio |
| Cliente leve | Essentia.js / onnxruntime-web (WebGPU) para BPM e tom, se quiser tirar carga do servidor |
| Backend IA | Python + **FastAPI**, com Demucs + modelo ACR |
| Hospedagem | **Railway / Render** |
| Cache / DB | **Supabase** |
| Transposição | Lógica pura em JS/TS no cliente |

### Esquema do cache (Supabase)
Uma linha por vídeo:

```
analyses
  video_id        text (PK)     -- ID do YouTube ou hash do áudio
  chords_timeline jsonb         -- [{inicio, fim, acorde}, ...]
  bpm             numeric
  key             text          -- ex.: "D maior"
  model_version   text          -- versão do modelo que gerou (para invalidar cache)
  created_at      timestamptz
```

---

## 6. Roadmap em fases (MVP primeiro)

- **Fase 0 — PoC sem extensão:** backend recebe um arquivo de áudio e devolve `acordes + BPM + tom` em JSON. Sem isso, nada mais importa.
- **Fase 1 — extensão mínima:** captura áudio do YouTube → backend → painel lateral com acordes (sem sincronia fina).
- **Fase 2 — cache + sincronia:** overlay sincronizado ao `currentTime` + cache no Supabase (segunda visita = instantâneo).
- **Fase 3 — transposição + velocidade:** botões de transpor e de `playbackRate`, tudo client-side.
- **Fase 4 — refino dos acordes complexos:** atacar o gargalo de vocabulário grande, iterando com mais dados.

---

## 7. Riscos a monitorar

- **DRM** — limita o público a fontes abertas (item 2.1).
- **ToS das plataformas** — capturar/processar áudio de terceiros é zona cinzenta; revisar antes de publicar na Chrome Web Store.
- **Custo do backend** — Demucs é caro em CPU/GPU. O cache resolve a maior parte; vídeos novos têm custo de primeira análise.
- **Propagação de erro** — se a separação falha num trecho, o acorde sai errado ali. O baixo ajuda a desambiguar, mas não é perfeito.

---

## 8. Próximo passo sugerido

Detalhar a **Fase 0**: o contrato do JSON do backend e o esqueleto do FastAPI. É a fundação de tudo o resto.

---

## 9. Backlog / ideias para incorporar conforme avançarmos

Ideias validadas em conversa, ainda sem fase definida — encaixar quando fizer sentido no roadmap:

### 9.1 Transcrição de letra + alinhamento com os acordes
O Demucs já separa o stem de vocais (`separator.py`) — dá pra rodar um modelo de
transcrição (Whisper / `faster-whisper`) nesse stem, pegar timestamp por palavra,
e cruzar com a `chords_timeline` (que já tem `start`/`end`) pra montar uma cifra
completa: letra com o acorde certo posicionado em cima da palavra certa.

- **Onde entra:** novo serviço `lyrics_transcriber.py`, chamado no mesmo pipeline
  do `/analyze`, em paralelo à detecção de BPM/tom/acordes.
- **Trade-off:** mais um modelo pesado rodando na CPU (soma tempo ao Demucs);
  precisão cai um pouco mesmo com vocal isolado, por causa de vazamento de
  instrumentação no stem.

### 9.2 Latência da primeira análise (músicas de ~4min não podem demorar demais)
O cache do Supabase (Fase 2) já resolve isso pra quem não é o primeiro a pedir
aquela música — é a alavanca principal e já está no roadmap. O que falta pensar
é o tempo do **primeiro** processamento de cada música nova, hoje lento porque o
Demucs roda em CPU:

- **Opção A — GPU:** Demucs em GPU é ~5-10x mais rápido que em CPU (ver
  `demucs_device` em `config.py`). Ganho grande, custo de hosting maior.
- **Opção B — "modo rápido":** pular a separação do Demucs e reconhecer acordes
  direto na mixagem completa via chroma (sem stems). Muito mais rápido, mas
  perde precisão em inversões/baixo (slash chords), já que sem o stem do baixo
  isolado o pipeline não desambigua bem esses casos (ver seção 4.1).

**Prioridade sugerida:** implementar o cache (Fase 2) primeiro, por resolver a
maioria dos casos reais de uso; revisitar GPU/modo rápido só se o tempo da
primeira análise continuar sendo um problema depois disso.
