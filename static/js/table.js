import {TABLES,number,finite,tableConfig} from './config.js';
import {LatestRequest,queryString,apiPath} from './api.js';
import {node,button} from './dom.js';
import {reveal} from './motion.js';

export class DataTable {
  request=new LatestRequest();page=1;sort='';direction='desc';q='';signature='';
  contexts=new Map();suspended=false;
  detailRequest=new LatestRequest();dialog=null;
  contratacao='';assistencia='';
  constructor(container,onRows=()=>{}){this.container=container;this.onRows=onRows;container.tabIndex=0;container.setAttribute('role','region');container.setAttribute('aria-label','Tabela de dados, com rolagem horizontal quando necessário');}
  update(state,kind,q='') {
    const signature=JSON.stringify([state.persona,kind,state.uf,state.municipio,state.competencia,state.ano,q]);
    const revisionChanged=this.state?.revision!==state.revision;
    this.state=state;
    if(signature===this.signature&&!this.suspended&&!revisionChanged)return;
    if(signature!==this.signature){
      if(this.signature)this.contexts.set(this.signature,{page:this.page,sort:this.sort,direction:this.direction});
      const saved=this.contexts.get(signature);
      this.page=saved?.page||1;this.sort=saved?.sort||tableConfig(kind,state.persona).sort;this.direction=saved?.direction||(this.sort==='nm'?'asc':'desc');
      if(this.contexts.size>30)this.contexts.delete(this.contexts.keys().next().value);
    }
    this.signature=signature;this.suspended=false;
    this.kind=kind;this.q=q;this.load();
  }
  load() {
    const config=tableConfig(this.kind,this.state.persona);
    const focused=document.activeElement;
    if(this.container.contains(focused)&&focused.dataset.focus){this.returnFocus=focused.dataset.focus;this.container.focus({preventScroll:true});}
    this.onRows(this.kind,[]);
    this.container.setAttribute('aria-busy','true');
    this.container.replaceChildren(node('p','Carregando registros…','data-message'));
    const qs=queryString(this.state,{q:this.q,page:this.page,page_size:20,sort:this.sort,direction:this.direction,...(this.state.persona==='pessoa_comum'&&this.kind==='pl'?{contratacao:this.contratacao,assistencia:this.assistencia}:{})});
    this.request.run(`${apiPath(this.state,config.endpoint)}?${qs}`,data=>{
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
    const config=tableConfig(this.kind,this.state.persona),table=node('table','','data-table');
    const hasDetails=this.state.persona==='pessoa_comum'&&this.kind==='pl';
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
    head.append(node('th','Origem'));if(hasDetails)head.append(node('th','Detalhes'));thead.append(head);
    for(const row of data.items){
      const tr=node('tr');
      for(const[key]of config.columns){
        const value=row[key];
        const td=node('td');
        if(key==='copart'){
          if(value===true){
            const b=node('span','Coparticipação','kpi-badge warning');
            td.append(b);
          } else if(value===false){
            const b=node('span','Sem copart','kpi-badge success');
            td.append(b);
          } else {
            td.textContent='Não informado';
          }
        } else if(key==='tipo'&&typeof value==='string'){
          let cls='plan-type-icon medical';
          if(value.toLowerCase().includes('individual')||value.toLowerCase().includes('familiar'))cls='plan-type-icon dental';
          else if(value.toLowerCase().includes('adesão')||value.toLowerCase().includes('adesao'))cls='plan-type-icon reference';
          const b=node('span',value,cls);
          td.append(b);
        } else if(key==='pct'&&finite(value)){
          const isLeader=row===data.items[0]&&value>=25;
          td.textContent=number(value,1)+'%';
          if(isLeader){
            const badge=node('span','Líder','market-badge concentrated');
            badge.style.marginLeft='6px';
            td.append(badge);
          }
        } else {
          let rendered=value==null?'—':String(value);
          if(finite(value)&&key!=='ano')rendered=number(value,['idh','gini'].includes(key)?3:['cob','renda'].includes(key)?2:0)+(key==='cob'?'%':'');
          td.textContent=rendered;
        }
        tr.append(td);
      }
      const origTd=node('td');
      const isAns=data.meta?.dataset==='ans_catalogo';
      const origBadge=node('span',row.sintetico?'Demo':(isAns?'ANS':'Oficial'),row.sintetico?'kpi-badge warning':'kpi-badge success');
      origTd.append(origBadge);
      tr.append(origTd);
      if(hasDetails){
        const td=node('td');
        const open=button('Ver detalhes',()=>this.showDetail(row.id),'table-detail-btn');
        open.setAttribute('aria-label',`Ver detalhes de ${row.nm}`);
        td.append(open);
        tr.append(td);
      }
      tbody.append(tr);
    }
    if(!data.items.length){const tr=node('tr'),td=node('td','Nenhum registro para este território, período e busca.');td.colSpan=config.columns.length+1+(hasDetails?1:0);tr.append(td);tbody.append(tr);}
    table.append(thead,tbody);
    const pages=Math.max(1,Math.ceil(data.total/data.page_size)),footer=node('div','','pagination');
    const previous=button('Anterior',()=>{this.page--;this.load();}),next=button('Próxima',()=>{this.page++;this.load();});
    previous.dataset.focus='previous';next.dataset.focus='next';
    previous.disabled=this.page<=1;next.disabled=this.page>=pages;
    footer.append(previous,node('span',`Página ${this.page} de ${pages} · ${number(data.total)} registros`),next);
    const descriptions={sd:'IDH resume desenvolvimento humano e varia de 0 a 1; valores maiores indicam maior desenvolvimento. Gini mede desigualdade de renda, de 0 a 1; valores maiores indicam maior desigualdade. Cobertura é a proporção da população com plano. Consulte o ano e a origem antes de comparar.',pl:'Coparticipação indica se o plano prevê participação do usuário no custo de atendimentos, conforme as regras do contrato. Abrangência é a área geográfica de cobertura cadastrada; esta consulta não confirma disponibilidade comercial nem preços.',op:'O estado da sede é o endereço da operadora. O filtro de estado considera a atuação registrada na base. Participação é a proporção de beneficiários no território e no mês da consulta.',mkt:'Participação de mercado, ou market share, é a proporção dos vínculos de beneficiários atribuída a cada operadora no território e no mês da consulta. Uma pessoa pode ter mais de um vínculo.'};
    const explanation=node('details','','table-explanation');explanation.append(node('summary','Como ler esta tabela'),node('p',data.meta?.dataset==='ans_catalogo'?data.meta.note:descriptions[this.kind]));
    const filters=node('div','','catalog-filters');
    if(hasDetails){
      const specs=[['assistencia','Atendimento',[['','Todos'],['medica','Médico-hospitalar'],['odonto','Somente odontológico']]],['contratacao','Contratação',[['','Todas'],['Individual ou familiar','Individual ou familiar'],['Coletivo empresarial','Coletivo empresarial'],['Coletivo por adesão','Coletivo por adesão']]]];
      for(const[key,label,choices]of specs){const wrapper=node('label',label),select=node('select');select.dataset.focus='filter-'+key;
        for(const[value,text]of choices){const option=node('option',text);option.value=value;select.append(option);}select.value=this[key];
        select.addEventListener('change',()=>{this[key]=select.value;this.page=1;this.load();});wrapper.append(select);filters.append(wrapper);}
    }
    this.container.replaceChildren(filters,explanation,table,footer);this.container.setAttribute('aria-busy','false');
    const status=document.getElementById('interaction-status');if(status)status.textContent=`${config.title}. Página ${this.page} de ${pages}. ${number(data.total)} registros.`;
    if(this.returnFocus&&document.activeElement===this.container){const target=this.container.querySelector(`[data-focus="${this.returnFocus}"]`);if(target&&!target.disabled)target.focus({preventScroll:true});}
    this.returnFocus=null;reveal(table,3);
  }
  showDetail(id){
    this.closeDetail();
    const dialog=this.dialog=node('dialog','','plan-dialog');dialog.setAttribute('aria-labelledby','plan-dialog-title');
    const title=node('h2','Detalhes do plano');title.id='plan-dialog-title';
    const close=button('Fechar',()=>dialog.close()),content=node('div','Carregando dados da ANS…');content.setAttribute('aria-live','polite');
    dialog.append(close,title,content);document.body.append(dialog);
    dialog.addEventListener('close',()=>this.closeDetail(),{once:true});dialog.showModal();
    this.detailRequest.run(apiPath(this.state,`planos/${id}`),data=>{
      const p=data.item;title.textContent=p.nm;content.replaceChildren();
      const fields=[['Registro do plano',p.registro],['Operadora',p.op],['Registro da operadora',p.registro_ans],['Contratação',p.tipo],['Cobertura assistencial',p.seg],['Abrangência',p.cob],['Participação nas despesas',p.fator],['Acomodação hospitalar',p.acomodacao],['Estados na base de cobertura',p.ufs.join(', ')||'Não informado'],['Situação',p.situacao],['Atualização na ANS',p.atualizado_em]];
      const list=node('dl');for(const[label,value]of fields)list.append(node('dt',label),node('dd',value||'Não informado'));content.append(list,node('p',data.meta.note));
      content.append(node('p','Preço e prestadores específicos ainda não estão integrados nesta consulta. Confirme essas informações com a operadora.'));
      for(const source of data.meta.sources){const link=node('a',source.nome);link.href=source.fonte;link.target='_blank';link.rel='noopener noreferrer';const paragraph=node('p');paragraph.append(link);content.append(paragraph);}
    },error=>content.replaceChildren(node('p',error.message),button('Tentar novamente',()=>this.showDetail(id))));
  }
  closeDetail(){this.detailRequest.cancel();this.dialog?.remove();this.dialog=null;}
  suspend(){this.request.cancel();this.closeDetail();this.suspended=true;}
  clear(message){this.suspend();this.container.setAttribute('aria-busy','false');this.container.replaceChildren(node('p',message,'data-message'));this.onRows(this.kind,[]);}
  destroy(){this.request.cancel();this.closeDetail();}
}
