"""PostgreSQL integration tests in an isolated, temporary schema."""
from pathlib import Path
from uuid import uuid4
from contextlib import contextmanager
import pytest
import psycopg2
from psycopg2 import sql
from backend import db
from backend.routes import app
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='session',autouse=True)
def isolated_schema():
    name='milton_test_'+uuid4().hex
    conn=db.connect();conn.autocommit=True
    with conn.cursor() as cur:cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(name)))
    db.close_pool();db.DB_CONFIG['options']=f'-c search_path={name},public'
    setup=db.connect()
    with setup:
        with setup.cursor() as cur:cur.execute((ROOT/'schema.sql').read_text(encoding='utf-8'))
    setup.close()
    yield name
    db.close_pool();db.DB_CONFIG.pop('options',None)
    with conn.cursor() as cur:cur.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(name)))
    conn.close()

def execute(statement,params=None):
    conn=db.connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(statement,params)
                return cur.fetchall() if cur.description else None
    finally:conn.close()

@pytest.fixture(autouse=True)
def fixture_data(isolated_schema):
    tables=execute('SELECT tablename FROM pg_tables WHERE schemaname=%s',(isolated_schema,))
    conn=db.connect()
    with conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(sql.SQL(',').join(sql.Identifier(isolated_schema,row[0]) for row in tables)))
    conn.close()
    execute("""
      INSERT INTO estado(codigo_ibge,sigla,nome,regiao) VALUES('35','SP','São Paulo','Sudeste'),('33','RJ','Rio de Janeiro','Sudeste');
      INSERT INTO municipio(codigo_ibge,nome,id_estado) VALUES('3550308','São Paulo',1),('3509502','Campinas',1),('3304557','Rio de Janeiro',2);
      INSERT INTO serie_temporal_anual(ano) VALUES(2023),(2024),(2025);
      INSERT INTO serie_temporal_mensal(id_serie_anual,ano,mes,competencia) VALUES(2,2024,1,'2024-01'),(2,2024,2,'2024-02');
      INSERT INTO operadora(registro_ans,cnpj,razao_social,nome_fantasia,modalidade,uf_sede) VALUES
       ('111111','11111111111111','Operadora A','Operadora A','Cooperativa','RJ'),('222222','22222222222222','Operadora B','Operadora B','Cooperativa','SP');
      INSERT INTO produto_saude(codigo_plano_ans,nome_plano,id_operadora,tipo_contratacao,segmentacao,cobertura) VALUES
       ('1','Plano A1',1,'individual','hospitalar','municipal'),('2','Plano A2',1,'individual','hospitalar','municipal'),('3','Plano B',2,'individual','hospitalar','municipal');
      INSERT INTO abrangencia_plano(id_produto_saude,id_municipio) VALUES(1,1),(2,3),(3,2);
      INSERT INTO market_share(id_municipio,id_serie_mensal,id_operadora,total_beneficiarios,percentual_market_share) VALUES
       (1,1,1,100,1),(1,2,1,120,.6),(1,2,2,80,.4),(2,2,1,200,1),(2,2,2,0,0),(3,2,1,50,1);
      INSERT INTO perfil_saude_publica(id_municipio,id_serie_anual,populacao_estimada,taxa_cobertura_plano_saude,idh,renda_per_capita) VALUES
       (1,1,900,.6,.7,1000),(1,2,1000,.5,.8,2000),(2,2,9000,.1,.6,1000);
    """)

@pytest.fixture
def client():return app.test_client()

def test_snapshot_grain_and_latest_fact_year(client):
    response=client.get('/api/snapshot');assert response.status_code==200
    data=response.json;sp=next(x for x in data['states'] if x['uf']=='SP')
    assert sp['ben']==400 and sp['op']==2 and sp['mkt_share']==80
    assert sp['cob']==pytest.approx(14) and sp['idh']==pytest.approx(.7)
    assert data['national']['ben']==450 and data['national']['op']==2
    assert data['meta']['ano']==2024

def test_operator_grain_and_operation_not_headquarters(client):
    data=client.get('/api/operadoras?uf=SP').json
    a=next(x for x in data['items'] if x['nm']=='Operadora A')
    assert a['uf']=='RJ' and a['ben']==320 and a['pl']==2 and a['pct']==80
    assert sum(x['pct'] for x in data['items'])==100

def test_period_and_zero(client):
    assert client.get('/api/snapshot?competencia=2024-01').json['national']['ben']==100
    data=client.get('/api/operadoras?municipio=3509502').json
    b=next(x for x in data['items'] if x['nm']=='Operadora B')
    assert b['ben']==0 and b['pct']==0
    assert client.get('/api/snapshot?competencia=2026-01').json['national']['ben'] is None

def test_missing_profiles(client):
    rj=next(x for x in client.get('/api/snapshot').json['states'] if x['uf']=='RJ')
    assert rj['cob'] is None and rj['idh'] is None

def test_plan_coverage(client):
    assert [x['nm'] for x in client.get('/api/planos?municipio=3550308').json['items']]==['Plano A1']
    assert client.get('/api/planos?uf=RJ').json['total']==1

