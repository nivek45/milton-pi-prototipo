import {setupDrawer} from './accessibility.js';
import {reveal,finishMotion} from './motion.js';
import {setupLocation,renderFilters} from './location.js';
import {PERSONAS,METRICS,TABLES,number} from './config.js';
import {createStore} from './store.js';
import {LatestRequest,queryString,validateSnapshot} from './api.js';
import {byId,node,button,text,options} from './dom.js';
import {BrazilMap} from './map.js';
import {DataTable} from './table.js';
import {renderPanel,renderInsights,renderPip,Charts} from './panels.js';

let storage;try{storage=window.localStorage;}catch{}
const store=createStore(storage),snapshotRequest=new LatestRequest(),municipalityRequest=new LatestRequest(),statsRequest=new LatestRequest();
const life=new AbortController(),charts=new Charts(),tables=new Map(),searches=new Map();
const map=new BrazilMap(uf=>selectUF(uf));
let searchTimer=0;
function chartRows(kind,rows){
  if(kind==='mkt')charts.show('chart-market',rows,'nm','ben','Beneficiários — página exibida');
  if(kind==='sd'){
    charts.show('chart-idh',rows,'m','idh','IDH — página exibida');
    charts.show('chart-cob',rows,'m','cob','Cobertura (%) — página exibida');
  }
}
for(const kind of ['mkt','op','pl','sd'])tables.set(kind,new DataTable(byId('table-'+kind),chartRows));
tables.set('swap',new DataTable(byId('swap-data-table').parentElement));

