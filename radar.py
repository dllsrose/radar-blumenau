"""Coleta pública Legisoft. Só promove a base após percorrer e validar as fontes."""
import argparse, concurrent.futures, hashlib, html, json, os, re, sys, threading, time, unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).parent.parent/'pydeps'))
from bs4 import BeautifulSoup
ROOT=Path(__file__).parent
BASE='https://digital.camarablu.sc.gov.br'
ROSTER=BASE+'/vereadores/mandato:2025-ate-2028-22/exercicio:1'
PRIMARY=('Indicação','Requerimento','Moção','Projeto de Lei','Projeto de Decreto Legislativo','Projeto de Resolução','Proposta de Emenda')
gate=threading.Lock(); slots=threading.Semaphore(2); last_request=0
def norm(x): return ''.join(c for c in unicodedata.normalize('NFD',x.casefold()) if unicodedata.category(c)!='Mn')
def txt(n): return ' '.join(n.get_text(' ',strip=True).split()) if n else ''
def stamp(): return datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()
def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf-8'); tmp.replace(path)
def soup(raw): return BeautifulSoup(raw,'html.parser')
def iso(s):
    m=re.search(r'\b\d{2}/\d{2}/\d{4}\b',s)
    return datetime.strptime(m[0],'%d/%m/%Y').strftime('%Y-%m-%d') if m else None
def calendar_date(title):
    # O último campo da listagem é a data do calendário; o título livre pode conter outra data.
    m=re.search(r'(\d{2}/\d{2}/\d{4})\s*$',title)
    return iso(m[1]) if m else None

