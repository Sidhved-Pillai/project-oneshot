"""Local-only invoice viewer: no uploads, external scripts, or image mutations."""
import base64


def invoice_viewer_html(payload, mime_type):
    mime = mime_type if mime_type in {'image/png', 'image/jpeg', 'image/webp', 'image/gif'} else 'image/jpeg'
    url = f'data:{mime};base64,' + base64.b64encode(payload).decode('ascii')
    return '''<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;font:14px system-ui}#viewer{height:510px;background:#eef2f7;border-radius:14px;overflow:hidden;display:flex;flex-direction:column}
#viewer:fullscreen{height:100vh;width:100vw;border-radius:0}nav{display:flex;gap:7px;align-items:center;padding:9px;background:#fff;flex-wrap:wrap}
button{border:1px solid #d5dce6;border-radius:20px;padding:8px 12px;background:#fff;cursor:pointer;font-size:16px}button:focus{outline:2px solid #0071e3}
#stage{flex:1;min-height:0;overflow:hidden;position:relative;touch-action:none;cursor:grab}#stage:active{cursor:grabbing}
img{position:absolute;left:50%;top:50%;max-width:100%;max-height:100%;object-fit:contain;user-select:none;-webkit-user-drag:none;transform-origin:center}
small{padding:6px 10px;background:#fff;color:#586170}
</style></head><body><section id="viewer" aria-label="Invoice image viewer">
<nav aria-label="Image controls"><button id="out" title="Zoom out" aria-label="Zoom out">−</button><button id="in" title="Zoom in" aria-label="Zoom in">+</button>
<button id="rotate" title="Rotate clockwise" aria-label="Rotate clockwise">↻</button><button id="reset">Fit</button><button id="full">Full screen</button><span id="level">100%</span></nav>
<div id="stage"><img src="IMAGE_DATA" alt="Invoice evidence" draggable="false"></div><small>Click image for full screen · Zoom with +/−, scroll or pinch · Drag to pan · Esc to exit</small></section>
<script>
const viewer=document.querySelector('#viewer'),stage=document.querySelector('#stage'),img=document.querySelector('img');
let scale=1,rotation=0,x=0,y=0,moved=false;const pointers=new Map();
function paint(){img.style.transform=`translate(-50%,-50%) translate(${x}px,${y}px) rotate(${rotation}deg) scale(${scale})`;document.querySelector('#level').textContent=Math.round(scale*100)+'%'}
function zoom(factor){scale=Math.max(.25,Math.min(8,scale*factor));paint()}
async function fullscreen(){try{if(!document.fullscreenElement&&viewer.requestFullscreen)await viewer.requestFullscreen();else if(document.fullscreenElement)await document.exitFullscreen()}catch(e){}}
document.querySelector('#in').onclick=()=>zoom(1.25);document.querySelector('#out').onclick=()=>zoom(.8);
document.querySelector('#rotate').onclick=()=>{rotation=(rotation+90)%360;paint()};document.querySelector('#reset').onclick=()=>{scale=1;rotation=0;x=0;y=0;paint()};document.querySelector('#full').onclick=fullscreen;
stage.addEventListener('wheel',e=>{e.preventDefault();zoom(e.deltaY<0?1.12:1/1.12)},{passive:false});
stage.onpointerdown=e=>{pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});stage.setPointerCapture(e.pointerId);moved=false};
stage.onpointermove=e=>{if(!pointers.has(e.pointerId))return;const old=pointers.get(e.pointerId),next={x:e.clientX,y:e.clientY};
if(Math.abs(next.x-old.x)+Math.abs(next.y-old.y)>2)moved=true;
if(pointers.size===2){const other=[...pointers.entries()].find(([id])=>id!==e.pointerId)[1];const before=Math.hypot(old.x-other.x,old.y-other.y),after=Math.hypot(next.x-other.x,next.y-other.y);if(before>0)zoom(after/before)}else{x+=next.x-old.x;y+=next.y-old.y;paint()}
pointers.set(e.pointerId,next)};
stage.onpointerup=e=>{const click=!moved&&pointers.size===1;pointers.delete(e.pointerId);if(click)fullscreen()};stage.onpointercancel=e=>pointers.delete(e.pointerId);
paint();
</script></body></html>'''.replace('IMAGE_DATA', url)
