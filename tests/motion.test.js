import test from 'node:test';
import assert from 'node:assert/strict';

let moduleId=0;
async function fixture(){
  const listeners=new Set();
  const media={matches:false,addEventListener:(_,fn)=>listeners.add(fn),removeEventListener:(_,fn)=>listeners.delete(fn)};
  globalThis.matchMedia=()=>media;
  let observer,mutations;
  globalThis.IntersectionObserver=class {
    observed=new Set();
    constructor(callback,options){this.callback=callback;this.options=options;observer=this;}
    observe(element){this.observed.add(element);}
    unobserve(element){this.observed.delete(element);}
    disconnect(){this.observed.clear();}
  };
  globalThis.MutationObserver=class {
    constructor(callback){this.callback=callback;mutations=this;}
    observe(){this.connected=true;}
    disconnect(){this.connected=false;}
  };
  const motion=await import(`../static/js/motion.js?motion-test=${++moduleId}`);
  const calls=[],children=[],events=new Map();
  const root={nodeType:1,matches:()=>false,querySelectorAll:()=>children,
    contains:element=>children.includes(element),
    addEventListener:(name,fn)=>events.set(name,fn),removeEventListener:name=>events.delete(name)};
  function element({hidden=false,focused=false}={}){
    const el={nodeType:1,isConnected:true,ownerDocument:{activeElement:focused?{}:null},
      matches:()=>true,querySelectorAll:()=>[],getClientRects:()=>hidden?[]:[{}],
      contains(target){return target===el.ownerDocument.activeElement;},
      animate(frames,options){
        const animation={cancelled:0,cancel(){this.cancelled++;this.oncancel?.();}};
        calls.push({el,frames,options,animation});return animation;
      }};
    children.push(el);return el;
  }
  return {motion,root,element,calls,children,events,media,
    get observer(){return observer;},get mutations(){return mutations;},
    preference(matches){media.matches=matches;for(const fn of listeners)fn();}};
}

test('stagger uses only transform/opacity, limits the batch and skips hidden/focused content',async()=>{
  const f=await fixture();
  const elements=[f.element({hidden:true}),f.element({focused:true}),...Array.from({length:40},()=>f.element())];
  f.motion.stagger(elements);
  assert.equal(f.calls.length,16);
  assert.deepEqual(f.calls.map(c=>c.options.delay).slice(0,3),[0,45,90]);
  assert.ok(f.calls.every(c=>c.options.delay<=240&&c.options.fill==='backwards'));
  for(const call of f.calls)for(const frame of call.frames)assert.deepEqual(Object.keys(frame).sort(),['opacity','transform']);
  f.motion.finishMotion();
  assert.ok(f.calls.every(c=>c.animation.cancelled===1));
});

test('replacing an animation cancels its predecessor and completion releases it',async()=>{
  const f=await fixture(),el=f.element();
  f.motion.reveal(el);f.motion.reveal(el);
  assert.equal(f.calls[0].animation.cancelled,1);
  f.calls[1].animation.onfinish();f.motion.finishMotion();
  assert.equal(f.calls[1].animation.cancelled,1);
});

test('scroll reveal uses the actual scroll root, reveals once, and tracks replacement rows',async()=>{
  const f=await fixture(),first=f.element(),dispose=f.motion.setupScrollMotion(f.root);
  assert.equal(f.observer.options.root,f.root);
  assert.equal(f.calls.length,0);
  f.observer.callback([{target:first,isIntersecting:false}]);
  assert.equal(f.calls.length,0);
  f.observer.callback([{target:first,isIntersecting:true}]);
  f.observer.callback([{target:first,isIntersecting:true}]);
  assert.equal(f.calls.length,1);
  const row=f.element();f.mutations.callback([{addedNodes:[row]}]);
  assert.ok(f.observer.observed.has(row));
  f.children.splice(f.children.indexOf(row),1);row.isConnected=false;
  f.mutations.callback([{addedNodes:[]}]);
  assert.ok(!f.observer.observed.has(row));
  dispose();assert.equal(f.events.size,0);assert.equal(f.mutations.connected,false);
});