def public_text(text):
    # Telefones podem ter DDD, nono dígito separado ou aparecer sem DDD.
    text=re.sub(r'(?<!\d)(?:\+?55\s*)?(?:\(\d{2}\)|\b\d{2})[\s.-]*(?:9\s+)?\d{4,5}[-\s]?\d{4}(?!\d)','[telefone omitido]',text)
    def phone_or_years(match):
        value=match[0]
        if re.fullmatch(r'(?:19|20)\d{2}\s*-\s*(?:19|20)\d{2}',value):return value
        return '[telefone omitido]'
    text=re.sub(r'(?<!\d)(?:9\s*)?\d{4}[-\s]\d{4}(?!\d)',phone_or_years,text)
    text=re.sub(r'(?<!\d)9\d{8}(?!\d)','[telefone omitido]',text)
    text=re.sub(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b','[CPF omitido]',text)
    text=re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b',lambda m:m[0] if m[0].lower().endswith('@camarablu.sc.gov.br') else '[e-mail omitido]',text)
    return text

class SecurityCheck(RuntimeError): pass
class Client:
    def __init__(self,cache): self.cache=cache; cache.mkdir(parents=True,exist_ok=True); self.pages={}
    def get(self,url,fresh=False):
        global last_request
        if urlsplit(url).hostname not in ('digital.camarablu.sc.gov.br','camarablu.sc.gov.br'): raise ValueError('Unexpected source host')
        p=self.cache/(hashlib.sha256(url.encode()).hexdigest()+'.json')
        if p.exists() and not fresh:
            v=json.loads(p.read_text(encoding='utf-8')); self.pages[url]=v['at']; return soup(v['body'])
        # O portal falha em rajadas (404 ou sem resposta por dezenas de segundos em páginas que existem):
        # as esperas crescem até cobrir cerca de três minutos antes de desistir.
        waits=(5,15,30,60,60)
        for attempt in range(len(waits)+1):
            try:
                with slots:
                    with gate:
                        time.sleep(max(0,.8-(time.monotonic()-last_request))); last_request=time.monotonic()
                    req=Request(url,headers={'User-Agent':'RadarBlumenau/1.0 (+https://github.com/dllsrose/radar-blumenau; civic transparency; max 2 connections)'})
                    with urlopen(req,timeout=50) as response: raw=response.read().decode('utf-8')
                if any(w in norm(raw) for w in ['confirme que voce nao e um robo','verificacao de seguranca']): raise SecurityCheck('Portal pediu verificação de segurança; coleta interrompida')
                v={'url':url,'at':stamp(),'body':raw}; atomic(p,v); self.pages[url]=v['at']; return soup(raw)
            except SecurityCheck: raise  # pedido de verificação não é repetido nem contornado
            except Exception as exc:
                if attempt==len(waits): raise
                print(f'NOVA TENTATIVA em {waits[attempt]}s após {type(exc).__name__}: {url}',flush=True)
                time.sleep(waits[attempt])
        raise RuntimeError('Unreachable')
def classify(title,text):
    t=norm(title+' '+text)
    honor=r'\b(paraben\w*|congratula\w*|homenag\w*|louvor|pesar|aplausos)\b|titulo de cidad|denomina\w* (?:a |o |de |oficialmente )?(?:rua|via|logradouro|praca)|institui\w*.*(?:dia municipal|semana municipal|data comemorativa)'
    commemorative=title.startswith(('Projeto','Proposta de Emenda')) and (
        re.search(r'\b(?:institui|instituir|cria|criar|inclui|incluir)\s+(?:(?:o|a|um|uma)\s+)?["“”\x27]*(?:dia|semana|mes)\b',t)
        or (re.search(r'\b(?:institui|instituir|cria|criar)\b',t) and re.search(r'\bmes de (?:conscientizacao|prevencao|combate|homenagem)\b',t))
    )
    if re.search(honor,t) or commemorative: return 'Homenagens'
    if title.startswith('Indicação'): return 'Melhorias nos bairros'
    if title.startswith('Requerimento'): return 'Perguntas e cobranças'
    if title.startswith(('Projeto','Proposta de Emenda')): return 'Propostas de lei'
    return 'Outros'
def people(client):
    s=client.get(ROSTER); result={}
    for li in s.select('li.list-item'):
        a=li.select_one('a[href^="/vereador/"]'); n=li.select_one('.vereador-nome')
        if not a or not n: continue
        url=urljoin(BASE,a['href']); slug=a['href'].rsplit('/',1)[-1]; name=txt(n)
        if slug in result: continue
        image=li.select_one('img'); result[slug]={'id':slug,'name':name,'url':url,'party':txt(li.select_one('.vereador-desc')),'photo':image.get('src','').split('?')[0] if image else '', 'aliases':[norm(name)]}
    if len(result)<15: raise RuntimeError('Cadastro incompleto: menos de 15 participantes da legislatura')
    aliases={'bruno-winzewski-1002019':['bruno winzewski','bruno ricardo winzewski','bruno win'],'egidio-da-rosa-beckhauser-1000668':['egidio beckhauser','egidio da rosa beckhauser'],'flavio-jose-linhares-1002017':['flavio jose linhares','flavinho'],'gilson-de-souza-468':['gilson de souza','professor gilson'],'rodrigo-emanuel-marchetti-1001714':['rodrigo emanuel marchetti','rodrigo marchetti'],'jovino-cardoso-neto-471':['jovino cardoso','jovino cardoso neto'],'silmara-silva-miguel-1000671':['silmara miguel','silmara silva miguel'],'marcelo-barasuol-lanzarin-472':['marcelo lanzarin','marcelo barasuol lanzarin']}
    for id,p in result.items(): p['aliases']=aliases.get(id,p['aliases'])
    return sorted(result.values(),key=lambda p:norm(p['name']))
def match_people(names,persons):
    # Delimitadores da autoria; correspondência exata de nomes ou aliases conhecidos.
    parts=[norm(x.strip()) for x in names.split(',')]
    return [p['id'] for p in persons if any(a in parts for a in p['aliases'])]
def document_listing(client,url,selector='li.list-item',allow_unavailable_vote=False):
    # O portal às vezes devolve uma página intermediária vazia com HTTP 200.
    # Não avançar nem tratar isso como fim da lista: aguardar e consultar novamente.
    for delay in (0,5,15,30,60,60):
        if delay:
            print(f'RECONSULTA de página vazia após {delay}s: {url}',flush=True)
            time.sleep(delay)
        s=client.get(url,fresh=bool(delay));items=s.select(selector)
        if items:return s,items
    if allow_unavailable_vote and norm(txt(s))=='nenhuma votacao disponivel':
        print(f'RESULTADO NOMINAL NÃO PUBLICADO NA FONTE: {url}',flush=True)
        return s,[]
    raise RuntimeError(f'Página vazia inesperada após reconsultas: {url}')

def collect_documents(client,year,start,end):
    url=f'{BASE}/documentos/tipo:legislativo-2/ano:{year}/ordem:Documento.is_protocolado_data%20DESC%2CDocumento.numero%20DESC'
    seen=set(); out={}; pages=0; total_rows=0; previous=None
    while url:
        if url in seen: raise RuntimeError('Ciclo na paginação de documentos')
        seen.add(url); s,items=document_listing(client,url)
        pages+=1; ids=[]; dates=[]
        for li in items:
            a=li.select_one('a[href^="/documento/"]'); title=txt(li.select_one('.title-link'))
            if not a or not title: raise RuntimeError('Mudança no formato de documento')
            meta=txt(li.select_one('.sub-title')); d=iso(meta); link=urljoin(BASE,a['href']);ids.append(link);total_rows+=1
            if not d: raise RuntimeError('Documento sem data de protocolo; não é seguro delimitar o período')
            dates.append(d)
            if not start<=d<=end: continue
            if not title.startswith(PRIMARY): continue
            # Exclui requerimentos procedimentais e pareceres; conserva propostas originais.
            if title.startswith(('Requerimento de Inclusão',)): continue
            text=public_text(txt(li.select_one('.document-desc')))
            out[link]={'id':link.rsplit('-',1)[-1],'title':title,'date':d,'authors':txt(li.select_one('.autores')),'text':text,'url':link,'meta':meta,'category':classify(title,text)}
        fingerprint=tuple(ids)
        if fingerprint==previous: raise RuntimeError('Pagina repetida pelo servidor')
        previous=fingerprint
        if pages%10==0: print(f'DOCUMENTOS {year}: {pages} páginas, {len(out)} propostas',flush=True)
        nxt=s.select_one('a[rel="next"]')
        if dates and max(dates)<start: break
        url=urljoin(BASE,nxt['href']) if nxt else None
        if pages>4000: raise RuntimeError('Limite de segurança de paginação')
    return list(out.values()),{'year':year,'pages':pages,'listedRows':total_rows,'proposals':len(out),'complete':True}
def session_links(client,start,end):
    url=BASE+'/sessoes'; seen=set(); links={}
    while url:
        if url in seen: raise RuntimeError('Ciclo na paginação de sessões')
        # A lista de sessões também volta vazia de vez em quando: reconsulta antes de desistir.
        seen.add(url);s,anchors=document_listing(client,url,'a[href^="/sessao/"]');dates=[]
        for a in anchors:
            t=txt(a);d=calendar_date(t)
            if not d: continue
            dates.append(d)
            if start<=d<=end and re.match(r'REUNIÃO (ORDINÁRIA|EXTRAORDINÁRIA)',t,re.I): links[urljoin(BASE,a['href'])]={'date':d,'title':t,**({'dateNote':'A data do calendário oficial diverge da data escrita no título. O filtro usa a data do calendário; o título original foi preservado.'} if iso(t)!=d else {})}
        if not dates: raise RuntimeError('Página de sessões sem datas legíveis')
        nxt=s.select_one('a[rel="next"]')
        if max(dates)<start or not nxt:break
        url=urljoin(BASE,nxt['href'])
    return links
def session_page(client,url):
    # O portal às vezes entrega a página da reunião pela metade (HTTP 200, sem o bloco de presenças):
    # reconsulta antes de aceitar. Poucas reuniões realmente não têm presença publicada; essas são
    # aceitas depois das reconsultas, e a validação final continua barrando qualquer perda de registro.
    for delay in (0,5,15,30):
        if delay:
            print(f'RECONSULTA de reunião sem presenças após {delay}s: {url}',flush=True)
            time.sleep(delay)
        s=client.get(url,fresh=bool(delay))
        if s.select_one('.wrap-presencas'): break
    return s
def session_detail(client,item):
    url,record=item; s=session_page(client,url); at=[];votes=[]
    if not s.select_one('.wrap-presencas') and not s.select_one('#materias-discussao-bloco'): raise RuntimeError('Formato da sessão não reconhecido')
    for p in s.select('.wrap-presencas .item-full-people'):
        info=p.select_one('.info')
        for icon in info.select('.google-icon') if info else []:icon.decompose()
        at.append({'name':txt(p.select_one('.title')),'status':txt(info),'url':urljoin(BASE,p['href'])})
    for a in s.select('a[data-ajax*="/votacao/"]'):
        vs,vote_people=document_listing(client,a['data-ajax'],'.item-small-people',allow_unavailable_vote=True);rows=[]
        for p in vote_people:
            info=p.select_one('.info')
            for icon in info.select('.google-icon') if info else []:icon.decompose()
            rows.append({'name':txt(p.select_one('.title')),'vote':txt(info)})
        block=a.find_parent(class_='item-full-accordion'); title=txt(block.select_one('.title')) if block else 'Votação'
        source=block.select_one('a[href^="/documento/"]') if block else None
        votes.append({'url':a['data-ajax'],'title':title,'availability':'published' if rows else 'unavailable','notice':'' if rows else 'O portal oficial informa “Nenhuma votação disponível”, confirmado após seis consultas. Nenhum voto foi inferido. O resultado será consultado novamente nas revisões do histórico.','documentUrl':urljoin(BASE,source['href']) if source else None,'rows':rows,'text':'\n'.join(x['name']+' — '+x['vote'] for x in rows)})
    return {**record,'url':url,'attendance':at,'votes':votes}
TOPICS=[('Buracos e pavimentação',r'buraco|pavimenta|calcamento|lajota|asfalt'),('Roçada e limpeza',r'rocada|rocar|limpeza|limpar|capina|recolher lixo|caixas? coletoras? de lixo'),('Bocas de lobo e drenagem',r'boca de lobo|caixas? coletoras?\b(?! de lixo)|drenagem|esgoto|tubulacao'),('Rios e ribeirões',r'ribeirao|ribeiro|desassoreamento|\brio\b'),('Iluminação pública',r'iluminacao|luminaria|lampada'),('Sinalização e trânsito',r'sinalizacao|faixa de pedestre|lombada|semaforo|redutor de velocidade'),('Manutenção de vias sem pavimento',r'patrolar|patrolagem|macadam|ensaibr')]
def addresses(text):
    # Busca somente o trecho do pedido, antes da justificativa: reduz menções incidentais.
    text=re.split(r'Justificativa\s*:',text,flags=re.I)[0]
    for short,long in [('Prof','Professor'),('Dr','Doutor'),('Eng','Engenheiro'),('Pres','Presidente'),('Cel','Coronel')]:
        text=re.sub(r'\b'+short+r'\.\s+',long+' ',text,flags=re.I)
    found=[]
    for m in re.finditer(r'\b(Rua|R\.|Avenida|Av\.|Travessa|Alameda|Servidão|Estrada|Rodovia)\s+([^,;\n:()]+)',text,re.I):
        name=re.split(r'\s+(?:n[º°o.]|número|em frente|próximo|proximo|esquina|localizad|no bairro|bairro|a partir|até|entre|defronte|nas proximidades|altura)\b',m[2],flags=re.I)[0]
        name=re.split(r'\.(?:\s|$)',name)[0].strip(' .-')
        if not 3<=len(name)<=75 or len(name.split())>9 or norm(name) in ('prof','professor','doutor','eng','presidente','coronel'): continue
        kind={'r.':'Rua','av.':'Avenida'}.get(m[1].lower(),m[1].title()); found.append(kind+' '+name)
    return list(dict.fromkeys(found))
def repeats(docs):
    groups=defaultdict(dict)
    for d in docs:
        if d['category'] not in ('Melhorias nos bairros','Perguntas e cobranças'):continue
        head=re.split(r'Justificativa\s*:',d['text'],flags=re.I)[0];n=norm(head)
        themes=[label for label,pat in TOPICS if re.search(pat,n)]
        if any(t in themes for t in ('Bocas de lobo e drenagem','Rios e ribeirões')):
            themes=[t for t in themes if t!='Roçada e limpeza']
        for street in addresses(head):
            for theme in themes:groups[(norm(street),theme)][d['url']]={'street':street,'doc':d}
    output=[]
    for (key,theme),items in groups.items():
        ds=[x['doc'] for x in items.values()]
        if len(ds)<2 or len(set(d['date'] for d in ds))<2:continue
        output.append({'street':next(iter(items.values()))['street'],'topic':theme,'count':len(ds),'dates':sorted(set(d['date'] for d in ds)),'documents':[d['url'] for d in sorted(ds,key=lambda d:d['date'])],'method':'Correspondência automática de logradouro e assunto; não confirma que o problema é o mesmo ou não foi resolvido.'})
    return sorted(output,key=lambda g:(-g['count'],norm(g['street'])))
def nominal_keys(rows):
    return {tuple(sorted(row.get('personIds',[]))) or ('name',norm(row.get('name',''))) for row in rows}

def validate(data,baseline=None):
    if len(data['people'])<15 or not data['documents'] or not data['sessions']:raise ValueError('Base vazia ou cadastro incompleto')
    urls=[d['url'] for d in data['documents']]
    if len(urls)!=len(set(urls)):raise ValueError('Documentos duplicados')
    if any(not data['start']<=d['date']<=data['end'] for d in data['documents']):raise ValueError('Data fora da cobertura')
    if any(not d['authors'] or not d['text'] for d in data['documents']):raise ValueError('Autoria ou texto ausente em proposta')
    if baseline and baseline.get('schemaVersion')==2:
        previous={d['url'] for d in baseline['documents']}
        if previous-set(urls):raise ValueError('Documentos desapareceram; preservar última versão e revisar')
        old_sessions={s['url']:s for s in baseline['sessions']}; current={s['url']:s for s in data['sessions']}
        if old_sessions.keys()-current.keys():raise ValueError('Sessões desapareceram')
        for u,s in old_sessions.items():
            if len(current[u]['attendance'])<len(s['attendance']) or len(current[u]['votes'])<len(s['votes']):raise ValueError('Perda de registros nominais; revisão necessária')
            if nominal_keys(s['attendance'])-nominal_keys(current[u]['attendance']):raise ValueError('Nomes desapareceram da presença; revisão necessária')
            current_votes={v['url']:v for v in current[u]['votes']}
            for old_vote in s['votes']:
                new_vote=current_votes.get(old_vote['url'])
                if new_vote is None or nominal_keys(old_vote['rows'])-nominal_keys(new_vote['rows']):raise ValueError('Votos nominais desapareceram; preservar publicação anterior')
    return {'valid':True,'uniqueProposals':len(urls),'participants':len(data['people']),'sessions':len(data['sessions']),'votes':sum(bool(v['rows']) for s in data['sessions'] for v in s['votes']),'unavailableVotes':sum(not v['rows'] for s in data['sessions'] for v in s['votes'])}
def weekday_today(): return datetime.now(ZoneInfo('America/Sao_Paulo')).weekday()
def history_group(url):
    # Grupo fixo (0 a 6) de cada reunião antiga: decide em que dia da semana ela é reconferida.
    return int(hashlib.sha256(url.encode()).hexdigest(),16)%7
def refresh_plan(start,end,weekday,incremental):
    """Devolve (início do período recente, anos de propostas a reconferir por inteiro, grupos de reuniões antigas).

    Toda execução revisita os últimos 45 dias. O histórico anterior é reconferido em partes ao longo
    da semana, em vez de tudo no domingo: cada ano de propostas num dia fixo (ano % 7) e as reuniões
    antigas em sete grupos estáveis, um por dia. Em sete dias seguidos o histórico inteiro é revisto.
    Sem base anterior compatível (ou com --full) tudo é coletado de uma vez."""
    years=range(int(start[:4]),int(end[:4])+1)
    if not incremental: return start,set(years),set(range(7))
    recent=max(start,(datetime.fromisoformat(end)-timedelta(days=45)).date().isoformat())
    return recent,{y for y in years if y%7==weekday},{weekday}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--full',action='store_true',help='reconferir todo o histórico de uma vez');ap.add_argument('--start',default='2025-01-01');ap.add_argument('--end',default=datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat());ap.add_argument('--cache',default='.cache/'+datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat());ap.add_argument('--output',default='dist/data.json');ap.add_argument('--baseline');args=ap.parse_args()
    baseline=json.loads(Path(args.baseline).read_text(encoding='utf-8')) if args.baseline and Path(args.baseline).exists() else None
    incremental=bool(baseline and baseline.get('schemaVersion')==2 and baseline['start']==args.start and baseline['end']<=args.end and not args.full)
    refresh_start,full_years,groups_due=refresh_plan(args.start,args.end,weekday_today(),incremental)
    years=range(int(args.start[:4]),int(args.end[:4])+1)
    print(f'PLANO: recentes desde {refresh_start}; anos de propostas reconferidos por inteiro {sorted(full_years)}; grupos de reuniões antigas {sorted(groups_due)}',flush=True)
    client=Client(ROOT/args.cache); persons=people(client);all_docs=[];coverage=[]
    # Dois anos são coletados em paralelo, limitados a duas conexões ao portal.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        tasks=[pool.submit(collect_documents,client,y,args.start if y in full_years else refresh_start,args.end) for y in years if y in full_years or y>=int(refresh_start[:4])]
        for task in concurrent.futures.as_completed(tasks):
            docs,report=task.result();all_docs+=docs;coverage.append(report)
    # A listagem de reuniões é sempre percorrida inteira (são poucas páginas); o detalhe e os votos só de quem está no plano do dia.
    old_sessions={s['url']:s for s in baseline['sessions']} if incremental else {}
    links={u:r for u,r in session_links(client,args.start,args.end).items() if r['date']>=refresh_start or u not in old_sessions or history_group(u) in groups_due}; sessions=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(session_detail,client,item) for item in links.items()]
        for f in concurrent.futures.as_completed(futures):
            sessions.append(f.result());print(f'SESSÕES {len(sessions)}/{len(links)}',flush=True)
    if incremental:
        # O que não está no plano de hoje vem da base anterior e é reconferido no seu dia da semana.
        all_docs.extend(d for d in baseline['documents'] if d['date']<refresh_start and int(d['date'][:4]) not in full_years)
        sessions.extend(s for u,s in old_sessions.items() if u not in links and s['date']<refresh_start and history_group(u) not in groups_due)
    for d in all_docs:
        d['text']=public_text(d['text']);d['category']=classify(d['title'],d['text']);d['authorIds']=match_people(d['authors'],persons)
    for s in sessions:
        for a in s['attendance']:a['personIds']=match_people(a['name'],persons)
        for v in s['votes']:
            for row in v['rows']:row['personIds']=match_people(row['name'],persons)
    collected=sorted(client.pages.values());data={'schemaVersion':2,'start':args.start,'end':args.end,'collectedAt':max(collected),'collectionStartedAt':min(collected),'people':persons,'documents':sorted({d['url']:d for d in all_docs}.values(),key=lambda d:(d['date'],d['id']),reverse=True),'sessions':sorted(sessions,key=lambda s:(s['date'],s['url']),reverse=True),'documentCoverage':coverage,'sources':{'roster':ROSTER,'institutionalRoster':'https://camarablu.sc.gov.br/quem-sao/'},'updateMode':'Coleta local diária às 03h17 (Brasília), com os últimos 45 dias e uma parte do histórico por dia, de modo que tudo é reconferido a cada semana; validação e publicação pelo GitHub Actions','limitations':['Não representa todos os atos informais do mandato, nem execução de obras.','Cadastro institucional e digital divergiam na conferência inicial; incluímos todos os participantes publicados para a legislatura.','Categorias e agrupamentos de pedidos são cálculos automáticos, sujeitos a correção.','Ausência de registro não é falta.','Conferência independente de presenças descrita no relatório de auditoria.']}
    if baseline:data['collectedAt']=max(data['collectedAt'],baseline['collectedAt'])
    data['processedAt']=stamp()
    data['refreshedFrom']=refresh_start
    # Data da última reconferência de cada parte do histórico; a base inteira foi revista desde a mais antiga delas.
    previous_full=baseline.get('fullCollectedAt',baseline['collectedAt']) if incremental else data['collectedAt']
    checks=baseline.get('historyChecks',{}) if incremental else {}
    data['historyChecks']={
        'documents':{str(y):data['collectedAt'] if y in full_years else checks.get('documents',{}).get(str(y),previous_full) for y in years},
        'sessions':{str(g):data['collectedAt'] if g in groups_due else checks.get('sessions',{}).get(str(g),previous_full) for g in range(7)}}
    data['fullCollectedAt']=min([*data['historyChecks']['documents'].values(),*data['historyChecks']['sessions'].values()])
    data['repeatedRequests']=repeats(data['documents'])
    data['validation']=validate(data,baseline);atomic(ROOT/args.output,data);print('BASE VALIDADA '+json.dumps(data['validation']),flush=True)
if __name__=='__main__':main()
