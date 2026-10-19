"""Isolated, repeatable functional prototype. Never target the real database."""
from backend.db import connect, DB_CONFIG
from migrate import migrate
import seed

CAPITALS = [
 ('1100205','Porto Velho','11'),('1200401','Rio Branco','12'),
 ('1302603','Manaus','13'),('1400100','Boa Vista','14'),
 ('1501402','Belém','15'),('1600303','Macapá','16'),('1721000','Palmas','17'),
 ('2111300','São Luís','21'),('2211001','Teresina','22'),('2304400','Fortaleza','23'),
 ('2408102','Natal','24'),('2507507','João Pessoa','25'),('2704302','Maceió','27'),
 ('2800308','Aracaju','28'),('3205309','Vitória','32'),
 ('5002704','Campo Grande','50'),('5103403','Cuiabá','51')]

def main():
    if DB_CONFIG['dbname'] != 'milton_demo_20261001':
        raise RuntimeError('Use exclusivamente MILTON_DB_NAME=milton_demo_20261001. A base real não pode receber esta carga.')
    migrate()
    seed.TOWNS = seed.TOWNS + [t for t in CAPITALS if t[0] not in {r[0] for r in seed.TOWNS}]
    with connect() as conn:
        seed.seed_demo(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM estado ORDER BY sigla")
            for index,(sid,) in enumerate(cur.fetchall()):
                for month in (1,2):
                    values={'vacina':(72+index%20+month,'%'),'alertas':(index%5,'quantidade'),
                            'cob_aps':(60+index%32+month,'%'),'leitos':(800+index*150+month*20,'quantidade'),
                            'prof':(2+index*.13+month*.1,'por 1.000 habitantes'),'estab':(50+index*18+month,'quantidade')}
                    for metric,(value,unit) in values.items():
                        cur.execute('''INSERT INTO indicador_saude(id_estado,metrica,competencia,valor,unidade,fonte,sintetico)
                          VALUES(%s,%s,%s,%s,%s,'Protótipo fictício para teste funcional',true)
                          ON CONFLICT(id_estado,id_municipio,metrica,competencia)
                          DO UPDATE SET valor=EXCLUDED.valor''',(sid,metric,f'2024-{month:02d}',value,unit))
            # Keep demonstration coverage internally consistent with the latest synthetic month.
            cur.execute('''UPDATE perfil_saude_publica p SET taxa_cobertura_plano_saude=x.ben::numeric/p.populacao_estimada
              FROM (SELECT f.id_municipio,SUM(f.total_beneficiarios) ben FROM market_share f
                    JOIN serie_temporal_mensal s ON s.id=f.id_serie_mensal WHERE s.competencia='2024-02'
                    GROUP BY f.id_municipio) x WHERE p.id_municipio=x.id_municipio''')
            cur.execute("UPDATE dataset_carga SET notas='Demonstração fictícia: 27 estados, 29 municípios, 4 operadoras e 8 planos. Não usar como estatística oficial.' WHERE fonte='seed_demo_v2'")
            cur.execute("INSERT INTO dataset_carga(nome,fonte,sintetico,notas) VALUES('indicador_saude','Protótipo fictício',true,'Seis métricas nas 27 UFs, em dois meses de teste.') ON CONFLICT(nome) DO NOTHING")
    print('Protótipo carregado no banco isolado milton_demo_20261001.')

if __name__ == '__main__': main()
