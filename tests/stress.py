"""Stress test del sito Mòrk's Place.

Uso:  python3 tests/stress.py [URL]      (default http://localhost:8765/index.html)
Serve un server locale che supporti le richieste a intervalli (Range), oppure l'URL pubblico.
Scrive tests/report/report.md e gli screenshot dei problemi in tests/report/.
"""
import sys, os, json, time, traceback
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765/index.html'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report')
os.makedirs(OUT, exist_ok=True)

DEVICES = {
    'iPhone SE':          dict(w=375, h=667, mobile=True),
    'iPhone 14':          dict(w=393, h=852, mobile=True),
    'iPhone 14 Pro Max':  dict(w=430, h=932, mobile=True),
    'Android (Pixel 7)':  dict(w=412, h=915, mobile=True),
    'Telefono orizzontale': dict(w=852, h=393, mobile=True),
    'iPad verticale':     dict(w=820, h=1180, mobile=True),
    'iPad orizzontale':   dict(w=1180, h=820, mobile=True),
    'Portatile 13"':      dict(w=1280, h=720, mobile=False),
    'Desktop':            dict(w=1440, h=900, mobile=False),
    'Full HD':            dict(w=1920, h=1080, mobile=False),
    'Ultrawide':          dict(w=2560, h=1080, mobile=False),
}
IPHONE_UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 '
             '(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1')

# ---------------- funzioni eseguite nella pagina ----------------
JS_STATE = """(()=>{var i=document.getElementById('ingresso'),sp=i.offsetHeight-innerHeight;
 var mp=[...document.querySelectorAll('#murG path')].map(p=>parseFloat(p.style.strokeDashoffset||'1'));
 var drawn=mp.filter(v=>Math.abs(v)<0.02).length;
 return {p:Math.max(0,Math.min(1,-i.getBoundingClientRect().top/sp)),drawn:drawn,total:mp.length,
   logo:parseFloat(getComputedStyle(document.getElementById('chLogo')).opacity),
   lead:parseFloat(document.getElementById('murLead').style.strokeDashoffset||'1'),
   sx:scrollX,sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth}})()"""

JS_TEXT_HITS = """(()=>{
 var g=document.getElementById('guest'),th=document.getElementById('thread'),p=document.getElementById('threadP');
 function absTop(el){var y=0;while(el&&el!==g){y+=el.offsetTop;el=el.offsetParent}return y}
 function absLeft(el){var x=0;while(el&&el!==g){x+=el.offsetLeft;el=el.offsetParent}return x}
 if(!p.getAttribute('d'))return ['filo non costruito'];
 var t0=parseFloat(th.style.top),L=p.getTotalLength(),pts=[];
 for(var i=0;i<=4000;i++){var q=p.getPointAtLength(L*i/4000);pts.push([q.x,q.y+t0])}
 var hits=[];
 document.querySelectorAll('#guest > section:not(#ingresso):not(.rail) *').forEach(function(e){
   if(!e.offsetHeight||e.closest('.cf-track'))return;
   var own=/^(IMG|INPUT|SELECT|BUTTON)$/.test(e.tagName);
   for(var c=e.firstChild;c&&!own;c=c.nextSibling)if(c.nodeType===3&&c.textContent.trim())own=true;
   if(!own)return;
   var x0=absLeft(e),y0=absTop(e),x1=x0+e.offsetWidth,y1=y0+e.offsetHeight;
   if(!/^(IMG|INPUT|SELECT|BUTTON|A)$/.test(e.tagName)){var rg=document.createRange();rg.selectNodeContents(e);var r=rg.getBoundingClientRect(),er=e.getBoundingClientRect();x0+=r.left-er.left;x1=x0+r.width}
   for(var k=0;k<pts.length;k++){var P=pts[k];if(P[0]>x0-3&&P[0]<x1+3&&P[1]>y0-3&&P[1]<y1+3){hits.push((e.textContent||e.tagName).trim().slice(0,40));break}}
 });
 return hits})()"""

