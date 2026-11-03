// Native, compositor-only motion. Content is visible without JS or observers.
const active=new Map();
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const easing='cubic-bezier(.22,1,.36,1)';
const targets=[
  '.location-eyebrow','.location-start h1','.location-start p','#city-form',
  '.page-head','.map-controls','.layer-pill-btn','.map-legend','.map-breadcrumb',
  '.card-panel','.metric-card','.stat-tile','.persona-context-card',
  '.persona-shortcuts > *','.data-table tbody tr','#city-results li',
].join(',');

function canReveal(element){
  if(reduced.matches||!element?.animate||!element.getClientRects().length)return false;
  const focused=element.ownerDocument?.activeElement;
  return !focused||!element.contains(focused);
}
function play(element,offset,delay,duration){
  active.get(element)?.cancel();
  const animation=element.animate([
    {opacity:0,transform:`translate3d(0,${offset}px,0)`},
    {opacity:1,transform:'translate3d(0,0,0)'},
  ],{duration,delay,easing,fill:'backwards'});
  active.set(element,animation);
  const release=()=>{if(active.get(element)===animation)active.delete(element);};
  animation.onfinish=()=>{release();animation.cancel();};
  animation.oncancel=release;
  return animation;
}
export function reveal(element,offset=12){
  if(canReveal(element))return play(element,offset,0,420);
}
export function stagger(elements,{offset=12,step=45,duration=420}={}){
  // Read visibility before starting any animations. Large tables stay responsive.
  const visible=Array.from(elements).filter(canReveal).slice(0,16);
  return visible.map((element,index)=>play(element,offset,Math.min(index*step,240),duration));
}
export function finishMotion(){
  for(const animation of active.values())animation.cancel();
  active.clear();
}
reduced.addEventListener('change',()=>{if(reduced.matches)finishMotion();});

// A short exit, then an entrance in the opposite direction. State changes only
// once, between phases; cancelling an older request cannot commit a stale view.
export function createViewSwap({getView,getElement,commit}){
  let current=null,disposed=false;
  function cancel(){
    const job=current;current=null;
    job?.animation?.cancel();
  }
  function finishImmediately(){
    const target=current?.target;
    cancel();
    if(target&&getView()!==target)commit(target);
  }
  const preferenceChanged=()=>{if(reduced.matches)finishImmediately();};
  reduced.addEventListener('change',preferenceChanged);
  async function toggle(){
    if(disposed)return;
    const target=(current?.target||getView())==='map'?'table':'map';
    cancel();
    if(target===getView())return;
    const outgoing=getElement(getView());
    if(reduced.matches||!outgoing?.animate||!outgoing.getClientRects().length){commit(target);return;}
    const direction=target==='table'?1:-1;
    const job=current={target,animation:outgoing.animate([
      {opacity:1,transform:'translate3d(0,0,0)'},
      {opacity:0,transform:`translate3d(${-direction*14}px,0,0)`},
    ],{duration:150,easing:'cubic-bezier(.4,0,1,1)',fill:'forwards'})};
    try{await job.animation.finished;}catch{}
    if(current!==job)return;
    commit(target);
    job.animation.cancel();
    if(current!==job)return;
    const incoming=getElement(target);
    if(reduced.matches||!incoming?.animate||!incoming.getClientRects().length){cancel();return;}
    job.animation=incoming.animate([
      {opacity:0,transform:`translate3d(${direction*18}px,0,0)`},
      {opacity:1,transform:'translate3d(0,0,0)'},
    ],{duration:300,easing,fill:'backwards'});
    try{await job.animation.finished;}catch{}
    if(current===job)cancel();
  }
  return {toggle,cancel,destroy(){disposed=true;cancel();reduced.removeEventListener('change',preferenceChanged);}};
}

export function setupScrollMotion(root){
  if(!root||!globalThis.IntersectionObserver||!globalThis.MutationObserver)return ()=>{};
  const seen=new WeakSet(),pending=new Set();
  let disposed=false;
  const observer=new IntersectionObserver(entries=>{
    if(disposed||reduced.matches)return;
    const entering=entries.filter(entry=>entry.isIntersecting&&pending.has(entry.target));
    for(const {target} of entering){seen.add(target);pending.delete(target);observer.unobserve(target);}
    stagger(entering.map(entry=>entry.target));
  },{root,threshold:0.08,rootMargin:'0px 0px -16px 0px'});

  function scan(node){
    if(node.nodeType!==1)return;
    const candidates=[...(node.matches(targets)?[node]:[]),...node.querySelectorAll(targets)];
    for(const element of candidates){
      if(!seen.has(element)&&!pending.has(element)){
        pending.add(element);observer.observe(element);
      }
    }
  }
  const mutations=new MutationObserver(records=>{
    if(disposed||reduced.matches)return;
    for(const record of records)for(const node of record.addedNodes)scan(node);
    // Release replaced rows/cards instead of retaining detached DOM nodes.
    for(const element of pending)if(!root.contains(element)){observer.unobserve(element);pending.delete(element);}
    for(const [element,animation] of active)if(!element.isConnected){animation.cancel();active.delete(element);}
  });
  function syncPreference(){
    observer.disconnect();mutations.disconnect();pending.clear();
    if(disposed||reduced.matches)return;
    scan(root);mutations.observe(root,{childList:true,subtree:true});
  }
  function onFocus(event){
    // Keyboard users never have to wait for a focused control to become visible.
    for(const [element,animation] of active)if(element.contains(event.target))animation.cancel();
  }
  root.addEventListener('focusin',onFocus);
  reduced.addEventListener('change',syncPreference);
  syncPreference();
  return()=>{
    disposed=true;observer.disconnect();mutations.disconnect();pending.clear();
    root.removeEventListener('focusin',onFocus);
    reduced.removeEventListener('change',syncPreference);
    finishMotion();
  };
}
