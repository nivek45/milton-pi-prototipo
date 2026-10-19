export const byId=id=>document.getElementById(id);
export function node(tag,text='',className='') {
  const element=document.createElement(tag);element.textContent=text;
  if(className)element.className=className;return element;
}
export function button(text,fn,className='seg-btn') {
  const el=node('button',text,className);el.type='button';el.addEventListener('click',fn);return el;
}
export function text(id,value){const el=byId(id);if(el&&el.textContent!==String(value))el.textContent=value;}
export function options(select,items,placeholder,value) {
  const list=[new Option(placeholder,'')];
  for(const [key,label] of items)list.push(new Option(label,key));
  select.replaceChildren(...list);select.value=value||'';
}