def test_pagination_search_order(client):
    first=client.get('/api/planos?page_size=1&sort=nm&direction=asc').json
    second=client.get('/api/planos?page_size=1&page=2&sort=nm&direction=asc').json
    assert first['total']==3 and first['items'][0]['id']!=second['items'][0]['id']
    assert client.get('/api/planos?q=Plano%20B').json['total']==1

@pytest.mark.parametrize('path',['/api.py','/./api.py','/%2e/api.py','/schema.sql','/docker-compose.yml','/.git/HEAD','/static/../api.py','/static/%2e%2e/api.py'])
def test_source_exposure(client,path):assert client.get(path).status_code==404

def test_history_and_cors(client):
    response=client.get('/api/historico',headers={'Origin':'https://example.invalid'})
    assert response.status_code==403 and 'Access-Control-Allow-Origin' not in response.headers
    assert "script-src 'self'" in response.headers['Content-Security-Policy']

@pytest.mark.parametrize('query',['page=0','page_size=1000','sort=nm;DROP%20TABLE%20estado','direction=sideways','uf=XX','uf=SP%27','competencia=2024-99','ano=no','municipio=123','uf=RJ&municipio=3550308'])
def test_inputs(client,query):assert client.get('/api/operadoras?'+query).status_code in (400,404)

def test_database_error(client,monkeypatch):
    from backend import routes
    @contextmanager
    def fail():
        raise psycopg2.OperationalError('test')
        yield
    monkeypatch.setattr(routes,'reader',fail)
    response=client.get('/api/health');assert response.status_code==503 and response.is_json

def test_constraints():
    with pytest.raises(psycopg2.errors.CheckViolation):execute('UPDATE market_share SET total_beneficiarios=-1')
    with pytest.raises(psycopg2.errors.CheckViolation):execute('UPDATE perfil_saude_publica SET idh=2')
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):execute("INSERT INTO serie_temporal_mensal(id_serie_anual,ano,mes,competencia) VALUES(1,2024,3,'2024-03')")

def test_etl_atomic_rollback(monkeypatch):
    import fetch_real_data as etl
    class Response:
        content=('Registro_ANS;CNPJ;Razao_Social;Modalidade\n333333;33333333333333;Nova;Cooperativa\n444444;33333333333333;Duplicada;Cooperativa\n').encode('latin-1')
    monkeypatch.setattr(etl,'response',lambda url:Response())
    conn=db.connect()
    try:
        with pytest.raises(psycopg2.errors.UniqueViolation):
            with conn:etl.fetch_operadoras(conn)
    finally:conn.close()
    assert execute("SELECT COUNT(*) FROM operadora WHERE registro_ans='333333'")[0][0]==0

def test_import_replaces_samples(monkeypatch):
    import fetch_real_data as etl
    import json
    class Response:
        def json(self):return json.loads((ROOT/'static/data/estados.json').read_text(encoding='utf-8'))
    monkeypatch.setattr(etl,'response',lambda url:Response())
    conn=db.connect()
    try:
        with conn:etl.fetch_estados(conn)
        with conn:etl.fetch_estados(conn)
    finally:conn.close()
    assert execute('SELECT COUNT(*) FROM estado')[0][0]==27
    assert execute("SELECT sintetico FROM estado WHERE sigla='SP'")[0][0] is False

def test_indicator_grain_units(client):
    execute("INSERT INTO indicador_saude(id_estado,metrica,competencia,valor,unidade,fonte) VALUES(1,'vacina','2024-02',85,'%','test')")
    assert client.get('/api/snapshot').json['indicators'][0]['valor']==85
    with pytest.raises(psycopg2.errors.CheckViolation):execute("INSERT INTO indicador_saude(id_estado,metrica,competencia,valor,unidade,fonte) VALUES(1,'vacina','2024-01',185,'%','test')")
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):execute("INSERT INTO indicador_saude(id_estado,id_municipio,metrica,competencia,valor,unidade,fonte) VALUES(2,1,'leitos','2024-02',10,'quantidade','test')")

def test_cadop_uppercase_utf8(monkeypatch):
    import fetch_real_data as etl
    class Response:
        content='REGISTRO_ANS;CNPJ;RAZAO_SOCIAL;MODALIDADE\n333333;33333333333333;Saúde São Paulo;Cooperativa\n'.encode('utf-8')
    monkeypatch.setattr(etl,'response',lambda url:Response())
    conn=db.connect()
    try:
        with conn:etl.fetch_operadoras(conn)
        with conn:etl.fetch_operadoras(conn)
    finally:conn.close()
    assert execute("SELECT razao_social,sintetico FROM operadora WHERE registro_ans='333333'")==[('Saúde São Paulo',False)]

def test_locality_search_accent_and_code(client):
    response=client.get('/api/localidades?q=sao')
    assert response.status_code==200
    assert response.json['items']==[{'codigo_ibge':'3550308','nome':'São Paulo','uf':'SP'}]
    assert client.get('/api/localidades?q=São').json==response.json
    assert client.get('/api/localidades?q=campinas').json['items'][0]['codigo_ibge']=='3509502'

def test_locality_search_limits_and_literal_wildcards(client):
    assert client.get('/api/localidades?q=a').status_code==400
    assert client.get('/api/localidades?q='+'a'*81).status_code==400
    assert client.get('/api/localidades?q=%25%25').json['items']==[]
    assert client.get('/api/localidades?q=%27%20OR%201=1--').json['items']==[]

