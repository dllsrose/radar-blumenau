import json
from pathlib import Path
from radar import validate
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
urls={doc['url'] for doc in d['documents']}
for group in d['repeatedRequests']:
    assert group['count']==len(set(group['documents']))>=2
    assert len(group['dates'])>=2
    assert set(group['documents'])<=urls
raw=(r/'dist/data.json').read_text(encoding='utf-8')
assert '?token=' not in raw,'URLs temporárias não devem ser publicadas'
print('Site e base conferidos:',json.dumps(d['validation'],ensure_ascii=True))
