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
def public_text(text):
    text=re.sub(r'(?<!\d)(?:\+?55\s*)?(?:\(\d{2}\)|\b\d{2})\s*\d{4,5}[-\s]?\d{4}(?!\d)','[telefone omitido]',text)
    text=re.sub(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b','[CPF omitido]',text)
    text=re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b',lambda m:m[0] if m[0].lower().endswith('@camarablu.sc.gov.br') else '[e-mail omitido]',text)
    return text
class Client:
    def __init__(self,cache): self.cache=cache; cache.mkdir(parents=True,exist_ok=True); self.pages={}
    def get(self,url,fresh=False):
        global last_request
        if urlsplit(url).hostname not in ('digital.camarablu.sc.gov.br','camarablu.sc.gov.br'): raise ValueError('Unexpected source host')
        p=self.cache/(hashlib.sha256(url.encode()).hexdigest()+'.json')
        if p.exists() and not fresh:
            v=json.loads(p.read_text(encoding='utf-8')); self.pages[url]=v['at']; return soup(v['body'])
        for attempt in range(4):
            try:
                with slots:
                    with gate:
                        time.sleep(max(0,.8-(time.monotonic()-last_request))); last_request=time.monotonic()
                    req=Request(url,headers={'User-Agent':'RadarBlumenau/1.0 (+https://github.com/dllsrose/radar-blumenau; civic transparency; max 2 connections)'})
                    with urlopen(req,timeout=50) as response: raw=response.read().decode('utf-8')
                if any(w in norm(raw) for w in ['confirme que voce nao e um robo','verificacao de seguranca']): raise RuntimeError('Portal pediu verificação de segurança; coleta interrompida')
                v={'url':url,'at':stamp(),'body':raw}; atomic(p,v); self.pages[url]=v['at']; return soup(raw)
            except Exception:
                if attempt==3: raise
                time.sleep(2**attempt*2)
        raise RuntimeError('Unreachable')
def classify(title,text):
    t=norm(title+' '+text)
    honor=r'\b(paraben\w*|congratula\w*|homenag\w*|louvor|pesar|aplausos)\b|titulo de cidad|denomina\w* (?:a |o |de |oficialmente )?(?:rua|via|logradouro|praca)|institui\w*.*(?:dia municipal|semana municipal|data comemorativa)'
    if re.search(honor,t): return 'Homenagens'
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
def document_listing(client,url,selector='li.list-item'):
    # O portal às vezes devolve uma página intermediária vazia com HTTP 200.
    # Não avançar nem tratar isso como fim da lista: aguardar e consultar novamente.
    for delay in (0,5,15,30,60,60):
        if delay:
            print(f'RECONSULTA de página vazia após {delay}s: {url}',flush=True)
            time.sleep(delay)
        s=client.get(url,fresh=bool(delay));items=s.select(selector)
        if items:return s,items
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
        seen.add(url);s=client.get(url);dates=[]
        for a in s.select('a[href^="/sessao/"]'):
            t=txt(a);d=iso(t)
            if not d: continue
            dates.append(d)
            if start<=d<=end and re.match(r'REUNIÃO (ORDINÁRIA|EXTRAORDINÁRIA)',t): links[urljoin(BASE,a['href'])]={'date':d,'title':t}
        if not dates: raise RuntimeError('Página de sessões sem datas legíveis')
        nxt=s.select_one('a[rel="next"]')
        if max(dates)<start or not nxt:break
        url=urljoin(BASE,nxt['href'])
    return links
def session_detail(client,item):
    url,record=item; s=client.get(url); at=[];votes=[]
    if not s.select_one('.wrap-presencas') and not s.select_one('#materias-discussao-bloco'): raise RuntimeError('Formato da sessão não reconhecido')
    for p in s.select('.wrap-presencas .item-full-people'):
        info=p.select_one('.info')
        for icon in info.select('.google-icon') if info else []:icon.decompose()
        at.append({'name':txt(p.select_one('.title')),'status':txt(info),'url':urljoin(BASE,p['href'])})
    for a in s.select('a[data-ajax*="/votacao/"]'):
        vs,vote_people=document_listing(client,a['data-ajax'],'.item-small-people');rows=[]
        for p in vote_people:
            info=p.select_one('.info')
            for icon in info.select('.google-icon') if info else []:icon.decompose()
            rows.append({'name':txt(p.select_one('.title')),'vote':txt(info)})
        if not rows: raise RuntimeError('Registro de votação vazio')
        block=a.find_parent(class_='item-full-accordion'); title=txt(block.select_one('.title')) if block else 'Votação'
        source=block.select_one('a[href^="/documento/"]') if block else None
        votes.append({'url':a['data-ajax'],'title':title,'documentUrl':urljoin(BASE,source['href']) if source else None,'rows':rows,'text':'\n'.join(x['name']+' — '+x['vote'] for x in rows)})
    return {**record,'url':url,'attendance':at,'votes':votes}
TOPICS=[('Buracos e pavimentação',r'buraco|pavimenta|calcamento|lajota|asfalt'),('Roçada e limpeza',r'rocada|rocar|limpeza|limpar|capina|recolher lixo'),('Bocas de lobo e drenagem',r'boca de lobo|caixa coletora|caixas coletoras|drenagem|esgoto|tubulacao'),('Rios e ribeirões',r'ribeirao|ribeiro|desassoreamento|\brio\b'),('Iluminação pública',r'iluminacao|luminaria|lampada'),('Sinalização e trânsito',r'sinalizacao|faixa de pedestre|lombada|semaforo|redutor de velocidade'),('Manutenção de vias sem pavimento',r'patrolar|patrolagem|macadam|ensaibr')]
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
    return {'valid':True,'uniqueProposals':len(urls),'participants':len(data['people']),'sessions':len(data['sessions']),'votes':sum(len(s['votes']) for s in data['sessions'])}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--start',default='2025-01-01');ap.add_argument('--end',default=datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat());ap.add_argument('--cache',default='.cache/'+datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat());ap.add_argument('--output',default='dist/data.json');ap.add_argument('--baseline');args=ap.parse_args()
    baseline=json.loads(Path(args.baseline).read_text(encoding='utf-8')) if args.baseline and Path(args.baseline).exists() else None
    refresh_start=args.start
    if baseline and baseline.get('schemaVersion')==2 and baseline['start']==args.start and baseline['end']<=args.end and datetime.now(ZoneInfo('America/Sao_Paulo')).weekday()!=6:
        refresh_start=max(args.start,(datetime.fromisoformat(args.end)-timedelta(days=45)).date().isoformat())
    client=Client(ROOT/args.cache); persons=people(client);all_docs=[];coverage=[]
    # Dois anos são coletados em paralelo, limitados a duas conexões ao portal.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        tasks=[pool.submit(collect_documents,client,y,refresh_start,args.end) for y in range(int(refresh_start[:4]),int(args.end[:4])+1)]
        for task in concurrent.futures.as_completed(tasks):
            docs,report=task.result();all_docs+=docs;coverage.append(report)
    links=session_links(client,refresh_start,args.end); sessions=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(session_detail,client,item) for item in links.items()]
        for f in concurrent.futures.as_completed(futures):
            sessions.append(f.result());print(f'SESSÕES {len(sessions)}/{len(links)}',flush=True)
    if refresh_start>args.start:
        all_docs.extend(d for d in baseline['documents'] if d['date']<refresh_start)
        sessions.extend(s for s in baseline['sessions'] if s['date']<refresh_start)
    for d in all_docs:d['authorIds']=match_people(d['authors'],persons)
    for s in sessions:
        for a in s['attendance']:a['personIds']=match_people(a['name'],persons)
        for v in s['votes']:
            for row in v['rows']:row['personIds']=match_people(row['name'],persons)
    collected=sorted(client.pages.values());data={'schemaVersion':2,'start':args.start,'end':args.end,'collectedAt':max(collected),'collectionStartedAt':min(collected),'people':persons,'documents':sorted({d['url']:d for d in all_docs}.values(),key=lambda d:(d['date'],d['id']),reverse=True),'sessions':sorted(sessions,key=lambda s:(s['date'],s['url']),reverse=True),'documentCoverage':coverage,'sources':{'roster':ROSTER,'institutionalRoster':'https://camarablu.sc.gov.br/quem-sao/'},'updateMode':'Coleta local diária às 03h17 (Brasília); validação e publicação pelo GitHub Actions','limitations':['Não representa todos os atos informais do mandato, nem execução de obras.','Cadastro institucional e digital divergiam na conferência inicial; incluímos todos os participantes publicados para a legislatura.','Categorias e agrupamentos de pedidos são cálculos automáticos, sujeitos a correção.','Ausência de registro não é falta.','Conferência independente de presenças descrita no relatório de auditoria.']}
    data['refreshedFrom']=refresh_start
    data['fullCollectedAt']=data['collectedAt'] if refresh_start==args.start else baseline.get('fullCollectedAt',baseline['collectedAt'])
    data['repeatedRequests']=repeats(data['documents'])
    data['validation']=validate(data,baseline);atomic(ROOT/args.output,data);print('BASE VALIDADA '+json.dumps(data['validation']),flush=True)
if __name__=='__main__':main()
