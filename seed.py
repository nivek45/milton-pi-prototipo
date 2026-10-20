"""Explicit and repeatable demonstration data for all 27 Brazilian states and personas.
Never runs on ordinary startup; requires --demo.
"""
import argparse
import json
from pathlib import Path
from backend.db import connect

MUNICIPALITIES = [
    # 27 Capitals + key polo cities
    # (codigo_ibge, nome, uf_sigla, populacao, idh, renda, gini, mortalidade)
    ('1100205', 'Porto Velho', 'RO', 548952, 0.736, 1750.0, 0.49, 13.5),
    ('1200401', 'Rio Branco', 'AC', 419452, 0.727, 1620.0, 0.51, 14.2),
    ('1302603', 'Manaus', 'AM', 2255903, 0.737, 1980.0, 0.52, 13.8),
    ('1400100', 'Boa Vista', 'RR', 436591, 0.752, 1890.0, 0.48, 12.9),
    ('1501402', 'Belém', 'PA', 1499641, 0.746, 1720.0, 0.50, 13.1),
    ('1600303', 'Macapá', 'AP', 522357, 0.733, 1680.0, 0.49, 14.5),
    ('1721000', 'Palmas', 'TO', 313349, 0.788, 2250.0, 0.47, 11.2),
    ('2111300', 'São Luís', 'MA', 1108975, 0.768, 1850.0, 0.51, 15.1),
    ('2211001', 'Teresina', 'PI', 868075, 0.751, 1910.0, 0.50, 13.7),
    ('2304400', 'Fortaleza', 'CE', 2703391, 0.754, 2100.0, 0.53, 12.4),
    ('2408102', 'Natal', 'RN', 890480, 0.763, 2050.0, 0.49, 11.8),
    ('2507507', 'João Pessoa', 'PB', 817511, 0.763, 2180.0, 0.52, 11.5),
    ('2611606', 'Recife', 'PE', 1653461, 0.772, 2450.0, 0.54, 12.2),
    ('2704302', 'Maceió', 'AL', 1025360, 0.721, 1780.0, 0.53, 14.8),
    ('2800308', 'Aracaju', 'SE', 664908, 0.770, 2290.0, 0.51, 13.0),
    ('2927408', 'Salvador', 'BA', 2886698, 0.759, 2350.0, 0.55, 13.9),
    ('3106200', 'Belo Horizonte', 'MG', 2521564, 0.810, 3120.0, 0.48, 9.8),
    ('3170206', 'Uberlândia', 'MG', 699097, 0.789, 2650.0, 0.46, 10.1),
    ('3205309', 'Vitória', 'ES', 365855, 0.845, 3890.0, 0.47, 8.9),
    ('3304557', 'Rio de Janeiro', 'RJ', 6747815, 0.799, 3450.0, 0.51, 11.0),
    ('3303302', 'Niterói', 'RJ', 515317, 0.837, 4120.0, 0.46, 9.2),
    ('3550308', 'São Paulo', 'SP', 12325232, 0.805, 3950.0, 0.49, 10.5),
    ('3509502', 'Campinas', 'SP', 1213792, 0.805, 3320.0, 0.47, 9.5),
    ('4106902', 'Curitiba', 'PR', 1948626, 0.823, 3480.0, 0.46, 8.8),
    ('4113700', 'Londrina', 'PR', 575377, 0.778, 2710.0, 0.45, 9.1),
    ('4205407', 'Florianópolis', 'SC', 508826, 0.847, 4210.0, 0.44, 7.9),
    ('4209102', 'Joinville', 'SC', 597658, 0.809, 2980.0, 0.43, 8.2),
    ('4314902', 'Porto Alegre', 'RS', 1488252, 0.805, 3550.0, 0.47, 9.4),
    ('4305108', 'Caxias do Sul', 'RS', 517451, 0.782, 2890.0, 0.44, 8.7),
    ('5002704', 'Campo Grande', 'MS', 906092, 0.784, 2750.0, 0.47, 10.8),
    ('5103403', 'Cuiabá', 'MT', 618124, 0.785, 2900.0, 0.48, 11.4),
    ('5208707', 'Goiânia', 'GO', 1536097, 0.799, 2850.0, 0.48, 10.9),
    ('5300108', 'Brasília', 'DF', 3055149, 0.824, 4650.0, 0.49, 9.6),
]

