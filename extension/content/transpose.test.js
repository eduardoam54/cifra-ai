// Testes de transpose.js — carrega o arquivo via vm (sem module.exports) pra
// manter o script 100% compatível com content script de navegador (sem CJS/ESM).
// Rodar com: node --test extension/content/transpose.test.js

const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "transpose.js"), "utf8");
const context = {};
vm.createContext(context);
vm.runInContext(source, context);
const { transposeChordSymbol, transposeKeyLabel } = context;

test("semitons 0 (ou falsy) devolve o símbolo sem alterar", () => {
  assert.equal(transposeChordSymbol("C", 0), "C");
  assert.equal(transposeChordSymbol("Cm7", 0), "Cm7");
});

test("transpõe acorde simples", () => {
  assert.equal(transposeChordSymbol("C", 2), "D");
  assert.equal(transposeChordSymbol("G", 5), "C");
});

test("preserva extensões do acorde (m7, sus4, maj7, b5)", () => {
  assert.equal(transposeChordSymbol("Cm7", 2), "Dm7");
  assert.equal(transposeChordSymbol("Gsus4", 2), "Asus4");
  assert.equal(transposeChordSymbol("Fmaj7", 5), "A#maj7");
  assert.equal(transposeChordSymbol("Bm7b5", 1), "Cm7b5"); // "b5" é da extensão, não é bemol da raiz
});

test("transpõe slash chords (baixo junto com a fundamental)", () => {
  assert.equal(transposeChordSymbol("G/B", 2), "A/C#");
  assert.equal(transposeChordSymbol("C/E", -1), "B/D#");
});

test("normaliza bemol pra sustenido antes de transpor", () => {
  assert.equal(transposeChordSymbol("Db", 1), "D");
  assert.equal(transposeChordSymbol("Ebm7", 2), "Fm7");
});

test("dá a volta no ciclo cromático (positivo e negativo)", () => {
  assert.equal(transposeChordSymbol("C", 11), "B");
  assert.equal(transposeChordSymbol("C", -11), "C#");
  assert.equal(transposeChordSymbol("C", 12), "C");
});

test("símbolo sem nota reconhecível (N.C.) fica intacto", () => {
  assert.equal(transposeChordSymbol("N.C.", 3), "N.C.");
});

test("transpõe o label de tonalidade preservando 'maior'/'menor'", () => {
  assert.equal(transposeKeyLabel("C maior", 2), "D maior");
  assert.equal(transposeKeyLabel("D# menor", 1), "E menor");
});

test("transposeKeyLabel com semitons 0 ou tom vazio devolve como veio", () => {
  assert.equal(transposeKeyLabel("C maior", 0), "C maior");
  assert.equal(transposeKeyLabel(null, 2), null);
});
