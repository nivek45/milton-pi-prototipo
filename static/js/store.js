import {PERSONAS} from './config.js';
export function initialState(storage) {
  let persona='pessoa_comum',metric='cob_plano';
  try {
    const saved=storage?.getItem('miltonPersona');
    if (Object.hasOwn(PERSONAS,saved)) persona=saved;
    const chosen=storage?.getItem('miltonMetric');
    metric=PERSONAS[persona].layers.includes(chosen)?chosen:PERSONAS[persona].layers[0];
  } catch { /* Storage is optional, never a data source. */ }
  return {persona,metric,page:'map',view:'map',uf:'',municipio:'',municipioName:'',competencia:'',ano:'',snapshot:null,status:'loading',error:'',revision:0};
}
export function reduce(state,action) {
  switch(action.type) {
    case 'persona': {
      if (!Object.hasOwn(PERSONAS,action.value)) return state;
      const p=PERSONAS[action.value];
      return {...state,persona:action.value,metric:p.layers[0],page:p.pages.includes(state.page)?state.page:'map'};
    }
    case 'metric': return PERSONAS[state.persona].layers.includes(action.value)?{...state,metric:action.value}:state;
    case 'page': return PERSONAS[state.persona].pages.includes(action.value)?{...state,page:action.value}:state;
    case 'view': return {...state,view:action.value || (state.view==='map'?'table':'map')};
    case 'locality': return {...state,uf:action.uf,municipio:action.code,municipioName:action.name,page:'map',view:'table'};
    case 'uf': return {...state,uf:action.value,municipio:'',municipioName:''};
    case 'municipio': return state.uf?{...state,municipio:action.value,municipioName:action.name||'',view:action.value?'table':state.view}:state;
    case 'period': return {...state,[action.key]:action.value};
    case 'loading': return {...state,status:'loading',error:'',snapshot:null};
    case 'snapshot': return {...state,snapshot:action.value,status:'ready',error:'',revision:state.revision+1};
    case 'error': return {...state,status:'error',error:action.value,snapshot:null};
    default:return state;
  }
}
export function createStore(storage) {
  let state=initialState(storage);
  const listeners=new Set();
  return {get:()=>state,subscribe(fn){listeners.add(fn);return()=>listeners.delete(fn);},dispatch(action){
    const previous=state; state=reduce(state,action);
    if(previous===state)return;
    if(action.type==='persona'||action.type==='metric')try{storage?.setItem('miltonPersona',state.persona);storage?.setItem('miltonMetric',state.metric);}catch{}
    for(const listener of listeners)listener(state,previous,action);
  }};
}
