import {METRICS,metricValue,metricFormat,finite} from './config.js';
import {LatestRequest} from './api.js';
import {byId,node,button,text} from './dom.js';

export class BrazilMap {
  geo=null;state=null;lastUF=null;frame=0;tipFrame=0;request=new LatestRequest();
  constructor(selectUF) {
    this.selectUF=selectUF;this.d3=window.d3;
    this.svg=this.d3.select('#map-svg');
    this.group=this.svg.append('g');
    this.paths=this.group.append('g');this.labels=this.group.append('g');
    this.zoom=this.d3.zoom().scaleExtent([1,20]).on('zoom',event=>{
      this.group.attr('transform',event.transform);
      this.labels.selectAll('text').attr('font-size',Math.min(16,11*Math.sqrt(event.transform.k))/event.transform.k);
    });
    this.svg.call(this.zoom).on('dblclick.zoom',null);
    this.observer=new ResizeObserver(()=>{
      cancelAnimationFrame(this.frame);this.frame=requestAnimationFrame(()=>this.resize());
    });
    this.observer.observe(byId('map-container'));
    this.motion=matchMedia('(prefers-reduced-motion: reduce)');
  }
  duration(value){return this.motion.matches?0:value;}
  load() {
    const overlay=byId('map-loading');overlay.style.display='flex';
    overlay.replaceChildren(node('div','Carregando malha estadual…','loading-chip'));
    return this.request.run('/static/data/brazil-states.geojson',geo=>{
      if(geo.type!=='FeatureCollection'||!Array.isArray(geo.features))throw new Error('Malha inválida.');
      this.geo=geo;overlay.style.display='none';this.resize();
    },error=>{
      overlay.style.display='flex';const content=node('div','','loading-chip');
      content.append(node('span','Não foi possível carregar o mapa. '+error.message),button('Recarregar mapa',()=>this.load()));
      overlay.replaceChildren(content);
    });
  }
  resize() {
    if(!this.geo)return;
    const rect=byId('map-container').getBoundingClientRect();
    if(rect.width<10||rect.height<10)return;
    this.width=rect.width;this.height=rect.height;
    this.svg.attr('viewBox',`0 0 ${this.width} ${this.height}`).attr('width',this.width).attr('height',this.height);
    this.projection=this.d3.geoMercator().fitExtent([[25,this.width<500?145:100],[this.width-25,this.height-105]],this.geo);
    this.path=this.d3.geoPath(this.projection);
    this.draw(true);this.focus(this.state?.uf||'',false);
  }
  update(state) {
    this.state=state;this.hideTooltip();
    if(!this.geo||!this.path)return;
    this.draw(false);
    if(state.uf!==this.lastUF)this.focus(state.uf);
    this.lastUF=state.uf;
  }
  scale() {
    const metric=this.state?.metric||'cob_plano';
    const spec=METRICS[metric];
    const values=(this.geo?.features||[]).map(d=>metricValue(this.state?.snapshot,d.properties.sigla,metric)).filter(finite);
    const domain=spec.domain||[0,Math.max(1,...values)];
    return this.d3.scaleSequential().domain(domain).interpolator(this.d3.interpolateRgbBasis(['#24362d','#40845f','#b0e5c7'])).clamp(true);
  }
  draw(geometry) {
    const metric=this.state?.metric||'cob_plano',scale=this.scale();
    const fill=d=>{const value=metricValue(this.state?.snapshot,d.properties.sigla,metric);return finite(value)?scale(value):'#33363b';};
    const paths=this.paths.selectAll('path').data(this.geo.features,d=>d.properties.sigla).join(
      enter=>enter.append('path').attr('class','state-feature').attr('fill','#33363b')
        .attr('tabindex',0).attr('role','button')
        .on('pointerenter',(event,d)=>this.showTooltip(event,d))
        .on('pointermove',event=>this.moveTooltip(event))
        .on('pointerleave',()=>this.hideTooltip())
        .on('focus',(event,d)=>this.showTooltip(event,d))
        .on('blur',()=>this.hideTooltip())
        .on('click',(event,d)=>{event.stopPropagation();this.hideTooltip();this.selectUF(d.properties.sigla);})
        .on('keydown',(event,d)=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();this.selectUF(d.properties.sigla);}if(event.key==='Escape')this.hideTooltip();}),
      update=>update,exit=>exit.interrupt('metric').remove());
    if(geometry)paths.attr('d',this.path);
    paths.attr('data-uf',d=>d.properties.sigla)
      .attr('aria-label',d=>`${d.properties.name}: ${metricFormat(metricValue(this.state?.snapshot,d.properties.sigla,metric),metric)}. Selecionar estado.`)
      .attr('aria-pressed',d=>String(this.state?.uf===d.properties.sigla))
      .classed('selected',d=>this.state?.uf===d.properties.sigla)
      .interrupt('metric').transition('metric').duration(this.duration(240)).attr('fill',fill);
    const labels=this.labels.selectAll('text').data(this.geo.features,d=>d.properties.sigla)
      .join('text').attr('class','state-label').attr('aria-hidden','true').text(d=>d.properties.sigla);
    if(geometry)labels.attr('x',d=>this.path.centroid(d)[0]).attr('y',d=>this.path.centroid(d)[1]).attr('font-size',9);
    this.renderLegend(scale,metric);this.drawMini(scale,fill);
  }
  renderLegend(scale,metric) {
    text('legend-label',METRICS[metric].label);
    const [min,max]=scale.domain(),bar=document.querySelector('.legend-bar'),labels=document.querySelector('.legend-values');
    const available=this.geo.features.some(d=>finite(metricValue(this.state?.snapshot,d.properties.sigla,metric)));
    if(!available){bar.replaceChildren();labels.replaceChildren();text('legend-note','Sem dados cadastrados para esta camada e período.');return;}
    const samples=[0,0.25,0.5,0.75,1].map(t=>min+(max-min)*t);
    bar.replaceChildren(...samples.map(value=>{const el=node('div','','legend-swatch');el.style.background=scale(value);return el;}));
    labels.replaceChildren(...samples.map(value=>node('span',metricFormat(value,metric))));
    text('legend-note','Cinza: sem dado • Escala compartilhada com o minimapa');
  }
  drawMini(scale,fill) {
    const svg=this.d3.select('#pip-svg');
    const projection=this.d3.geoMercator().fitExtent([[4,4],[202,100]],this.geo);
    const path=this.d3.geoPath(projection);
    svg.attr('viewBox','0 0 206 104').selectAll('path').data(this.geo.features,d=>d.properties.sigla).join('path')
      .attr('d',path).attr('fill',fill).attr('stroke',d=>d.properties.sigla===this.state?.uf?'#fff':'#151619')
      .attr('stroke-width',d=>d.properties.sigla===this.state?.uf?1.4:0.5);
  }
  focus(uf,animate=true) {
    if(!this.path)return;
    const feature=this.geo.features.find(d=>d.properties.sigla===uf);
    let transform=this.d3.zoomIdentity;
    if(feature){
      const [[x0,y0],[x1,y1]]=this.path.bounds(feature);
      const k=Math.min(14,0.65/Math.max((x1-x0)/this.width,(y1-y0)/this.height));
      transform=transform.translate(this.width/2-k*(x0+x1)/2,this.height/2-k*(y0+y1)/2).scale(k);
    }
    this.svg.interrupt().transition().duration(animate?this.duration(300):0).call(this.zoom.transform,transform);
  }
  zoomBy(factor){if(this.path)this.svg.interrupt().transition().duration(this.duration(180)).call(this.zoom.scaleBy,factor);}
  showTooltip(event,feature) {
    const metric=this.state?.metric||'cob_plano',uf=feature.properties.sigla,tip=byId('tooltip');
    tip.replaceChildren(node('strong',feature.properties.name),node('div',METRICS[metric].label),
      node('div',metricFormat(metricValue(this.state?.snapshot,uf,metric),metric),'highlight'),node('small','Selecione o estado para consultar os dados.'));
    tip.hidden=false;tip.setAttribute('aria-hidden','false');tip.classList.add('show');
    const observation=this.state?.snapshot?.indicators.find(i=>i.uf===uf && i.metrica===metric);
    if(observation)tip.append(node('small',`${observation.fonte} · ${observation.competencia}${observation.sintetico?' · Demonstração':''}`));
    if(event.type==='focus'){
      const box=event.target.getBoundingClientRect();this.positionTooltip(box.x+box.width/2,box.y+box.height/2);
    }else this.moveTooltip(event);
  }
  moveTooltip(event){const{x,y}={x:event.clientX,y:event.clientY};cancelAnimationFrame(this.tipFrame);this.tipFrame=requestAnimationFrame(()=>this.positionTooltip(x,y));}
  positionTooltip(x,y){const tip=byId('tooltip');tip.style.left=Math.max(8,Math.min(x+14,innerWidth-270))+'px';tip.style.top=Math.max(8,Math.min(y+14,innerHeight-160))+'px';}
  hideTooltip(){cancelAnimationFrame(this.tipFrame);const tip=byId('tooltip');if(tip){tip.classList.remove('show');tip.hidden=true;tip.setAttribute('aria-hidden','true');}}
  destroy(){this.request.cancel();this.observer.disconnect();cancelAnimationFrame(this.frame);this.hideTooltip();this.svg.interrupt().on('.zoom',null);this.paths.selectAll('*').interrupt('metric').on('pointerenter pointermove pointerleave focus blur click keydown',null);}
}
