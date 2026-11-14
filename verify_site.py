import json
from pathlib import Path
from radar import validate, calendar_date
r=Path(__file__).parent
d=json.loads((r/'dist/data.json').read_text(encoding='utf-8'))
validate(d)
for f in ('index.html','style.css','app.js','audit.json'):assert (r/'dist'/f).stat().st_size>0,f
audit=json.loads((r/'dist/audit.json').read_text(encoding='utf-8'))
assert len(audit['samples'])>=3
ids={p['id'] for p in d['people']}
for doc in d['documents']:
    assert all(id in ids for id in doc['authorIds'])
    assert doc['url'].startswith('https://digital.camarablu.sc.gov.br/documento/')
session_urls=[s['url'] for s in d['sessions']]
assert len(session_urls)==len(set(session_urls)), 'Sessões duplicadas'
for session in d['sessions']:
    assert session['date']==calendar_date(session['title']), 'Data da sessão difere do calendário oficial'
    assert d['start']<=session['date']<=d['end'], 'Sessão fora do período'
    assert all(a['status'] in ('Presente','Ausente','Ausência justificada','') for a in session['attendance']), 'Estado nominal desconhecido: revisar antes de publicar'
    records=session['attendance']+[row for vote in session['votes'] for row in vote['rows']]
    for record in records:
        assert record.get('personIds'), 'Nome nominal sem vínculo no cadastro: '+record['name']
        assert all(person_id in ids for person_id in record['personIds'])
    for vote in session['votes']:
        assert vote['rows'] or (vote.get('availability')=='unavailable' and vote.get('notice')), 'Votação vazia sem indicação explícita da fonte'
urls={doc['url'] for doc in d['documents']}
for group in d['repeatedRequests']:
    assert group['count']==len(set(group['documents']))>=2
    assert len(group['dates'])>=2
    assert set(group['documents'])<=urls
raw=(r/'dist/data.json').read_text(encoding='utf-8')
assert '?token=' not in raw,'URLs temporárias não devem ser publicadas'
print('Site e base conferidos:',json.dumps(d['validation'],ensure_ascii=True))
