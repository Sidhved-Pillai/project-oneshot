/* Mouse and keyboard scroll controls; all interaction stays in the browser. */
window.installReportScrollbars = function(host, scroller) {
  if (host.__reportScrollbars?.scroller === scroller) return;
  host.__reportScrollbars?.destroy();
  const doc=host.ownerDocument, win=doc.defaultView;
  const cleanup=[], bars=[];
  function listen(el,type,fn,options){el.addEventListener(type,fn,options);cleanup.push(()=>el.removeEventListener(type,fn,options))}
  for (const axis of ['x','y']) {
    const horizontal=axis==='x', bar=doc.createElement('div');
    bar.className='report-scrollbar '+(horizontal?'horizontal':'vertical');
    const back=doc.createElement('button'), track=doc.createElement('div'), thumb=doc.createElement('div'), next=doc.createElement('button');
    back.type=next.type='button';back.textContent=horizontal?'‹':'⌃';next.textContent=horizontal?'›':'⌄';
    back.setAttribute('aria-label',horizontal?'Scroll table left':'Scroll table up');next.setAttribute('aria-label',horizontal?'Scroll table right':'Scroll table down');
    track.className='report-scroll-track';thumb.className='report-scroll-thumb';thumb.tabIndex=0;
    thumb.setAttribute('role','scrollbar');thumb.setAttribute('aria-label',horizontal?'Table horizontal scroll':'Table vertical scroll');thumb.setAttribute('aria-orientation',horizontal?'horizontal':'vertical');
    thumb.setAttribute('aria-valuemin','0');track.append(thumb);bar.append(back,track,next);host.append(bar);bars.push(bar);
    const pos=()=>horizontal?scroller.scrollLeft:scroller.scrollTop;
    const viewport=()=>horizontal?scroller.clientWidth:scroller.clientHeight;
    const total=()=>horizontal?scroller.scrollWidth:scroller.scrollHeight;
    const length=()=>horizontal?track.clientWidth:track.clientHeight;
    const max=()=>Math.max(0,total()-viewport());
    const move=value=>{if(horizontal)scroller.scrollLeft=value;else scroller.scrollTop=value};
    const size=()=>Math.min(length(),Math.max(28,length()*viewport()/Math.max(total(),1)));
    function sync(){const overflow=max()>1,s=size(),offset=overflow?(length()-s)*pos()/max():0;
      thumb.style[horizontal?'width':'height']=s+'px';thumb.style.transform=horizontal?'translateX('+offset+'px)':'translateY('+offset+'px)';
      thumb.hidden=!overflow;back.disabled=next.disabled=!overflow;thumb.tabIndex=overflow?0:-1;
      thumb.setAttribute('aria-valuemax',String(max()));thumb.setAttribute('aria-valuenow',String(Math.round(pos())));
    }
    listen(back,'click',()=>move(pos()-60));listen(next,'click',()=>move(pos()+60));
    listen(track,'pointerdown',e=>{if(e.target!==track)return;const r=track.getBoundingClientRect(),point=horizontal?e.clientX-r.left:e.clientY-r.top;move(pos()+(point<(length()-size())*pos()/Math.max(max(),1)?-viewport():viewport())*.85)});
    listen(thumb,'pointerdown',e=>{e.preventDefault();const start=horizontal?e.clientX:e.clientY,origin=pos();thumb.setPointerCapture(e.pointerId);
      const drag=ev=>move(origin+((horizontal?ev.clientX:ev.clientY)-start)*max()/Math.max(1,length()-size()));
      const stop=()=>{thumb.removeEventListener('pointermove',drag);thumb.removeEventListener('lostpointercapture',stop)};
      thumb.addEventListener('pointermove',drag);thumb.addEventListener('lostpointercapture',stop);
    });
    listen(thumb,'keydown',e=>{let value;if(['ArrowLeft','ArrowUp'].includes(e.key))value=pos()-40;else if(['ArrowRight','ArrowDown'].includes(e.key))value=pos()+40;else if(e.key==='Home')value=0;else if(e.key==='End')value=max();else if(e.key==='PageDown')value=pos()+viewport();else if(e.key==='PageUp')value=pos()-viewport();if(value!==undefined){e.preventDefault();move(value)}});
    listen(scroller,'scroll',sync,{passive:true});listen(win,'resize',sync);
    const observer=new win.ResizeObserver(sync);observer.observe(scroller);observer.observe(track);if(scroller.firstElementChild)observer.observe(scroller.firstElementChild);cleanup.push(()=>observer.disconnect());sync();
  }
  host.__reportScrollbars={scroller,destroy(){cleanup.forEach(fn=>fn());bars.forEach(bar=>bar.remove())}};
};
