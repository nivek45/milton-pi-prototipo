import {LatestRequest} from './api.js';
const marketRequest=new LatestRequest();
import {PERSONAS,METRICS,metricValue,metricFormat,number,finite} from './config.js';
import {byId,node,text,button} from './dom.js';

function tile(label,value,badge=''){
  const box=node('div','','stat-tile'+(value==='Dado indisponível'?' unavailable':''));
  box.append(node('div',label,'tile-tag'));
  const numRow=node('div','','tile-number-row');
  numRow.append(node('div',value,'tile-number'));
  if(badge){const b=node('span',badge.text,'kpi-badge '+badge.type);numRow.append(b);}
  box.append(numRow);
  return box;
}

function kpiBadge(value,metric){
  if(!finite(value))return '';
  if(metric==='vacina'||metric==='cob_aps'){
    if(value>=80)return {text:'✓ Meta',type:'success'};
    if(value>=50)return {text:'⚠ Atenção',type:'warning'};
    return {text:'✗ Crítico',type:'danger'};
  }
  if(metric==='leitos'||metric==='prof'||metric==='estab'){
    return {text:'Cadastrado',type:'success'};
  }
  if(metric==='alertas'){
    if(value===0)return {text:'Sem alertas',type:'success'};
    if(value<=3)return {text:'Atenção',type:'warning'};
    return {text:'Crítico',type:'danger'};
  }
  return '';
}

function marketBadge(mktShare){
  if(!finite(mktShare))return '';
  if(mktShare>=50)return {text:'Mercado Concentrado',type:'concentrated'};
  if(mktShare>=30)return {text:'Concentração Moderada',type:'concentrated'};
  return {text:'Mercado Disperso',type:'dispersed'};
}

function personaContextCard(state){
  const configs={
    pessoa_comum:{icon:'🏥',title:'Encontre o plano ideal',desc:'Compare planos de saúde disponíveis na sua região. Veja cobertura, operadoras e tipos de contratação.'},
    setor_publico:{icon:'📊',title:'Painel de Gestão Pública',desc:'Monitore indicadores de vacinação, atenção primária, leitos e profissionais por estado.'},
    setor_privado:{icon:'📈',title:'Inteligência de Mercado',desc:'Analise market share, concentração e oportunidades de expansão por território.'}
  };
  const cfg=configs[state.persona];
  const card=node('div','','persona-context-card');
  const icon=node('div',cfg.icon,'persona-context-icon');
  const textDiv=node('div','','persona-context-text');
  textDiv.append(node('div',cfg.title,'persona-context-title'),node('div',cfg.desc,'persona-context-desc'));
  card.append(icon,textDiv);
  return card;
}

