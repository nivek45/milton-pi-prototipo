import {LatestRequest} from './api.js';
import {byId,node,button,text} from './dom.js';

export function setupLocation(selectUF){
 const input=byId('city-search'),results=byId('city-results'),form=byId('city-form');
 const life=new AbortController(),request=new LatestRequest();let timer;
 const close=()=>{clearTimeout(timer);request.cancel();results.replaceChildren();results.hidden=true;};
 function search(){
  close();const q=input.value.trim();
  if(q.length<2){text('city-status','Digite pelo menos 2 letras.');return;}
  text('city-status','Buscando cidades…');
  request.run('/api/localidades?q='+encodeURIComponent(q),data=>{
   if(!Array.isArray(data.items))throw new Error('Resposta de cidades inválida.');
   for(const city of data.items){
    const item=node('li');item.append(button(`${city.nome} — ${city.uf}`,()=>{
     input.value=`${city.nome} — ${city.uf}`;close();selectUF(city.uf,city);
     text('city-status',`${city.nome} selecionada. A tabela mostra os dados disponíveis para a cidade.`);
     byId('city-search').focus();
    },'city-result'));results.append(item);
   }
   results.hidden=!data.items.length;
   text('city-status',data.items.length?`${data.items.length} cidades encontradas${data.items.length===20?' (limite de 20; refine a busca)':''}. Use Tab para escolher.`:'Nenhuma cidade encontrada. Confira o nome ou tente outra grafia.');
  },error=>text('city-status',error.message+' Use Buscar para tentar novamente.'));
 }
 input.addEventListener('input',()=>{close();text('city-status','');if(input.value.trim().length>=2)timer=setTimeout(search,300);},{signal:life.signal});
 form.addEventListener('submit',event=>{event.preventDefault();search();},{signal:life.signal});
 form.addEventListener('keydown',event=>{if(event.key==='Escape'){close();input.focus();text('city-status','Busca fechada.');}},{signal:life.signal});
 return()=>{close();life.abort();};
}

let filterSignature='';
export function renderFilters(state,store,selectUF,changePeriod){
 const month=state.competencia||state.snapshot?.meta.competencia||'sem dados';
 const year=state.ano||state.snapshot?.meta.ano||'sem dados';
 text('period-summary',`${month} · ${year}`);
 const signature=JSON.stringify([state.uf,state.municipio,state.competencia,state.ano]);
 if(signature===filterSignature)return;filterSignature=signature;
 const target=byId('active-filters');target.replaceChildren();
 const add=(label,fn)=>{const btn=button(`${label} ×`,()=>{fn();const focus=byId('global-uf').disabled?byId('more-filters').querySelector('summary'):byId('global-uf');focus.focus();},'filter-chip');btn.setAttribute('aria-label',`Remover filtro: ${label}`);target.append(btn);};
 if(state.uf)add(`Estado: ${state.uf}`,()=>selectUF(''));
 if(state.municipio)add(`Cidade: ${state.municipioName}`,()=>{store.dispatch({type:'municipio',value:'',name:''});byId('global-municipio').value='';byId('city-search').value='';});
 if(state.competencia)add(`Mês: ${state.competencia}`,()=>changePeriod('competencia',''));
 if(state.ano)add(`Ano: ${state.ano}`,()=>changePeriod('ano',''));
}
