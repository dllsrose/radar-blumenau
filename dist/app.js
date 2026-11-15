'use strict';

/* ============================================================
   Radar Blumenau — interface principal
   Lê dist/data.json (schemaVersion 2) e dist/audit.json.
   A conferência de atas fica em attendance.js.
   ============================================================ */

/* ---------- Utilidades ---------- */
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const norm = s => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const fmt = d => d.split('-').reverse().join('/');
const number = n => n.toLocaleString('pt-BR');
const source = (url, label = 'Fonte oficial ↗') =>
  `<a class="source" href="${esc(url)}" target="_blank" rel="noopener">${esc(label)}</a>`;

/* ---------- Estado ---------- */
const PAGE_SIZE = 10;
const VIEWS = ['inicio', 'propostas', 'ruas', 'vereadores', 'presencas', 'sessoes', 'metodo'];
// Endereços antigos continuam funcionando.
const LEGACY = {recorrentes: 'ruas', 'presencas-conferidas': 'presencas', auditoria: 'presencas'};

let activeFrom = '', activeTo = '';
let data, audit;
let filtered = [], periodDocs = [], periodSessions = [];
let page = 1, repeatLimit = 8, sessionLimit = 12;
let currentView = 'inicio';

const range = () => `${fmt(activeFrom)} a ${fmt(activeTo)}`;
const inPeriod = d => d >= activeFrom && d <= activeTo;
const ownDocs = p => periodDocs.filter(d => d.authorIds.includes(p.id));

