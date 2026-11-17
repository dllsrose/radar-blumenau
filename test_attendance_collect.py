import copy, unittest
from attendance_collect import validate_progress, inventory, calendar
from radar import soup

class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.base={'start':'2025-01-01','end':'2026-11-14','minutes':[{'url':'ata1','downloaded':True,'date':'2025-02-01','rows':[{'personId':'a'}],'sessionUrl':'sessao1'}],'sessionGaps':[{'url':'sessao2'}]}
    def test_preserves_history_and_accepts_additions(self):
        new=copy.deepcopy(self.base);new['end']='2026-11-15';new['sessionGaps'].append({'url':'sessao3'})
        validate_progress(new,self.base)
    def test_rejects_missing_minutes(self):
        new=copy.deepcopy(self.base);new['minutes']=[]
        with self.assertRaises(RuntimeError):validate_progress(new,self.base)
    def test_rejects_loss_of_historical_nominal_reading(self):
        old=copy.deepcopy(self.base);old['minutes'][0].update(rows=[],historicalRows=[{'name':'Nome histórico','status':'Presente'}])
        new=copy.deepcopy(old);new['minutes'][0]['historicalRows']=[]
        with self.assertRaises(RuntimeError):validate_progress(new,old)
    def test_rejects_lost_pdf_date_and_reading(self):
        for key,value in [('downloaded',False),('date',None),('rows',[])]:
            new=copy.deepcopy(self.base);new['minutes'][0][key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):validate_progress(new,self.base)
    def test_rejects_disappearing_calendar_and_regression(self):
        new=copy.deepcopy(self.base);new['sessionGaps']=[]
        with self.assertRaises(RuntimeError):validate_progress(new,self.base)
        new=copy.deepcopy(self.base);new['start']='2026-01-01'
        with self.assertRaises(RuntimeError):validate_progress(new,self.base)
    def test_inventory_collects_all_types_and_follows_pagination(self):
        class Client:
            def get(self,url,fresh=False):
                if url.endswith('/next'):
                    return soup('<li class="list-item"><a href="/documento/ata-2" class="title-link">Ata Comissão ordinária</a></li>')
                return soup('<li class="list-item"><a href="/documento/ata-1" class="title-link">Ata Reunião ordinária</a></li><a rel="next" href="/next">Próxima</a>')
        self.assertEqual(len(inventory(Client(),'2025-01-01','2025-12-31')),2)
    def test_calendar_keeps_other_meeting_types(self):
        class Client:
            pages={}
            calls=0
            def get(self,url,fresh=False):
                self.pages[url]='2026-11-14'
                if url.endswith('/sessoes'):
                    # A primeira resposta vem sem nenhuma reunião, como o portal faz às vezes.
                    Client.calls+=1
                    return soup('<p>Sessões</p>' if Client.calls==1 else '<a href="/sessao/1">Audiência pública - 03/02/2025</a>')
                return soup('<div class="wrap-presencas"><div class="item-full-people"><span class="title">Pessoa</span><div class="info">Presente</div></div></div>')
        from unittest.mock import patch
        import radar
        with patch.object(radar.time,'sleep'), patch('builtins.print'):
            rows=calendar(Client(),'2025-01-01','2026-11-14',[{'id':'a','aliases':['pessoa']}])
        self.assertEqual(rows[0]['attendance'][0]['personIds'],['a'])
        self.assertEqual(Client.calls,2)

class PdfDownloadTests(unittest.TestCase):
    """Queda de conexão no servidor de PDFs é repetida; erro HTTP e falha persistente continuam interrompendo."""
    class Response:
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self): return b'%PDF-1.4'

    def run_fetch(self,effects):
        from unittest.mock import patch
        import attendance_collect
        with patch.object(attendance_collect,'urlopen',side_effect=effects) as opened, patch.object(attendance_collect.time,'sleep'), patch('builtins.print'):
            try: return attendance_collect.fetch_pdf('https://sc-blumenau-camara.ad.sistemalegislativo.com.br/x.pdf','ata'),opened.call_count
            except Exception as exc: return exc,opened.call_count

    def test_connection_drop_is_retried(self):
        from urllib.error import URLError
        result,calls=self.run_fetch([URLError('sem resposta'),TimeoutError(),self.Response()])
        self.assertEqual((result,calls),(b'%PDF-1.4',3))

    def test_persistent_connection_failure_still_stops(self):
        from urllib.error import URLError
        result,calls=self.run_fetch([URLError('sem resposta')]*4)
        self.assertIsInstance(result,URLError); self.assertEqual(calls,4)

    def test_http_error_is_not_retried(self):
        from urllib.error import HTTPError
        result,calls=self.run_fetch([HTTPError('u',404,'Not Found',None,None)])
        self.assertIsInstance(result,HTTPError); self.assertEqual(calls,1)

class PortalBurstTests(unittest.TestCase):
    """O portal responde 404 em rajadas para páginas que existem; pedido de verificação nunca é repetido."""
    class Response:
        def __init__(self,body): self.body=body
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self): return self.body.encode()

    def run_get(self,effects):
        import tempfile, radar
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp, patch.object(radar,'urlopen',side_effect=effects) as opened, patch.object(radar.time,'sleep'), patch('builtins.print'):
            try: return radar.Client(Path(tmp)).get(radar.BASE+'/sessao/x'),opened.call_count
            except Exception as exc: return exc,opened.call_count

    def test_burst_of_404_is_waited_out(self):
        from urllib.error import HTTPError
        result,calls=self.run_get([HTTPError('u',404,'Not Found',None,None)]*4+[self.Response('<p>ok</p>')])
        self.assertEqual((result.get_text(),calls),('ok',5))

    def test_persistent_404_still_stops(self):
        from urllib.error import HTTPError
        result,calls=self.run_get([HTTPError('u',404,'Not Found',None,None)]*6)
        self.assertIsInstance(result,HTTPError); self.assertEqual(calls,6)

    def test_security_check_is_never_retried(self):
        import radar
        result,calls=self.run_get([self.Response('Confirme que você não é um robô')]*6)
        self.assertIsInstance(result,radar.SecurityCheck); self.assertEqual(calls,1)

if __name__=='__main__':unittest.main()