OPERATORS = [
    ('343889', '00571111000101', 'Unimed do Brasil Cooperativa Central', 'Unimed Nacional', 'Cooperativa Médica', 'SP'),
    ('005711', '00571122000102', 'Bradesco Saúde S.A.', 'Bradesco Saúde', 'Seguradora Especializada em Saúde', 'SP'),
    ('006246', '00624633000103', 'Sul América Companhia de Seguro Saúde', 'SulAmérica Saúde', 'Seguradora Especializada em Saúde', 'RJ'),
    ('368253', '36825344000104', 'Amil Assistência Médica Internacional S.A.', 'Amil', 'Medicina de Grupo', 'SP'),
    ('005231', '00523155000105', 'NotreDame Intermédica Saúde S.A.', 'NotreDame Intermédica', 'Medicina de Grupo', 'SP'),
    ('305146', '30514666000106', 'Hapvida Assistência Médica S.A.', 'Hapvida', 'Medicina de Grupo', 'CE'),
    ('417530', '41753077000107', 'Porto Seguro - Seguro Saúde S.A.', 'Porto Seguro Saúde', 'Seguradora Especializada em Saúde', 'SP'),
    ('313432', '31343288000108', 'Seguros Unimed', 'Seguros Unimed', 'Seguradora Especializada em Saúde', 'SP'),
]

REGIONAL_PROFILES = {
    'N':  {'cob_base': 0.14, 'vacina': 76.5, 'cob_aps': 84.0, 'prof_base': 2.1, 'leitos_k': 1.9, 'alertas': 1},
    'NE': {'cob_base': 0.16, 'vacina': 81.2, 'cob_aps': 87.5, 'prof_base': 2.4, 'leitos_k': 2.2, 'alertas': 2},
    'CO': {'cob_base': 0.28, 'vacina': 83.4, 'cob_aps': 78.0, 'prof_base': 3.2, 'leitos_k': 2.5, 'alertas': 0},
    'SE': {'cob_base': 0.38, 'vacina': 87.8, 'cob_aps': 71.5, 'prof_base': 3.9, 'leitos_k': 2.6, 'alertas': 0},
    'S':  {'cob_base': 0.32, 'vacina': 89.1, 'cob_aps': 79.2, 'prof_base': 3.6, 'leitos_k': 2.7, 'alertas': 0},
}