export function renderPanel(state,shortcut=()=>{}) {
  marketRequest.cancel();
  const selected=state.snapshot?.states.find(row=>row.uf===state.uf);
  const scope=state.municipio?state.municipioName:selected?.nome||state.uf||'Brasil';
  text('panel-title',scope);text('breadcrumb-uf',state.uf?(selected?.nome||state.uf):'Todos os Estados');
  const level=state.municipio?'Municipal (tabela)':state.uf?'Estadual':'Nacional';
  text('geo-level-pill',level);text('swap-scope-pill',`Escopo: ${scope} · ${level}`);
  text('panel-subtitle',state.municipio?'O mapa mantém a malha estadual. A tabela usa o código IBGE selecionado.':'Dados dos municípios cadastrados no recorte selecionado');
  const panel=byId('panel-content');panel.replaceChildren();
  if(state.status!=='ready'){panel.append(node('p',state.status==='error'?state.error:'Carregando os indicadores…'));return;}
  if(state.municipio){panel.append(node('p',`Consulte os dados de ${scope} na tabela. Não há malha municipal neste protótipo.`));return;}
  const data=state.uf?selected:state.snapshot.national;
  if(!data){panel.append(node('p','Território sem dados cadastrados.'));return;}
  const persona=PERSONAS[state.persona];

  // Persona context card
  panel.append(personaContextCard(state));

  const grid=node('div','','stat-grid-2x2');

  if(state.persona==='pessoa_comum'){
    // Pessoa Comum: planos, operadoras, cobertura info
    const plValue=state.uf?metricValue(state.snapshot,state.uf,'planos_ans'):(data.pl??null);
    grid.append(tile('Planos com cobertura na região',metricFormat(plValue,'planos_ans')));
    grid.append(tile('Operadoras com atuação',number(data.op)));
    if(state.uf){
      const mun=data.mun;
      grid.append(tile('Municípios no estado',number(mun)));
    }
  } else if(state.persona==='setor_publico'){
    // Setor Público: KPIs com badges de alerta
    for(const metric of persona.layers){
      const value=state.uf?metricValue(state.snapshot,state.uf,metric):(METRICS[metric].field?data[METRICS[metric].field]:null);
      const badge=kpiBadge(value,metric);
      grid.append(tile(METRICS[metric].label,metricFormat(value,metric),badge));
    }
    // Additional population/coverage info
    if(data.pop)grid.append(tile('População estimada',number(data.pop)));
  } else if(state.persona==='setor_privado'){
    // Setor Privado: beneficiários, market share com badge de concentração
    for(const metric of persona.layers){
      const value=state.uf?metricValue(state.snapshot,state.uf,metric):(METRICS[metric].field?data[METRICS[metric].field]:null);
      const badge=metric==='mkt_share'?marketBadge(value):'';
      grid.append(tile(METRICS[metric].label,metricFormat(value,metric),badge));
    }
    grid.append(tile('Operadoras ativas',number(data.op)));
  }

  panel.append(grid);

  // Metric explanation
  const help=node('details','','metric-help');help.append(node('summary','O que este indicador significa?'),node('p',METRIC_HELP[state.metric]));panel.append(help);

  const selectedValue=state.uf?metricValue(state.snapshot,state.uf,state.metric):data[METRICS[state.metric].field];
  if(selectedValue==null)panel.append(node('p',state.uf?`Não temos dados de ${METRICS[state.metric].label.toLowerCase()} para ${scope} neste período.`:'Escolha um estado para consultar os indicadores disponíveis.','data-message'));

  // Persona-specific insights
  if(state.persona==='setor_publico'&&state.uf){
    const insightDiv=node('div','','public-insights');
    // Compare with national average
    const nationalCob=state.snapshot.national.cob;
    const stateCob=data.cob;
    if(finite(nationalCob)&&finite(stateCob)){
      const diff=stateCob-nationalCob;
      const direction=diff>0?'acima':'abaixo';
      insightDiv.append(node('p',`Cobertura de planos em ${scope}: ${number(stateCob,1)}% — ${number(Math.abs(diff),1)} pontos ${direction} da média nacional (${number(nationalCob,1)}%).`,'data-message'));
    }
    panel.append(insightDiv);
  }

  if(state.persona==='setor_privado'&&state.uf){
    // Opportunity detection
    const cob=data.cob;
    if(finite(cob)&&cob<30){
      const opp=node('div','','market-badge dispersed');
      opp.textContent=`🎯 Oportunidade: cobertura de planos em ${scope} é ${number(cob,1)}% — abaixo de 30%`;
      opp.style.cssText='margin:12px 0;padding:10px 14px;font-size:12px;';
      panel.append(opp);
    }
  }

  // Navigation shortcuts
  const shortcuts=node('div','','persona-shortcuts');
  const links={
    pessoa_comum:[['pl','🔍 Ver planos da região'],['op','🏢 Conhecer as operadoras']],
    setor_publico:[['sd','📋 Consultar indicadores municipais'],['ov','📊 Ver cobertura da base']],
    setor_privado:[['pl','📦 Ver planos da região'],['op','🏢 Consultar operadoras atuantes'],['mkt','📈 Análise de mercado']]
  };
  for(const[page,label]of links[state.persona])shortcuts.append(button(label,()=>shortcut(page),'shortcut-button'));
  panel.append(shortcuts);

  // Market details for Setor Privado
  if(state.uf&&state.persona==='setor_privado'){
    const detail=node('details','','market-details');detail.append(node('summary','Aprofundar · Operadoras e participação de mercado'));
    const content=node('div');detail.append(content);panel.append(detail);
    let loaded=false;const loadMarket=()=>{
      if(!detail.open||loaded)return;loaded=true;content.replaceChildren(node('p','Carregando operadoras…'));
      const params=new URLSearchParams({uf:state.uf,page_size:'5',sort:'ben',direction:'desc'});
      const period=state.competencia||state.snapshot.meta.competencia;if(period)params.set('competencia',period);
      marketRequest.run('/api/market-share?'+params,data=>{
        content.replaceChildren(node('p',`Operadora líder: ${metricFormat(selected.mkt_share,'mkt_share')} dos vínculos no estado.`));
        const table=node('table','','market-preview');table.append(node('caption',`Operadoras com mais beneficiários · ${period||'período não informado'}`));
        const head=node('thead'),hr=node('tr');for(const title of ['Operadora','Beneficiários','Participação']){const th=node('th',title);th.scope='col';hr.append(th);}head.append(hr);table.append(head);
        const body=node('tbody');
        for(const[i,row]of data.items.entries()){
          const tr=node('tr');
          const nmCell=node('td',row.nm);
          if(i===0)nmCell.innerHTML=`<strong>${row.nm}</strong> <span class="market-badge concentrated" style="margin-left:6px">Líder</span>`;
          tr.append(nmCell,node('td',number(row.ben)),node('td',number(row.pct,1)+'%'));
          body.append(tr);
        }
        table.append(body);content.append(table);
        content.append(button('🏢 Ver todas as operadoras',()=>shortcut('op'),'shortcut-button'));
        content.append(button('📈 Abrir análise de mercado',()=>shortcut('mkt'),'shortcut-button'));
      },error=>{loaded=false;content.replaceChildren(node('p',error.message),button('Tentar novamente',loadMarket));});
    };detail.addEventListener('toggle',loadMarket);
  }

  // Sources
  const sources=node('details'),summary=node('summary','📁 Fontes e metodologia');sources.append(summary);sources.append(node('p',state.persona==='pessoa_comum'?state.snapshot.meta.note:`${number(data.municipios_perfil)} de ${number(data.mun)} municípios cadastrados têm perfil anual nesta consulta.`));
  for(const source of state.snapshot.meta.sources){sources.append(node('p',`${source.nome}: ${source.fonte}. ${source.sintetico?'Dados sintéticos. ':''}${source.notas||''}`));}
  panel.append(sources);
}

