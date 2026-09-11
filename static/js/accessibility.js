export function setupDrawer(){
 const sidebar=document.getElementById('sidebar'),backdrop=document.getElementById('sidebar-backdrop');
 const trigger=document.querySelector('.mobile-toggle'),main=document.querySelector('main'),header=document.querySelector('header');
 const mobile=matchMedia('(max-width:900px)'),life=new AbortController();let open=false;
 const close=document.createElement('button');close.type='button';close.className='drawer-close';close.textContent='Fechar menu';sidebar.prepend(close);
 function toggle(value=!open){
  const wasOpen=open;open=mobile.matches&&value;
  sidebar.classList.toggle('open',open);backdrop.classList.toggle('active',open);
  sidebar.inert=mobile.matches&&!open;sidebar.setAttribute('aria-hidden',String(mobile.matches&&!open));
  trigger.setAttribute('aria-expanded',String(open));trigger.setAttribute('aria-label',open?'Fechar menu':'Abrir menu');
  main.inert=open;header.inert=open;
  document.getElementById('pip-card').inert=open;
  if(open)close.focus();else if(wasOpen&&mobile.matches)trigger.focus();
 }
 close.addEventListener('click',()=>toggle(false),{signal:life.signal});
 backdrop.addEventListener('click',()=>toggle(false),{signal:life.signal});
 sidebar.addEventListener('keydown',event=>{
  if(!open||event.key!=='Tab')return;
  const elements=[...sidebar.querySelectorAll('button,a,[tabindex="0"]')].filter(el=>!el.disabled&&el.getClientRects().length);
  const first=elements[0],last=elements.at(-1);
  if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
  else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
 },{signal:life.signal});
 mobile.addEventListener('change',()=>toggle(false),{signal:life.signal});toggle(false);
 return{toggle,destroy:()=>life.abort()};
}
