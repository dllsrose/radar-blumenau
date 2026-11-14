"""Conferência documental: não infere ausência a partir de nomes omitidos."""
import json,re,sys
from pathlib import Path
from datetime import datetime
from collections import Counter,defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parent))
from radar import norm, stamp
EXTRA={
 'ailton-de-souza-ito-451':['ailton de souza','ailton souza'],
 'alexandre-matias-452':['alexandre agenor matias'],
 'bruno-cunha-467':['bruno horwatitsch cunha'],
 'cristiane-loureiro-1000667':['cristiane marta loureiro'],
 'silmara-silva-miguel-1000671':['silmara ferreira da silva miguel','silmara da silva miguel'],
 'flavio-jose-linhares-1002017':['flavio linhares'],
 'mario-kato-1002283':['mario henrique kato'],
}
MONTHS=['janeiro','fevereiro','marco','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro']
def date_of(text):
 t=norm(text[:1800]).replace('do ano de dois mil e vinte e cinco','de 2025').replace('do ano de dois mil e vinte e seis','de 2026').replace('dois mil e vinte e cinco','2025').replace('dois mil e vinte e seis','2026')
 for word,number in [('tres',3),('primeiro',1),('um',1),('dois',2)]:t=re.sub(r'(?<=aos )'+word+r'(?= dias?)',str(number),t)
 m=re.search(r'aos?\s+(\d{1,2})(?:[º°o])?\s+dias?\s+(?:d[oe]\s+mes\s+)?(?:de\s+)?(\w+)\s+de\s+(20\d{2})',t)
 if not m:m=re.search(r'\bem\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(20\d{2})',t)
 if m and m[2] in MONTHS:
  try:return datetime(int(m[3]),MONTHS.index(m[2])+1,int(m[1])).date().isoformat()
  except ValueError:pass
 return None

def extract(text,people):
 t=norm(' '.join(text.split()));t=re.sub(r'constatou-\s+se','constatou-se',t);opening_end=re.search(r'constatad[oa]|momento civico',t);commission=re.search(r'constatou-se a presenca',t[:opening_end.start()] if opening_end else t[:5000])
 if commission:
  tail=t[commission.start():];stop=re.search(r'\.\s+(?:em seguida|apos|o senhor|a senhora|passou|nada|abertos os trabalhos|com a licenca|exerceu a relatoria|conforme|pela nao|na sequencia)|em seguida|apos,',tail)
  opening=tail[:stop.start()] if stop else tail.split('.')[0]
  opening=opening.replace('constatou-se a presenca','presentes os')
  return extract('tendo como '+opening+' Constatado',people)
 end=re.search(r'constatad[oa]|momento civico|ordem do dia',t)
 if not end or end.start()>5000:return [],'Abertura nominal não delimitada com segurança'
 opening=t[:end.start()]
 start=re.search(r'tendo como|presentes?\s+(?:tambem|os|as|a|o)|com a presenca',opening)
 if not start:return [],'Lista nominal de abertura não identificada'
 opening=opening[start.start():]
 markers=list(re.finditer(r'ausencias?\s+justificadas?|ausentes?|ausencias?|em afastamento(?: provisorio)?|afastad[oa]s?|em licenca|licenciad[oa]s?|presentes?\s+(?:tambem|os|as)|tendo como',opening))
 if not markers:return [],'Estados não identificados'
 aliases={p['id']:set(p.get('aliases',[])+[norm(p['name'])]+EXTRA.get(p['id'],[])) for p in people}
 rows={};conflicts=set()
 for i,m in enumerate(markers):
  segment=opening[m.end():markers[i+1].start() if i+1<len(markers) else len(opening)]
  label=m[0];status='Presente'
  if 'afast' in label:status='Afastamento'
  elif 'licenc' in label:status='Licença'
  elif label.startswith('aus'):status='Ausência justificada' if 'justificad' in label else 'Ausência citada sem classificação'
  for pid,names in aliases.items():
   if any(re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)',segment) for a in names):
    if pid in rows and rows[pid]!=status:conflicts.add(pid)
    rows[pid]=status
 for pid in conflicts:rows[pid]='Revisão necessária'
 return [{'personId':pid,'status':status} for pid,status in rows.items()],None if rows else 'Sem nomes reconhecidos'

