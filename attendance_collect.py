"""Coleta recorrente de atas; caches privados, publicação somente após validação."""
import argparse, concurrent.futures, hashlib, json, re, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pypdf import PdfReader
import radar
from attendance_audit import build

def inventory(client, start, end):
    result = {}
    for year in range(int(start[:4]), int(end[:4])+1):
        url=f'{radar.BASE}/documentos/tipo:legislativo-2/ano:{year}/ordem:Documento.is_protocolado_data%20DESC%2CDocumento.numero%20DESC'
        seen=set(); previous=None
        while url:
            if url in seen: raise RuntimeError('Ciclo no inventário de atas')
            seen.add(url); page,items=radar.document_listing(client,url); links=[]
            for item in items:
                a=item.select_one('a[href^="/documento/"]'); title=radar.txt(item.select_one('.title-link'))
                if not a or not title: raise RuntimeError('Formato do inventário não reconhecido')
                link=urljoin(radar.BASE,a['href']); links.append(link)
                if re.match(r'^Ata\b',title,re.I): result[link]={'url':link,'title':title}
            if tuple(links)==previous: raise RuntimeError('Página repetida no inventário')
            previous=tuple(links)
            nxt=page.select_one('a[rel="next"]'); url=urljoin(radar.BASE,nxt['href']) if nxt else None
            if len(seen)>4000: raise RuntimeError('Inventário excedeu limite de páginas')
        print('INVENTÁRIO DE ATAS',year,len(seen),'páginas',len(result),'atas',flush=True)
    return list(result.values())