test('live reduced-motion changes cancel animations and observers; disposal ignores queued callbacks',async()=>{
  const f=await fixture(),el=f.element(),dispose=f.motion.setupScrollMotion(f.root);
  f.observer.callback([{target:el,isIntersecting:true}]);
  f.preference(true);
  assert.equal(f.calls[0].animation.cancelled,1);
  assert.equal(f.observer.observed.size,0);assert.equal(f.mutations.connected,false);
  const next=f.element();f.motion.reveal(next);assert.equal(f.calls.length,1);
  f.preference(false);assert.ok(f.observer.observed.has(next));
  dispose();f.observer.callback([{target:next,isIntersecting:true}]);
  assert.equal(f.calls.length,1);
});

test('keyboard focus reveals an animating control immediately',async()=>{
  const f=await fixture(),el=f.element(),dispose=f.motion.setupScrollMotion(f.root);
  f.observer.callback([{target:el,isIntersecting:true}]);
  el.ownerDocument.activeElement={};
  f.events.get('focusin')({target:el.ownerDocument.activeElement});
  assert.equal(f.calls[0].animation.cancelled,1);
  dispose();
});

async function swapFixture(){
  const f=await fixture(),animations=[],commits=[];
  let view='map';
  const elements=Object.fromEntries(['map','table'].map(name=>[name,{
    getClientRects:()=>[{}],
    animate(frames,options){
      let resolve,reject;
      const finished=new Promise((yes,no)=>{resolve=yes;reject=no;});
      const animation={frames,options,finished,finish:resolve,cancel(){this.cancelled=true;reject(new Error('cancelled'));}};
      animations.push(animation);return animation;
    },
  }]));
  const swap=f.motion.createViewSwap({getView:()=>view,getElement:key=>elements[key],commit:target=>{view=target;commits.push(target);}});
  return {...f,swap,animations,commits,get view(){return view;}};
}

test('map/table swap commits between exit and entrance, reversing direction on return',async()=>{
  const f=await swapFixture();
  const toTable=f.swap.toggle();
  assert.equal(f.view,'map');assert.equal(f.animations[0].frames[1].transform,'translate3d(-14px,0,0)');
  f.animations[0].finish();await Promise.resolve();
  assert.equal(f.view,'table');assert.equal(f.animations[1].frames[0].transform,'translate3d(18px,0,0)');
  f.animations[1].finish();await toTable;
  const toMap=f.swap.toggle();
  assert.equal(f.animations[2].frames[1].transform,'translate3d(14px,0,0)');
  f.animations[2].finish();await Promise.resolve();
  assert.equal(f.view,'map');assert.equal(f.animations[3].frames[0].transform,'translate3d(-18px,0,0)');
  f.animations[3].finish();await toMap;
  assert.deepEqual(f.commits,['table','map']);
  assert.ok(f.animations.every(a=>a.cancelled));
  for(const a of f.animations)for(const frame of a.frames)assert.deepEqual(Object.keys(frame).sort(),['opacity','transform']);
  f.swap.destroy();
});

test('rapid toggles and disposal cannot commit an obsolete view',async()=>{
  const f=await swapFixture();
  const first=f.swap.toggle(),second=f.swap.toggle();
  await Promise.all([first,second]);
  assert.equal(f.view,'map');assert.deepEqual(f.commits,[]);
  const third=f.swap.toggle();f.swap.destroy();await third;
  assert.deepEqual(f.commits,[]);
});

test('reduced motion switches immediately and finishes a pending swap exactly once',async()=>{
  const f=await swapFixture();
  const pending=f.swap.toggle();f.preference(true);await pending;
  assert.equal(f.view,'table');assert.deepEqual(f.commits,['table']);
  await f.swap.toggle();assert.equal(f.view,'map');assert.equal(f.animations.length,1);
  f.swap.destroy();
});

test('reversing during entrance cancels it and returns to the requested view',async()=>{
  const f=await swapFixture(),first=f.swap.toggle();
  f.animations[0].finish();await Promise.resolve();
  assert.equal(f.view,'table');
  const reverse=f.swap.toggle();
  assert.ok(f.animations[1].cancelled);
  f.animations[2].finish();await Promise.resolve();
  assert.equal(f.view,'map');
  f.animations[3].finish();await Promise.all([first,reverse]);
  assert.deepEqual(f.commits,['table','map']);f.swap.destroy();
});
