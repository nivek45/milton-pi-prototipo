"""Same-origin API, explicit periods, and provenance."""
import logging
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from flask import Flask, jsonify, request, abort, send_file
from werkzeug.exceptions import HTTPException
import psycopg2
from psycopg2.pool import PoolError
from backend.db import reader
from backend import queries

ROOT = Path(__file__).resolve().parent.parent
app = Flask(__name__, static_folder=str(ROOT / 'static'), static_url_path='/static')
app.json.sort_keys = False

def clean(value):
    if isinstance(value, Decimal): return float(value)
    if isinstance(value, (date, datetime)): return value.isoformat()
    if isinstance(value, dict): return {k: clean(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    return value

def result(value):
    return jsonify(clean(value))

def filters():
    uf = request.args.get('uf', '').upper() or None
    municipality = request.args.get('municipio') or None
    period = request.args.get('competencia') or None
    year = request.args.get('ano') or None
    if uf and not re.fullmatch(r'[A-Z]{2}', uf): abort(400, 'UF inválida.')
    if municipality and not re.fullmatch(r'\d{7}', municipality): abort(400, 'Código IBGE municipal inválido.')
    if period and not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', period): abort(400, 'Competência deve usar YYYY-MM.')
    if year and (not year.isdigit() or not 2000 <= int(year) <= 2100): abort(400, 'Ano inválido.')
    return dict(uf=uf, municipio=municipality, competencia=period, ano=int(year) if year else None)

def validate_territory(cur, params):
    if params['uf']:
        cur.execute('SELECT 1 FROM estado WHERE sigla=%s', (params['uf'],))
        if not cur.fetchone(): abort(404, 'UF não cadastrada.')
    if params['municipio']:
        cur.execute('''SELECT 1 FROM municipio m JOIN estado e ON e.id=m.id_estado
          WHERE m.codigo_ibge=%s AND (%s IS NULL OR e.sigla=%s)''',
          (params['municipio'],params['uf'],params['uf']))
        if not cur.fetchone(): abort(404, 'Município não encontrado neste território.')

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
    if request.path.startswith('/api/'): response.headers['Cache-Control'] = 'no-store'
    return response

@app.errorhandler(HTTPException)
def http_error(exc):
    return result({'error': exc.description, 'status': exc.code}), exc.code

@app.errorhandler(psycopg2.Error)
def database_error(exc):
    logging.exception('Database request failed')
    return result({'error': 'Banco indisponível. Tente novamente.', 'status':503}),503

@app.errorhandler(PoolError)
def pool_error(exc):
    return result({'error':'Servidor ocupado. Tente novamente.', 'status':503}),503

@app.errorhandler(Exception)
def unexpected_error(exc):
    logging.exception('Unexpected application error')
    return result({'error':'Não foi possível concluir a consulta.', 'status':500}),500

@app.get('/')
def index():
    return send_file(ROOT / 'dashboard.html')

@app.get('/api/health')
def health():
    with reader() as cur: cur.execute('SELECT 1')
    return result({'status':'ok'})

@app.get('/api/snapshot')
@app.get('/api/estados-summary')
def snapshot():
    params=filters()
    with reader() as cur:
        validate_territory(cur,params)
        cur.execute(queries.SUMMARY,params)
        states=cur.fetchall()
        cur.execute(queries.NATIONAL,params)
        national=cur.fetchone()
        cur.execute('SELECT nome,fonte,sintetico,atualizado_em,notas FROM dataset_carga ORDER BY nome')
        sources=cur.fetchall()
        cur.execute('''SELECT DISTINCT s.competencia FROM serie_temporal_mensal s
          JOIN market_share f ON f.id_serie_mensal=s.id ORDER BY s.competencia DESC''')
        periods=[r['competencia'] for r in cur.fetchall()]
        cur.execute('''SELECT DISTINCT s.ano FROM serie_temporal_anual s
          JOIN perfil_saude_publica p ON p.id_serie_anual=s.id ORDER BY s.ano DESC''')
        years=[r['ano'] for r in cur.fetchall()]
        cur.execute('''SELECT DISTINCT ON(e.sigla,i.metrica) e.sigla AS uf,i.metrica,i.valor,
          i.unidade,i.fonte,i.sintetico,i.competencia
          FROM indicador_saude i JOIN estado e ON e.id=i.id_estado
          WHERE i.id_municipio IS NULL AND (%s IS NULL OR i.competencia=%s)
          ORDER BY e.sigla,i.metrica,i.competencia DESC''',(params['competencia'],params['competencia']))
        indicators=cur.fetchall()
    return result({'states':states,'national':national,'indicators':indicators,
      'meta':{'sources':sources,'periods':periods,'years':years,
      'competencia':states[0]['competencia'] if states else None,
      'ano':states[0]['ano'] if states else None,
      'synthetic':any(s['sintetico'] for s in states) or any(s['sintetico'] for s in sources) or any(s['sintetico'] for s in indicators),
      'note':'Cobertura ponderada pela população dos municípios com dados; IDH é média municipal, não IDH oficial estadual.'}})

def page_query(sql, sort_columns, search_columns, default_sort):
    params=filters()
    try:
        page=int(request.args.get('page',1)); size=int(request.args.get('page_size',20))
    except ValueError: abort(400,'Paginação inválida.')
    if page<1 or page>100000 or not 1<=size<=100: abort(400,'Paginação fora dos limites.')
    sort=request.args.get('sort',default_sort)
    direction=request.args.get('direction','desc')
    if sort not in sort_columns or direction not in ('asc','desc'): abort(400,'Ordenação inválida.')
    search=request.args.get('q','').strip()
    if len(search)>100: abort(400,'Busca muito longa.')
    params.update(q='%'+search+'%',limit=size,offset=(page-1)*size)
    # Identifiers come exclusively from server-owned whitelists.
    search_sql=' OR '.join(f'COALESCE({c}::text,\'\') ILIKE %(q)s' for c in search_columns)
    base=f'SELECT * FROM ({sql}) records WHERE ({search_sql})'
    with reader() as cur:
        validate_territory(cur,params)
        cur.execute(f'SELECT COUNT(*) AS total FROM ({base}) counted',params)
        total=cur.fetchone()['total']
        cur.execute(f'{base} ORDER BY {sort} {direction} NULLS LAST,id ASC LIMIT %(limit)s OFFSET %(offset)s',params)
        rows=cur.fetchall()
    return result({'items':rows,'total':total,'page':page,'page_size':size,
                   'meta':{'territory':'atuação/abrangência','competencia':params['competencia'],'ano':params['ano']}})

@app.get('/api/operadoras')
@app.get('/api/market-share')
def operators():
    return page_query(queries.OPERATORS,{'nm','mod','uf','ben','pct','pl'},['nm','mod','uf'],'ben')

@app.get('/api/market-share/<uf>')
def legacy_uf(uf):
    from flask import redirect
    if not re.fullmatch('[A-Za-z]{2}',uf): abort(400,'UF inválida.')
    return redirect('/api/market-share?uf='+uf.upper(),code=307)

@app.get('/api/planos')
def plans():
    return page_query(queries.PLANS,{'nm','op','tipo','cob','copart','mun'},['nm','op','tipo'],'nm')

@app.get('/api/perfil-saude')
def profiles():
    return page_query(queries.PROFILES,{'m','uf','pop','idh','cob','renda','gini'},['m','uf'],'idh')

@app.get('/api/municipios')
def municipalities():
    params=filters()
    if not params['uf']: abort(400,'Selecione uma UF.')
    with reader() as cur:
        validate_territory(cur,params)
        cur.execute('''SELECT m.codigo_ibge,m.nome FROM municipio m JOIN estado e ON e.id=m.id_estado
           WHERE e.sigla=%s ORDER BY m.nome,m.codigo_ibge''',(params['uf'],))
        rows=cur.fetchall()
    return result({'items':rows})

@app.get('/api/stats')
def stats():
    with reader() as cur:
        cur.execute('''SELECT 'produto_saude' AS tabela, COUNT(*) AS linhas FROM produto_saude WHERE ativo
          UNION ALL SELECT 'operadora',COUNT(*) FROM operadora
          UNION ALL SELECT 'municipio',COUNT(*) FROM municipio
          UNION ALL SELECT 'market_share',COUNT(*) FROM market_share
          UNION ALL SELECT 'perfil_saude_publica',COUNT(*) FROM perfil_saude_publica
          UNION ALL SELECT 'estado',COUNT(*) FROM estado''')
        rows=cur.fetchall()
    return result({'items':rows,'exact':True,'note':'Planos: somente ativos. Market share e perfis: registros de todos os períodos.'})

@app.get('/api/localidades')
def locality_search():
    import unicodedata
    query=request.args.get('q','').strip()
    if not 2 <= len(query) <= 80: abort(400,'Digite entre 2 e 80 caracteres para buscar uma cidade.')
    query=''.join(c for c in unicodedata.normalize('NFD',query.lower()) if not unicodedata.combining(c))
    # Treat wildcard characters as literal input, not as an unbounded search.
    query=query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
    with reader() as cur:
        cur.execute('''SELECT m.codigo_ibge,m.nome,e.sigla AS uf
          FROM municipio m JOIN estado e ON e.id=m.id_estado
          WHERE translate(lower(m.nome),'áàâãäéèêëíìîïóòôõöúùûüç','aaaaaeeeeiiiiooooouuuuc') LIKE %s
          ORDER BY m.nome,e.sigla,m.codigo_ibge LIMIT 20''',('%'+query+'%',))
        rows=cur.fetchall()
    return result({'items':rows})

@app.get('/api/historico')
def history():
    abort(403,'Históricos individuais são privados e não estão disponíveis neste observatório público.')