JS_LEAD_HITS = """(()=>{var p=document.getElementById('murLead');if(!p.getAttribute('d'))return ['striscia non costruita'];
 var L=p.getTotalLength(),hits=new Set();
 var els=[...document.querySelectorAll('#ch3 h2,#ch3 .live,#ch3 a')];
 for(var i=0;i<=800;i++){var q=p.getPointAtLength(L*i/800);els.forEach(function(e){var r=e.getBoundingClientRect();
   if(e.tagName==='H2'){var rg=document.createRange();rg.selectNodeContents(e);r=rg.getBoundingClientRect()}
   if(q.x>r.left-2&&q.x<r.right+2&&q.y>r.top-2&&q.y<r.bottom+2)hits.add(e.textContent.trim().slice(0,30))})}
 return [...hits]})()"""

JS_TEXT_CUT = """(()=>{var out=[];document.querySelectorAll('h1,h2,h3,p,a,button,b,small,span,label,dd,dt,li').forEach(function(e){
  if(!e.offsetWidth||e.closest('#owner')||e.closest('.cf-track')||e.closest('.track'))return;
  var cs=getComputedStyle(e); if(cs.visibility==='hidden')return;
  if(cs.overflow==='hidden'||cs.overflowX==='hidden'||cs.textOverflow==='ellipsis'){
    /* confronta lo spazio del solo testo con lo spazio disponibile (gli effetti decorativi non contano) */
    var rg=document.createRange();rg.selectNodeContents(e);var tr=rg.getBoundingClientRect(),er=e.getBoundingClientRect();
    if(e.textContent.trim()&&(tr.left<er.left-1||tr.right>er.right+1))out.push(e.tagName+': '+e.textContent.trim().slice(0,40));
  }
  var r=e.getBoundingClientRect(); if(r.width&&(r.left<-1||r.right>innerWidth+1)&&!e.closest('.rail')&&!e.closest('.cf')&&cs.position!=='fixed')out.push('fuori schermo: '+e.textContent.trim().slice(0,40)+' ('+Math.round(r.left)+'→'+Math.round(r.right)+')');
 });return [...new Set(out)].slice(0,12)})()"""

JS_HEADER = """(()=>{var a=document.querySelector('.mark').getBoundingClientRect(),b=document.querySelector('.top-cta').getBoundingClientRect();
 return {overlap:!(a.right<b.left||b.right<a.left||a.bottom<b.top||b.bottom<a.top),gap:Math.round(b.left-a.right)}})()"""

JS_FRAMES = """(ms)=>new Promise(res=>{var t=[],last=performance.now(),end=last+ms;function f(now){t.push(now-last);last=now;
 if(now<end)requestAnimationFrame(f);else{t.sort((a,b)=>a-b);res({n:t.length,p50:t[Math.floor(t.length*.5)],p95:t[Math.floor(t.length*.95)],max:t[t.length-1]})}}requestAnimationFrame(f)})"""


class Run:
    def __init__(self):
        self.rows = []   # (device, test, ok, detail)
        self.shots = []

    def add(self, dev, test, ok, detail=''):
        self.rows.append((dev, test, ok, detail))
        print(('OK  ' if ok else 'ERR ') + dev + ' | ' + test + ('' if ok else ' | ' + str(detail)[:200]), flush=True)


def hero_span(pg):
    return pg.evaluate("document.getElementById('ingresso').offsetHeight-innerHeight")


def goto_y(pg, y, wait=500):
    pg.evaluate(f"window.scrollTo({{top:{int(y)},left:0,behavior:'instant'}})")
    pg.wait_for_timeout(wait)


def shot(pg, run, dev, name):
    f = os.path.join(OUT, (dev + '_' + name).replace(' ', '_').replace('"', '').replace('(', '').replace(')', '') + '.png')
    pg.screenshot(path=f)
    run.shots.append(f)