export function renderInsights(state) {
  const row=byId('insight-row');row.replaceChildren();
  const personaLabels={
    pessoa_comum:['Planos disponíveis','Compare cobertura e custo'],
    setor_publico:['Gestão Pública','Monitore indicadores de saúde'],
    setor_privado:['Inteligência Comercial','Analise oportunidades de mercado']
  };
  const pLabel=personaLabels[state.persona];
  const cards=[
    ['Território',state.municipioName||state.uf||'Brasil','Local selecionado para a consulta'],
    ['Período dos dados',state.snapshot?`${state.snapshot.meta.competencia||'Sem competência'} / ${state.snapshot.meta.ano||'Sem ano'}`:'—','Mês de beneficiários / ano dos dados municipais'],
    [pLabel[0],state.snapshot?(state.snapshot.meta.synthetic?'Base demonstrativa':'Dados oficiais'):'Aguardando dados',pLabel[1]],
  ];
  for(const[label,value,note]of cards){const card=node('div','','insight-card');card.append(node('div',label,'insight-label'),node('div',value,'insight-value'),node('div',note,'insight-sub'));row.append(card);}
}

export function renderPip(state) {
  const card=byId('pip-card');card.style.display=state.page==='map'&&(state.uf||state.view==='table')?'block':'none';
  const uf=state.snapshot?.states.find(row=>row.uf===state.uf);
  const scope=state.municipioName||uf?.nome||state.uf||'Brasil';
  const action=state.view==='map'?(scope==='Brasil'?'Ver dados do Brasil':`Ver dados de ${scope}`):'Voltar ao mapa';card.setAttribute('aria-label',action);
  text('pip-label',`${scope} · ${METRICS[state.metric].label}`);
  const value=state.uf?metricFormat(metricValue(state.snapshot,state.uf,state.metric),state.metric):'Visão estadual';
  text('pip-sub',action);card.title=value;
  byId('pip-mini-map').style.display=state.view==='table'?'block':'none';
}