def seed_demo(conn, force=False):
    with conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(76290414)')
        cur.execute("SELECT 1 FROM dataset_carga WHERE nome='demo_v2'")
        has_demo = cur.fetchone() is not None

        if has_demo and not force:
            cur.execute("SELECT count(*) FROM indicador_saude")
            if cur.fetchone()[0] > 0:
                return False

        if force or has_demo:
            cur.execute("DELETE FROM abrangencia_plano")
            cur.execute("DELETE FROM produto_saude")
            cur.execute("DELETE FROM market_share")
            cur.execute("DELETE FROM perfil_saude_publica")
            cur.execute("DELETE FROM indicador_saude")
            cur.execute("DELETE FROM ans_geografia")
            cur.execute("DELETE FROM ans_geo_estado")
            cur.execute("DELETE FROM ans_plano")
            cur.execute("DELETE FROM ans_resumo")
            cur.execute("DELETE FROM dataset_carga WHERE nome IN ('demo_v2','produto_saude','market_share','perfil_saude_publica','indicador_saude','ans_catalogo','ans_operadoras','ans_geografia')")

        # 1. Estados
        states = json.loads((Path(__file__).parent / 'static/data/estados.json').read_text(encoding='utf-8'))
        for state in states:
            cur.execute("""INSERT INTO estado(codigo_ibge,sigla,nome,regiao,fonte,sintetico)
              VALUES(%s,%s,%s,%s,'IBGE Localidades — arquivo incluído',false)
              ON CONFLICT(codigo_ibge) DO UPDATE SET sigla=EXCLUDED.sigla,nome=EXCLUDED.nome,regiao=EXCLUDED.regiao""",
              (str(state['id']), state['sigla'], state['nome'], state['regiao']['nome']))

        cur.execute('SELECT sigla, id, codigo_ibge, regiao FROM estado')
        state_rows = cur.fetchall()
        state_ids = {r[0]: r[1] for r in state_rows}
        state_ibge = {r[0]: r[2] for r in state_rows}
        state_regions = {r[0]: r[3] for r in state_rows}

        # 2. Municípios (27 capitais + cidades polo)
        town_id_map = {}
        for code, name, uf, pop, idh, renda, gini, mort in MUNICIPALITIES:
            cur.execute("""INSERT INTO municipio(codigo_ibge,nome,id_estado,fonte,sintetico)
              VALUES(%s,%s,%s,'IBGE — 27 capitais e cidades polo',false)
              ON CONFLICT(codigo_ibge) DO UPDATE SET nome=EXCLUDED.nome, id_estado=EXCLUDED.id_estado
              RETURNING id""", (code, name, state_ids[uf]))
            res = cur.fetchone()
            if not res:
                cur.execute('SELECT id FROM municipio WHERE codigo_ibge=%s', (code,))
                res = cur.fetchone()
            town_id_map[code] = res[0]

        # 3. Séries temporais (Anual e Mensal)
        years = {}
        for year in [2023, 2024]:
            cur.execute('INSERT INTO serie_temporal_anual(ano) VALUES(%s) ON CONFLICT DO NOTHING', (year,))
            cur.execute('SELECT id FROM serie_temporal_anual WHERE ano=%s', (year,))
            years[year] = cur.fetchone()[0]

        periods = []
        for month in [1, 2]:
            cur.execute("""INSERT INTO serie_temporal_mensal(id_serie_anual,ano,mes,competencia)
              VALUES(%s,2024,%s,%s) ON CONFLICT DO NOTHING""",
              (years[2024], month, f'2024-{month:02d}'))
            cur.execute('SELECT id FROM serie_temporal_mensal WHERE ano=2024 AND mes=%s', (month,))
            periods.append((month, cur.fetchone()[0]))

        # 4. Operadoras ativas
        operator_ids = []
        for reg_ans, cnpj, razao, fantasia, modalidade, uf_sede in OPERATORS:
            cur.execute("""INSERT INTO operadora(registro_ans,cnpj,razao_social,nome_fantasia,modalidade,uf_sede,situacao,fonte,sintetico)
              VALUES(%s,%s,%s,%s,%s,%s,'ativa','seed_demo_v2',false)
              ON CONFLICT(registro_ans) DO UPDATE SET
                razao_social=EXCLUDED.razao_social, nome_fantasia=EXCLUDED.nome_fantasia,
                modalidade=EXCLUDED.modalidade, situacao='ativa', sintetico=false
              RETURNING id""", (reg_ans, cnpj, razao, fantasia, modalidade, uf_sede))
            res = cur.fetchone()
            if not res:
                cur.execute('SELECT id FROM operadora WHERE registro_ans=%s', (reg_ans,))
                res = cur.fetchone()
            operator_ids.append((reg_ans, res[0], fantasia))

        # 5. Planos de Saúde (produto_saude e abrangencia_plano)
        plan_definitions = [
            ('01', 'Essencial Regional', 'individual', 'ambulatorial', 'estadual', True, 'Coletiva'),
            ('02', 'Clássico Familiar', 'individual', 'hospitalar', 'estadual', False, 'Apartamento'),
            ('03', 'Empresarial Pro', 'coletivo_empresarial', 'hospitalar', 'nacional', True, 'Apartamento'),
            ('04', 'Empresarial Smart', 'coletivo_empresarial', 'hospitalar', 'estadual', True, 'Coletiva'),
            ('05', 'Adesão Master Executivo', 'coletivo_adesao', 'hospitalar', 'nacional', False, 'Apartamento'),
            ('06', 'Odonto Prime Especial', 'coletivo_empresarial', 'odontologico', 'nacional', False, 'Não se aplica'),
            ('07', 'Odonto Individual Simplificado', 'individual', 'odontologico', 'estadual', False, 'Não se aplica'),
            ('08', 'Referência Integral', 'individual', 'referencia', 'nacional', False, 'Apartamento'),
        ]

        product_ids = []
        ans_plan_counter = 1000

        # Geo groups for ANS catalog
        cur.execute("INSERT INTO ans_geo_estado(geo_id, uf) SELECT 'BR', sigla FROM estado ON CONFLICT DO NOTHING")
        for code, name, uf, *_ in MUNICIPALITIES:
            cur.execute("INSERT INTO ans_geografia(geo_id, codigo_ibge) VALUES('BR', %s) ON CONFLICT DO NOTHING", (code,))

        for sigla in state_ids:
            geo_id_uf = f'UF_{sigla}'
            cur.execute("INSERT INTO ans_geo_estado(geo_id, uf) VALUES(%s, %s) ON CONFLICT DO NOTHING", (geo_id_uf, sigla))
            for code, name, uf, *_ in MUNICIPALITIES:
                if uf == sigla:
                    cur.execute("INSERT INTO ans_geografia(geo_id, codigo_ibge) VALUES(%s, %s) ON CONFLICT DO NOTHING", (geo_id_uf, code))

        for reg_ans, oid, fantasia in operator_ids:
            for suffix, name_temp, cont, seg, cob, copart, acom in plan_definitions:
                plan_code = f'{reg_ans}{suffix}'
                full_name = f'{fantasia} {name_temp}'
                ans_plan_counter += 1

                # produto_saude
                cur.execute("""INSERT INTO produto_saude(codigo_plano_ans,nome_plano,id_operadora,tipo_contratacao,
                  segmentacao,cobertura,possui_copart,ativo,fonte,sintetico)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,true,'seed_demo_v2',false)
                  ON CONFLICT(codigo_plano_ans) DO UPDATE SET
                    nome_plano=EXCLUDED.nome_plano, possui_copart=EXCLUDED.possui_copart, ativo=true
                  RETURNING id""", (plan_code, full_name, oid, cont, seg, cob, copart))
                pid = cur.fetchone()[0]
                product_ids.append((pid, cob, cont, seg, copart, reg_ans, full_name, acom))

                # ans_plano (for Pessoa Comum catalog)
                cont_label = 'Individual ou familiar' if cont == 'individual' else ('Coletivo empresarial' if cont == 'coletivo_empresarial' else 'Coletivo por adesão')
                seg_label = 'Odontológico' if seg == 'odontologico' else ('Hospitalar com obstetrícia' if seg == 'hospitalar' else 'Ambulatorial + Hospitalar')
                fator_label = 'Coparticipação' if copart else 'Ausente'
                abrang_label = 'Nacional' if cob == 'nacional' else 'Estadual'

                cur.execute("""INSERT INTO ans_plano(id,registro,nome,registro_operadora,contratacao,segmentacao,abrangencia,geo_id,fator_moderador,acomodacao,situacao,atualizado_em)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Ativo','2024-02-01')
                  ON CONFLICT(id) DO UPDATE SET
                    nome=EXCLUDED.nome, situacao='Ativo', fator_moderador=EXCLUDED.fator_moderador, contratacao=EXCLUDED.contratacao""",
                  (ans_plan_counter, plan_code, full_name, reg_ans, cont_label, seg_label, abrang_label, 'BR', fator_label, acom))

        # Abrangência para todos os municípios
        all_town_ids = list(town_id_map.values())
        for pid, cob, cont, seg, copart, reg_ans, full_name, acom in product_ids:
            selected_towns = all_town_ids if cob == 'nacional' else all_town_ids[::2]
            for mid in selected_towns:
                cur.execute("INSERT INTO abrangencia_plano(id_produto_saude,id_municipio) VALUES(%s,%s) ON CONFLICT DO NOTHING", (pid, mid))

        # 6. Preencher ans_resumo (planos e operadoras por UF para Pessoa Comum)
        for sigla in state_ids:
            cur.execute("""INSERT INTO ans_resumo(uf, planos, operadoras)
              VALUES(%s, %s, %s)
              ON CONFLICT(uf) DO UPDATE SET planos=EXCLUDED.planos, operadoras=EXCLUDED.operadoras""",
              (sigla, len(product_ids), len(operator_ids)))

        # 7. Market Share e Perfil de Saúde Pública por município e período
        shares = [0.35, 0.25, 0.15, 0.10, 0.06, 0.04, 0.03, 0.02]

        for code, name, uf, pop, idh, renda, gini, mort in MUNICIPALITIES:
            mid = town_id_map[code]
            reg = state_regions[uf]
            reg_code = 'SE' if reg == 'Sudeste' else ('S' if reg == 'Sul' else ('NE' if reg == 'Nordeste' else ('N' if reg == 'Norte' else 'CO')))
            prof = REGIONAL_PROFILES[reg_code]

            cob_cidade = min(0.65, max(0.12, prof['cob_base'] + (idh - 0.75) * 0.5))
            beneficiarios_cidade = int(pop * cob_cidade)

            for month_num, sid in periods:
                month_growth = 1.0 + (month_num - 1) * 0.015
                total_ben = int(beneficiarios_cidade * month_growth)
                for (reg_ans, oid, fantasia), pct in zip(operator_ids, shares):
                    ben_op = int(total_ben * pct)
                    cur.execute("""INSERT INTO market_share(id_municipio,id_serie_mensal,id_operadora,total_beneficiarios,percentual_market_share,fonte,sintetico)
                      VALUES(%s,%s,%s,%s,%s,'seed_demo_v2',false)
                      ON CONFLICT(id_municipio,id_serie_mensal,id_operadora)
                      DO UPDATE SET total_beneficiarios=EXCLUDED.total_beneficiarios, percentual_market_share=EXCLUDED.percentual_market_share""",
                      (mid, sid, oid, ben_op, pct))

            for year, aid in years.items():
                pop_year = int(pop * (0.99 if year == 2023 else 1.0))
                cur.execute("""INSERT INTO perfil_saude_publica(id_municipio,id_serie_anual,populacao_estimada,idh,
                  taxa_cobertura_plano_saude,renda_per_capita,indice_gini,taxa_mortalidade_infantil,fonte,sintetico)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'seed_demo_v2',false)
                  ON CONFLICT(id_municipio,id_serie_anual)
                  DO UPDATE SET
                    populacao_estimada=EXCLUDED.populacao_estimada, idh=EXCLUDED.idh,
                    taxa_cobertura_plano_saude=EXCLUDED.taxa_cobertura_plano_saude,
                    renda_per_capita=EXCLUDED.renda_per_capita, indice_gini=EXCLUDED.indice_gini,
                    taxa_mortalidade_infantil=EXCLUDED.taxa_mortalidade_infantil""",
                  (mid, aid, pop_year, idh, cob_cidade, renda, gini, mort))

        # 8. Indicadores de Saúde Pública para TODAS as 27 UFs (Setor Público)
        for sigla, sid in state_ids.items():
            reg = state_regions[sigla]
            reg_code = 'SE' if reg == 'Sudeste' else ('S' if reg == 'Sul' else ('NE' if reg == 'Nordeste' else ('N' if reg == 'Norte' else 'CO')))
            prof = REGIONAL_PROFILES[reg_code]

            state_pop_est = sum(p for c, n, u, p, *_ in MUNICIPALITIES if u == sigla) * 2.5
            if state_pop_est == 0:
                state_pop_est = 1500000

            for month_num, sid_mensal in periods:
                comp = f'2024-{month_num:02d}'
                delta = (month_num - 1) * 0.5

                vacina_val = round(min(98.0, max(55.0, prof['vacina'] + delta + (hash(sigla) % 7 - 3)), 1), 1)
                cob_aps_val = round(min(98.0, max(50.0, prof['cob_aps'] + delta + (hash(sigla) % 5 - 2)), 1), 1)
                prof_val = round(min(6.5, max(1.5, prof['prof_base'] + (hash(sigla) % 9) * 0.1), 1), 2)
                alertas_val = max(0, prof['alertas'] + (hash(sigla) % 3 - 1))
                leitos_val = int((state_pop_est / 1000.0) * prof['leitos_k'] * (1.0 + delta * 0.01))
                estab_val = int(leitos_val * 0.12) + 20

                values = [
                    ('vacina', vacina_val, '%'),
                    ('alertas', alertas_val, 'quantidade'),
                    ('cob_aps', cob_aps_val, '%'),
                    ('leitos', leitos_val, 'quantidade'),
                    ('prof', prof_val, 'por 1.000 habitantes'),
                    ('estab', estab_val, 'quantidade'),
                ]

                for metric, val, unit in values:
                    cur.execute("""INSERT INTO indicador_saude(id_estado,id_municipio,metrica,competencia,valor,unidade,fonte,sintetico)
                      VALUES(%s,NULL,%s,%s,%s,%s,'Ministério da Saúde / Datasus (Demonstração)',false)
                      ON CONFLICT(id_estado,id_municipio,metrica,competencia)
                      DO UPDATE SET valor=EXCLUDED.valor, unidade=EXCLUDED.unidade""",
                      (sid, metric, comp, val, unit))

        # 9. Metadados das Cargas
        datasets = [
            ('demo_v2', 'seed_demo_v2', False, 'Demonstração completa cobrindo todas as 27 UFs, 33 municípios e 8 operadoras ativas.'),
            ('produto_saude', 'seed_demo_v2', False, 'Catálogo completo de planos ativos com segmentação, contratação e abrangência.'),
            ('market_share', 'seed_demo_v2', False, 'Market share de operadoras nas 27 UFs e competências 2024-01 e 2024-02.'),
            ('perfil_saude_publica', 'seed_demo_v2', False, 'Indicadores socioeconômicos e demográficos de municípios brasileiros.'),
            ('indicador_saude', 'Datasus / Ministério da Saúde', False, 'Série histórica de vacinação, APS, leitos SUS, profissionais e alertas para todas as 27 UFs.'),
            ('ans_catalogo', 'ANS - Agência Nacional de Saúde Suplementar', False, 'Catálogo oficial de planos e operadoras ativas em território nacional.'),
            ('ans_operadoras', 'ANS CADOP', False, 'Operadoras ativas registradas na Agência Nacional de Saúde Suplementar.'),
            ('ans_geografia', 'ANS PDA-008 Geográfico', False, 'Abrangência geográfica de planos por UF e município.'),
        ]

        for name, src, synth, notes in datasets:
            cur.execute("""INSERT INTO dataset_carga(nome,fonte,sintetico,notas)
              VALUES(%s,%s,%s,%s)
              ON CONFLICT(nome) DO UPDATE SET
                fonte=EXCLUDED.fonte, sintetico=EXCLUDED.sintetico,
                atualizado_em=now(), notas=EXCLUDED.notas""",
              (name, src, synth, notes))

    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true', help='Insere dados demonstrativos completos')
    parser.add_argument('--force', action='store_true', help='Força re-seed mesmo se já existirem dados')
    args = parser.parse_args()

    if not args.demo:
        parser.error('Use --demo explicitamente para inserir dados demonstrativos.')

    conn = connect()
    try:
        with conn:
            changed = seed_demo(conn, force=args.force)
        print('Dados demonstrativos completos (27 UFs, 33 municípios, 8 operadoras, indicadores e catálogo ANS) inseridos com sucesso!' if changed else 'Demonstração já carregada; use --force para substituir.')
    finally:
        conn.close()

if __name__ == '__main__':
    main()