def test_device(b, run, dev, spec):
    ctx = b.new_context(viewport={'width': spec['w'], 'height': spec['h']}, is_mobile=spec['mobile'],
                        has_touch=spec['mobile'], device_scale_factor=2 if spec['mobile'] else 1,
                        user_agent=IPHONE_UA if spec['mobile'] and spec['w'] < 900 else None)
    pg = ctx.new_page()
    errs, bad_req = [], []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and not any(k in m.text for k in ('supabase', 'ERR_', 'Failed to load resource', 'net::')) else None)
    pg.on('requestfailed', lambda r: bad_req.append(r.url) if 'localhost' in r.url or 'github.io' in r.url else None)
    pg.on('popup', lambda p: p.close())
    t0 = time.time(); pg.goto(URL, wait_until='load'); load = time.time() - t0
    pg.wait_for_timeout(1500)

    # 1. caricamento
    broken = pg.evaluate("[...document.images].filter(i=>i.complete&&i.naturalWidth===0&&i.getAttribute('src')).map(i=>i.getAttribute('src').slice(0,40))")
    run.add(dev, 'Caricamento senza errori', not errs and not bad_req and not broken,
            f'errori JS {errs[:3]} | richieste fallite {bad_req[:3]} | immagini rotte {broken[:3]}')
    run.add(dev, f'Tempo di caricamento ({load:.1f}s in locale)', load < 6, f'{load:.1f}s')

    # 2. intestazione
    hd = pg.evaluate(JS_HEADER)
    run.add(dev, 'Logo e "Prenota un tavolo" non si sovrappongono', not hd['overlap'], hd)

    # 3. hero: sequenza
    sp = hero_span(pg); seq_ok = True; det = []
    for p in (0, .1, .3, .5, .7, .86, .95, 1.0):
        goto_y(pg, sp * p, 650); st = pg.evaluate(JS_STATE)
        if p == 0 and (st['drawn'] > 0 or st['logo'] < .9): seq_ok = False; det.append(f'inizio: {st}')
        if p >= .86 and st['drawn'] < st['total'] * .97: seq_ok = False; det.append(f'p={p} murale incompleto {st["drawn"]}/{st["total"]}')
        if st['sx'] != 0 or st['sw'] > st['cw']: seq_ok = False; det.append(f'p={p} pagina spostata di lato {st}')
    run.add(dev, 'Hero: logo → murale disegnato → completo con "Benvenuti"', seq_ok, det)
    goto_y(pg, sp * .97, 700); shot(pg, run, dev, 'hero_benvenuti')
    lh = pg.evaluate(JS_LEAD_HITS)
    run.add(dev, 'Hero: la striscia non tocca "Benvenuti" e i pulsanti', not lh, lh)

    # 4. filo nel sito
    th = pg.evaluate(JS_TEXT_HITS)
    run.add(dev, 'Filo: non passa sopra nessuna scritta', not th, th)

    # 5. testi tagliati / fuori schermo, controllati in punti diversi della pagina
    H = pg.evaluate("document.documentElement.scrollHeight"); cut = set(); side = []
    for y in range(int(sp + spec['h']), H, max(400, spec['h'])):
        goto_y(pg, y, 250)
        cut.update(pg.evaluate(JS_TEXT_CUT))
        s = pg.evaluate("[scrollX,document.documentElement.scrollWidth,document.documentElement.clientWidth]")
        if s[0] or s[1] > s[2]: side.append((y, s))
    run.add(dev, 'Nessun testo tagliato o fuori schermo', not cut, sorted(cut)[:8])
    run.add(dev, 'La pagina non si allarga mai di lato', not side, side[:3])

    # 6. scroll violento su e giù, poi stato coerente
    goto_y(pg, 0, 300)
    for _ in range(3):
        for _ in range(25): pg.mouse.wheel(0, 900)
        pg.wait_for_timeout(120)
        for _ in range(25): pg.mouse.wheel(0, -900)
        pg.wait_for_timeout(120)
    pg.wait_for_timeout(1800)
    goto_y(pg, 0, 900); st = pg.evaluate(JS_STATE)
    ok = st['drawn'] == 0 and st['logo'] > .9 and st['lead'] > .98 and st['sx'] == 0
    run.add(dev, 'Scroll violento su e giù: l\'hero torna pulito', ok, st)
    if not ok: shot(pg, run, dev, 'dopo_scroll_violento')

    # 7. Torna su dal fondo
    goto_y(pg, H, 900)
    try:
        pg.click('#toTop', timeout=3000)
        pg.wait_for_function("scrollY<2", timeout=9000)
        pg.wait_for_timeout(900)
        st = pg.evaluate(JS_STATE)
        ok = st['drawn'] == 0 and st['logo'] > .9 and st['sx'] == 0
        run.add(dev, '"Torna su" dal fondo: hero intatto', ok, st)
        goto_y(pg, sp * .9, 900); st = pg.evaluate(JS_STATE)
        run.add(dev, '"Torna su" poi di nuovo giù: murale al suo posto', st['drawn'] >= st['total'] * .97 and st['sx'] == 0, st)
        if not ok: shot(pg, run, dev, 'dopo_torna_su')
    except Exception as e:
        run.add(dev, '"Torna su" dal fondo: hero intatto', False, str(e)[:120])

    # 8. pulsanti interni: arrivano alla sezione giusta
    bad = []
    for target in ('prenota', 'evento', 'dove', 'tessera', 'spazi'):
        goto_y(pg, 0, 300)
        link = pg.query_selector(f'.top-cta[href="#{target}"]') if target == 'prenota' else None
        pg.evaluate(f"document.querySelector('a[href=\"#{target}\"]')&&document.querySelector('a[href=\"#{target}\"]').scrollIntoView&&0")
        pg.evaluate(f"(()=>{{var a=[...document.querySelectorAll('a[href=\"#{target}\"]')].find(x=>x.offsetParent);if(a)a.click()}})()")
        try:
            pg.wait_for_function(f"Math.abs(document.getElementById('{target}').getBoundingClientRect().top)<160", timeout=9000)
        except Exception:
            top = pg.evaluate(f"Math.round(document.getElementById('{target}').getBoundingClientRect().top)")
            bad.append(f'#{target} (resta a {top}px)')
    run.add(dev, 'Pulsanti interni portano alla sezione giusta', not bad, bad)

    # 9. modulo di prenotazione
    goto_y(pg, pg.evaluate("document.getElementById('prenota').offsetTop"), 600)
    pg.click('#wBtn', force=True); pg.wait_for_timeout(300)
    err_vis = pg.evaluate("!document.getElementById('wErr').hidden")
    href_empty = pg.get_attribute('#wBtn', 'href')
    pg.fill('#wName', 'Mario Rossi'); pg.fill('#wCard', '12345')
    pg.select_option('#wDate', index=1); pg.wait_for_timeout(200)
    href = pg.get_attribute('#wBtn', 'href') or ''
    err_gone = pg.evaluate("document.getElementById('wErr').hidden")
    ok = err_vis and href_empty == '#prenota' and ('wa.me/' in href or href.startswith('tel:')) and err_gone
    run.add(dev, 'Prenotazione: vuoto bloccato, compilato apre WhatsApp', ok,
            dict(errore_mostrato=err_vis, link_vuoto=href_empty, link_pieno=href[:60], errore_sparito=err_gone))

    # 10. caroselli e ingrandimento foto
    try:
        goto_y(pg, pg.evaluate("document.getElementById('spazi').offsetTop"), 700)
        cap0 = pg.inner_text('#foto-sala1 .cf-cap')
        pg.click('#foto-sala1 .cf-next'); pg.wait_for_timeout(900)
        cap1 = pg.inner_text('#foto-sala1 .cf-cap')
        box = pg.eval_on_selector('#foto-sala1 .cf-frame', "e=>{var r=e.getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]}")
        pg.mouse.click(box[0], box[1]); pg.wait_for_timeout(700)
        lb_open = pg.evaluate("document.getElementById('lb').classList.contains('on')")
        pg.keyboard.press('Escape'); pg.wait_for_timeout(500)
        lb_closed = pg.evaluate("!document.getElementById('lb').classList.contains('on')")
        run.add(dev, 'Caroselli: freccia avanti, foto ingrandita, chiusura', cap0 != cap1 and lb_open and lb_closed,
                dict(prima=cap0, dopo=cap1, aperta=lb_open, chiusa=lb_closed))
    except Exception as e:
        run.add(dev, 'Caroselli: freccia avanti, foto ingrandita, chiusura', False, str(e)[:150])

    # 11. mappa su richiesta
    goto_y(pg, pg.evaluate("document.getElementById('dove').offsetTop"), 500)
    before = pg.evaluate("document.querySelectorAll('#map iframe').length")
    pg.click('#mapBtn'); pg.wait_for_timeout(500)
    after = pg.evaluate("document.querySelectorAll('#map iframe').length")
    run.add(dev, 'Mappa: si carica solo dopo il tocco', before == 0 and after == 1, dict(prima=before, dopo=after))

    # 12. finale: il filo arriva sul logo
    goto_y(pg, H, 1200)
    lit = pg.evaluate("document.getElementById('finale').classList.contains('lit')")
    run.add(dev, 'In fondo il filo raggiunge il logo e lo accende', lit, '')

    # 13. fluidità durante lo scroll dell'hero (indicativa: browser senza schermo)
    goto_y(pg, 0, 300)
    pg.evaluate(f"(()=>{{var y=0,end={int(sp)};(function s(){{y+=end/90;window.scrollTo(0,y);if(y<end)requestAnimationFrame(s)}})()}})()")
    fr = pg.evaluate(JS_FRAMES, 1500)
    run.add(dev, f'Fluidità hero (p95 {fr["p95"]:.0f} ms per fotogramma)', fr['p95'] < 50, fr)

    # 14. rotazione / ridimensionamento a metà hero
    goto_y(pg, sp * .6, 500)
    pg.set_viewport_size({'width': spec['h'], 'height': spec['w']}); pg.wait_for_timeout(900)
    sp2 = hero_span(pg); goto_y(pg, sp2 * .9, 900)
    st = pg.evaluate(JS_STATE)
    box = pg.evaluate("(()=>{var r=document.getElementById('murG').getBoundingClientRect();return [r.left,r.right,innerWidth]})()")
    ok = st['drawn'] >= st['total'] * .97 and box[0] >= -2 and box[1] <= box[2] + 2 and st['sx'] == 0
    run.add(dev, 'Rotazione schermo a metà hero: murale ricalcolato', ok, dict(stato=st, murale=box))
    th2 = pg.evaluate("(()=>{window.dispatchEvent(new Event('resize'));return 0})()"); pg.wait_for_timeout(600)
    th2 = pg.evaluate(JS_TEXT_HITS)
    run.add(dev, 'Rotazione: il filo resta fuori dalle scritte', not th2, th2)
    if not ok: shot(pg, run, dev, 'dopo_rotazione')

    run.add(dev, 'Nessun errore JS durante tutte le prove', not errs, errs[:3])
    ctx.close()