function loadSnapshot(){
  store.dispatch({type:'loading'});
  const state=store.get();
  snapshotRequest.run('/api/snapshot?'+queryString(state,{uf:'',municipio:''}),data=>{
    store.dispatch({type:'snapshot',value:validateSnapshot(data)});
  },error=>store.dispatch({type:'error',value:error.message}));
}
function selectUF(uf,city=null){
  if(!city){byId('city-search').value='';text('city-status','');}
  if(city)store.dispatch({type:'locality',uf,code:city.codigo_ibge,name:city.nome});
  else store.dispatch({type:'uf',value:uf});
  const select=byId('global-municipio');select.disabled=true;
  options(select,[],uf?'Carregando municípios…':'Selecione um estado','');
  municipalityRequest.cancel();
  if(!uf)return;
  municipalityRequest.run('/api/municipios?uf='+encodeURIComponent(uf),data=>{
    if(!Array.isArray(data.items))throw new Error('Lista de municípios inválida.');
    options(select,data.items.map(m=>[m.codigo_ibge,m.nome]),'Todas as cidades',store.get().municipio);select.disabled=false;
  },error=>{options(select,[],'Falha ao carregar municípios','');text('scope-message',error.message);});
}
function toggleSidebar(force){
  drawer.toggle(force);
}
function switchPage(page){store.dispatch({type:'page',value:page});toggleSidebar(false);const title=document.querySelector('.page.active h2');title?.setAttribute('tabindex','-1');title?.focus({preventScroll:true});}
function changePeriod(key,value){store.dispatch({type:'period',key,value});loadSnapshot();}
function filter(kind,value){
  clearTimeout(searchTimer);searchTimer=setTimeout(()=>{
    searches.set(kind==='swap'?'swap-'+store.get().persona:kind,value);renderActiveTable(store.get());
  },180);
}
function renderActiveTable(state){
  const active=state.page==='map'&&state.view==='table'?'swap':TABLES[state.page]?state.page:null;
  // A hidden table has no active request; it will be fetched when shown again.
  for(const[key,table]of tables){if(key!==active)table.suspend();}
  if(!active)return;
  const kind=active==='swap'?PERSONAS[state.persona].table:active;
  if(state.status!=='ready'){tables.get(active).clear(state.status==='error'?state.error:'Carregando a base…');return;}
  const effective={...state,competencia:state.competencia||state.snapshot.meta.competencia||'',ano:state.ano||state.snapshot.meta.ano||''};
  tables.get(active).update(effective,kind,searches.get(active==='swap'?'swap-'+state.persona:active)||'');
  if(active==='swap'){
    text('swap-table-title',TABLES[kind].title);
    text('swap-table-subtitle','Filtro territorial por atuação/abrangência; dados consultados diretamente na API.');
    text('swap-table-count','Use os controles de paginação abaixo da tabela.');
    text('swap-table-persona-tag',PERSONAS[state.persona].label);
    text('swap-geo-banner',state.municipio?`Município selecionado: ${state.municipioName} (IBGE ${state.municipio}).`:'Selecione um estado e um município para restringir a consulta. Aproximar o mapa não altera o escopo.');
  }
}
function renderStats(){
  byId('overview-metrics').replaceChildren();
  charts.show('chart-doughnut',[],'tabela','linhas','Contagens exatas — todos os períodos');
  text('overview-bars','Carregando contagens…');
  statsRequest.run('/api/stats',data=>{
    const cards=byId('overview-metrics');cards.replaceChildren();const bars=byId('overview-bars');bars.replaceChildren();
    const labels={produto_saude:'Planos ativos',operadora:'Operadoras cadastradas',municipio:'Municípios cadastrados',market_share:'Registros mensais',perfil_saude_publica:'Perfis anuais',estado:'UFs cadastradas'};
    for(const row of data.items){const card=node('div','','metric-card');card.append(node('div',labels[row.tabela]||row.tabela),node('strong',number(row.linhas)));cards.append(card);bars.append(node('p',`${labels[row.tabela]||row.tabela}: ${number(row.linhas)}`));}
    text('footer-time','Consulta ao banco: '+new Date().toLocaleString('pt-BR'));
    charts.show('chart-doughnut',data.items,'tabela','linhas','Contagens exatas — todos os períodos');
  },error=>text('overview-bars',error.message));
}
function render(state,previous={},action={}){
  const persona=PERSONAS[state.persona];
  const previousView=previous.page+'-'+previous.view,currentView=state.page+'-'+state.view;
  const focused=document.activeElement;
  if(previous.page&&previousView!==currentView)scrollPositions.set(previousView,document.querySelector('main').scrollTop);
  document.body.dataset.loadState=state.status;
  byId('persona-selector').style.setProperty('--persona-index',Object.keys(PERSONAS).indexOf(state.persona));
  document.querySelectorAll('.persona-btn').forEach(el=>{const active=el.dataset.persona===state.persona;el.classList.toggle('active',active);el.setAttribute('aria-pressed',String(active));});
  text('persona-badge-name',persona.label);text('persona-badge-desc',persona.description);
  text('map-page-heading',persona.heading);text('map-page-subheading',persona.description);
  document.querySelectorAll('.nav-link').forEach(el=>{
    const page=el.dataset.arg;el.style.display=persona.pages.includes(page)?'flex':'none';el.classList.toggle('active',page===state.page);
    el.setAttribute('aria-current',page===state.page?'page':'false');
  });
  document.querySelectorAll('.page').forEach(el=>el.classList.toggle('active',el.id==='page-'+state.page));
  byId('map-layout-el').style.display=state.view==='map'?'':'none';
  byId('swap-table-container').style.display=state.view==='table'?'block':'none';
  text('swap-view-label',state.view==='map'?'Ver tabela':'Ver mapa');
  if(previous.persona!==state.persona){
    byId('layer-pills-container').replaceChildren(...persona.layers.map(key=>{
      const btn=button(METRICS[key].label,()=>store.dispatch({type:'metric',value:key}),'layer-pill-btn'+(key===state.metric?' active':''));
      btn.dataset.metric=key;btn.setAttribute('aria-pressed',String(key===state.metric));return btn;
    }));
  }
  document.querySelectorAll('[data-metric]').forEach(btn=>{const selected=btn.dataset.metric===state.metric;btn.classList.toggle('active',selected);btn.setAttribute('aria-pressed',String(selected));});
  if(state.snapshot && previous.snapshot!==state.snapshot){
    const states=state.snapshot.states.map(s=>[s.uf,`${s.uf} — ${s.nome}`]);
    for(const id of ['global-uf','swap-uf-filter'])options(byId(id),states,'Todos os estados',state.uf);
    options(byId('global-competencia'),state.snapshot.meta.periods.map(p=>[p,p]),'Último com dados',state.competencia);
    options(byId('global-ano'),state.snapshot.meta.years.map(y=>[y,y]),'Último com dados',state.ano);
  }
  byId('global-uf').value=state.uf;byId('swap-uf-filter').value=state.uf;
  byId('global-uf').disabled=state.status!=='ready';byId('swap-uf-filter').disabled=state.status!=='ready';
  text('scope-message',state.municipio?'A cidade selecionada filtra a tabela. O mapa mostra o estado.':'O estado filtra onde os planos atendem, não o endereço da operadora.');
  const status=state.status==='loading'?'Carregando dados':state.status==='error'?'Dados indisponíveis':state.snapshot.meta.synthetic?'Base de demonstração / mista':'Base consultada';
  text('status-text',status);
  text('data-status',state.status==='error'?state.error:state.status==='loading'?'Consultando o banco…':
    `${state.snapshot.meta.synthetic?'DEMONSTRAÇÃO: esta base contém dados sintéticos. ':''}Beneficiários: ${state.snapshot.meta.competencia||'sem dados'} · Perfil: ${state.snapshot.meta.ano||'sem dados'}. Camadas sem fonte cadastrada são exibidas como indisponíveis.`);
  byId('reload-data').disabled=state.status==='loading';
  const contentChanged=['persona','metric','uf','municipio','status','snapshot'].some(key=>state[key]!==previous[key]);
  if(contentChanged){renderPanel(state,shortcut);renderInsights(state);map.update(state);reveal(byId('panel-content'));}
  renderPip(state);renderActiveTable(state);renderFilters(state,store,selectUF,changePeriod);
  if(previous.page!==state.page||previous.view!==state.view||previous.persona!==state.persona){
    reveal(byId(state.page==='map'?(state.view==='map'?'map-layout-el':'swap-table-container'):'page-'+state.page));
  }
  if(['persona','metric','uf','locality','municipio','view'].includes(action.type)){
    text('interaction-status',`${persona.label}. ${state.municipioName||state.uf||'Brasil'}. ${METRICS[state.metric].label}. ${state.view==='map'?'Mapa estadual':'Tabela de dados'}.`);
  }
  if(previous.page&&previousView!==currentView){
    document.querySelector('main').scrollTop=scrollPositions.get(currentView)||0;
    if(focused&&!focused.getClientRects().length){const title=byId(state.view==='table'&&state.page==='map'?'swap-table-title':'map-page-heading');title?.setAttribute('tabindex','-1');title?.focus({preventScroll:true});}
  }
  if(state.page==='ov'&&(previous.page!=='ov'||previous.revision!==state.revision))renderStats();
  if(state.page!=='ov')statsRequest.cancel();
  if(state.view==='map'&&(previous.view!=='map'||previous.page!==state.page))requestAnimationFrame(()=>map.resize());
}

