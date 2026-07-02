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
- **ToS das plataformas** — capturar/processar áudio de terceiros é zona cinzenta; revisar antes de publicar na Chrome Web Store. Ver análise em 7.1.
- **Custo do backend** — Demucs é caro em CPU/GPU. O cache resolve a maior parte; vídeos novos têm custo de primeira análise.
- **Propagação de erro** — se a separação falha num trecho, o acorde sai errado ali. O baixo ajuda a desambiguar, mas não é perfeito.

### 7.1 Análise preliminar de ToS / risco legal

Pesquisa feita nos Termos de Serviço do YouTube e nas políticas do Chrome Web Store (ver fontes no fim desta seção). **Isto não é aconselhamento jurídico** — é o suficiente pra decidir com informação antes de publicar, não pra validar publicação.

**YouTube ToS — o texto é bem restritivo:**
> "acessar, reproduzir, fazer download, distribuir, transmitir, exibir, vender, licenciar, alterar, modificar ou usar de outra forma qualquer parte do Serviço ou qualquer Conteúdo, exceto: (a) se autorizado de forma expressa pelo Serviço; ou (b) mediante uma permissão prévia por escrito do YouTube"

Isso cobre literalmente "usar de outra forma" — capturar o áudio de uma aba via `chrome.tabCapture` e mandar pra um backend externo pra análise é, ao pé da letra, um uso não previsto pelo player oficial. Na prática, a aplicação real do YouTube historicamente mira **downloaders em massa e scrapers automatizados** (a cláusula de "meios automatizados" cita explicitamente robôs/botnets/scrapers), não extensões que capturam áudio sob ação manual do próprio usuário, um vídeo por vez, sem redistribuir o conteúdo. Mas o risco formal existe e não desaparece só por sermos um caso de uso pequeno.

**Mitigação já embutida na arquitetura atual (bom sinal):**
- O áudio bruto **nunca é persistido** — `analyze.py` processa em diretório temporário e roda `shutil.rmtree` no `finally`, mesmo em erro. Só a *timeline de acordes derivada* (fatos: acorde, BPM, tom) fica no cache — não o áudio, não a música em si.
- Acordes/BPM/tom isolados são, em geral, tratados como fatos/ideias não protegíveis por copyright (equivalente a alguém transcrever de ouvido) — bem diferente de redistribuir a gravação ou a letra.

**Chrome Web Store — políticas do programa de desenvolvedor:**
- Exige permissões mínimas necessárias (`tabCapture`, `offscreen`, `sidePanel` já batem com isso — nada de permissão "por via das dúvidas").
- Exige transparência total sobre coleta/uso de dados — como o áudio sai do dispositivo do usuário rumo a um backend de terceiros, **vai precisar de política de privacidade explícita** antes de publicar, deixando claro: o que é capturado, pra onde vai, que não fica salvo, e o que é cacheado (resultado da análise, por vídeo, não o áudio).
- A política do Chrome Web Store rege a conduta da extensão em si — **não neutraliza** o risco separado do ToS do YouTube; são duas camadas de risco independentes.

**Risco adicional identificado — maior que o dos acordes:** o item 9.1 do backlog (transcrição de letra via Whisper) é uma categoria de risco diferente e mais alta. Letra de música **é conteúdo protegido por copyright** (não é fato/ideia como um acorde) — sites de letras historicamente tiveram disputas e precisam de licenciamento (ex.: LyricFind) pra exibir letras legalmente. Reproduzir letra transcrita, mesmo que gerada localmente via IA, ainda é reproduzir a obra protegida. Recomendo tratar isso como recurso separado, sinalizado com risco mais alto, se/quando for implementado (ver nota em 9.1).

**Recomendação prática:**
1. Enquanto o projeto for uso pessoal/pequena escala (não publicado na Chrome Web Store), o risco é baixo — é o equivalente digital de anotar os acordes de ouvido enquanto assiste ao vídeo.
2. Antes de publicar na Web Store: escrever política de privacidade explícita (obrigatória pela política de dados do usuário) e reavaliar se cachear a timeline de acordes por `video_id` de forma pública/compartilhada entre usuários muda o perfil de risco (hoje o schema do Supabase já é por vídeo, não por usuário — vale decidir se o cache é privado por instalação ou compartilhado globalmente).
3. Não implementar 9.1 (letras) sem decisão explícita e ciente do risco de copyright mais alto que os acordes/BPM/tom.

**Fontes consultadas:**
- [YouTube Terms of Service](https://www.youtube.com/static?template=terms)
- [YouTube Terms of Service Explained — TLDRLegal](https://www.tldrlegal.com/license/youtube-terms-of-service)
- [Chrome Web Store — Program Policies](https://developer.chrome.com/docs/webstore/program-policies)
- [Chrome Web Store — Updated Privacy Policy & Secure Handling Requirements](https://developer.chrome.com/docs/webstore/program-policies/user-data-faq)

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
- **Risco legal mais alto que o resto do projeto** (ver 7.1): letra é conteúdo
  protegido por copyright, diferente de acordes/BPM/tom (tratados como fato).
  Se cachear no Supabase, cachear só pra uso próprio/privado, não expor a letra
  transcrita publicamente sem entender essa diferença de risco.

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