def kind(title):
 t=norm(title)
 for key,label in [('comissao extraordinaria','Comissão extraordinária'),('comissao ordinaria','Comissão ordinária'),('reuniao extraordinaria','Plenário extraordinário'),('reuniao ordinaria','Plenário ordinário'),('audiencia','Audiência pública'),('solene','Solene'),('itinerante','Itinerante')]:
  if key in t:return label
 return 'Outros'

def committee_key(title):
    t=norm(title)
    if 'emendas' in t:
        if 'lei organica' in t:return 'emendas-lei-organica'
        if 'regimento interno' in t:return 'emendas-regimento'
    for key in ['esgotamento','mista','telefonia','seguranca nas escolas','hiv','furb','area azul','saude mental','barragem','corpo de bombeiros','sistema pronto','constituicao','financas','educacao','transportes','turismo','defesa civil','cultura']:
        if key in t:return key
    return None

def session_kind(title):
    t=norm(title)
    if 'conselho de etica' in t:return 'Conselho de ética'
    if 'comissao' in t:return 'Comissão extraordinária' if 'extraordinaria' in t else 'Comissão ordinária'
    if 'frente parlamentar' in t:return 'Frente parlamentar'
    if 'solene' in t:return 'Solene'
    if 'itinerante' in t:return 'Itinerante'
    if 'audiencia' in t:return 'Audiência pública'
    return 'Plenário extraordinário' if 'extraordinaria' in t else 'Plenário ordinário' if 'ordinaria' in t else 'Outros'

def meeting_identity(text):
    opening=norm(' '.join(text[:1800].split()))
    number=re.search(r'ata da\s+(\d+)[ªaºo]?\s+reuniao\s+(?:extraordinaria|ordinaria)',opening)
    clock=re.search(r'\bas\s+(\d{1,2})\s+horas?(?:\s+e\s+(\d{1,2})\s+minutos?)?',opening)
    if number and clock:return {'number':int(number[1]),'time':f'{int(clock[1]):02d}:{int(clock[2] or 0):02d}'}
    return None

def mark_duplicates(minutes):
    groups=defaultdict(list)
    for a in minutes:
        if a.get('duplicateOf'):a['duplicateMeeting']=True;continue
        if a['date'] and a['kind'].startswith('Plenário'):groups[(a['date'],a['kind'])].append(a)
    for group in groups.values():
        if len(group)<2:continue
        identities=[a.get('meetingIdentity') for a in group]
        distinct=all(identities) and len({i['number'] for i in identities})==len(group) and len({i['time'] for i in identities})==len(group)
        for a in group:
            if distinct:a['reviewNote']=(a.get('reviewNote','')+' Reuniões distintas no mesmo dia: números e horários de abertura diferentes nas atas.').strip()
            else:a['duplicateMeeting']=True

def verified_review(review,source,source_hashes):
    if not review or review.get('sha256')!=source.get('sha256'):return {}
    if review.get('duplicateOf') and source_hashes.get(review['duplicateOf'])!=review.get('duplicateOfSha256'):return {}
    return review

