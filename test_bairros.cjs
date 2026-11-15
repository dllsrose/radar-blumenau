const assert = require('node:assert');
const {BAIRROS, bairrosCitados} = require('./dist/bairros.js');

assert.strictEqual(BAIRROS.length, 35);
assert.strictEqual(new Set(BAIRROS).size, 35);

const casos = [
  ['localizado no bairro Velha.', ['Velha']],
  ['no bairro Velha Central, próximo ao mercado', ['Velha Central']],
  ['nos bairros Velha Central e Água Verde. Justificativa', ['Água Verde', 'Velha Central']],
  ['nos bairros Garcia, Progresso e Glória', ['Garcia', 'Glória', 'Progresso']],
  ['Bairro: Itoupava Norte', ['Itoupava Norte']],
  ['no bairro da Velha e no Bairro do Salto', ['Salto', 'Velha']],
  ['bairro Salto do Norte', ['Salto do Norte']],
  ['BAIRRO AGUA VERDE', ['Água Verde']],
  // Sem a palavra "bairro" antes do nome, não conta.
  ['Rua Progresso, em frente ao centro de saúde', []],
  ['manutenção na Rua Victor Konder', []],
  ['moradores da Velha pedem', []],
  // Depois de um bairro só, o que vem após "e" não é lista.
  ['no bairro Velha e no centro de saúde', ['Velha']],
  ['nos bairros Velha e centro de convivência', ['Velha']],
  // Nome parecido não é confundido.
  ['bairro Itoupavazinha', ['Itoupavazinha']],
  ['bairro Velhaco', []],
  ['melhorias em diversos bairros da cidade', []],
  // Grafias erradas conhecidas dos textos oficiais vão para o nome oficial.
  ['no bairro Vorsdadt.', ['Vorstadt']],
  ['bairro Velhas Grande. Justificativa', ['Velha Grande']],
  ['bairro Itoupava Centrral?', ['Itoupava Central']],
  ['bairro Via Nova.', ['Vila Nova']],
  ['Bairro Panso Manso, defronte ao', ['Passo Manso']],
  // Pontuação ou palavra colada entre "bairro" e o nome.
  ['nº 1060, noBairro Vila Nova. Justificativa', ['Vila Nova']],
  ['localizado no bairro .Vila Nova.', ['Vila Nova']],
  ['no bairro do Do Salto. Obs', ['Salto']],
  // Localidade que não é bairro oficial continua de fora; grafia errada sem "bairro" também.
  ['bairro Grande Garcia', []],
  ['bairro Nova Rússia', []],
  ['moradores da Vorsdadt', []],
  ['', []],
];
for (const [texto, esperado] of casos) {
  assert.deepStrictEqual(bairrosCitados(texto).sort(), esperado.slice().sort(), texto);
}
console.log('Reconhecimento de bairros: OK');
