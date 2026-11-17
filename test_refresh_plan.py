"""A conferência do histórico é dividida pela semana sem deixar parte alguma de fora."""
import json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import radar
from radar import history_group, refresh_plan

START, END = '2025-01-01', '2026-11-16'
OLD = '2026-11-01T03:17:00-03:00'
NOW = '2026-11-16T03:20:00-03:00'
PRESENT = [{'name': 'Fulano', 'status': 'Presente', 'url': 'x'}]


def session(n, date):
    return {'url': f'https://digital.camarablu.sc.gov.br/sessao/reuniao-{n}', 'date': date, 'title': f'REUNIÃO ORDINÁRIA {n}', 'attendance': PRESENT, 'votes': []}


def document(n, date):
    return {'id': str(n), 'title': 'Indicação', 'date': date, 'authors': 'Fulano', 'text': 'Texto', 'meta': '', 'category': 'Melhorias nos bairros',
            'url': f'https://digital.camarablu.sc.gov.br/documento/{n}'}


def baseline():
    sessions = [session(n, '2025-06-10') for n in range(40)] + [session('recente', '2026-11-10')]
    return {'schemaVersion': 2, 'start': START, 'end': '2026-11-15', 'collectedAt': '2026-11-15T03:30:00-03:00', 'fullCollectedAt': OLD,
            'documents': [document(1, '2025-03-01'), document(2, '2026-02-01'), document(3, '2026-11-10')], 'sessions': sessions}


class FakeClient:
    def __init__(self, cache): self.pages = {'x': NOW}


def run_main(base, weekday, listed=None, portal_documents=None, extra=()):
    """Executa radar.main com o portal simulado; devolve (base gerada, anos pedidos, reuniões consultadas)."""
    listed = base['sessions'] if listed is None else listed
    portal_documents = base['documents'] if portal_documents is None else portal_documents
    asked_years, fetched = [], []

    def collect(client, year, start, end):
        asked_years.append((year, start))
        return [d for d in portal_documents if d['date'][:4] == str(year) and d['date'] >= start], {'year': year, 'complete': True}

    def detail(client, item, expected=False):
        fetched.append(item[0])
        return {**item[1], 'url': item[0], 'attendance': PRESENT, 'votes': []}

    with tempfile.TemporaryDirectory() as folder:
        source, out = Path(folder) / 'baseline.json', Path(folder) / 'candidate.json'
        source.write_text(json.dumps(base), encoding='utf-8')
        people = [{'id': f'p{n}', 'name': f'Pessoa {n}', 'aliases': [f'pessoa {n}']} for n in range(15)]
        with patch.object(radar, 'Client', FakeClient), patch.object(radar, 'people', lambda c: people), \
             patch.object(radar, 'collect_documents', collect), patch.object(radar, 'session_detail', detail), \
             patch.object(radar, 'session_links', lambda c, s, e: {x['url']: {'date': x['date'], 'title': x['title']} for x in listed}), \
             patch.object(radar, 'weekday_today', lambda: weekday), patch('builtins.print'), \
             patch.object(sys, 'argv', ['radar.py', '--start', START, '--end', END, '--baseline', str(source), '--output', str(out), *extra]):
            radar.main()
        return json.loads(out.read_text(encoding='utf-8')), asked_years, fetched


class RefreshPlanTests(unittest.TestCase):
    def test_without_baseline_everything_is_collected(self):
        self.assertEqual(refresh_plan(START, END, 3, False), (START, {2025, 2026}, set(range(7))))

    def test_daily_plan_covers_recent_days_and_one_part_of_history(self):
        self.assertEqual(refresh_plan(START, END, 2, True), ('2026-10-02', {2025}, {2}))

    def test_whole_history_is_rechecked_within_a_week(self):
        plans = [refresh_plan(START, '2028-06-30', day, True) for day in range(7)]
        self.assertEqual(set().union(*(years for _, years, _ in plans)), {2025, 2026, 2027, 2028})
        self.assertEqual(set().union(*(groups for _, _, groups in plans)), set(range(7)))

    def test_session_group_is_stable_and_uses_all_seven_days(self):
        urls = [f'https://digital.camarablu.sc.gov.br/sessao/reuniao-{n}' for n in range(200)]
        self.assertEqual([history_group(u) for u in urls], [history_group(u) for u in urls])
        self.assertEqual({history_group(u) for u in urls}, set(range(7)))

    def test_daily_run_keeps_everything_and_fetches_only_the_plan(self):
        base = baseline()
        new_old = session('antiga-nova', '2025-02-02')  # reunião antiga publicada depois: precisa entrar no mesmo dia
        data, asked, fetched = run_main(base, 2, listed=base['sessions'] + [new_old])  # quarta-feira: 2025 % 7 == 2
        self.assertEqual(sorted(asked), [(2025, START), (2026, '2026-10-02')])
        due = {s['url'] for s in base['sessions'] if history_group(s['url']) == 2}
        self.assertTrue(0 < len(due) < 40)
        self.assertEqual(set(fetched), due | {base['sessions'][-1]['url'], new_old['url']})
        self.assertEqual({d['url'] for d in data['documents']}, {d['url'] for d in base['documents']})
        self.assertEqual(len(data['sessions']), 42)
        self.assertEqual(data['historyChecks']['documents'], {'2025': NOW, '2026': OLD})
        self.assertEqual(data['historyChecks']['sessions']['2'], NOW)
        self.assertEqual(data['historyChecks']['sessions']['3'], OLD)
        self.assertEqual(data['fullCollectedAt'], OLD)

    def test_session_missing_from_listing_blocks_on_its_check_day(self):
        base = baseline()
        gone = next(s for s in base['sessions'] if history_group(s['url']) == 4)
        listed = [s for s in base['sessions'] if s is not gone]
        data, _, _ = run_main(base, 1, listed=listed)  # fora do dia dela: segue da base anterior, como antes
        self.assertIn(gone['url'], {s['url'] for s in data['sessions']})
        with self.assertRaisesRegex(ValueError, 'Sessões desapareceram'):
            run_main(base, 4, listed=listed)

    def test_document_missing_from_portal_blocks_on_its_year_check_day(self):
        base = baseline()
        portal = list(base['documents'])
        base['documents'].append(document(9, '2025-05-05'))  # está na base anterior, mas sumiu do portal
        data, _, _ = run_main(base, 5, portal_documents=portal)  # sábado: 2025 não é reconferido, o registro segue
        self.assertEqual(len(data['documents']), 4)
        with self.assertRaisesRegex(ValueError, 'Documentos desapareceram'):
            run_main(base, 2, portal_documents=portal)

    def test_full_flag_rechecks_everything_at_once(self):
        base = baseline()
        data, asked, fetched = run_main(base, 2, extra=['--full'])
        self.assertEqual(sorted(asked), [(2025, START), (2026, START)])
        self.assertEqual(len(fetched), 41)
        self.assertEqual(data['fullCollectedAt'], data['collectedAt'])


if __name__ == '__main__':
    unittest.main()
