import {TABLES,number,finite} from './config.js';
import {LatestRequest,queryString} from './api.js';
import {node,button} from './dom.js';
import {reveal} from './motion.js';

export class DataTable {
  request=new LatestRequest();page=1;sort='';direction='desc';q='';signature='';
  contexts=new Map();suspended=false;
  constructor(container,onRows=()=>{}){this.container=container;this.onRows=onRows;container.tabIndex=0;container.setAttribute('role','region');container.setAttribute('aria-label','Tabela de dados, com rolagem horizontal quando necessário');}
  update(state,kind,q='') {
    const signature=JSON.stringify([kind,state.uf,state.municipio,state.competencia,state.ano,q]);
    const revisionChanged=this.state?.revision!==state.revision;
    this.state=state;
    if(signature===this.signature&&!this.suspended&&!revisionChanged)return;
    if(signature!==this.signature){
      if(this.signature)this.contexts.set(this.signature,{page:this.page,sort:this.sort,direction:this.direction});
      const saved=this.contexts.get(signature);
      this.page=saved?.page||1;this.sort=saved?.sort||TABLES[kind].sort;this.direction=saved?.direction||(this.sort==='nm'?'asc':'desc');
      if(this.contexts.size>30)this.contexts.delete(this.contexts.keys().next().value);
    }
    this.signature=signature;this.suspended=false;
    this.kind=kind;this.q=q;this.load();
  }
  load() {
    const config=TABLES[this.kind];
    const focused=document.activeElement;
    if(this.container.contains(focused)&&focused.dataset.focus){this.returnFocus=focused.dataset.focus;this.container.focus({preventScroll:true});}
    this.onRows(this.kind,[]);
    this.container.setAttribute('aria-busy','true');
    this.container.replaceChildren(node('p','Carregando registros…','data-message'));
    const qs=queryString(this.state,{q:this.q,page:this.page,page_size:20,sort:this.sort,direction:this.direction});
    this.request.run(`/api/${config.endpoint}?${qs}`,data=>{
      if(!Array.isArray(data.items)||!Number.isInteger(data.total)||data.total<0)throw new Error('Resposta tabular inválida.');
      const lastPage=Math.max(1,Math.ceil(data.total/data.page_size));
      if(this.page>lastPage){this.page=lastPage;this.load();return;}
      this.render(data);this.onRows(this.kind,data.items);
    },error=>{
      this.container.setAttribute('aria-busy','false');
      this.container.replaceChildren(node('p',error.message,'data-message'),button('Tentar novamente',()=>this.load()));
      const status=document.getElementById('interaction-status');if(status)status.textContent=`${config.title}. ${error.message}`;
      this.onRows(this.kind,[]);
    });
  }
  render(data) {
    const config=TABLES[this.kind],table=node('table','','data-table');
    table.append(node('caption',config.title,'sr-only'));
    const thead=node('thead'),head=node('tr'),tbody=node('tbody');
    for(const[key,label]of config.columns){
      const th=node('th');th.scope='col';
      if(!['registro_ans','competencia','ano'].includes(key)){
        th.setAttribute('aria-sort',this.sort===key?(this.direction==='asc'?'ascending':'descending'):'none');
        const sortButton=button(label+(this.sort===key?(this.direction==='asc'?' ↑':' ↓'):''),()=>{
          this.direction=this.sort===key&&this.direction==='asc'?'desc':'asc';this.sort=key;this.page=1;this.load();
        },'table-sort');sortButton.dataset.focus='sort-'+key;sortButton.setAttribute('aria-label',`Ordenar por ${label}`);th.append(sortButton);
      }else th.textContent=label;
      head.append(th);
    }
    head.append(node('th','Origem'));thead.append(head);
    for(const row of data.items){
      const tr=node('tr');
      for(const[key]of config.columns){
        const value=row[key];let rendered=value==null?'—':String(value);
        if(key==='copart')rendered=value?'Sim':'Não';
        else if(finite(value)&&key!=='ano')rendered=number(value,['idh','gini'].includes(key)?3:['pct','cob','renda'].includes(key)?2:0);
        tr.append(node('td',rendered));
      }
      tr.append(node('td',row.sintetico?'Demonstração':'Fonte cadastrada'));
      tbody.append(tr);
    }
    if(!data.items.length){const tr=node('tr'),td=node('td','Nenhum registro para este território, período e busca.');td.colSpan=config.columns.length+1;tr.append(td);tbody.append(tr);}
    table.append(thead,tbody);
    const pages=Math.max(1,Math.ceil(data.total/data.page_size)),footer=node('div','','pagination');
    const previous=button('Anterior',()=>{this.page--;this.load();}),next=button('Próxima',()=>{this.page++;this.load();});
    previous.dataset.focus='previous';next.dataset.focus='next';
    previous.disabled=this.page<=1;next.disabled=this.page>=pages;
    footer.append(previous,node('span',`Página ${this.page} de ${pages} · ${number(data.total)} registros`),next);
    const descriptions={sd:'IDH resume desenvolvimento humano e varia de 0 a 1; valores maiores indicam maior desenvolvimento. Gini mede desigualdade de renda, de 0 a 1; valores maiores indicam maior desigualdade. Cobertura é a proporção da população com plano. Consulte o ano e a origem antes de comparar.',pl:'Coparticipação indica se o plano prevê participação do usuário no custo de atendimentos, conforme as regras do contrato. Abrangência é a área geográfica de cobertura cadastrada; esta consulta não confirma disponibilidade comercial nem preços.',op:'O estado da sede é o endereço da operadora. O filtro de estado considera a atuação registrada na base. Participação é a proporção de beneficiários no território e no mês da consulta.',mkt:'Participação de mercado, ou market share, é a proporção dos vínculos de beneficiários atribuída a cada operadora no território e no mês da consulta. Uma pessoa pode ter mais de um vínculo.'};
    const explanation=node('details','','table-explanation');explanation.append(node('summary','Como ler esta tabela'),node('p',descriptions[this.kind]));
    this.container.replaceChildren(explanation,table,footer);this.container.setAttribute('aria-busy','false');
    const status=document.getElementById('interaction-status');if(status)status.textContent=`${config.title}. Página ${this.page} de ${pages}. ${number(data.total)} registros.`;
    if(this.returnFocus&&document.activeElement===this.container){const target=this.container.querySelector(`[data-focus="${this.returnFocus}"]`);if(target&&!target.disabled)target.focus({preventScroll:true});}
    this.returnFocus=null;reveal(table,3);
  }
  suspend(){this.request.cancel();this.suspended=true;}
  clear(message){this.suspend();this.container.setAttribute('aria-busy','false');this.container.replaceChildren(node('p',message,'data-message'));this.onRows(this.kind,[]);}
  destroy(){this.request.cancel();}
}
