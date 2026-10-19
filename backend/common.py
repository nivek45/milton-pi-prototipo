"""Public, aggregate ANS catalog for Pessoa Comum, isolated from mock profiles."""
from flask import Blueprint, request, abort
from backend.db import common_reader as reader
from backend.routes import filters, validate_territory, result

bp=Blueprint('pessoa_comum',__name__,url_prefix='/api/pessoa-comum')
BASE="""FROM ans_plano p JOIN operadora o ON o.registro_ans=p.registro_operadora
 WHERE p.situacao='Ativo' AND NOT o.sintetico AND o.situacao='ativa'
 AND (%(uf)s IS NULL OR EXISTS(SELECT 1 FROM ans_geo_estado g WHERE g.geo_id=p.geo_id AND g.uf=%(uf)s))
 AND (%(municipio)s IS NULL OR EXISTS(SELECT 1 FROM ans_geografia g WHERE g.geo_id=p.geo_id AND g.codigo_ibge=%(municipio)s))
"""
PLAN_FIELDS="""p.id,p.registro,p.nome AS nm,COALESCE(o.nome_fantasia,o.razao_social) AS op,
 p.contratacao AS tipo,p.segmentacao AS seg,p.abrangencia AS cob,p.fator_moderador AS fator,
 p.acomodacao,p.atualizado_em,false AS sintetico,
 CASE WHEN p.fator_moderador ILIKE '%%coparticipa%%' THEN true
 WHEN p.fator_moderador IN ('Ausente','Franquia') THEN false ELSE NULL END AS copart"""

def ready(cur):
    cur.execute("SELECT to_regclass('ans_plano') AS table_name")
    if not cur.fetchone()['table_name']: abort(503,'Catálogo ANS ainda não importado. Nenhum dado de demonstração será usado neste perfil.')
    cur.execute("SELECT 1 FROM dataset_carga WHERE nome='ans_catalogo' AND NOT sintetico")
    if not cur.fetchone(): abort(503,'Importação do catálogo ANS pendente.')

def metadata(cur):
    cur.execute("SELECT nome,fonte,sintetico,atualizado_em,notas FROM dataset_carga WHERE nome IN ('ans_catalogo','ans_geografia','ans_operadoras') ORDER BY nome")
    sources=cur.fetchall()
    cur.execute('SELECT MAX(atualizado_em) AS data FROM ans_plano')
    return {'sources':sources,'synthetic':False,'dataset':'ans_catalogo',
      'atualizado_em':cur.fetchone()['data'],
      'note':'Planos com situação Ativo e operadora ativa no cadastro ANS. Cobertura geográfica cadastrada não confirma comercialização, preço ou atendimento em um prestador específico.'}

@bp.get('/snapshot')
def snapshot():
    with reader() as cur:
        ready(cur)
        cur.execute('''SELECT e.sigla AS uf,e.codigo_ibge,e.nome,e.regiao AS reg,
          r.planos AS pl,r.operadoras AS op,false AS sintetico,
          (SELECT COUNT(*) FROM municipio m WHERE m.id_estado=e.id) AS mun,
          NULL::numeric AS ben,NULL::numeric AS cob,NULL::numeric AS mkt_share,
          NULL::numeric AS idh,NULL::numeric AS renda,NULL::numeric AS pop,
          0 AS municipios_perfil,NULL AS competencia,NULL AS ano
          FROM estado e JOIN ans_resumo r ON r.uf=e.sigla ORDER BY e.sigla''')
        states=cur.fetchall()
        cur.execute('SELECT COUNT(*) AS pl,COUNT(DISTINCT o.id) AS op '+BASE,
          {'uf':None,'municipio':None})
        national=cur.fetchone()
        meta=metadata(cur);meta.update(periods=[],years=[],competencia=None,ano=None)
    return result({'states':states,'national':national,'indicators':[],'meta':meta})

