import {LatestRequest} from './api.js';
import {byId, button, node, options} from './dom.js';

// IBGE GeoJSON uses the opposite exterior winding to D3's spherical projection.
function orientForMap(feature, d3) {
  const geometry = feature.geometry;
  const polygons = geometry.type === 'MultiPolygon' ? geometry.coordinates : [geometry.coordinates];
  for (const rings of polygons) {
    if (d3.geoArea({type:'Polygon', coordinates:rings}) > 2 * Math.PI) {
      for (const ring of rings) ring.reverse();
    }
  }
  return feature;
}

export class TerritoryLayer {
  meshRequest = new LatestRequest();
  unitsRequest = new LatestRequest();
  life = new AbortController();
  features = [];
  units = [];
  uf = '';
  city = '';
  facilityCity = '';
  page = 1;
  selectedUnit = '';

  constructor(map, selectCity) {
    this.map = map;
    this.selectCity = selectCity;
    this.boundaries = map.group.append('g').attr('class','municipal-boundaries');
    this.points = map.group.append('g').attr('class','facility-points');
    const listen = (id, event, fn) => byId(id).addEventListener(event, fn, {signal:this.life.signal});
    listen('map-municipio','change',event => this.choose(event.target.value));
    listen('territory-back','click',() => this.map.selectUF(this.city ? this.uf : ''));
    listen('unit-reset','click',() => {this.markUnit(null);this.map.focus(this.uf);byId('map-municipio').focus({preventScroll:true});});
    listen('mesh-retry','click',() => this.loadMesh());
    listen('facility-prev','click',() => this.loadUnits(this.page - 1));
    listen('facility-next','click',() => this.loadUnits(this.page + 1));
    listen('facility-retry','click',() => this.loadUnits(this.page));
  }

  choose(code) {
    const feature = this.features.find(f => f.properties.code === code);
    if (feature) this.selectCity(this.uf, {codigo_ibge:code, nome:feature.properties.nome});
    else if (!code) this.map.selectUF(this.uf);
  }

  update(state) {
    const visible = state.page === 'map' && state.view === 'map';
    const uf = visible ? state.uf : '';
    const city = uf ? state.municipio : '';
    byId('territory-explorer').hidden = !uf;
    const changedUF = uf !== this.uf;
    const changedCity = city !== this.city;
    this.city = city;
    if (changedUF) {
      this.uf = uf;
      this.meshRequest.cancel();
      this.features = [];
      this.boundaries.selectAll('*').remove();
      if (uf) this.loadMesh();
    }
    byId('territory-back').textContent = city ? 'Voltar a ' + uf : 'Voltar ao Brasil';
    if (changedCity || changedUF) {
      byId('map-municipio').value = city;
      this.styleSelection();
      if (!changedUF && uf) this.map.focus(uf);
    }

    const facilityCity = state.persona === 'setor_publico' ? city : '';
    byId('facility-panel').hidden = !facilityCity;
    byId('facility-link').hidden = !facilityCity;
    if (facilityCity !== this.facilityCity) {
      this.facilityCity = facilityCity;
      this.markUnit(null);
      this.unitsRequest.cancel();
      this.units = [];
      this.drawPoints();
      if (facilityCity) {
        byId('facility-heading').textContent = 'Unidades de saúde em ' + state.municipioName;
        this.loadUnits(1);
      }
    }
  }

  loadMesh() {
    const select = byId('map-municipio');
    select.disabled = true;
    options(select, [], 'Carregando municípios…', '');
    byId('mesh-retry').hidden = true;
    byId('mesh-status').textContent = 'Consultando limites no IBGE…';
    this.meshRequest.run('/api/publico/malhas/' + this.uf, data => {
      this.features = data.features.map(feature => orientForMap(feature, this.map.d3));
      const cities = this.features.map(f => [f.properties.code, f.properties.nome]);
      cities.sort((a,b) => a[1].localeCompare(b[1], 'pt-BR'));
      options(select, cities, 'Todos os municípios', this.city);
      select.disabled = false;
      byId('mesh-status').textContent = 'Selecione um município no mapa ou na lista. A escala de cores é estadual.';
      this.drawGeometry();
      if (this.city) this.map.focus(this.uf);
    }, error => {
      options(select, [], 'Limites indisponíveis', '');
      byId('mesh-status').textContent = error.message;
      byId('mesh-retry').hidden = false;
    }, 25000);
  }

  selectedFeature() {
    return this.features.find(f => f.properties.code === this.city);
  }

