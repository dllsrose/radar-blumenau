import unittest
from attendance_audit import date_of,extract,meeting_identity,mark_duplicates,session_kind,committee_key,verified_review,reviewed_date,reviewed_session
from radar import session_links
from unittest.mock import Mock
from radar import soup
class AttendanceTests(unittest.TestCase):
 def test_individual_pdf_date_review_requires_documented_page_and_official_support(self):
  r={'date':'2026-10-22','dateReviewMode':'pdf-page-reviewed','datePdfPage':1,'datePdfText':'Aos vinte e dois dias do mês de outubro','dateEvidence':'Página conferida e evento corroborado','dateSourceUrl':'https://camarablu.sc.gov.br/detalhe-noticia/15652/example/'}
  self.assertEqual(reviewed_date(None,r,[],'Comissão ordinária'),'2026-10-22')
  for bad in [{**r,'datePdfPage':0},{**r,'datePdfText':''},{**r,'dateSourceUrl':'https://example.com'},{**r,'date':'2026-02-30'},{**r,'dateEvidence':''}]:
   self.assertIsNone(reviewed_date(None,bad,[],'Comissão ordinária'))
  self.assertIsNone(reviewed_date(None,r,[],'Plenário ordinário'))
  expired=verified_review({**r,'sha256':'reviewed'},{'sha256':'changed'},{})
  self.assertIsNone(reviewed_date(None,expired,[],'Comissão ordinária'))
 def test_reviewed_association_requires_same_day_family_and_evidence(self):
  s={'url':'rf','date':'2026-07-28','title':'Reunião ordinária RF'}
  r={'sessionUrl':'rf','associationEvidence':'Mesmos projetos em redação final'}
  self.assertEqual(reviewed_session(r,[],[s],s['date'],'Plenário extraordinário'),s)
  self.assertIsNone(reviewed_session({'sessionUrl':'rf'},[],[s],s['date'],'Plenário extraordinário'))
  self.assertIsNone(reviewed_session(r,[],[s],'2026-07-29','Plenário extraordinário'))
  self.assertIsNone(reviewed_session(r,[],[s],s['date'],'Comissão ordinária'))
 def test_report_date_review_is_restricted_and_preserves_plenary_guard(self):
  r={'date':'2025-06-26','dateSourceUrl':'https://camarablu.sc.gov.br/detalhe-noticia/14849/example/','dateEvidence':'Tema e participantes correspondentes'}
  self.assertEqual(reviewed_date('2024-06-26',r,[],'Audiência pública'),'2025-06-26')
  self.assertEqual(reviewed_date('2024-06-26',r,[],'Plenário ordinário'),'2024-06-26')
  self.assertEqual(reviewed_date(None,r,[],'Audiência pública'),None)
  for bad in [{**r,'date':'2025-02-31'},{**r,'dateSourceUrl':'https://camarablu.sc.gov.br.evil.test/detalhe-noticia/1'},{**r,'dateEvidence':''}]:
   self.assertEqual(reviewed_date('2024-06-26',bad,[],'Audiência pública'),'2024-06-26')
 def test_date_review_requires_matching_calendar_and_evidence(self):
  sessions=[{'url':'official','date':'2025-10-09','title':'Reunião Ordinária'}]
  review={'date':'2025-10-09','sessionUrl':'official','dateEvidence':'Pauta e votação conferidas'}
  self.assertEqual(reviewed_date('2025-09-09',review,sessions,'Plenário ordinário'),'2025-10-09')
  for bad in [{**review,'date':'2025-10-10'},{**review,'sessionUrl':'other'},{**review,'dateEvidence':''}]:
   self.assertEqual(reviewed_date('2025-09-09',bad,sessions,'Plenário ordinário'),'2025-09-09')
  self.assertEqual(reviewed_date('2025-09-09',review,sessions,'Solene'),'2025-09-09')
  expired=verified_review({**review,'sha256':'old'},{'sha256':'new'},{})
  self.assertEqual(reviewed_date('2025-09-09',expired,sessions,'Plenário ordinário'),'2025-09-09')
 def test_review_expires_if_either_pdf_changes(self):
  review={'sha256':'abc','duplicateOf':'other','duplicateOfSha256':'def'}
  self.assertEqual(verified_review(review,{'sha256':'abc'},{'other':'def'}),review)
  self.assertEqual(verified_review(review,{'sha256':'new'},{'other':'def'}),{})
  self.assertEqual(verified_review(review,{'sha256':'abc'},{'other':'new'}),{})
 def test_split_hyphen_in_commission_attendance(self):
  rows,issue=extract('Constatou-\nse a presença de Ana e a ausência justificada de Bia. Conforme indicação, Ana, Bia e Cris compõem a comissão. Após, realizou-se a eleição.',self.people())
  self.assertIsNone(issue)
  self.assertEqual({r['personId']:r['status'] for r in rows},{'a':'Presente','b':'Ausência justificada'})
 def test_distinct_meetings_same_day(self):
  a={'date':'2025-09-11','kind':'Plenário extraordinário','meetingIdentity':meeting_identity('Ata da 23ª Reunião Extraordinária. Aos 11 dias, às 15 horas e 30 minutos.')}
  b={'date':'2025-09-11','kind':'Plenário extraordinário','meetingIdentity':meeting_identity('Ata da 24ª Reunião Extraordinária. Aos 11 dias, às 16 horas e 30 minutos.')}
  mark_duplicates([a,b]);self.assertFalse(a.get('duplicateMeeting'));self.assertFalse(b.get('duplicateMeeting'))
  b['meetingIdentity']['time']=a['meetingIdentity']['time'];mark_duplicates([a,b]);self.assertTrue(a['duplicateMeeting'])
 def test_confirmed_republication_counts_one(self):
  a={'date':'2025-04-10','kind':'Plenário ordinário','id':'a'}
  b={**a,'id':'b','duplicateOf':'a'}
  mark_duplicates([a,b]);self.assertFalse(a.get('duplicateMeeting'));self.assertTrue(b['duplicateMeeting'])
 def test_ethics_council_not_plenary_and_committees_are_distinct(self):
  self.assertEqual(session_kind('Reunião Extraordinária - Conselho de Ética'),'Conselho de ética')
  self.assertNotEqual(committee_key('Comissão de análise às emendas à lei orgânica'),committee_key('Comissão de análise às emendas ao regimento interno'))
 def people(self):return [{'id':'a','name':'Ana','aliases':['ana']},{'id':'b','name':'Bia','aliases':['bia']},{'id':'c','name':'Cris','aliases':['cris']}]
 def test_absence_is_not_inferred_from_missing_name(self):
  rows,_=extract('Tendo como Presidente Ana. Ausência justificada Bia. Constatado',self.people())
  self.assertEqual({r['personId']:r['status'] for r in rows},{'a':'Presente','b':'Ausência justificada'})
 def test_leave_not_counted_as_presence_or_absence(self):
  rows,_=extract('Tendo como Presidente Ana. Em afastamento provisório Bia. Em licença Cris. Constatado',self.people())
  self.assertEqual({r['personId']:r['status'] for r in rows},{'a':'Presente','b':'Afastamento','c':'Licença'})
 def test_internal_contradiction_requires_review(self):
  rows,_=extract('Tendo como Presidente Ana. Presentes também Bia. Ausência justificada Bia. Constatado',self.people())
  self.assertEqual(next(r['status'] for r in rows if r['personId']=='b'),'Revisão necessária')
 def test_composition_does_not_imply_attendance(self):
  rows,_=extract('Tendo na presidência Ana, vice Bia. Constatou-se a presença de Ana e a ausência justificada de Bia. Em seguida, a reunião prosseguiu.',self.people())
  self.assertEqual({r['personId']:r['status'] for r in rows},{'a':'Presente','b':'Ausência justificada'})
 def test_commission_speeches_do_not_change_opening_attendance(self):
  rows,_=extract('Constatou-se a presença de Ana e a ausência justificada de Bia. Abertos os trabalhos, Bia foi mencionada por Ana. Em seguida, prosseguiu.',self.people())
  self.assertEqual({r['personId']:r['status'] for r in rows},{'a':'Presente','b':'Ausência justificada'})
  rows,_=extract('Constatou-se a presença de Ana. Em licença Bia. Exerceu a relatoria Ana. Após, prosseguiu.',self.people())
  self.assertEqual({r['personId']:r['status'] for r in rows},{'a':'Presente','b':'Licença'})
 def test_later_discussion_does_not_replace_plenary_opening(self):
  rows,_=extract('Tendo como Presidente Ana. Ausência justificada Bia. Constatado o quórum, abriu os trabalhos. Depois leu uma ata: constatou-se a presença de Bia. Em seguida, encerrou.',self.people())
  self.assertEqual({r['personId']:r['status'] for r in rows},{'a':'Presente','b':'Ausência justificada'})
 def test_written_dates(self):
  self.assertEqual(date_of('Aos três dias do mês de fevereiro de 2026'),'2026-02-03')
  self.assertEqual(date_of('Aos 20 dias de maio de 2026'),'2026-05-20')
  self.assertEqual(date_of('Em 06 de agosto de 2026'),'2026-08-06')
  self.assertEqual(date_of('Aos 20 dias do mês de outubro de dois mil e vinte e seis'),'2026-10-20')
 def test_calendar_titles_ignore_letter_case(self):
  c=Mock();c.get.return_value=soup('<a href="/sessao/a">Reunião Ordinária - 05/03/2026</a><a href="/sessao/b">REUNIÃO EXTRAORDINÁRIA - 05/03/2026</a>')
  self.assertEqual(len(session_links(c,'2025-01-01','2026-11-14')),2)
 def test_empty_session_listing_is_fetched_again(self):
  # O portal às vezes devolve a lista de sessões sem nenhuma reunião; a segunda consulta traz a lista.
  from unittest.mock import patch
  import radar
  c=Mock();c.get.side_effect=[soup('<p>Sessões</p>'),soup('<a href="/sessao/a">Reunião Ordinária - 05/03/2026</a>')]
  with patch.object(radar.time,'sleep'),patch('builtins.print'):
   self.assertEqual(len(session_links(c,'2025-01-01','2026-11-14')),1)
  self.assertEqual(c.get.call_args_list[1].kwargs,{'fresh':True})
 def test_half_delivered_session_page_is_fetched_again(self):
  # O portal às vezes entrega a reunião sem o bloco de presenças; a reconsulta traz a página inteira.
  from unittest.mock import patch
  import radar
  half=soup('<div id="materias-discussao-bloco"></div>')
  full=soup('<div class="wrap-presencas"><a class="item-full-people" href="/vereador/a"><span class="title">Ana</span><div class="info">Presente</div></a></div><div id="materias-discussao-bloco"></div>')
  c=Mock();c.get.side_effect=[half,half,full]
  with patch.object(radar.time,'sleep'),patch('builtins.print'):
   detail=radar.session_detail(c,('https://digital.camarablu.sc.gov.br/sessao/a',{'date':'2026-03-05','title':'Reunião'}))
  self.assertEqual([r['name'] for r in detail['attendance']],['Ana']);self.assertEqual(c.get.call_count,3)
 def test_session_really_without_attendance_is_accepted_after_rechecks(self):
  from unittest.mock import patch
  import radar
  c=Mock();c.get.return_value=soup('<div id="materias-discussao-bloco"></div>')
  with patch.object(radar.time,'sleep'),patch('builtins.print'):
   detail=radar.session_detail(c,('https://digital.camarablu.sc.gov.br/sessao/a',{'date':'2026-03-05','title':'Reunião'}))
  self.assertEqual(detail['attendance'],[]);self.assertEqual(c.get.call_count,3)
 def test_session_known_to_have_attendance_waits_longer(self):
  from unittest.mock import patch
  import radar
  half=soup('<div id="materias-discussao-bloco"></div>')
  full=soup('<div class="wrap-presencas"><a class="item-full-people" href="/vereador/a"><span class="title">Ana</span><div class="info">Presente</div></a></div>')
  c=Mock();c.get.side_effect=[half]*6+[full]
  with patch.object(radar.time,'sleep'),patch('builtins.print'):
   detail=radar.session_detail(c,('https://digital.camarablu.sc.gov.br/sessao/a',{'date':'2026-03-05','title':'Reunião'}),True)
  self.assertEqual(len(detail['attendance']),1);self.assertEqual(c.get.call_count,7)
 def test_persistently_empty_session_listing_still_stops(self):
  from unittest.mock import patch
  import radar
  c=Mock();c.get.return_value=soup('<p>Sessões</p>')
  with patch.object(radar.time,'sleep'),patch('builtins.print'),self.assertRaises(RuntimeError):session_links(c,'2025-01-01','2026-11-14')
if __name__=='__main__':unittest.main()
