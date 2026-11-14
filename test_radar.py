import copy, unittest
from unittest.mock import Mock, patch
from radar import calendar_date, document_listing, soup
from radar import classify, repeats, validate, addresses, match_people, public_text
class RadarTests(unittest.TestCase):
    def test_same_count_cannot_hide_missing_attendance_identity(self):
        old={'schemaVersion':2,'people':[{}]*15,'documents':[self.doc()],'sessions':[{'url':'s','attendance':[{'name':'Ana','personIds':['a']}],'votes':[]}],'start':'2025-01-01','end':'2026-11-14'}
        new=copy.deepcopy(old);new['sessions'][0]['attendance']=[{'name':'Bia','personIds':['b']}]
        with self.assertRaises(ValueError):validate(new,old)
        new['sessions'][0]['attendance']=[{'name':'Ana Silva','personIds':['a']}]
        validate(new,old)

    def test_commemorative_days_weeks_and_months(self):
        for text in ('PARA INSTITUIR O "DIA DO PARAENSE".', 'PARA INSTITUIR A SEMANA FARROUPILHA.', 'INSTITUI O FEVEREIRO LAVANDA, COMO MÊS DE CONSCIENTIZAÇÃO.'):
            self.assertEqual(classify('Projeto de Lei 1/2025',text),'Homenagens')
        self.assertEqual(classify('Projeto de Lei 2/2025','Institui atendimento das instituições de ensino durante o dia.'),'Propostas de lei')
    def test_phone_formats_and_year_ranges(self):
        for phone in ('47 9 9999 1234','47 9 9999-1234','99999-1234','9999-1234','999991234','(47) 99999-1234'):
            self.assertEqual(public_text('Contato: '+phone),'Contato: [telefone omitido]')
        self.assertEqual(public_text('Rua Bahia, 1234. CEP 89010-922. Mandato 2025-2028.'),'Rua Bahia, 1234. CEP 89010-922. Mandato 2025-2028.')

    def test_explicit_unpublished_vote_remains_identified_after_retries(self):
        client=Mock();client.get.return_value=soup('<p>Nenhuma votação disponível</p>')
        with patch('radar.time.sleep'):
            _,rows=document_listing(client,'https://digital.camarablu.sc.gov.br/sessao/documento/votacao/611971','.item-small-people',allow_unavailable_vote=True)
        self.assertEqual(rows,[])
        self.assertEqual(client.get.call_count,6)
        client.get.return_value=soup('<p>Resposta desconhecida</p>')
        with patch('radar.time.sleep'),self.assertRaises(RuntimeError):
            document_listing(client,'https://digital.camarablu.sc.gov.br/sessao/documento/votacao/611971','.item-small-people',allow_unavailable_vote=True)
    def test_missing_vote_rows_cannot_replace_published_votes(self):
        old={'schemaVersion':2,'people':[{}]*15,'documents':[self.doc()],'sessions':[{'url':'s','attendance':[],'votes':[{'url':'v','rows':[{'name':'Ana'}]}]}],'start':'2025-01-01','end':'2026-11-14'}
        new=copy.deepcopy(old);new['sessions'][0]['votes'][0]['rows']=[]
        with self.assertRaises(ValueError):validate(new,old)

    def test_calendar_date_overrides_free_title_date(self):
        self.assertEqual(calendar_date('REUNIÃO DA COMISSÃO - 14/05/2025 - 14/05/2026'),'2026-05-14')
        self.assertEqual(calendar_date('REUNIÃO ORDINÁRIA DE 10 DE NOVEMBRO DE 2026 - 10/11/2026'),'2026-11-10')

    def test_temporarily_unavailable_vote_is_retried_not_omitted(self):
        client=Mock();client.get.side_effect=[soup('Nenhuma votação disponível'),soup('<div class="item-small-people"><span class="title">Ana</span><span class="info">Favorável</span></div>')]
        with patch('radar.time.sleep'):
            _,rows=document_listing(client,'https://digital.camarablu.sc.gov.br/sessao/documento/votacao/632698','.item-small-people')
        self.assertEqual(len(rows),1)
        self.assertTrue(client.get.call_args.kwargs['fresh'])
    def test_transient_empty_listing_is_refetched_without_skipping(self):
        client=Mock();client.get.side_effect=[soup('<p>Nenhum registro encontrado.</p>'),soup('<p>Nenhum registro encontrado.</p>'),soup('<li class="list-item">registro recuperado</li>')]
        with patch('radar.time.sleep') as sleep:
            _,items=document_listing(client,'https://digital.camarablu.sc.gov.br/documentos/page:471')
        self.assertEqual(len(items),1)
        self.assertEqual([c.kwargs['fresh'] for c in client.get.call_args_list],[False,True,True])
        self.assertEqual([c.args[0] for c in sleep.call_args_list],[5,15])
    def test_persistently_empty_listing_fails_closed(self):
        client=Mock();client.get.return_value=soup('<p>Nenhum registro encontrado.</p>')
        with patch('radar.time.sleep'), self.assertRaises(RuntimeError):
            document_listing(client,'https://digital.camarablu.sc.gov.br/documentos/page:471')
    def doc(self,date='2026-11-01',url='https://digital.camarablu.sc.gov.br/documento/1',text='Fechar buraco na Rua Bahia, próximo ao número 10.'):
        return {'date':date,'url':url,'title':'Indicação 1/2026','authors':'Ana','text':text,'category':'Melhorias nos bairros'}
    def test_repetition_requires_different_dates_and_topic(self):
        a=self.doc();b=self.doc('2026-11-02',url=a['url']+'b');c=self.doc('2026-11-03',url=a['url']+'c',text='Instalar iluminação na Rua Bahia, número 10.')
        g=repeats([a,b,c]);self.assertEqual(len(g),1);self.assertEqual(g[0]['count'],2)
        self.assertEqual(repeats([a,copy.deepcopy(a)]),[])
    def test_incidental_street_not_extracted_from_justification(self):
        self.assertEqual(addresses('Roçar a Rua Amazonas, 22. Justificativa: assim como na Rua Bahia, há mato.'),['Rua Amazonas'])
        self.assertEqual(addresses('Reparar a Rua Prof. Jacob Ineichen, 10.'),['Rua Professor Jacob Ineichen'])
        self.assertNotEqual(addresses('Rua Prof. João Silva, 10.'),addresses('Rua Prof. José Silva, 10.'))
    def test_categories_and_false_honor_match(self):
        self.assertEqual(classify('Projeto de Lei 12/2026','Denomina a Rua Nova.'),'Homenagens')
        self.assertEqual(classify('Requerimento 1/2026','Solicita reparo apesar da chuva.'),'Perguntas e cobranças')
        self.assertEqual(classify('Moção 1/2026','Parabeniza os professores.'),'Homenagens')
    def test_exact_alias_and_coauthor(self):
        p=[{'id':'r','aliases':['rodrigo marchetti','rodrigo emanuel marchetti']}]
        self.assertEqual(match_people('Ana, Rodrigo Emanuel Marchetti',p),['r'])
        self.assertEqual(match_people('Rodrigo Marchetti Júnior',p),[])
    def test_loss_of_data_blocks_promotion(self):
        a={'schemaVersion':2,'people':[{}]*15,'documents':[self.doc()],'sessions':[{'url':'s','attendance':[{}],'votes':[]}],'start':'2025-01-01','end':'2026-11-13'}
        validate(a)
        b=copy.deepcopy(a);b['sessions'][0]['attendance']=[]
        with self.assertRaises(ValueError):validate(b,a)
        b=copy.deepcopy(a);b['documents']=[]
        with self.assertRaises(ValueError):validate(b,a)
    def test_missing_author_fails_closed(self):
        a={'people':[{}]*15,'documents':[self.doc()],'sessions':[{}],'start':'2025-01-01','end':'2026-11-13'}
        a['documents'][0]['authors']=''
        with self.assertRaises(ValueError):validate(a)
    def test_private_contacts_not_republished(self):
        self.assertEqual(public_text('Morador (47) 99999-1234, pessoa@example.com.'),'Morador [telefone omitido], [e-mail omitido].')
        self.assertIn('Rua Bahia, 1234',public_text('Rua Bahia, 1234'))
if __name__=='__main__':unittest.main()
