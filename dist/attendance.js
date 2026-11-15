/* Radar Blumenau — conferência de presenças nas atas (lê dist/attendance-audit.json). */
const AUDIT_ABSENCE=['Ausência justificada','Ausência citada sem classificação'];
function attendanceTotals(audit,from,to,kind){
  const minutes=audit.minutes.filter(a=>a.date&&a.date>=from&&a.date<=to&&a.kind===kind);
  const eligible=minutes.filter(a=>!a.duplicateMeeting&&a.rows.length&&!a.issue);
  const totals=audit.people.map(p=>({...p,present:0,justified:0,unclassified:0,license:0,leave:0,conflict:0,records:[]}));
  const map=new Map(totals.map(p=>[p.id,p]));
  for(const a of eligible)for(const r of a.rows){const p=map.get(r.personId);if(!p)continue;
    const key={'Presente':'present','Ausência justificada':'justified','Ausência citada sem classificação':'unclassified','Licença':'license','Afastamento':'leave','Revisão necessária':'conflict'}[r.status];if(key)p[key]++;
    p.records.push({minute:a,row:r});
  }
  for(const p of totals){p.absences=p.justified+p.unclassified;p.denominator=p.present+p.absences;p.rate=p.denominator?100*p.absences/p.denominator:null;}
  return {totals,minutes,eligible};
}
if(typeof module!=='undefined')module.exports={attendanceTotals};
if(typeof document!=='undefined'){
let attendanceAudit,minutesLimit=20;
const aq=s=>document.querySelector(s),ae=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const af=d=>d?d.split('-').reverse().join('/'):'Data não extraída com segurança';
const al=(u,t)=>`<a href="${ae(u)}" target="_blank" rel="noopener">${ae(t)} ↗</a>`;
function dateReview(a){if(a.dateReviewMode==='pdf-page-reviewed')return `<p class="muted">Data lida e conferida na página ${ae(a.datePdfPage)} do PDF: ${af(a.date)}. ${ae(a.dateEvidence)} ${a.dateSourceUrl?al(a.dateSourceUrl,'Fonte de apoio'):''}</p>`;return a.sourceDate?`<p class="muted">Data escrita na ata: ${af(a.sourceDate)}. Data adotada: ${af(a.date)}. ${ae(a.dateEvidence)} ${a.dateSourceUrl?al(a.dateSourceUrl,'Fonte da correção'):''}</p>`:'';}
function auditRange(){return [typeof activeFrom!=='undefined'&&activeFrom||attendanceAudit.start,typeof activeTo!=='undefined'&&activeTo||attendanceAudit.end];}
window.renderAttendanceAudit=function(){
 if(!attendanceAudit)return;
 const [from,to]=auditRange(),kind=aq('#attendance-kind').value,sort=aq('#attendance-sort').value;
 const result=attendanceTotals(attendanceAudit,from,to,kind);
 const list=result.totals.sort((a,b)=>sort==='name'?a.name.localeCompare(b.name,'pt-BR'):(sort==='rate'?(b.rate??-1)-(a.rate??-1):b[sort]-a[sort])||a.name.localeCompare(b.name,'pt-BR'));
 aq('#attendance-coverage').textContent=`${af(from)} a ${af(to)} · ${result.eligible.length} documentos com identificação nominal (inclui complementações e leituras parciais) elegível de ${result.minutes.length} atas desse tipo no recorte. Contagens pela ata, inclusive quando a lista do portal diverge. Conferência disponível de ${af(attendanceAudit.start)} a ${af(attendanceAudit.end)}.${to>attendanceAudit.end||from<attendanceAudit.start?' Parte do intervalo selecionado está fora desta conferência datada.':''}`;
 // Um cartão por vereador, com os mesmos nove números da antiga tabela.
 const num=(label,value,strong)=>`<div><dt>${label}</dt><dd>${strong?`<strong>${value}</strong>`:value}</dd></div>`;
 aq('#attendance-table').innerHTML=list.map(p=>{
  const rate=p.rate===null?'—':p.rate.toLocaleString('pt-BR',{maximumFractionDigits:1})+'%';
  const bar=p.denominator?`<div class="bar" role="img" aria-label="${p.present} presenças, ${p.justified} ausências justificadas e ${p.unclassified} ausências sem classificação na ata"><span class="bar-present" style="flex:${p.present}"></span><span class="bar-justified" style="flex:${p.justified}"></span><span class="bar-unclassified" style="flex:${p.unclassified}"></span></div>`:'<p class="note">Sem registros nominais elegíveis neste recorte.</p>';
  return `<article class="card rank-card">
   <div class="rank-head">
    <button type="button" class="rank-name" data-attendance-person="${ae(p.id)}">${ae(p.name)} <span>ver fontes →</span></button>
    <span class="rank-rate"><strong>${rate}</strong><small>de ausências nos registros</small></span>
   </div>
   ${bar}
   <dl class="rank-nums">
    ${num('Ausências citadas',p.absences,true)}${num('Justificadas',p.justified)}${num('Sem classificação na ata',p.unclassified)}${num('Presenças',p.present)}${num('Licenças',p.license)}${num('Afastamentos',p.leave)}${num('A revisar',p.conflict)}${num('Registros para o percentual',p.denominator)}
   </dl>
  </article>`;}).join('');
 aq('#attendance-table').querySelectorAll('[data-attendance-person]').forEach(b=>b.onclick=()=>showAttendancePerson(list.find(p=>p.id===b.dataset.attendancePerson),kind));
 renderMinutes();
};
function showAttendancePerson(p,kind){
 const grouped=p.records.slice().sort((a,b)=>b.minute.date.localeCompare(a.minute.date));
 aq('#attendance-person-title').textContent=p.name+' · '+kind;
 aq('#attendance-person-content').innerHTML=`<p>${p.absences} ausências citadas: ${p.justified} justificadas e ${p.unclassified} sem classificação na ata. Licenças, afastamentos e contradições não entram no percentual.</p><p class="muted">A ausência de nome numa ata não foi contada como falta. O período de exercício legal não foi presumido. ${al(p.url,'Ficha oficial')}</p>${grouped.map(({minute:a,row:r})=>{const c=a.comparison.find(x=>x.personId===p.id);return `<div class="profile-row"><strong>${af(a.date)} · ${ae(r.status)}</strong>${dateReview(a)}<br>${al(a.url,a.title)}${a.sessionUrl?' · '+al(a.sessionUrl,'Página da reunião'):''}<p class="muted">${c?'Portal: '+ae(c.portalStatus)+' · '+ae(c.result):'Sem correspondência inequívoca com uma página de reunião.'}</p></div>`;}).join('')||'<p>Sem registros nominais elegíveis neste recorte.</p>'}`;
 aq('#attendance-person').showModal();
}
function renderMinutes(){
 const [from,to]=auditRange(),q=aq('#minutes-search').value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase(),status=aq('#minutes-status').value;
 let rows=attendanceAudit.minutes.filter(a=>(status==='outside'?(a.date&&(a.date<attendanceAudit.start||a.date>attendanceAudit.end)):(!a.date||(a.date>=from&&a.date<=to)))&&(!q||(a.title+' '+a.kind+' '+(a.committee||'')+' '+(a.date||'')).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().includes(q)));
 if(status==='differences')rows=rows.filter(a=>a.comparison.some(c=>c.result!=='Coincide'));
 if(status==='pending')rows=rows.filter(a=>!a.sessionUrl||a.issue||(a.duplicateMeeting&&!a.duplicateOf)||!a.date||a.rows.some(r=>r.status==='Revisão necessária'));
 rows.sort((a,b)=>(b.date||'').localeCompare(a.date||'')||a.title.localeCompare(b.title));
 aq('#minutes-count').textContent=`${rows.length} atas nesta consulta. Atas sem data extraída continuam visíveis para revisão.`;
 aq('#minutes-results').innerHTML=rows.slice(0,minutesLimit).map(a=>`<details class="audit-card"><summary><strong>${ae(a.title)}</strong> · ${af(a.date)} · ${ae(a.kind)}</summary>${dateReview(a)}${a.corroboratingSources?.length?`<p>${a.corroboratingSources.map(s=>al(s.url,s.label)).join(' · ')}</p>`:''}<p>${al(a.url,'Abrir ata oficial')}${a.sessionUrl?' · '+al(a.sessionUrl,'Abrir reunião oficial'):''}</p><p class="muted">${a.issue?ae(a.issue):a.sessionUrl?'Comparação nominal disponível abaixo.':'Página correspondente não associada de forma inequívoca.'}${a.reviewNote?' '+ae(a.reviewNote):''}${a.duplicateMeeting?(a.duplicateOf?' Republicação confirmada: a reunião é contada apenas pelo documento '+ae(a.duplicateOf)+'.':' Mais de uma ata para o mesmo tipo e data, sem distinção segura: excluídas da ordenação para evitar duplicidade.'):''}</p>${a.comparison.length?`<div class="table-scroll"><table><thead><tr><th>Nome</th><th>${a.nominalSource==='official-video-transcript'?'Gravação oficial + notícia':'Ata'}</th><th>Portal</th><th>Comparação</th></tr></thead><tbody>${a.comparison.map(c=>`<tr><td>${ae(attendanceAudit.people.find(p=>p.id===c.personId)?.name||c.personId)}</td><td>${ae(c.status)}</td><td>${ae(c.portalStatus)}</td><td>${ae(c.result)}</td></tr>`).join('')}</tbody></table></div>`:`<ul>${[...a.rows,...(a.historicalRows||[])].map(r=>`<li>${ae(r.name||attendanceAudit.people.find(p=>p.id===r.personId)?.name||r.personId)}: ${ae(r.status)}</li>`).join('')}</ul>`}</details>`).join('')||'<p>Nenhuma ata corresponde aos filtros.</p>';
 aq('#minutes-more').hidden=rows.length<=minutesLimit;
}
aq('#attendance-kind').onchange=window.renderAttendanceAudit;aq('#attendance-sort').onchange=window.renderAttendanceAudit;
aq('#minutes-search').oninput=()=>{minutesLimit=20;renderMinutes();};aq('#minutes-status').onchange=()=>{minutesLimit=20;renderMinutes();};aq('#minutes-more').onclick=()=>{minutesLimit+=20;renderMinutes();};aq('#close-attendance-person').onclick=()=>aq('#attendance-person').close();
loadFile('attendance-audit.json').then(a=>{attendanceAudit=a;aq('#attendance-audit-summary').textContent=`Conferência de ${new Date(a.checkedAt).toLocaleDateString('pt-BR')} · ${a.counts.inventoried} atas inventariadas; ${a.counts.downloaded} PDFs obtidos; ${a.counts.withNominalReading} documentos com identificação nominal (inclui complementações e leituras parciais); ${a.counts.calendarSessions} páginas de reunião no levantamento; ${a.counts.matchedSessions} reuniões associadas às atas. A seleção abrange todo o período, sem amostragem. Casos sem leitura ou associação segura permanecem pendentes.`;aq('#attendance-method').innerHTML=a.method.map(t=>`<li>${ae(t)}</li>`).join('');aq('#attendance-gaps').innerHTML=`<summary>Páginas de reunião sem ata associada (${a.sessionGaps.length})</summary><p class="muted">Inclui tipos sem ata localizada ou com data/título divergente. Não significa falta de vereador.</p>${a.sessionGaps.map(s=>`<details class="profile-row"><summary>${af(s.date)} · ${ae(s.title)}</summary><p>${al(s.url,'Fonte oficial da reunião')}</p><p class="muted">Estados apenas do portal, sem confirmação na ata.</p><ul>${s.rows.map(r=>`<li>${ae(a.people.find(p=>p.id===r.personId)?.name||r.personId)}: ${ae(r.status)}</li>`).join('')||'<li>Sem registro nominal publicado nesta página.</li>'}</ul></details>`).join('')}`;window.renderAttendanceAudit();}).catch(()=>{aq('#attendance-audit-summary').textContent='Não foi possível carregar a conferência. Nenhuma falta foi inferida.';});
}