export class Charts {
  charts=new Map();
  show(id,rows,labelKey,valueKey,label) {
    if(!window.Chart)return;
    const canvas=byId(id);if(!canvas)return;
    canvas.setAttribute('role','img');canvas.setAttribute('aria-label',label+'. Os valores também estão disponíveis no conteúdo textual desta página.');
    // Persona-aware colors
    const persona=document.body.dataset.persona||'pessoa_comum';
    const colors={
      pessoa_comum:['#4ecda5','#36b893','#2a9c7d','#1e8067','#156551'],
      setor_publico:['#6b8cff','#5a7de8','#4a6ed0','#3a5fb8','#2a50a0'],
      setor_privado:['#f0a050','#e09040','#d08030','#c07020','#b06010']
    };
    const palette=colors[persona]||colors.pessoa_comum;
    const bgColors=rows.slice(0,20).map((_,i)=>palette[i%palette.length]);

    const values=rows.slice(0,20),data={labels:values.map(r=>r[labelKey]),datasets:[{label,data:values.map(r=>r[valueKey]),backgroundColor:bgColors,borderRadius:4,borderSkipped:false}]};
    const chart=this.charts.get(id);
    if(chart){chart.data=data;chart.update('none');}
    else this.charts.set(id,new window.Chart(canvas,{
      type:id==='chart-doughnut'?'doughnut':'bar',data,
      options:{responsive:true,maintainAspectRatio:false,animation:{duration:400,easing:'easeOutQuart'},
        plugins:{legend:{display:id==='chart-doughnut',labels:{color:'#aaa',padding:12,usePointStyle:true}},title:{display:true,text:label,color:'#ccc',padding:{bottom:12}}},
        scales:id==='chart-doughnut'?{}:{x:{ticks:{color:'#888',maxRotation:45},grid:{color:'rgba(255,255,255,0.04)'}},y:{beginAtZero:true,ticks:{color:'#888'},grid:{color:'rgba(255,255,255,0.04)'}}}
      }
    }));
  }
  destroy(){for(const chart of this.charts.values())chart.destroy();this.charts.clear();}
}

const METRIC_HELP={
 planos_ans:'Número de planos com situação Ativo, operadora no cadastro ativo da ANS e cobertura geográfica registrada na região. Não representa número de beneficiários, ofertas de venda ou prestadores disponíveis. A mesma opção pode aparecer em mais de um estado.',
 cob_plano:'Cobertura é a proporção da população com plano de saúde. A média considera a população dos municípios com dados; não representa automaticamente todos os municípios do estado.',
 vacina:'Proporção de pessoas vacinadas no público definido pela fonte. A vacina, o público e o período precisam ser consultados na metodologia da série.',
 alertas:'Quantidade de alertas registrados pela fonte no período. A ausência de informação não significa ausência de riscos à saúde.',
 cob_aps:'APS significa Atenção Primária à Saúde: o primeiro nível de atendimento, como as unidades básicas de saúde. O indicador informa a cobertura estimada pela fonte.',
 leitos:'Quantidade de leitos disponíveis ao SUS cadastrados na fonte. Não informa disponibilidade imediata para internação.',
 prof:'Número de profissionais por 1.000 habitantes, conforme os critérios da fonte. Permite considerar o tamanho da população.',
 ben_ans:'Quantidade de vínculos de beneficiários registrada na base. ANS é a Agência Nacional de Saúde Suplementar; uma pessoa pode ter mais de um vínculo.',
 estab:'Quantidade de estabelecimentos privados de saúde cadastrados na fonte e no período selecionado.',
 mkt_share:'Participação de mercado (market share) é a parcela dos beneficiários atendida por uma operadora. O mapa mostra a participação da maior operadora em cada estado.'
};
