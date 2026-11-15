import unittest

import build_lite

P = build_lite.PREFIX


def sample(total=5):
    docs = [{
        'id': str(i), 'title': f'Indicação {i}', 'date': f'2025-01-{i + 1:02d}', 'category': 'Pedidos',
        'authors': 'Fulana', 'authorIds': ['fulana-1'] if i % 2 else ['fulana-1', 'beltrano-2'],
        'meta': 'Situação: Protocolado', 'url': f'{P}indicacao-{i}', 'text': f'texto completo {i}',
    } for i in range(total)]
    return {
        'schemaVersion': 2, 'start': '2025-01-01', 'end': '2025-01-31', 'collectedAt': '2025-02-01T00:00:00-03:00',
        'people': [{'id': 'fulana-1', 'name': 'Fulana'}, {'id': 'beltrano-2', 'name': 'Beltrano'}],
        'sources': {'roster': 'x'}, 'documentCoverage': [{'year': 2025, 'pages': 1}],
        'documents': docs,
        'sessions': [{'title': 's', 'date': '2025-01-02', 'url': 'u', 'attendance': [], 'votes': [
            {'title': 'a', 'rows': [{'name': 'Fulana', 'vote': 'Sim'}]},
            {'title': 'b', 'rows': [], 'availability': 'unavailable', 'notice': 'n'}]}],
        'repeatedRequests': [{'street': 'Rua A', 'topic': 'Buraco', 'count': 2, 'dates': ['2025-01-02', '2025-01-04'],
                              'documents': [f'{P}indicacao-1', f'{P}indicacao-3'], 'method': 'm'}],
    }


class BuildLiteTest(unittest.TestCase):
    def test_reconstroi_as_mesmas_propostas(self):
        data = sample()
        self.assertEqual(build_lite.restore_documents(build_lite.build(data)), data['documents'])

    def test_divide_o_texto_em_partes(self):
        original = build_lite.CHUNK
        build_lite.CHUNK = 2
        try:
            data = sample()
            files = build_lite.build(data)
        finally:
            build_lite.CHUNK = original
        self.assertEqual(files['inicio.json']['textChunks'], 3)
        self.assertEqual([len(files[f'texto-{i}.json']) for i in range(3)], [2, 2, 1])
        self.assertEqual(build_lite.restore_documents(files), data['documents'])

    def test_totais_da_abertura_vem_dos_registros(self):
        stats = build_lite.build(sample())['inicio.json']['stats']
        self.assertEqual((stats['documents'], stats['sessions'], stats['votes'], stats['unavailableVotes']), (5, 1, 1, 1))
        self.assertEqual(stats['byAuthor'], {'fulana-1': 5, 'beltrano-2': 3})

    def test_abertura_nao_carrega_texto_das_propostas(self):
        first = build_lite.build(sample())['inicio.json']
        self.assertNotIn('documents', first)
        self.assertNotIn('texto completo', str(first))

    def test_ruas_apontam_para_a_proposta_certa(self):
        data = sample()
        files = build_lite.build(data)
        docs = build_lite.restore_documents(files)
        group = files['ruas.json'][0]
        self.assertEqual([docs[i]['url'] for i in group['documents']], data['repeatedRequests'][0]['documents'])

    def test_endereco_fora_do_padrao_e_mantido_inteiro(self):
        data = sample()
        data['documents'][0]['url'] = 'https://exemplo.org/outro'
        self.assertEqual(build_lite.restore_documents(build_lite.build(data))[0]['url'], 'https://exemplo.org/outro')


if __name__ == '__main__':
    unittest.main()
