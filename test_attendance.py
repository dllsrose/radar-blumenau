import unittest
from attendance_audit import date_of,extract,meeting_identity,mark_duplicates,session_kind,committee_key,verified_review
from radar import session_links
from unittest.mock import Mock
from radar import soup
class AttendanceTests(unittest.TestCase):
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
if __name__=='__main__':unittest.main()
