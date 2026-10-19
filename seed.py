"""Explicit and repeatable demonstration data. Never runs on ordinary startup."""
import argparse
import json
from pathlib import Path
from backend.db import connect

TOWNS=[('3550308','São Paulo','35'),('3304557','Rio de Janeiro','33'),('3106200','Belo Horizonte','31'),
 ('4106902','Curitiba','41'),('4314902','Porto Alegre','43'),('4205407','Florianópolis','42'),
 ('2927408','Salvador','29'),('2611606','Recife','26'),('5300108','Brasília','53'),('5208707','Goiânia','52'),
 ('3509502','Campinas','35'),('3170206','Uberlândia','31')]

def seed_demo(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(76290414)')
        cur.execute("SELECT 1 FROM dataset_carga WHERE nome='demo_v2'")
        if cur.fetchone(): return False
        cur.execute('SELECT EXISTS(SELECT 1 FROM market_share) OR EXISTS(SELECT 1 FROM perfil_saude_publica) OR EXISTS(SELECT 1 FROM produto_saude)')
        if cur.fetchone()[0]: raise ValueError('Seed demo requer fatos vazios; use outro banco para preservar a base existente.')
        states=json.loads((Path(__file__).parent/'static/data/estados.json').read_text(encoding='utf-8'))
        for state in states:
            cur.execute("""INSERT INTO estado(codigo_ibge,sigla,nome,regiao,fonte,sintetico)
              VALUES(%s,%s,%s,%s,'IBGE Localidades — arquivo incluído',false) ON CONFLICT(codigo_ibge) DO NOTHING""",
              (str(state['id']),state['sigla'],state['nome'],state['regiao']['nome']))
        cur.execute('SELECT codigo_ibge,id FROM estado');state_ids=dict(cur.fetchall())
        town_ids=[]
        for code,name,uf in TOWNS:
            cur.execute("""INSERT INTO municipio(codigo_ibge,nome,id_estado,fonte,sintetico)
              VALUES(%s,%s,%s,'IBGE — seleção demonstrativa de municípios',false) ON CONFLICT(codigo_ibge) DO NOTHING""",(code,name,state_ids[uf]))
            cur.execute('SELECT id FROM municipio WHERE codigo_ibge=%s',(code,));town_ids.append(cur.fetchone()[0])
        years={}
        for year in [2023,2024]:
            cur.execute('INSERT INTO serie_temporal_anual(ano) VALUES(%s) ON CONFLICT DO NOTHING',(year,))
            cur.execute('SELECT id FROM serie_temporal_anual WHERE ano=%s',(year,));years[year]=cur.fetchone()[0]
        periods=[]
        for month in [1,2]:
            cur.execute('INSERT INTO serie_temporal_mensal(id_serie_anual,ano,mes,competencia) VALUES(%s,2024,%s,%s) ON CONFLICT DO NOTHING',(years[2024],month,f'2024-{month:02d}'))
            cur.execute('SELECT id FROM serie_temporal_mensal WHERE ano=2024 AND mes=%s',(month,));periods.append(cur.fetchone()[0])
        operators=[]
        for idx in range(4):
            code=f'{990000+idx:06d}'
            cur.execute("""INSERT INTO operadora(registro_ans,cnpj,razao_social,nome_fantasia,modalidade,uf_sede,fonte,sintetico)
              VALUES(%s,%s,%s,%s,'Demonstração','SP','seed_demo_v2',true) ON CONFLICT(registro_ans) DO NOTHING""",
              (code,f'{99000000000000+idx:014d}',f'Operadora Demo {idx+1}',f'Operadora Demo {idx+1}'))
            cur.execute('SELECT id,sintetico FROM operadora WHERE registro_ans=%s',(code,));oid,synthetic=cur.fetchone()
            if not synthetic: raise ValueError('Registro ANS demo em uso por dado real; seed cancelado.')
            operators.append(oid)
            for plan_idx in range(2):
                cur.execute("""INSERT INTO produto_saude(codigo_plano_ans,nome_plano,id_operadora,tipo_contratacao,
                  segmentacao,cobertura,possui_copart,fonte,sintetico) VALUES(%s,%s,%s,'individual','hospitalar','municipal',%s,'seed_demo_v2',true) RETURNING id""",
                  (f'{990000000000+idx*10+plan_idx:012d}',f'Plano Demo {idx+1}.{plan_idx+1}',oid,bool(plan_idx)))
                pid=cur.fetchone()[0]
                for mid in town_ids[idx::4]:cur.execute('INSERT INTO abrangencia_plano(id_produto_saude,id_municipio) VALUES(%s,%s)',(pid,mid))
        for idx,mid in enumerate(town_ids):
            for month_index,sid in enumerate(periods):
                total=10000+idx*1000+month_index*500
                for oid,pct in zip(operators,[.4,.3,.2,.1]):
                    cur.execute("""INSERT INTO market_share(id_municipio,id_serie_mensal,id_operadora,total_beneficiarios,percentual_market_share,fonte,sintetico)
                      VALUES(%s,%s,%s,%s,%s,'seed_demo_v2',true)""",(mid,sid,oid,int(total*pct),pct))
            for year,aid in years.items():
                cur.execute("""INSERT INTO perfil_saude_publica(id_municipio,id_serie_anual,populacao_estimada,idh,
                  taxa_cobertura_plano_saude,renda_per_capita,indice_gini,fonte,sintetico)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,'seed_demo_v2',true)""",
                  (mid,aid,100000+idx*12000,.72+idx*.01,.2+idx*.015,1500+idx*100,.45))
        for name in ['demo_v2','produto_saude','market_share','perfil_saude_publica']:
            cur.execute("""INSERT INTO dataset_carga(nome,fonte,sintetico,notas) VALUES(%s,'seed_demo_v2',true,'Amostra sintética de 12 municípios; não usar como estatística oficial.')
              ON CONFLICT(nome) DO UPDATE SET fonte=EXCLUDED.fonte,sintetico=true,atualizado_em=now(),notas=EXCLUDED.notas""",(name,))
    return True

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--demo',action='store_true');args=parser.parse_args()
    if not args.demo: parser.error('Use --demo explicitamente para inserir dados demonstrativos.')
    conn=connect()
    try:
        with conn: changed=seed_demo(conn)
        print('Dados DEMONSTRATIVOS inseridos.' if changed else 'Demonstração já carregada; nenhuma duplicação.')
    finally:conn.close()

if __name__=='__main__':main()
