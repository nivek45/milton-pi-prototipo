const active=new Map();
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
export function reveal(element,offset=5) {
  if(!element)return;
  active.get(element)?.cancel();active.delete(element);
  if(reduced.matches||!element.animate||!element.getClientRects().length)return;
  const animation=element.animate([{opacity:.55,transform:`translateY(${offset}px)`},{opacity:1,transform:'translateY(0)'}],{duration:220,easing:'cubic-bezier(.22,1,.36,1)'});
  active.set(element,animation);
  const release=()=>{if(active.get(element)===animation)active.delete(element);};
  animation.onfinish=release;animation.oncancel=release;
}
export function finishMotion(){for(const animation of active.values())animation.cancel();active.clear();}
reduced.addEventListener('change',()=>{if(reduced.matches)finishMotion();});