/* ---------- Navegação por abas (hash) ---------- */
function parseHash() {
  const raw = location.hash.replace(/^#\/?/, '');
  const [path, query = ''] = raw.split('?');
  const [name, arg = ''] = path.split('/');
  const view = VIEWS.includes(name) ? name : (LEGACY[name] || 'inicio');
  return {view, arg: decodeURIComponent(arg), params: new URLSearchParams(query)};
}

function route() {
  const {view, arg, params} = parseHash();
  const changed = view !== currentView;
  currentView = view;
  document.body.dataset.view = view;
  document.querySelectorAll('.view').forEach(s => { s.hidden = s.dataset.view !== view; });
  document.querySelectorAll('[data-nav]').forEach(a => {
    if (a.dataset.nav === view) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  const menu = $('.menu-mobile'); if (menu) menu.open = false;

  if (data) {
    // Período vindo do link compartilhado.
    const de = params.get('de'), ate = params.get('ate');
    if (de && ate && (de !== activeFrom || ate !== activeTo)) { $('#from').value = de; $('#to').value = ate; updatePeriod(); }

    if (view === 'propostas' && [...params.keys()].some(k => ['q', 'autor', 'cat'].includes(k))) {
      $('#search').value = params.get('q') || '';
      $('#author').value = params.get('autor') || '';
      $('#category').value = params.get('cat') || '';
      filter();
    }
    if (view === 'ruas' && params.has('q')) { $('#repeat-search').value = params.get('q'); repeatLimit = 8; renderRepeats(); }
    if (view === 'vereadores' && arg && data.people.some(p => p.id === arg)) profile(arg);
    else if ($('#profile').open) $('#profile').close();
  }
  if (changed) window.scrollTo(0, 0);
}

// Mantém o endereço igual ao que está na tela, para poder compartilhar.
function syncHash() {
  if (!data) return;
  const p = new URLSearchParams();
  if (currentView === 'propostas') {
    if ($('#search').value.trim()) p.set('q', $('#search').value.trim());
    if ($('#author').value) p.set('autor', $('#author').value);
    if ($('#category').value) p.set('cat', $('#category').value);
  }
  if (currentView === 'ruas' && $('#repeat-search').value.trim()) p.set('q', $('#repeat-search').value.trim());
  if (activeFrom !== data.start || activeTo !== data.end) { p.set('de', activeFrom); p.set('ate', activeTo); }
  const query = p.toString();
  history.replaceState(null, '', '#' + currentView + (query ? '?' + query : ''));
}

/* ---------- Período ---------- */
function updatePeriod() {
  if (!data) return;
  const from = $('#from').value, to = $('#to').value;
  if (!from || !to || from > to || from < data.start || to > data.end) {
    $('#period-error').textContent = `Escolha um intervalo válido dentro da cobertura. Os resultados continuam em ${range()}.`;
    return;
  }
  $('#period-error').textContent = '';
  activeFrom = from; activeTo = to;
  periodDocs = data.documents.filter(d => inPeriod(d.date));
  periodSessions = data.sessions.filter(s => inPeriod(s.date));
  sessionLimit = 12;

  const votes = periodSessions.reduce((n, s) => n + s.votes.filter(v => v.rows.length).length, 0);
  const stats = [
    [data.people.length, 'participantes cadastrados', data.sources.roster],
    [periodDocs.length, 'propostas no período', 'https://digital.camarablu.sc.gov.br/documentos/tipo:legislativo-2'],
    [periodSessions.length, 'reuniões na base principal', 'https://digital.camarablu.sc.gov.br/sessoes'],
    [votes, 'registros de votação', 'https://digital.camarablu.sc.gov.br/sessoes']
  ];
  $('#stats').innerHTML = stats.map(([n, t, u]) => `
    <div class="stat">
      <strong><a href="${esc(u)}" target="_blank" rel="noopener" aria-label="Fonte oficial: ${esc(t)}">${number(n)}</a></strong>
      <span>${t}</span>
      ${source(u)}
    </div>`).join('');
  $('#session-period').textContent = range();

  renderPeople(); renderSessions(); filter(); renderRepeats();
  if (typeof window.renderAttendanceAudit === 'function') window.renderAttendanceAudit();
}

/* ---------- Propostas ---------- */
function filter() {
  if (!data) return;
  const q = norm($('#search').value.trim()), id = $('#author').value, cat = $('#category').value;
  filtered = periodDocs.filter(d => (!q || d.search.includes(q)) && (!id || d.authorIds.includes(id)) && (!cat || d.category === cat));
  page = 1;
  renderDocs();
}

function documentCard(d) {
  const short = d.text.length > 245 ? d.text.slice(0, 245) + '…' : d.text;
  return `
    <article class="card doc">
      <div class="doc-top">
        <span class="tag" data-cat="${esc(d.category)}">${esc(d.category)}</span>
        <span class="doc-date">Protocolo <strong>${fmt(d.date)}</strong></span>
      </div>
      <h3>${esc(d.title)}</h3>
      <p>${esc(short)}</p>
      <p class="meta">Autoria: ${esc(d.authors)}</p>
      <div class="doc-actions">
        <details>
          <summary>Ler proposta e situação</summary>
          <p class="doc-full">${esc(d.text)}</p>
          <p class="meta">${esc(d.meta)}</p>
          <p class="meta">Categoria calculada automaticamente. Confira a fonte.</p>
        </details>
        ${source(d.url, 'Ver proposta oficial ↗')}
      </div>
    </article>`;
}

function renderDocs() {
  const max = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  page = Math.min(page, max);
  $('#result-count').textContent = `${number(filtered.length)} ${filtered.length === 1 ? 'proposta' : 'propostas'} · ${range()}`;
  $('#documents').innerHTML = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map(documentCard).join('')
    || '<div class="empty"><strong>Nenhum registro nesta busca.</strong><p>Tente outra grafia ou remova filtros. Isso não significa ausência de trabalho fora da base coletada.</p></div>';
  $('#page').textContent = `${number(page)} de ${number(max)}`;
  $('#prev').disabled = page === 1;
  $('#next').disabled = page === max;
}

/* ---------- Sessões e votos ---------- */
function sessionKind(s) {
  const t = norm(s.title);
  return t.includes('comissao') ? 'Comissões' : t.includes('frente parlamentar') ? 'Frentes parlamentares' : 'Plenário';
}
const attendanceStatus = a => a ? (a.status || 'Situação não informada') : 'Sem registro';
const attendanceFor = p => periodSessions.map(s => ({s, a: s.attendance.find(a => a.personIds.includes(p.id))}));

function sessionContent(s) {
  const attendance = s.attendance.map(a => `<div>${esc(a.name)}<span>${esc(attendanceStatus(a))}</span></div>`).join('')
    || '<p>Sem registro nominal disponível.</p>';
  const votes = s.votes.map(v => `
    <details class="vote">
      <summary>${esc(v.title)}</summary>
      ${v.notice ? `<p class="note"><strong>Resultado nominal não disponível.</strong> ${esc(v.notice)}</p>` : ''}
      <div class="vote-table">${v.rows.map(r => `<div><span>${esc(r.name)}</span><strong>${esc(r.vote)}</strong></div>`).join('')}</div>
      ${source(v.url, 'Conferir registro de votos ↗')}${v.documentUrl ? ' · ' + source(v.documentUrl, 'Ler matéria ↗') : ''}
    </details>`).join('') || '<p class="note">Nenhuma votação nominal extraída desta página.</p>';
  return `
    ${source(s.url, 'Abrir sessão oficial ↗')}
    ${s.dateNote ? `<p class="note"><strong>Divergência de data na fonte:</strong> ${esc(s.dateNote)}</p>` : ''}
    <p class="note">Estados reproduzidos da fonte. Quem não aparece não é considerado ausente pelo Radar.</p>
    <div class="attendance">${attendance}</div>
    <h3>Votações da reunião</h3>
    ${votes}`;
}

function renderSessions() {
  const q = norm($('#session-search').value.trim()), kind = $('#session-kind').value;
  const list = periodSessions.filter(s => (!kind || sessionKind(s) === kind) && (!q || norm(s.title).includes(q)));
  $('#session-count').textContent = `${number(list.length)} ${list.length === 1 ? 'reunião' : 'reuniões'} · ${range()}`;
  $('#sessions').innerHTML = list.slice(0, sessionLimit).map(s => `
    <details class="card session">
      <summary>
        <span class="session-title">${esc(s.title)}</span>
        <span class="chips"><span class="chip">${sessionKind(s)}</span><span class="chip">${s.attendance.length} registros nominais</span></span>
      </summary>
      <div class="session-content"></div>
    </details>`).join('') || '<p class="empty">Nenhuma sessão coletada para este intervalo ou busca.</p>';
  document.querySelectorAll('#sessions .session').forEach((element, index) => {
    element.addEventListener('toggle', () => {
      element.querySelector('.session-content').innerHTML = element.open ? sessionContent(list[index]) : '';
    });
  });
  if (list.length > sessionLimit) {
    $('#sessions').insertAdjacentHTML('beforeend', `<button id="more-sessions" class="button button-ghost" type="button">Mostrar mais sessões (${list.length - sessionLimit} restantes) ↓</button>`);
    $('#more-sessions').onclick = () => { sessionLimit += 12; renderSessions(); };
  }
}

/* ---------- Vereadores ---------- */
// O portal entrega a foto em 65 px; pedimos uma versão maior e, se falhar, voltamos à original.
const bigPhoto = url => String(url).replace(/\/w\d+-h\d+-/, '/w240-h240-');
const photoTag = (p, alt) => `<img loading="lazy" src="${esc(bigPhoto(p.photo))}" data-fallback="${esc(p.photo)}" alt="${esc(alt)}">`;
document.addEventListener('error', e => {
  const img = e.target;
  if (img.tagName === 'IMG' && img.dataset.fallback) { const f = img.dataset.fallback; delete img.dataset.fallback; img.src = f; }
}, true);

function renderPeople() {
  $('#people').innerHTML = data.people.map(p => `
    <a class="card person" href="#vereadores/${encodeURIComponent(p.id)}" aria-label="Ver perfil de ${esc(p.name)}">
      ${photoTag(p, '')}
      <div class="person-body">
        <h3>${esc(p.name)}</h3>
        <small>${esc(p.party)} · cadastro da legislatura</small>
        <span class="person-count"><strong>${number(ownDocs(p).length)}</strong> propostas no período</span>
      </div>
      <span class="person-arrow" aria-hidden="true">→</span>
    </a>`).join('');
}

function profile(id) {
  const p = data.people.find(p => p.id === id), docs = ownDocs(p), records = attendanceFor(p);
  const count = records.reduce((o, {s, a}) => { const key = sessionKind(s) + ' · ' + attendanceStatus(a); o[key] = (o[key] || 0) + 1; return o; }, {});
  const votes = periodSessions.flatMap(s => s.votes.flatMap(v => v.rows.filter(r => r.personIds.includes(id)).map(r => ({s, v, r}))));

  $('#profile-content').innerHTML = `
    <div class="profile-head">
      ${photoTag(p, 'Retrato oficial de ' + p.name)}
      <div>
        <p class="eyebrow">Participante da legislatura · ${esc(p.party)}</p>
        <h2>${esc(p.name)}</h2>
        ${source(p.url, 'Ficha oficial ↗')}
      </div>
    </div>
    <p><strong>${number(docs.length)} propostas</strong> com autoria identificada entre ${range()}.</p>
    <p class="note">Contagem calculada na base. Não é avaliação de desempenho nem declaração de exercício em todo o período.</p>
    <div class="profile-actions">
      <button class="button" id="show-author" type="button">Ler propostas deste vereador →</button>
      <button class="button button-ghost" id="show-attendance-audit" type="button">Conferir presenças nas atas →</button>
    </div>
    <h3>Presenças registradas nas páginas de sessão</h3>
    <p class="note">Este resumo usa a base de sessões e votos. A conferência ampliada inclui as demais reuniões do calendário e compara as atas.</p>
    <div class="presence-summary">${Object.entries(count).map(([k, v]) => `<span><strong>${v}</strong> ${esc(k)}</span>`).join('')}</div>
    <p class="note">Contagens nominais, sem inferir comparecimento obrigatório durante licenças ou substituições. Veja as fontes abaixo.</p>
    <details class="fold">
      <summary>Conferir sessão por sessão (${records.length})</summary>
      ${records.map(({s, a}) => `<div class="row">${source(s.url, s.title)}<br><strong>${esc(a ? attendanceStatus(a) : 'Sem registro nominal — não interpretado como ausência')}</strong></div>`).join('')}
    </details>
    <details class="fold">
      <summary>Conferir votos publicados (${votes.length})</summary>
      <div id="profile-votes"></div>
      <button class="button button-ghost" id="profile-more-votes" type="button">Mostrar mais votos ↓</button>
    </details>`;

  let voteLimit = 50;
  const moreVotes = $('#profile-more-votes');
  const renderVotes = () => {
    $('#profile-votes').innerHTML = votes.slice(0, voteLimit).map(({s, v, r}) =>
      `<div class="row">${fmt(s.date)} · ${esc(v.title)}<br><strong>${esc(r.vote)}</strong> · ${source(v.url, 'Ver voto oficial ↗')}</div>`).join('')
      || '<p>Sem voto nominal identificado neste período.</p>';
    moreVotes.hidden = voteLimit >= votes.length;
    moreVotes.textContent = `Mostrar mais votos (${Math.max(0, votes.length - voteLimit)} restantes) ↓`;
  };
  moreVotes.onclick = () => { voteLimit += 50; renderVotes(); };
  renderVotes();

  $('#show-author').onclick = () => { location.hash = '#propostas?autor=' + encodeURIComponent(id); };
  $('#show-attendance-audit').onclick = () => { location.hash = '#presencas'; };
  if (!$('#profile').open) $('#profile').showModal();
  $('#profile').scrollTop = 0;
}

/* ---------- Minha rua (pedidos recorrentes) ---------- */
function renderRepeats() {
  if (!data) return;
  const q = norm($('#repeat-search').value.trim()), allowed = new Map(periodDocs.map(d => [d.url, d]));
  const groups = data.repeatedRequests
    .map(g => ({...g, docs: g.documents.filter(u => allowed.has(u)).map(u => allowed.get(u))}))
    .filter(g => g.docs.length >= 2 && new Set(g.docs.map(d => d.date)).size >= 2 && (!q || norm(g.street + ' ' + g.topic).includes(q)));
  $('#repeat-count').textContent = `${number(groups.length)} grupos no período selecionado · contagens calculadas`;
  $('#repeat-results').innerHTML = groups.slice(0, repeatLimit).map(g => `
    <details class="card repeat">
      <summary>
        <span><strong>${esc(g.street)}</strong><small>${esc(g.topic)}</small></span>
        <span class="repeat-number">${g.docs.length} pedidos</span>
      </summary>
      <p class="note">Agrupamento automático. Pode incluir trechos e situações diferentes. Não comprova falta de atendimento.</p>
      ${g.docs.sort((a, b) => a.date.localeCompare(b.date)).map(d => `
        <div class="row">
          <strong>${fmt(d.date)}</strong> · ${esc(d.authors)}<br>
          ${esc(d.title)} · ${source(d.url, 'Ler pedido ↗')}
          <p>${esc(d.text.slice(0, 260))}${d.text.length > 260 ? '…' : ''}</p>
        </div>`).join('')}
    </details>`).join('') || '<p class="empty">Nenhum grupo encontrado. Nem todo logradouro ou assunto é reconhecido automaticamente.</p>';
  $('#repeat-more').hidden = groups.length <= repeatLimit;
}

/* ---------- Conferência inicial por amostragem ---------- */
function renderAudit() {
  $('#audit-scope').textContent = `Conferência por amostragem realizada em ${fmt(audit.checkedAt)}. ${audit.scope} Não é auditoria externa.`;
  $('#audit-results').innerHTML = audit.samples.map(s => `
    <article class="row">
      <span class="tag">${s.match ? 'Conferido: coincide' : 'Comparação pendente'}</span>
      <h3>${fmt(s.date)} · ${esc(s.type)}</h3>
      <p>${esc(s.result)}</p>
      ${source(s.source, s.match ? 'Conferir ata oficial ↗' : 'Consultar atas publicadas ↗')} · ${source(s.session, 'Conferir sessão ↗')}
    </article>`).join('');
}

/* ---------- Exportação ---------- */
function download(content, type, name) {
  const u = URL.createObjectURL(new Blob([content], {type}));
  const a = document.createElement('a');
  a.href = u; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
}

function exportJson() {
  if (!data) return;
  const clean = filtered.map(({search, ...d}) => d);
  const payload = {periodo: {inicio: activeFrom, fim: activeTo}, coleta: data.collectedAt, criterio: 'Resultados filtrados; grupos calculados automaticamente; fontes em cada registro', registros: clean};
  download(JSON.stringify(payload, null, 2), 'application/json;charset=utf-8', 'radar-blumenau-busca.json');
}

function exportCsv() {
  if (!data) return;
  // Ponto e vírgula e BOM: abre direto no Excel em português.
  const cell = v => '"' + String(v ?? '').replace(/"/g, '""').replace(/\r?\n/g, ' ') + '"';
  const head = ['Data do protocolo', 'Título', 'Categoria (calculada)', 'Autoria', 'Texto', 'Situação', 'Fonte oficial'];
  const lines = filtered.map(d => [fmt(d.date), d.title, d.category, d.authors, d.text, d.meta, d.url].map(cell).join(';'));
  download('﻿' + [head.map(cell).join(';'), ...lines].join('\r\n'), 'text/csv;charset=utf-8', 'radar-blumenau-busca.csv');
}

/* ---------- Carga ---------- */
async function loadFile(name) {
  const embedded = document.getElementById(name);
  if (embedded) return JSON.parse(embedded.textContent);
  const r = await fetch(name);
  if (!r.ok) throw new Error('Não foi possível carregar ' + name);
  return r.json();
}

async function init() {
  try {
    [data, audit] = await Promise.all([loadFile('data.json'), loadFile('audit.json')]);
    if (data.schemaVersion !== 2) throw new Error('Base incompatível');
    data.people.sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'));
    data.documents.forEach(d => { d.search = norm(d.text + ' ' + d.title + ' ' + d.authors); });

    $('#from').min = $('#to').min = data.start;
    $('#from').max = $('#to').max = data.end;
    $('#from').value = data.start; $('#to').value = data.end;
    $('#hero-period').textContent = `${fmt(data.start)} a ${fmt(data.end)}`;

    $('#coverage-copy').innerHTML = `<strong>Cobertura: ${fmt(data.start)} a ${fmt(data.end)}.</strong> Propostas por protocolo e reuniões ordinárias e extraordinárias publicadas, incluindo plenário, comissões e frentes parlamentares. O levantamento ampliado de presenças está na conferência das atas. A informação ausente não vira falta. <a href="#presencas">Veja a conferência e os limites →</a>`;
    const unavailable = data.sessions.reduce((n, s) => n + s.votes.filter(v => !v.rows.length).length, 0);
    if (unavailable) $('#coverage-copy').insertAdjacentHTML('beforeend', ` <strong>${number(unavailable)} ${unavailable === 1 ? 'matéria sem resultado nominal disponível na fonte, sinalizada' : 'matérias sem resultado nominal disponível na fonte, sinalizadas'} nas reuniões.</strong>`);

    $('#author').innerHTML = '<option value="">Todos os autores</option>' + data.people.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
    const checked = new Date(data.collectedAt).toLocaleString('pt-BR', {timeZone: 'America/Sao_Paulo'});
    $('#collected').textContent = `Última coleta concluída: ${checked} (Brasília). Cobertura de ${fmt(data.start)} a ${fmt(data.end)}. ${data.documentCoverage.reduce((n, r) => n + r.pages, 0)} páginas de documentos percorridas nesta rodada. Atualização da página não inicia coleta.`;

    renderAudit();
    updatePeriod();
    const age = Date.now() - new Date(data.collectedAt).getTime();
    if (age > 48 * 3600000) $('#coverage-copy').insertAdjacentHTML('beforeend', ' <strong>Atenção: a última coleta tem mais de 48 horas. Consulte o histórico de atualização.</strong>');
    route();
  } catch (e) {
    $('#stats').innerHTML = '<p role="alert">Não foi possível carregar a base. Nenhum total foi inferido. Recarregue a página ou consulte a fonte oficial.</p>';
    console.error(e);
  }
}

/* ---------- Eventos ---------- */
window.addEventListener('hashchange', route);

$('#home-search-form').addEventListener('submit', e => {
  e.preventDefault();
  const q = $('#home-search').value.trim();
  location.hash = '#propostas' + (q ? '?q=' + encodeURIComponent(q) : '');
});

$('#search').addEventListener('input', () => { filter(); syncHash(); });
$('#author').addEventListener('change', () => { filter(); syncHash(); });
$('#category').addEventListener('change', () => { filter(); syncHash(); });
$('#clear').onclick = () => { $('#search').value = ''; $('#author').value = ''; $('#category').value = ''; filter(); syncHash(); };
$('#prev').onclick = () => { page--; renderDocs(); $('#propostas').scrollIntoView(); };
$('#next').onclick = () => { page++; renderDocs(); $('#propostas').scrollIntoView(); };
$('#export').onclick = exportJson;
$('#export-csv').onclick = exportCsv;
$('#share').onclick = async () => {
  syncHash();
  const button = $('#share'), original = button.textContent;
  try { await navigator.clipboard.writeText(location.href); button.textContent = 'Link copiado ✓'; }
  catch { button.textContent = 'Copie o endereço do navegador'; }
  setTimeout(() => { button.textContent = original; }, 2500);
};

$('#from').addEventListener('change', () => { updatePeriod(); syncHash(); });
$('#to').addEventListener('change', () => { updatePeriod(); syncHash(); });
$('#all-period').onclick = () => { if (data) { $('#from').value = data.start; $('#to').value = data.end; updatePeriod(); syncHash(); } };

$('#repeat-search').oninput = () => { repeatLimit = 8; renderRepeats(); syncHash(); };
$('#repeat-more').onclick = () => { repeatLimit += 8; renderRepeats(); };

$('#session-search').oninput = () => { sessionLimit = 12; renderSessions(); };
$('#session-kind').onchange = () => { sessionLimit = 12; renderSessions(); };

$('#close-profile').onclick = () => $('#profile').close();
$('#profile').addEventListener('close', () => {
  if (location.hash.startsWith('#vereadores/')) history.replaceState(null, '', '#vereadores');
});
// Fecha a janela ao tocar fora dela.
document.querySelectorAll('dialog').forEach(d => d.addEventListener('click', e => { if (e.target === d) d.close(); }));

route();
init();
