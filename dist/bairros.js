/* Radar Blumenau — reconhece bairros citados no texto de uma proposta.

   Regra conservadora: só conta quando o texto escreve "bairro" (ou "bairros")
   seguido do nome. Assim "Rua Progresso" ou "centro de saúde" não viram bairro.
   Quem cita só a rua fica de fora: é limite conhecido, avisado na página.

   Lista dos 35 bairros oficiais de Blumenau (divisão em vigor desde 2006). */
const BAIRROS = [
  'Água Verde', 'Badenfurt', 'Boa Vista', 'Bom Retiro', 'Centro', 'Escola Agrícola', 'Fidélis',
  'Fortaleza', 'Fortaleza Alta', 'Garcia', 'Glória', 'Itoupava Central', 'Itoupava Norte',
  'Itoupava Seca', 'Itoupavazinha', 'Jardim Blumenau', 'Nova Esperança', 'Passo Manso',
  'Ponta Aguda', 'Progresso', 'Ribeirão Fresco', 'Salto', 'Salto do Norte', 'Salto Weissbach',
  'Testo Salto', 'Tribess', 'Valparaíso', 'Velha', 'Velha Central', 'Velha Grande',
  'Victor Konder', 'Vila Formosa', 'Vila Itoupava', 'Vila Nova', 'Vorstadt'
];

const semAcento = s => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
// Grafias erradas que aparecem nos textos oficiais, conferidas uma a uma na base e levadas ao
// nome oficial. Só valem depois da palavra "bairro", como os nomes certos. Localidades que não são
// bairro oficial (Grande Garcia, Santa Maria, Nova Rússia…) continuam de fora.
const GRAFIAS = {
  'vorsdadt': 'Vorstadt', 'itoupava centrral': 'Itoupava Central', 'velhas grande': 'Velha Grande',
  'boa vita': 'Boa Vista', 'paso manso': 'Passo Manso', 'panso manso': 'Passo Manso',
  'itouopavazinha': 'Itoupavazinha', 'ituvavazinha': 'Itoupavazinha', 'via nova': 'Vila Nova',
  'gracia': 'Garcia', 'badenfurf': 'Badenfurt', 'bademfurt': 'Badenfurt', 'pnta aguda': 'Ponta Aguda',
  'escolas agricola': 'Escola Agrícola', 'vilka itoupava': 'Vila Itoupava'
};
// Nomes mais longos primeiro: "Velha Central" antes de "Velha".
const CHAVES = [...BAIRROS.map(nome => ({nome, chave: semAcento(nome)})), ...Object.entries(GRAFIAS).map(([chave, nome]) => ({nome, chave}))].sort((a, b) => b.chave.length - a.chave.length);

// Lê um nome de bairro no começo do trecho. Devolve {nome, resto} ou null.
function lerNome(trecho) {
  const limpo = trecho.replace(/^[\s:,.-]*(?:d[aeo]s?\s+)*/, '');
  const achado = CHAVES.find(c => limpo.startsWith(c.chave) && !/[a-z0-9]/.test(limpo[c.chave.length] || ''));
  return achado ? {nome: achado.nome, resto: limpo.slice(achado.chave.length)} : null;
}

function bairrosCitados(texto) {
  const t = semAcento(texto), achados = new Set();
  // Aceita também a palavra colada na anterior, como em "noBairro Vila Nova".
  const marca = /\b(?:[nd][ao])?bairro(s?)\b/g;
  let m;
  while ((m = marca.exec(t))) {
    let item = lerNome(t.slice(marca.lastIndex, marca.lastIndex + 200));
    if (!item) continue;
    achados.add(item.nome);
    // "bairros A, B e C": segue a lista enquanto vier outro nome logo depois.
    while (m[1] && item) {
      const depois = item.resto.match(/^\s*(?:,|e\b)\s*/);
      item = depois ? lerNome(item.resto.slice(depois[0].length)) : null;
      // "…e centro de convivência": nome seguido de "de/do/da" não é bairro.
      if (item && /^\s+d[aeo]s?\b/.test(item.resto)) item = null;
      if (item) achados.add(item.nome);
    }
  }
  return BAIRROS.filter(nome => achados.has(nome));
}

if (typeof module !== 'undefined') module.exports = {BAIRROS, bairrosCitados};
