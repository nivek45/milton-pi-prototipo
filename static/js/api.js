export async function requestJSON(url,{signal,timeout=10000}={}) {
  const controller=new AbortController();
  const abort=()=>controller.abort();
  if(signal?.aborted)abort();
  signal?.addEventListener('abort',abort,{once:true});
  const timer=setTimeout(abort,timeout);
  try {
    const response=await fetch(url,{signal:controller.signal,headers:{Accept:'application/json'}});
    const data=await response.json();
    if(!response.ok)throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  } catch(error) {
    if(error.name==='AbortError' && !signal?.aborted)throw new Error('Tempo de resposta excedido. Tente novamente.');
    throw error;
  } finally {
    clearTimeout(timer);signal?.removeEventListener('abort',abort);
  }
}
export class LatestRequest {
  generation=0; controller=null;
  async run(url,apply,fail) {
    this.cancel();const generation=this.generation;
    const controller=this.controller=new AbortController();
    try {
      const data=await requestJSON(url,{signal:controller.signal});
      if(generation===this.generation)apply(data);
    } catch(error) {
      if(generation===this.generation && !controller.signal.aborted)fail(error);
    }
  }
  cancel(){this.generation++;this.controller?.abort();}
}
export function queryString(state,extra={}) {
  const values={uf:state.uf,municipio:state.municipio,competencia:state.competencia,ano:state.ano,...extra};
  return new URLSearchParams(Object.entries(values).filter(([,value])=>value!=='' && value!=null)).toString();
}
export function validateSnapshot(data) {
  if(!Array.isArray(data?.states)||!Array.isArray(data.indicators)||!data.meta||!data.national)throw new Error('Resposta do resumo inválida.');
  for(const row of data.states) {
    if(!/^[A-Z]{2}$/.test(row.uf)||typeof row.nome!=='string')throw new Error('Território inválido na resposta.');
    for(const key of ['ben','op','cob','idh','renda','pop','mun','mkt_share']) {
      if(row[key]!=null && (typeof row[key]!=='number'||!Number.isFinite(row[key])))throw new Error(`Valor inválido: ${key}.`);
    }
  }
  return data;
}
