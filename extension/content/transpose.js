// Fase 3: transposição pura de símbolos de cifra (client-side, sem reanálise).
// Desloca só a nota fundamental (e o baixo, em slash chords tipo "G/B") por N
// semitons; o resto do símbolo (m7, sus4, maj7, b5...) não é tocado.

const CIFRAS_AI_CHROMATIC = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

const CIFRAS_AI_FLAT_TO_SHARP = {
  Db: "C#", Eb: "D#", Gb: "F#", Ab: "G#", Bb: "A#",
};

const CIFRAS_AI_NOTE_RE = /^([A-G])([#b]?)/;

function transposeNote(note, semitones) {
  const normalized = CIFRAS_AI_FLAT_TO_SHARP[note] || note;
  const index = CIFRAS_AI_CHROMATIC.indexOf(normalized);
  if (index === -1) return note; // nota não reconhecida — devolve sem mexer
  const shifted = (((index + semitones) % 12) + 12) % 12;
  return CIFRAS_AI_CHROMATIC[shifted];
}

function transposeChordSymbol(symbol, semitones) {
  if (!semitones || !symbol) return symbol;

  const transposePart = (part) => {
    const match = part.match(CIFRAS_AI_NOTE_RE);
    if (!match) return part;
    const note = match[1] + match[2];
    const rest = part.slice(match[0].length);
    return transposeNote(note, semitones) + rest;
  };

  const [root, bass] = symbol.split("/");
  const transposedRoot = transposePart(root);
  return bass === undefined ? transposedRoot : `${transposedRoot}/${transposePart(bass)}`;
}

function transposeKeyLabel(keyLabel, semitones) {
  if (!semitones || !keyLabel) return keyLabel;
  const [note, ...rest] = keyLabel.split(" ");
  return [transposeChordSymbol(note, semitones), ...rest].join(" ");
}