  drawGeometry() {
    if (!this.map.path) return;
    const paths = this.boundaries.selectAll('path').data(this.features, f => f.properties.code)
      .join(enter => {
        const path = enter.append('path').attr('class','municipality')
          .on('click',(event,f) => {event.stopPropagation(); this.choose(f.properties.code);});
        path.append('title');
        return path;
      }).attr('d',this.map.path).attr('data-municipio', f => f.properties.code);
    paths.select('title').text(f => f.properties.nome);
    this.styleSelection();
    this.drawPoints();
  }

  styleSelection() {
    this.boundaries.selectAll('path').classed('selected', f => f.properties.code === this.city);
  }

  loadUnits(page) {
    if(this.selectedUnit)this.map.focus(this.uf);
    this.markUnit(null);
    this.page = page;
    this.units = [];
    this.drawPoints();
    const list = byId('facility-list'), status = byId('facility-status');
    list.replaceChildren();
    byId('facility-retry').hidden = true;
    byId('facility-prev').disabled = true;
    byId('facility-next').disabled = true;
    status.textContent = 'Consultando o cadastro do CNES…';
    this.unitsRequest.run('/api/publico/unidades/' + this.facilityCity + '?page=' + page, data => {
      this.units = data.items;
      this.drawPoints();
      for (const unit of this.units) {
        const item = node('li');
        item.dataset.cnes = unit.cnes;
        item.append(node('strong',unit.nome), node('span',unit.tipo + ' · CNES ' + unit.cnes));
        if (this.hasPosition(unit)) {
          const locate = button('Localizar no mapa', () => {
            this.markUnit(unit);
            this.map.focusUnit(unit);
            byId('unit-reset').focus({preventScroll:true});
            byId('territory-explorer').scrollIntoView({behavior:this.map.motion.matches?'instant':'smooth',block:'start'});
          });
          locate.setAttribute('aria-label','Localizar '+unit.nome+' no mapa');
          item.append(locate);
        }
        list.append(item);
      }
      const count = this.mappedUnits().length;
      status.textContent = this.units.length
        ? 'Fonte: CNES · Página ' + page + ' · ' + this.units.length + ' unidades nesta página, ' + count + ' com posição no mapa.'
        : 'Fonte: CNES · Nenhuma unidade retornada nesta página.';
      byId('facility-prev').disabled = page <= 1;
      byId('facility-next').disabled = !data.has_next;
    }, error => {
      status.textContent = error.message;
      byId('facility-retry').hidden = false;
      byId('facility-prev').disabled = page <= 1;
    }, 25000);
  }

  hasPosition(unit) {
    return Number.isFinite(unit.lon) && Number.isFinite(unit.lat) && (unit.lat !== 0 || unit.lon !== 0);
  }

  mappedUnits() { return this.units.filter(unit => this.hasPosition(unit)); }

  markUnit(unit) {
    this.selectedUnit = unit?.cnes || '';
    this.points.selectAll('circle').classed('selected',u => u.cnes === this.selectedUnit);
    this.zoom(this.map.d3.zoomTransform(this.map.svg.node()).k);
    byId('unit-reset').hidden = !unit;
    const caption = byId('unit-caption');
    caption.hidden = !unit;
    caption.textContent = unit ? unit.nome + ' · ' + unit.tipo : '';
  }

  drawPoints() {
    if (!this.map.projection) return;
    const points = this.points.selectAll('circle').data(this.mappedUnits(), u => u.cnes)
      .join(enter => {
        const circle = enter.append('circle').attr('class','facility-point')
          .on('click',(event,u) => {
            event.stopPropagation();
            this.markUnit(u);
            const item = byId('facility-list').querySelector('[data-cnes="' + u.cnes + '"]');
            if (item) {
              item.tabIndex = -1;
              item.focus({preventScroll:true});
              item.scrollIntoView({behavior:this.map.motion.matches?'instant':'smooth',block:'nearest'});
            }
          });
        circle.append('title');
        return circle;
      });
    points.attr('transform', u => 'translate(' + this.map.projection([u.lon,u.lat]) + ')');
    points.select('title').text(u => u.nome + ' · ' + u.tipo);
    this.zoom(this.map.d3.zoomTransform(this.map.svg.node()).k);
  }

  zoom(k) { this.points.selectAll('circle').attr('r', u => (u.cnes === this.selectedUnit ? 8 : 4.5) / k); }

  destroy() { this.meshRequest.cancel(); this.unitsRequest.cancel(); this.life.abort(); }
}