const drawer=setupDrawer();
byId('sidebar-backdrop').removeAttribute('data-action');
const scrollPositions=new Map();
const actions={
  setPersona:(_,arg)=>{clearTimeout(searchTimer);searches.set('swap-'+store.get().persona,byId('swap-search-input').value);byId('swap-search-input').value=searches.get('swap-'+arg)||'';store.dispatch({type:'persona',value:arg});},
  switchPage:(_,arg)=>switchPage(arg),toggleSidebar:()=>toggleSidebar(),
  swapView:()=>store.dispatch({type:'view'}),handlePipClick:()=>store.dispatch({type:'view'}),
  zoomMap:(_,arg)=>map.zoomBy(Number(arg)),resetMap:()=>{selectUF('');map.focus('');},
  onSwapUFFilterChange:event=>selectUF(event.target.value),
  filterSwapTable:event=>filter('swap',event.target.value),filterTable:(event,arg)=>filter(arg,event.target.value),
};
for(const el of document.querySelectorAll('[data-action]')){
  const fn=actions[el.dataset.action];if(!fn)continue;
  el.addEventListener(el.dataset.event||'click',event=>fn(event,el.dataset.arg),{signal:life.signal});
  if(el.tagName==='DIV'&&!el.matches('input,select')){el.setAttribute('role','button');el.tabIndex=0;el.addEventListener('keydown',event=>{
    if(event.key==='Enter'||event.key===' '){event.preventDefault();fn(event,el.dataset.arg);}
  },{signal:life.signal});}
}
byId('global-uf').addEventListener('change',event=>selectUF(event.target.value),{signal:life.signal});
byId('global-municipio').addEventListener('change',event=>store.dispatch({type:'municipio',value:event.target.value,name:event.target.selectedOptions[0]?.text||''}),{signal:life.signal});
byId('global-competencia').addEventListener('change',event=>changePeriod('competencia',event.target.value),{signal:life.signal});
byId('global-ano').addEventListener('change',event=>changePeriod('ano',event.target.value),{signal:life.signal});
byId('reload-data').addEventListener('click',loadSnapshot,{signal:life.signal});
document.addEventListener('keydown',event=>{if(event.key==='Escape'){toggleSidebar(false);map.hideTooltip();}},{signal:life.signal});
const disposeLocation=setupLocation(selectUF);
function shortcut(target){
 if(target==='table'){store.dispatch({type:'page',value:'map'});store.dispatch({type:'view',value:'table'});}
 else switchPage(target);
 const heading=document.querySelector('.page.active h2, .page.active h3');heading?.setAttribute('tabindex','-1');heading?.focus({preventScroll:true});
}
const unsubscribe=store.subscribe(render);render(store.get());map.load();loadSnapshot();
window.addEventListener('pagehide',event=>{
  if(event.persisted)return;
  finishMotion();disposeLocation();drawer.destroy();life.abort();unsubscribe();clearTimeout(searchTimer);snapshotRequest.cancel();municipalityRequest.cancel();statsRequest.cancel();
  map.destroy();charts.destroy();for(const table of tables.values())table.destroy();
});
