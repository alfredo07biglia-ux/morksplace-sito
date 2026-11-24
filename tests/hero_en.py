from playwright.sync_api import sync_playwright
LANGSW=True
LEAD="""(()=>{var p=document.getElementById('murLead'),d=p.getAttribute('d');if(!d)return 'vuota';var L=p.getTotalLength(),hits=new Set(),svg=document.getElementById('murSvg').getBoundingClientRect();
 var g=document.getElementById('murG').getBoundingClientRect();
 var els=[...document.querySelectorAll('#ch3 h2,#ch3 .live,#ch3 a')];
 for(var i=0;i<=800;i++){var q=p.getPointAtLength(L*i/800);var X=q.x+svg.left,Y=q.y+svg.top;els.forEach(function(e){var r=e.getBoundingClientRect();
   if(e.tagName==='H2'){var rg=document.createRange();rg.selectNodeContents(e);r=rg.getBoundingClientRect()}
   if(X>r.left-2&&X<r.right+2&&Y>r.top-2&&Y<r.bottom+2)hits.add(e.textContent.trim().slice(0,24))})}
 var s=p.getPointAtLength(0); var inside=s.x>=g.left-svg.left-2&&s.x<=g.right-svg.left+2&&s.y>=g.top-svg.top-2&&s.y<=g.bottom-svg.top+2;
 var e=p.getPointAtLength(L);
 return {tocca:[...hits],parte_dal_murale:inside,arriva_in_fondo:Math.abs(e.y-svg.height)<6,murale_in_schermo:g.left>=-2&&g.right<=svg.width+2&&g.top>=0}})()"""
def check(pg,tag):
    sp=pg.evaluate("document.getElementById('ingresso').offsetHeight-innerHeight")
    pg.evaluate(f"window.scrollTo(0,{int(sp*.97)})"); pg.wait_for_timeout(700)
    r=pg.evaluate(LEAD); ok=not r['tocca'] and r['parte_dal_murale'] and r['arriva_in_fondo'] and r['murale_in_schermo']
    print(('OK ' if ok else 'ERR'),tag,r)
    return ok
with sync_playwright() as pw:
    b=pw.chromium.launch(); allok=True
    for w,h in ((390,844),(1332,700),(1809,798),(820,1180),(852,393)):
        ctx=b.new_context(viewport={'width':w,'height':h}); pg=ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto('http://localhost:8765/index.html?lang=en',wait_until='load'); pg.wait_for_timeout(1200)
        allok&=check(pg,f'{w}x{h} normale')
        H=pg.evaluate("document.documentElement.scrollHeight"); pg.evaluate(f"window.scrollTo(0,{H})"); pg.wait_for_timeout(500)
        pg.reload(wait_until='load'); pg.wait_for_timeout(1200); allok&=check(pg,f'{w}x{h} ricarica in fondo')
        pg.set_viewport_size({'width':w,'height':h+80}); pg.wait_for_timeout(400); allok&=check(pg,f'{w}x{h} barra telefono nascosta')
        pg.set_viewport_size({'width':w,'height':h}); pg.wait_for_timeout(400)
        pg.evaluate("document.getElementById('liveText').textContent='Apre mercoledì alle 20:30'"); pg.wait_for_timeout(500); allok&=check(pg,f'{w}x{h} testo badge cambiato')
        pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(300)
        for _ in range(40): pg.mouse.wheel(0,600)
        for _ in range(40): pg.mouse.wheel(0,-600)
        pg.wait_for_timeout(1200); allok&=check(pg,f'{w}x{h} scroll violento')
        pg.goto('http://localhost:8765/privacy.html'); pg.go_back(); pg.wait_for_timeout(1200); allok&=check(pg,f'{w}x{h} indietro dalla privacy')
        if errs: print('ERRORI JS',errs); allok=False
        ctx.close()
    print('TUTTO OK' if allok else 'CI SONO PROBLEMI'); b.close()
