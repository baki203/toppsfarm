"""Fingerprint-Engine: deterministisches Canvas-/WebGL-/Audio-Noise aus einem Seed."""
from __future__ import annotations


def fingerprint_init_script(seed: int) -> str:
    """Liefert ein JS-Init-Script, das per add_init_script vor jedem Seitencode laeuft.
    Aus dem Seed wird ein deterministischer PRNG erzeugt, dessen Werte die
    Canvas-, WebGL- und Audio-Fingerprints leicht, aber reproduzierbar verrauschen."""
    return (
        "(()=>{"
        f"const _seed={int(seed)&0x7fffffff};"
        "let _s=_seed;"
        "const _rnd=()=>{_s=(_s+0x6D2B79F5)|0;let t=Math.imul(_s^(_s>>>15),1|_s);"
        "t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};"
        "const _noise=(d)=>d+((_rnd()-0.5)*(_rnd()*0.0008+0.0002));"
        "const _hash=()=>Math.floor(_rnd()*10000);"
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        "window.chrome=window.chrome||{runtime:{}};"
        "const _gctx=HTMLCanvasElement.prototype.getContext;"
        "HTMLCanvasElement.prototype.getContext=function(type,...a){"
        "const ctx=_gctx.apply(this,[type,...a]);"
        "if(ctx&&ctx.fillText){const pf=ctx.fillText.bind(ctx);"
        "ctx.fillText=function(t,x,y,...r){pf(t,x+_noise(0.2),y+_noise(0.2),...r);};}"
        "return ctx;};"
        "const _gl=WebGLRenderingContext.prototype.getParameter;"
        "WebGLRenderingContext.prototype.getParameter=function(p){"
        "const v=_gl.apply(this,arguments);"
        "if(typeof v==='number'&&Number.isFinite(v)){return _noise(v);}"
        "if(v&&typeof v==='object'){try{return v.slice().map(n=>"
        "typeof n==='number'?Number.isFinite(n)?_noise(n):n:n);}catch(e){}}"
        "return v;};"
        "const _nosc=OscillatorNode.prototype.getFrequency;"
        "if(_nosc){OscillatorNode.prototype.getFrequency=function(){"
        "return _noise(_nosc.apply(this,arguments));};}"
        # UA als Basis-Beispiel (wird vom Browser fuer locale/tz korrigiert)
        "const _fp={seed:_seed,noiseHash:_hash()};"
        "Object.defineProperty(window,'__baki_fp__',{value:_fp});"
        "})();"
    )


async def apply(page, seed: int) -> None:
    """Registriert das Fingerprint-Init-Script. `page` darf eine Seite (Playwright
    Page) oder ein Kontext (BrowserContext, wie von launch_persistent_context)
    sein."""
    ctx = page if hasattr(page, "add_init_script") else page.context
    await ctx.add_init_script(fingerprint_init_script(seed))