def calendar(client,start,end,people,known=()):
    # known: reuniões que já tinham presenças na conferência anterior; nelas a reconsulta espera mais.
    url=radar.BASE+'/sessoes'; seen=set(); links={}
    while url:
        if url in seen: raise RuntimeError('Ciclo no calendário')
        # A lista de sessões às vezes volta vazia: reconsulta antes de desistir.
        seen.add(url); page,anchors=radar.document_listing(client,url,'a[href^="/sessao/"]'); dates=[]
        for a in anchors:
            title=radar.txt(a); date=radar.calendar_date(title)
            if not date: continue
            dates.append(date)
            if start<=date<=end:
                link=urljoin(radar.BASE,a['href']); links[link]={'url':link,'title':title,'date':date}
        if not dates: raise RuntimeError('Calendário sem datas legíveis')
        nxt=page.select_one('a[rel="next"]')
        if max(dates)<start or not nxt: break
        url=urljoin(radar.BASE,nxt['href'])
    def one(item):
        page=radar.session_page(client,item['url'],item['url'] in known); rows=[]
        if not page.select_one('.wrap-presencas') and not page.select_one('#materias-discussao-bloco'):
            raise RuntimeError('Página de reunião sem estrutura reconhecida')
        for p in page.select('.wrap-presencas .item-full-people'):
            info=p.select_one('.info')
            for icon in info.select('.google-icon') if info else []: icon.decompose()
            name=radar.txt(p.select_one('.title')); ids=radar.match_people(name,people)
            if not ids: raise RuntimeError('Nome de presença sem vínculo no cadastro')
            rows.append({'name':name,'status':radar.txt(info),'personIds':ids})
        return {**item,'attendance':rows,'sourceCheckedAt':client.pages[item['url']]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: rows=list(pool.map(one,links.values()))
    print('CALENDÁRIO DE PRESENÇAS',len(rows),'páginas',flush=True)
    return rows

def fetch_pdf(link,referer):
    # O servidor de PDFs às vezes deixa de responder: aguarda e tenta de novo antes de desistir.
    # Resposta HTTP de erro (403, 404…) não é repetida aqui; segue a regra de quem chamou.
    for attempt in range(4):
        try:
            with radar.slots:
                with radar.gate:
                    time.sleep(max(0,.8-(time.monotonic()-radar.last_request))); radar.last_request=time.monotonic()
                with urlopen(Request(link,headers={'User-Agent':'RadarBlumenau/1.0 (+https://github.com/dllsrose/radar-blumenau; attendance verification)','Referer':referer}),timeout=60) as response: return response.read()
        except HTTPError: raise
        except OSError:
            if attempt==3: raise
            print(f'NOVA TENTATIVA de PDF após falha de conexão ({attempt+1}/3): {link}',flush=True)
            time.sleep(2**attempt*5)

def pdf_record(item,client,root,refresh=False):
    ident=item['url'].rsplit('-',1)[-1]; pdf=root/'pdf'/f'{ident}.pdf'; txt=root/'text'/f'{ident}.txt'
    # PDFs já obtidos são relidos semanalmente; indisponíveis são tentados diariamente.
    # Se a rotina recomeça no mesmo dia, o que já foi relido hoje não é baixado outra vez.
    reread_today=pdf.exists() and datetime.fromtimestamp(pdf.stat().st_mtime).date()==datetime.now().date()
    if (refresh and not reread_today) or not pdf.exists():
        page=client.get(item['url'],fresh=True); match=re.search(r'PDFObject.embed\("([^\"]+)',str(page))
        if not match: raise RuntimeError('Formato de PDF não reconhecido')
        link=match[1]
        if urlsplit(link).hostname!='sc-blumenau-camara.ad.sistemalegislativo.com.br': raise RuntimeError('Host de PDF não autorizado')
        try:
            raw=fetch_pdf(link,item['url'])
            if not raw.startswith(b'%PDF'): raise RuntimeError('Fonte não retornou PDF')
            # Extrai antes de substituir qualquer arquivo válido.
            import io
            text='\n\f\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(raw)).pages)
            pdf.write_bytes(raw); txt.write_text(text,encoding='utf-8')
        except HTTPError as exc:
            if exc.code not in (403,404) or pdf.exists(): raise RuntimeError('Falha ao atualizar PDF') from None
            return {**item,'id':ident,'downloaded':False}
    if not txt.exists(): txt.write_text('\n\f\n'.join(p.extract_text() or '' for p in PdfReader(pdf).pages),encoding='utf-8')
    return {**item,'id':ident,'downloaded':True,'pdfFile':str(pdf),'textFile':str(txt),'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()}

def validate_progress(candidate,baseline):
    if candidate['start']>baseline['start'] or candidate['end']<baseline['end']: raise RuntimeError('Cobertura das atas regrediu')
    old={m['url']:m for m in baseline['minutes']}; new={m['url']:m for m in candidate['minutes']}
    if not old.keys()<=new.keys(): raise RuntimeError('Atas desapareceram do inventário')
    for url,m in old.items():
        n=new[url]
        if m['downloaded'] and not n['downloaded']: raise RuntimeError('PDF anteriormente obtido ficou indisponível')
        if (m['rows'] or m.get('historicalRows')) and not (n['rows'] or n.get('historicalRows')): raise RuntimeError('Lista nominal anteriormente legível foi perdida')
        if m['date'] and not n['date']: raise RuntimeError('Data anteriormente legível foi perdida')
    old_sessions={m['sessionUrl'] for m in baseline['minutes'] if m['sessionUrl']}|{s['url'] for s in baseline['sessionGaps']}
    new_sessions={m['sessionUrl'] for m in candidate['minutes'] if m['sessionUrl']}|{s['url'] for s in candidate['sessionGaps']}
    if not old_sessions<=new_sessions: raise RuntimeError('Reuniões desapareceram do calendário')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--data',default='dist/data.json'); ap.add_argument('--baseline',default='dist/attendance-audit.json'); ap.add_argument('--output',default='.local/attendance-candidate.json'); ap.add_argument('--root',default='../full-attendance'); ap.add_argument('--cache'); args=ap.parse_args()
    data=json.loads(Path(args.data).read_text(encoding='utf-8')); root=Path(args.root).resolve()
    for sub in ('pdf','text'): (root/sub).mkdir(parents=True,exist_ok=True)
    client=radar.Client(Path(args.cache or '.cache/'+data['end']))
    items=inventory(client,data['start'],data['end'])
    if not items: raise RuntimeError('Inventário de atas vazio')
    baseline=json.loads(Path(args.baseline).read_text(encoding='utf-8'))
    last_full=baseline.get('automation',{}).get('lastFullPdfCheck',baseline['checkedAt'][:10])
    refresh=datetime.fromisoformat(data['end']).weekday()==6 or (datetime.fromisoformat(data['end'])-datetime.fromisoformat(last_full)).days>=7
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: downloaded=list(pool.map(lambda item:pdf_record(item,client,root,refresh),items))
    previous=root/'calendar-attendance.json'
    known={s['url'] for s in json.loads(previous.read_text(encoding='utf-8')) if s['attendance']} if previous.exists() else set()
    sessions=calendar(client,data['start'],data['end'],data['people'],known)
    # Presenças que existiam ontem não podem sumir hoje: o portal entrega páginas pela metade.
    lost=known-{s['url'] for s in sessions if s['attendance']}
    if lost: raise RuntimeError(f'Presenças do calendário desapareceram em {len(lost)} reunião(ões); revisão necessária')
    radar.atomic(root/'calendar-attendance.json',sessions)
    candidate=build(data,downloaded,root)
    candidate['inventorySources']=[f'{radar.BASE}/documentos/tipo:legislativo-2/ano:{y}' for y in range(int(data['start'][:4]),int(data['end'][:4])+1)]
    candidate['automation']={'mode':'local-daily','pdfRefresh':'weekly-and-new-or-pending-daily','calendarRefresh':'daily','inventoryRefresh':'daily','lastSuccessfulCheck':candidate['checkedAt'],'lastFullPdfCheck':data['end'] if refresh else last_full}
    candidate['method']=[x for x in candidate['method'] if not x.startswith(('A conferência é uma fotografia','O inventário usa atas protocoladas'))]
    candidate['method']+=['Inventário e páginas de reunião são atualizados diariamente pelo computador. PDFs novos e pendentes são consultados a cada execução; os já obtidos são revisitados aos domingos.','A data exibida é da última conferência concluída. Falhas preservam a publicação anterior. Documentos fora do período ficam fora das contagens.']
    validate_progress(candidate,baseline)
    radar.atomic(Path(args.output),candidate); radar.atomic(root/'downloaded.json',downloaded)
    print('CONFERÊNCIA AUTOMÁTICA VALIDADA',json.dumps(candidate['counts'],ensure_ascii=True),flush=True)

if __name__=='__main__': main()
