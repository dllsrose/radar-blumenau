import json
from pathlib import Path
from radar import validate, calendar_date, public_text, classify, nominal_keys
r=Path(__file__).parent
d=json.loads((r/'dist/data.json').read_text(encoding='utf-8'))
assert validate(d)==d['validation'], 'Totais armazenados divergem dos registros'
for f in ('index.html','style.css','app.js','audit.json'):assert (r/'dist'/f).stat().st_size>0,f
audit=json.loads((r/'dist/audit.json').read_text(encoding='utf-8'))
assert len(audit['samples'])>=3
ids={p['id'] for p in d['people']}
for doc in d['documents']:
    assert public_text(doc['text'])==doc['text'], 'Texto contém padrão de contato não ocultado'
    assert classify(doc['title'],doc['text'])==doc['category'], 'Regra de classificação não aplicada igualmente'
    assert all(id in ids for id in doc['authorIds'])
    assert doc['url'].startswith('https://digital.camarablu.sc.gov.br/documento/')
session_urls=[s['url'] for s in d['sessions']]
assert len(session_urls)==len(set(session_urls)), 'Sessões duplicadas'
for session in d['sessions']:
    assert session['date']==calendar_date(session['title']), 'Data da sessão difere do calendário oficial'
    assert d['start']<=session['date']<=d['end'], 'Sessão fora do período'
    assert all(a['status'] in ('Presente','Ausente','Ausência justificada','Licença','') for a in session['attendance']), 'Estado nominal desconhecido: revisar antes de publicar'
    assert len(nominal_keys(session['attendance']))==len(session['attendance']), 'Presença duplicada'
    records=session['attendance']+[row for vote in session['votes'] for row in vote['rows']]
    for record in records:
        assert record.get('personIds'), 'Nome nominal sem vínculo no cadastro: '+record['name']
        assert all(person_id in ids for person_id in record['personIds'])
    for vote in session['votes']:
        assert len(nominal_keys(vote['rows']))==len(vote['rows']), 'Voto nominal duplicado'
        assert vote['rows'] or (vote.get('availability')=='unavailable' and vote.get('notice')), 'Votação vazia sem indicação explícita da fonte'
urls={doc['url'] for doc in d['documents']}
for group in d['repeatedRequests']:
    assert group['count']==len(set(group['documents']))>=2
    assert len(group['dates'])>=2
    assert set(group['documents'])<=urls
raw=(r/'dist/data.json').read_text(encoding='utf-8')
assert '?token=' not in raw,'URLs temporárias não devem ser publicadas'
print('Site e base conferidos:',json.dumps(d['validation'],ensure_ascii=True))

# A conferência mantém data e cobertura explícitas, inclusive na rotina diária.
a=json.loads((r/'dist/attendance-audit.json').read_text(encoding='utf-8'))
assert a['schemaVersion']==1 and a['counts']['inventoried']==len(a['minutes'])
assert a['counts']['downloaded']==sum(x['downloaded'] for x in a['minutes'])
assert len({x['url'] for x in a['minutes']})==len(a['minutes'])
known={x['id'] for x in a['people']}
allowed={'Presente','Ausência justificada','Ausência citada sem classificação','Licença','Afastamento','Revisão necessária'}
for minute in a['minutes']:
    assert minute['url'].startswith('https://digital.camarablu.sc.gov.br/documento/')
    assert not any(k in minute for k in ('text','pdfFile','textFile','error'))
    assert len({row['personId'] for row in minute['rows']})==len(minute['rows'])
    for row in minute['rows']:assert row['personId'] in known and row['status'] in allowed
    if minute['sessionUrl']:assert minute['sessionUrl'].startswith('https://digital.camarablu.sc.gov.br/sessao/')
assert len({m['sessionUrl'] for m in a['minutes'] if m['sessionUrl']})==a['counts']['matchedSessions']
assert len(a['sessionGaps'])==a['counts']['sessionGaps']
print('Conferência documental de atas validada:',a['counts']['inventoried'],'atas')

for gap in a['sessionGaps']:
    assert gap['url'].startswith('https://digital.camarablu.sc.gov.br/sessao/')
    for row in gap['rows']:assert row['personId'] in known

assert a['counts']['matchedSessions']+a['counts']['sessionGaps']==a['counts']['calendarSessions']