def paginated(kind):
    params=filters()
    try: page=int(request.args.get('page',1));size=int(request.args.get('page_size',20))
    except ValueError: abort(400,'Paginação inválida.')
    if not 1<=page<=100000 or not 1<=size<=100: abort(400,'Paginação fora dos limites.')
    query=request.args.get('q','').strip()
    if len(query)>100: abort(400,'Busca muito longa.')
    sort=request.args.get('sort','nm');direction=request.args.get('direction','asc')
    allowed={'nm','op','tipo','seg','cob','copart','registro','fator','acomodacao'} if kind=='planos' else {'nm','mod','uf','pl','registro_ans'}
    if sort not in allowed or direction not in ('asc','desc'): abort(400,'Ordenação inválida.')
    params.update(q='%'+query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%',limit=size,offset=(page-1)*size)
    params['contratacao']=request.args.get('contratacao','')
    params['assistencia']=request.args.get('assistencia','')
    if params['contratacao'] not in ('','Individual ou familiar','Coletivo empresarial','Coletivo por adesão') or params['assistencia'] not in ('','medica','odonto'):
        abort(400,'Filtro de plano inválido.')
    plan_filters=""" AND (%(contratacao)s='' OR p.contratacao=%(contratacao)s)
      AND (%(assistencia)s='' OR (%(assistencia)s='odonto' AND p.segmentacao='Odontológico')
        OR (%(assistencia)s='medica' AND p.segmentacao<>'Odontológico'))"""
    if kind=='planos':
        base='SELECT '+PLAN_FIELDS+' '+BASE+plan_filters+" AND (p.nome ILIKE %(q)s OR p.registro ILIKE %(q)s OR o.razao_social ILIKE %(q)s OR o.nome_fantasia ILIKE %(q)s)"
    else:
        base="""SELECT o.id,o.registro_ans,COALESCE(o.nome_fantasia,o.razao_social) AS nm,
          o.modalidade AS mod,o.uf_sede AS uf,COUNT(*) AS pl,false AS sintetico """+BASE+" AND (o.razao_social ILIKE %(q)s OR o.nome_fantasia ILIKE %(q)s OR o.registro_ans ILIKE %(q)s OR o.modalidade ILIKE %(q)s) GROUP BY o.id"
    with reader() as cur:
        ready(cur);validate_territory(cur,params)
        cur.execute('SELECT COUNT(*) AS total FROM ('+base+') rows',params);total=cur.fetchone()['total']
        cur.execute(f'SELECT * FROM ({base}) rows ORDER BY {sort} {direction} NULLS LAST,id ASC LIMIT %(limit)s OFFSET %(offset)s',params)
        items=cur.fetchall();meta=metadata(cur)
    return result({'items':items,'total':total,'page':page,'page_size':size,'meta':meta})

@bp.get('/planos')
def plans(): return paginated('planos')

@bp.get('/operadoras')
def operators(): return paginated('operadoras')

@bp.get('/planos/<int:plan_id>')
def plan_detail(plan_id):
    with reader() as cur:
        ready(cur)
        cur.execute('SELECT '+PLAN_FIELDS+',o.registro_ans,o.razao_social,p.situacao '+BASE+' AND p.id=%(id)s',{'uf':None,'municipio':None,'id':plan_id})
        plan=cur.fetchone()
        if not plan: abort(404,'Plano ativo não encontrado no catálogo consultado.')
        cur.execute('SELECT uf FROM ans_geo_estado WHERE geo_id=(SELECT geo_id FROM ans_plano WHERE id=%s) ORDER BY uf',(plan_id,))
        plan['ufs']=[row['uf'] for row in cur.fetchall()];meta=metadata(cur)
    return result({'item':plan,'meta':meta})

@bp.get('/municipios')
def municipalities():
    params=filters()
    if not params['uf']: abort(400,'Selecione uma UF.')
    with reader() as cur:
        validate_territory(cur,params)
        cur.execute('''SELECT m.codigo_ibge,m.nome FROM municipio m JOIN estado e ON e.id=m.id_estado
          WHERE e.sigla=%s AND NOT m.sintetico ORDER BY m.nome,m.codigo_ibge''',(params['uf'],))
        return result({'items':cur.fetchall()})

@bp.get('/localidades')
def localities():
    import unicodedata
    query=request.args.get('q','').strip()
    if not 2<=len(query)<=80: abort(400,'Digite entre 2 e 80 caracteres.')
    query=''.join(c for c in unicodedata.normalize('NFD',query.lower()) if not unicodedata.combining(c))
    query=query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
    with reader() as cur:
        cur.execute('''SELECT m.codigo_ibge,m.nome,e.sigla AS uf FROM municipio m
          JOIN estado e ON e.id=m.id_estado WHERE NOT m.sintetico
          AND translate(lower(m.nome),'áàâãäéèêëíìîïóòôõöúùûüç','aaaaaeeeeiiiiooooouuuuc') LIKE %s
          ORDER BY m.nome,e.sigla,m.codigo_ibge LIMIT 20''',('%'+query+'%',))
        return result({'items':cur.fetchall()})
