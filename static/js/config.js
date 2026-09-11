export const PERSONAS = {
  pessoa_comum: { label:'Pessoa Comum', heading:'Saúde na Sua Região', description:'Cobertura e indicadores do território selecionado', pages:['map','pl','sd'], layers:['cob_plano','vacina','alertas'], table:'pl' },
  setor_publico: { label:'Setor Público', heading:'Gestão de Saúde Pública', description:'Indicadores públicos com fonte e período de referência', pages:['map','ov','sd'], layers:['cob_aps','leitos','prof'], table:'sd' },
  setor_privado: { label:'Setor Privado', heading:'Inteligência de Mercado', description:'Beneficiários e participação no mercado do território selecionado', pages:['map','mkt','op','pl'], layers:['ben_ans','estab','mkt_share'], table:'op' },
};
export const METRICS = {
  cob_plano:{label:'Cobertura de Plano',field:'cob',unit:'%',domain:[0,100],period:'ano'},
  vacina:{label:'Cobertura Vacinal',unit:'%',domain:[0,100],period:'competencia'},
  alertas:{label:'Alertas Ativos',unit:'quantidade',period:'competencia'},
  cob_aps:{label:'Atenção primária (APS)',unit:'%',domain:[0,100],period:'competencia'},
  leitos:{label:'Leitos SUS',unit:'quantidade',period:'competencia'},
  prof:{label:'Profissionais / 1.000 hab.',unit:'por 1.000 habitantes',period:'competencia'},
  ben_ans:{label:'Beneficiários ANS',field:'ben',unit:'quantidade',period:'competencia'},
  estab:{label:'Estabelecimentos Privados',unit:'quantidade',period:'competencia'},
  mkt_share:{label:'Participação da operadora líder',field:'mkt_share',unit:'%',domain:[0,100],period:'competencia'},
};
export const finite = value => typeof value==='number' && Number.isFinite(value);
export function metricValue(snapshot, uf, key) {
  const spec=METRICS[key];
  if (!snapshot || !spec) return null;
  const state=snapshot.states.find(row=>row.uf===uf);
  const value=spec.field ? state?.[spec.field] : snapshot.indicators.find(i=>i.uf===uf && i.metrica===key)?.valor;
  return finite(value) ? value : null;
}
export function number(value,digits=0) {
  return finite(value) ? value.toLocaleString('pt-BR',{maximumFractionDigits:digits,minimumFractionDigits:digits}) : '—';
}
export function metricFormat(value,key) {
  if (!finite(value)) return 'Dado indisponível';
  const unit=METRICS[key].unit;
  return number(value,unit==='quantidade'?0:1)+(unit==='%'?'%':unit==='quantidade'?'':' / 1.000 hab.');
}
export const TABLES = {
  pl:{endpoint:'planos',title:'Planos disponíveis no território',sort:'nm',columns:[['nm','Plano'],['op','Operadora'],['tipo','Contratação'],['cob','Abrangência'],['copart','Coparticipação'],['mun','Municípios cadastrados']]},
  op:{endpoint:'operadoras',title:'Operadoras com atuação no território',sort:'ben',columns:[['nm','Operadora'],['mod','Modalidade'],['uf','Estado da sede'],['ben','Beneficiários'],['pct','Participação (%)'],['pl','Planos ativos']]},
  mkt:{endpoint:'market-share',title:'Participação no mercado do território',sort:'ben',columns:[['nm','Operadora'],['registro_ans','Registro ANS'],['ben','Beneficiários'],['pct','Participação (%)'],['competencia','Mês de referência']]},
  sd:{endpoint:'perfil-saude',title:'Indicadores municipais',sort:'idh',columns:[['m','Município'],['uf','Estado'],['pop','População'],['idh','IDH'],['cob','Cobertura (%)'],['renda','Renda per capita'],['gini','Gini'],['ano','Ano']]},
};