def test_reduced(b, run):
    ctx = b.new_context(viewport={'width': 393, 'height': 852}, reduced_motion='reduce', is_mobile=True, has_touch=True)
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until='load'); pg.wait_for_timeout(1200)
    vis = pg.evaluate("[...document.querySelectorAll('#ch1,#ch2,#ch3')].map(e=>getComputedStyle(e).opacity)")
    run.add('Movimento ridotto (accessibilità)', 'Pagina usabile senza animazioni', not errs, dict(errori=errs[:2], testi=vis))
    ctx.close()


def main():
    run = Run()
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for dev, spec in DEVICES.items():
            try:
                test_device(b, run, dev, spec)
            except Exception:
                run.add(dev, 'Esecuzione prove', False, traceback.format_exc()[-300:])
        test_reduced(b, run)
        b.close()
    ok = sum(1 for r in run.rows if r[2]); tot = len(run.rows)
    lines = [f'# Stress test Mòrk\'s Place', '', f'URL: {URL}  ', f'Data: {time.strftime("%d/%m/%Y %H:%M")}  ',
             f'Risultato: **{ok}/{tot} prove superate**', '', '| Dispositivo | Prova | Esito | Dettaglio |', '|---|---|---|---|']
    for d, t, o, det in run.rows:
        lines.append(f'| {d} | {t} | {"✅" if o else "❌"} | {"" if o else str(det).replace("|", "/")[:180]} |')
    open(os.path.join(OUT, 'report.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    json.dump([dict(device=d, test=t, ok=o, detail=str(det)) for d, t, o, det in run.rows],
              open(os.path.join(OUT, 'report.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'\n{ok}/{tot} prove superate. Report: {OUT}/report.md')


if __name__ == '__main__':
    main()
