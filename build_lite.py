"""Gera dist/lite/: a mesma base de dist/data.json, dividida em arquivos menores.

O site abre com inicio.json (pequeno) e busca o resto por partes. Nada é
recalculado nem resumido: são os mesmos registros, apenas repartidos.
dist/data.json continua sendo a base oficial e não é alterado.

Uso: python build_lite.py
"""
import json
import shutil
from pathlib import Path

CHUNK = 2000  # propostas por arquivo de texto
PREFIX = 'https://digital.camarablu.sc.gov.br/documento/'
COLUMNS = ('id', 'title', 'date', 'category', 'authors', 'authorIds', 'meta')


def build(data):
    """Devolve {nome do arquivo: conteúdo} a partir da base completa."""
    docs, sessions = data['documents'], data['sessions']
    position = {d['url']: i for i, d in enumerate(docs)}
    assert len(position) == len(docs), 'Proposta com endereço repetido'

    by_author = {p['id']: 0 for p in data['people']}
    for d in docs:
        for person_id in d['authorIds']:
            by_author[person_id] += 1

    texts = [[d['text'] for d in docs[i:i + CHUNK]] for i in range(0, len(docs), CHUNK)]
    files = {f'texto-{i}.json': chunk for i, chunk in enumerate(texts)}

    files['inicio.json'] = {
        'schemaVersion': data['schemaVersion'], 'lite': 1,
        'start': data['start'], 'end': data['end'], 'collectedAt': data['collectedAt'],
        'people': data['people'], 'sources': data['sources'],
        'documentCoverage': data['documentCoverage'],
        'stats': {
            'documents': len(docs), 'sessions': len(sessions),
            'votes': sum(1 for s in sessions for v in s['votes'] if v['rows']),
            'unavailableVotes': sum(1 for s in sessions for v in s['votes'] if not v['rows']),
            'byAuthor': by_author,
        },
        'textChunks': len(texts), 'chunkSize': CHUNK,
    }

    columns = {key: [d[key] for d in docs] for key in COLUMNS}
    # O endereço oficial começa sempre igual; guardamos só o final.
    columns['url'] = [d['url'][len(PREFIX):] if d['url'].startswith(PREFIX) else d['url'] for d in docs]
    columns['urlPrefix'] = PREFIX
    files['propostas.json'] = columns

    files['sessoes.json'] = sessions
    # Cada grupo aponta para a posição da proposta em propostas.json.
    files['ruas.json'] = [
        {'street': g['street'], 'topic': g['topic'], 'documents': [position[u] for u in g['documents']]}
        for g in data['repeatedRequests']
    ]
    return files


def restore_documents(files):
    """Remonta as propostas a partir dos arquivos leves (usado no teste)."""
    c = files['propostas.json']
    texts = [t for i in range(files['inicio.json']['textChunks']) for t in files[f'texto-{i}.json']]
    docs = []
    for i, url in enumerate(c['url']):
        d = {key: c[key][i] for key in COLUMNS}
        d['url'] = url if url.startswith('http') else c['urlPrefix'] + url
        d['text'] = texts[i]
        docs.append(d)
    return docs


def main():
    root = Path(__file__).parent / 'dist'
    data = json.loads((root / 'data.json').read_text(encoding='utf-8'))
    files = build(data)

    # Conferência: os arquivos leves remontam exatamente as mesmas propostas.
    keys = COLUMNS + ('url', 'text')
    assert restore_documents(files) == [{k: d[k] for k in keys} for d in data['documents']], \
        'Arquivos leves divergem da base'

    out = root / 'lite'
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    total = 0
    for name, content in files.items():
        raw = json.dumps(content, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        (out / name).write_bytes(raw)
        total += len(raw)
    first = len(json.dumps(files['inicio.json'], ensure_ascii=False).encode('utf-8'))
    print(f'Arquivos leves gerados: {len(files)} arquivos, {total} bytes; abertura com {first} bytes')


if __name__ == '__main__':
    main()
