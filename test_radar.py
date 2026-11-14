import copy, unittest
from radar import classify, repeats, validate, addresses, match_people, public_text
class RadarTests(unittest.TestCase):
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