def build(data,downloaded,root):
    out=[];sessions=defaultdict(list)
    review_path=Path(__file__).parent/'attendance_reviews.json'
    reviews=json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {}
    source_hashes={a['id']:a.get('sha256') for a in downloaded}
    calendar_path=root/'calendar-attendance.json'
    source_sessions=json.loads(calendar_path.read_text(encoding='utf-8')) if calendar_path.exists() else data['sessions']
    for session in source_sessions:sessions[(session['date'],session_kind(session['title']))].append(session)
    for a in downloaded:
        text=Path(a['textFile']).read_text(encoding='utf-8') if a['downloaded'] else ''
        text=re.sub(r'Blumenau:\s+Presidente,','Blumenau, tendo como Presidente,',text) if a['id'] in ('530433','532495','535117','526616') else text
        text=text.replace('Flávio José Linha49res','Flávio José Linhares') if a['id']=='517332' else text
        text=re.sub(r'Almir\s+Viera','Almir Vieira',text) if a['id']=='516885' else text
        text=re.sub(r'Flavio\s+Linahres','Flávio Linhares',text) if a['id']=='531722' else text
        text=re.sub(r'Silmara\s+Silva\s+Siguel','Silmara Silva Miguel',text) if a['id']=='549930' else text
        date=date_of(text);rows,issue=extract(text,data['people']) if text else ([], 'PDF não obtido; conferência pendente')
        if a['id']=='530040':
            for row in rows:
                if row['personId']=='almir-vieira-454':row['status']='Presente'
        k='Frente parlamentar' if 'frente parlamentar' in norm(text[:350]) else kind(a['title']); candidates=sessions.get((date,k),[])
        # Sem associação automática entre comissões distintas do mesmo dia.
        if k.startswith('Comissão'):
            ck=committee_key(text[:1000]);candidates=[x for x in candidates if ck and committee_key(x['title'])==ck]
        match=candidates[0] if len(candidates)==1 else None
        review=verified_review(reviews.get(a['id'],{}),a,source_hashes)
        if review.get('sessionUrl'):
            reviewed=[s for s in candidates if s['url']==review['sessionUrl']]
            if len(reviewed)==1:match=reviewed[0]
        comparisons=[]
        if match:
            portal_states=defaultdict(set)
            for entry in match['attendance']:
                for pid in entry['personIds']:portal_states[pid].add(entry['status'] or 'Situação não informada')
            portal={pid:next(iter(states)) if len(states)==1 else 'Estados conflitantes no portal' for pid,states in portal_states.items()}
            for row in rows:
                state=portal.get(row['personId'],'Sem registro');equal=row['status']==state
                compatible=row['status']=='Ausência citada sem classificação' and state in ('Ausente','Ausência justificada')
                comparisons.append({**row,'portalStatus':state,'result':('Contradição na ata' if a['id'] in ('554140','552007','550814','550374','550038') else 'Revisar leitura') if row['status']=='Revisão necessária' else 'Coincide' if equal else 'Somente na ata' if state=='Sem registro' else 'Situação não informada no portal' if state=='Situação não informada' else 'Ausência coincide; classificação difere' if compatible else 'Divergência'})
            named={r['personId'] for r in rows}
            comparisons.extend({'personId':pid,'status':'Sem registro identificado na ata','portalStatus':state,'result':'Somente no portal'} for pid,state in portal.items() if pid not in named)
        record={key:a[key] for key in ('id','url','title','downloaded')}
        record.update(date=date,kind=k,rows=rows,issue=issue,sha256=a.get('sha256'),sessionUrl=match['url'] if match else None,comparison=comparisons,candidateSessions=[x['url'] for x in candidates],inPeriod=bool(date and data['start']<=date<=data['end']),committee=committee_key(text[:1000]) if k.startswith('Comissão') else None)
        record['meetingIdentity']=meeting_identity(text) if k.startswith('Plenário') else None
        if review.get('note'):record['reviewNote']=review['note']
        if review.get('duplicateOf') and source_hashes.get(review['duplicateOf'])==review.get('duplicateOfSha256'):
            record['duplicateOf']=review['duplicateOf']
        if a['id'] in ('517332','516885','531722','549930'):record['reviewNote']='Variação de grafia do nome conferida e conciliada com o cadastro nominal.'
        if a['id']=='530040':record['reviewNote']='A ata registra comparecimento posterior à Ordem do Dia. Mantido Presente, sem afirmar permanência integral.'
        out.append(record)
    # Uma ata repetida para a mesma reunião não aumenta contagens.
    mark_duplicates(out)
    matched={a['sessionUrl'] for a in out if a['sessionUrl']}
    gaps=[{'date':s['date'],'title':s['title'],'url':s['url'],'kind':session_kind(s['title']),'reason':'Ata não associada de forma inequívoca; não significa ausência de ata no portal.','rows':[{'personId':pid,'status':entry['status'] or 'Situação não informada'} for entry in s['attendance'] for pid in entry['personIds']]} for s in source_sessions if s['url'] not in matched]
    result={'schemaVersion':1,'checkedAt':stamp(),'start':data['start'],'end':data['end'],'people':[{k:p[k] for k in ('id','name','url','party')} for p in data['people']],'minutes':out,'sessionGaps':gaps,'counts':{'calendarSessions':len(source_sessions),'inventoried':len(downloaded),'downloaded':sum(a['downloaded'] for a in out),'withDate':sum(bool(a['date']) for a in out),'withNominalReading':sum(bool(a['rows']) for a in out),'matchedSessions':len(matched),'sessionGaps':len(gaps),'comparisonResults':dict(Counter(c['result'] for a in out for c in a['comparison']))},'method':['Levantamento integral do inventário de atas, sem amostragem na seleção. Extração automatizada com revisão dos casos identificados; não é auditoria externa.','Estados reproduzidos da abertura; falta de nome nunca vira ausência. Motivos pessoais não são republicados.','Uma página no calendário não comprova, sozinha, que a reunião ocorreu ou que determinado vereador deveria comparecer.','Uma ausência sem classificação na ata não é declarada injustificada. Licenças e afastamentos são separados.','Ordenação usa apenas atas de plenário com data identificada, lista nominal legível e sem ambiguidade de reunião. Não mede desempenho.','Percentual usa registros nominais de presença e ausência nas atas elegíveis, não sessões de comparecimento obrigatório. Não há reconstrução integral dos períodos legais de exercício.','Comissões, solenidades e audiências têm composição e obrigações diferentes; não entram na comparação do plenário.','A conferência é uma fotografia datada. Novas coletas do portal não significam novas atas conferidas.','Os resultados de comparação são contados por ata e nome; duas atas podem se referir à mesma reunião. A ordenação exclui esses casos ambíguos.','O inventário usa atas protocoladas em 2025 e 2026. Documentos cujo texto aponta reunião fora do período são preservados no relatório e excluídos das contagens.','Pendências podem decorrer do formato ou da extração automática, não necessariamente de erro da Câmara. Casos sem leitura segura ficam pendentes; divergência não determina sozinha qual fonte está correta.'], 'inventorySources':['https://digital.camarablu.sc.gov.br/documentos/tipo:legislativo-2/ano:2025','https://digital.camarablu.sc.gov.br/documentos/tipo:legislativo-2/ano:2026']}
    result['method']=[m for m in result['method'] if not m.startswith('Os resultados de comparação são contados')]
    result['method'].append('Reuniões de plenário no mesmo dia só são separadas quando número e horário de abertura são distintos. Republicações confirmadas contam uma vez; outras ambiguidades permanecem excluídas. Associações revisadas ficam vinculadas ao hash do PDF e são reavaliadas se ele mudar.')
    return result

def main():
    root=Path(__file__).parent.parent/'full-attendance';data=json.loads((Path(__file__).parent/'dist/data.json').read_text(encoding='utf-8'))
    downloaded=json.loads((root/'downloaded.json').read_text(encoding='utf-8'))
    result=build(data,downloaded,root)
    (root/'parsed.json').write_text(json.dumps(result['minutes'],ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'audit-candidate.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result['counts'],ensure_ascii=True))
    for a in result['minutes']:
        if not a['date'] or not a['rows'] or any(r['status']=='Revisão necessária' for r in a['rows']):print('REVISAR',a['id'],a['title'],a['date'],a['issue'],len(a['rows']))
if __name__=='__main__':main()
