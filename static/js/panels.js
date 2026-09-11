import {PERSONAS,METRICS,metricValue,metricFormat,number} from './config.js';
import {byId,node,text,button} from './dom.js';

function tile(label,value){const box=node('div','','stat-tile'+(value==='Dado indisponível'?' unavailable':''));box.append(node('div',label,'tile-tag'),node('div',value,'tile-number'));return box;}
export function renderPanel(state,shortcut=()=>{}) {
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
  const grid=node('div','','stat-grid-2x2');
  for(const metric of persona.layers){
    const value=state.uf?metricValue(state.snapshot,state.uf,metric):(METRICS[metric].field?data[METRICS[metric].field]:null);
    grid.append(tile(METRICS[metric].label,metricFormat(value,metric)));
  }
  panel.append(grid);
  const help=node('details','','metric-help');help.append(node('summary','O que este indicador significa?'),node('p',METRIC_HELP[state.metric]));panel.append(help);
  const selectedValue=state.uf?metricValue(state.snapshot,state.uf,state.metric):data[METRICS[state.metric].field];
  if(selectedValue==null)panel.append(node('p',state.uf?`Não temos dados de ${METRICS[state.metric].label.toLowerCase()} para ${scope} neste período.`:'Escolha um estado para consultar os indicadores disponíveis.','data-message'));
  panel.append(node('p',`${number(data.municipios_perfil)} de ${number(data.mun)} municípios cadastrados têm perfil anual nesta consulta.`,'data-message'));
  const shortcuts=node('div','','persona-shortcuts');
  const links={pessoa_comum:[['pl','Consultar planos da região'],['sd','Entender os dados da cidade']],setor_publico:[['sd','Consultar indicadores municipais'],['ov','Ver cobertura da base']],setor_privado:[['mkt','Ver participação de mercado'],['op','Consultar operadoras atuantes']]};
  for(const[page,label]of links[state.persona])shortcuts.append(button(label,()=>shortcut(page),'shortcut-button'));
  panel.append(shortcuts);
  const sources=node('details'),summary=node('summary','Fontes e metodologia');sources.append(summary);
  for(const source of state.snapshot.meta.sources){sources.append(node('p',`${source.nome}: ${source.fonte}. ${source.sintetico?'Dados sintéticos. ':''}${source.notas||''}`));}
  panel.append(sources);
}
export function renderInsights(state) {
  const row=byId('insight-row');row.replaceChildren();
  const cards=[
    ['Território',state.municipioName||state.uf||'Brasil','Local selecionado para a consulta'],
    ['Período dos dados',state.snapshot?`${state.snapshot.meta.competencia||'Sem competência'} / ${state.snapshot.meta.ano||'Sem ano'}`:'—','Mês de beneficiários / ano dos dados municipais'],
    ['Qualidade da base',state.snapshot?(state.snapshot.meta.synthetic?'Demonstração / base mista':'Fontes cadastradas'):'Aguardando dados','Consulte a fonte antes de interpretar os valores'],
  ];
  for(const[label,value,note]of cards){const card=node('div','','insight-card');card.append(node('div',label,'insight-label'),node('div',value,'insight-value'),node('div',note,'insight-sub'));row.append(card);}
}
export function renderPip(state) {
  const card=byId('pip-card');card.style.display=state.page==='map'?'block':'none';
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
    const values=rows.slice(0,20),data={labels:values.map(r=>r[labelKey]),datasets:[{label,data:values.map(r=>r[valueKey]),backgroundColor:'#64ad87'}]};
    const chart=this.charts.get(id);
    if(chart){chart.data=data;chart.update('none');}
    else this.charts.set(id,new window.Chart(canvas,{
      type:'bar',data,
      options:{responsive:true,maintainAspectRatio:false,animation:false,
        plugins:{legend:{display:false},title:{display:true,text:label}},
        scales:{x:{ticks:{color:'#aaa'}},y:{beginAtZero:true,ticks:{color:'#aaa'}}}
      }
    }));
  }
  destroy(){for(const chart of this.charts.values())chart.destroy();this.charts.clear();}
}

const METRIC_HELP={
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
