import test from 'node:test';
import assert from 'node:assert/strict';
import {initialState,reduce} from '../static/js/store.js';
import {metricValue,metricFormat} from '../static/js/config.js';
import {validateSnapshot,LatestRequest,requestJSON} from '../static/js/api.js';

test('restoration selects an allowed metric before rendering',()=>{
  const state=initialState({getItem:key=>key==='miltonPersona'?'pessoa_comum':'vacina'});
  assert.equal(state.metric,'vacina');
  assert.equal(initialState({getItem:()=>{throw new Error('disabled');}}).metric,'cob_plano');
});
test('zero and unavailable are distinct; no proxy metrics',()=>{
  const snapshot={states:[{uf:'SP',ben:0,idh:.8,cob:0}],indicators:[]};
  assert.equal(metricValue(snapshot,'SP','ben_ans'),0);
  assert.equal(metricValue(snapshot,'SP','cob_plano'),0);
  assert.equal(metricValue(snapshot,'SP','vacina'),null);
  assert.equal(metricFormat(null,'vacina'),'Dado indisponível');
});
test('PIP alternates views and municipality requires a UF',()=>{
  let state=initialState();state=reduce(state,{type:'view'});assert.equal(state.view,'table');
  state=reduce(state,{type:'view'});assert.equal(state.view,'map');
  state=reduce(state,{type:'municipio',value:'3550308'});assert.equal(state.municipio,'');
  state=reduce(state,{type:'uf',value:'SP'});
  state=reduce(state,{type:'municipio',value:'3550308',name:'São Paulo'});assert.equal(state.view,'table');
  state=reduce(state,{type:'uf',value:'RJ'});assert.equal(state.municipio,'');
});
test('persona switch resets invalid metrics and disallowed pages',()=>{
  const state=reduce({...initialState(),page:'pl',metric:'vacina'},{type:'persona',value:'setor_publico'});
  assert.equal(state.metric,'cob_aps');assert.equal(state.page,'map');
});
test('failed reload clears old dataset',()=>{
  const state=reduce({...initialState(),snapshot:{states:[]}},{type:'error',value:'network'});
  assert.equal(state.snapshot,null);assert.equal(state.status,'error');
});

test('city, date and view survive persona changes and reloads',()=>{
  let state=reduce(initialState(),{type:'locality',uf:'SP',code:'3509502',name:'Campinas'});
  state=reduce(state,{type:'period',key:'competencia',value:'2024-01'});
  state=reduce(state,{type:'persona',value:'setor_publico'});
  state=reduce(state,{type:'loading'});
  assert.equal(state.municipio,'3509502');assert.equal(state.uf,'SP');
  assert.equal(state.competencia,'2024-01');assert.equal(state.view,'table');
  state=reduce(state,{type:'view'});state=reduce(state,{type:'view'});
  assert.equal(state.municipioName,'Campinas');
});

test('table restores pagination and sorting when returning to a previous scope',async()=>{
  globalThis.matchMedia=()=>({matches:true,addEventListener(){}});
  const {DataTable}=await import('../static/js/table.js');
  const table=new DataTable({setAttribute(){}});let loads=0;table.load=()=>loads++;
  const state={uf:'SP',municipio:'',competencia:'2024-01',ano:'2024',revision:1};
  table.update(state,'op');table.page=3;table.sort='nm';table.direction='asc';
  table.suspend();table.update(state,'op');assert.equal(table.page,3);
  table.update({...state,uf:'RJ'},'op');assert.equal(table.page,1);
  table.update(state,'op');assert.equal(table.page,3);assert.equal(table.sort,'nm');
  table.update({...state,revision:2},'op');assert.equal(table.page,3);assert.equal(loads,5);
});
test('API contract rejects string numbers',()=>{
  assert.throws(()=>validateSnapshot({states:[{uf:'SP',nome:'São Paulo',ben:'10'}],indicators:[],meta:{},national:{}}));
});
test('late response cannot overwrite newer request',async()=>{
  const original=globalThis.fetch;const responses={};
  globalThis.fetch=url=>new Promise(resolve=>responses[url]=resolve);
  try{
    const request=new LatestRequest(),applied=[];
    const old=request.run('old',x=>applied.push(x),()=>{});
    const current=request.run('new',x=>applied.push(x),()=>{});
    responses.new({ok:true,json:async()=>2});await current;
    responses.old({ok:true,json:async()=>1});await old;
    assert.deepEqual(applied,[2]);
  }finally{globalThis.fetch=original;}
});
test('timeout covers response body',async()=>{
  const original=globalThis.fetch;
  globalThis.fetch=async(_,{signal})=>({ok:true,json:()=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError')),{once:true}))});
  try{await assert.rejects(requestJSON('slow',{timeout:10}),/Tempo de resposta/);}finally{globalThis.fetch=original;}
});

test('reduced motion skips animation and cancels motion when enabled',async()=>{
  const media={matches:true,addEventListener(_name,fn){this.changed=fn;}};
  globalThis.matchMedia=()=>media;
  const motion=await import('../static/js/motion.js?reduced-test');
  let started=0,cancelled=0;
  const animation={cancel(){cancelled++;this.oncancel?.();}};
  const element={getClientRects:()=>[{}],animate(){started++;return animation;}};
  motion.reveal(element);assert.equal(started,0);
  media.matches=false;motion.reveal(element);assert.equal(started,1);
  media.matches=true;media.changed();assert.equal(cancelled,1);
});
