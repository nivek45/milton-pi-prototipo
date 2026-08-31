"""
seed.py — Script de dados FICTICIOS para o prototipo Milton PI API
Insere ~10-20 linhas por tabela, respeitando a ordem de dependencia de FKs.

Workflow recomendado (dados reais primeiro, ficticios depois):
    1. python fetch_real_data.py   # popula estado, municipio, operadora com dados IBGE/ANS
    2. python seed.py              # popula as demais tabelas com dados ficticios

Se fetch_real_data.py ja tiver rodado, seed.py detecta dados existentes em
estado/municipio/operadora e pula a geracao de linhas ficticias para essas
tabelas, evitando duplicatas.

Dependencias:
    pip install psycopg2-binary faker

Uso standalone (sem fetch_real_data.py, cria tudo ficticio):
    python seed.py

Variaveis de ambiente:
    MILTON_DB_HOST, MILTON_DB_PORT, MILTON_DB_NAME, MILTON_DB_USER, MILTON_DB_PASS
"""

import os
import random
import hashlib
from datetime import date, datetime, timedelta
from decimal import Decimal

import psycopg2
from psycopg2.extras import execute_values
from faker import Faker

fake = Faker("pt_BR")
random.seed(42)

# Configuração de conexão
DB_CONFIG = {
    "host":     os.getenv("MILTON_DB_HOST", "localhost"),
    "port":     int(os.getenv("MILTON_DB_PORT", 5432)),
    "dbname":   os.getenv("MILTON_DB_NAME", "miltondb"),
    "user":     os.getenv("MILTON_DB_USER", "milton"),
    "password": os.getenv("MILTON_DB_PASS", "miltonpass"),
}


def connect():
    return psycopg2.connect(**DB_CONFIG)


def run(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params or ())


def insert_returning(conn, sql, params):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


def insert_many_returning(conn, sql, rows):
    with conn.cursor() as cur:
        ids = []
        for row in rows:
            cur.execute(sql, row)
            ids.append(cur.fetchone()[0])
        return ids


# FASE 2 — Dimensões

ESTADOS = [
    ("35", "SP", "São Paulo",      "Sudeste"),
    ("31", "MG", "Minas Gerais",   "Sudeste"),
    ("33", "RJ", "Rio de Janeiro", "Sudeste"),
    ("41", "PR", "Paraná",         "Sul"),
    ("43", "RS", "Rio Grande do Sul", "Sul"),
    ("42", "SC", "Santa Catarina", "Sul"),
    ("29", "BA", "Bahia",          "Nordeste"),
    ("26", "PE", "Pernambuco",     "Nordeste"),
    ("53", "DF", "Distrito Federal", "Centro-Oeste"),
    ("52", "GO", "Goiás",          "Centro-Oeste"),
]

MUNICIPIOS = [
    ("3550308", "São Paulo",        "SP", -23.548943, -46.638819),
    ("3106200", "Belo Horizonte",   "MG", -19.919092, -43.938493),
    ("3304557", "Rio de Janeiro",   "RJ", -22.906847, -43.172897),
    ("4106902", "Curitiba",         "PR", -25.428956, -49.267137),
    ("4314902", "Porto Alegre",     "RS", -30.034647, -51.217659),
    ("4209102", "Florianópolis",    "SC", -27.594870, -48.548219),
    ("2927408", "Salvador",         "BA", -12.971599, -38.501262),
    ("2611606", "Recife",           "PE", -8.063169,  -34.871139),
    ("5300108", "Brasília",         "DF", -15.779660, -47.929850),
    ("5208707", "Goiânia",          "GO", -16.686882, -49.264694),
    ("3518800", "Campinas",         "SP", -22.905570, -47.060627),
    ("3170206", "Uberlândia",       "MG", -18.912139, -48.276063),
]


def _count_rows(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]


def seed_estados(conn) -> dict:
    """
    Retorna dict sigla -> id.
    Se fetch_real_data.py ja populou a tabela, apenas le os dados existentes.
    """
    existing = _count_rows(conn, "estado")
    if existing > 0:
        print(f"  estado: {existing} linhas ja existem (dados reais). Pulando seed ficticio.")
        with conn.cursor() as cur:
            cur.execute("SELECT sigla, id FROM estado")
            return {row[0]: row[1] for row in cur.fetchall()}

    print("  estado: sem dados reais. Inserindo estados ficticios...")
    sql = """
        INSERT INTO estado (codigo_ibge, sigla, nome, regiao)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (sigla) DO NOTHING
        RETURNING id
    """
    with conn.cursor() as cur:
        sigla_to_id = {}
        for cod, sigla, nome, regiao in ESTADOS:
            cur.execute(sql, (cod, sigla, nome, regiao))
            row = cur.fetchone()
            if row:
                sigla_to_id[sigla] = row[0]
            else:
                cur.execute("SELECT id FROM estado WHERE sigla = %s", (sigla,))
                sigla_to_id[sigla] = cur.fetchone()[0]
    return sigla_to_id


def seed_municipios(conn, sigla_to_id):
    """
    Retorna lista de IDs.
    Se fetch_real_data.py ja populou a tabela, apenas le os dados existentes.
    """
    existing = _count_rows(conn, "municipio")
    if existing > 0:
        print(f"  municipio: {existing} linhas ja existem (dados reais). Pulando seed ficticio.")
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM municipio")
            return [row[0] for row in cur.fetchall()]

    print("  municipio: sem dados reais. Inserindo municipios ficticios...")
    sql = """
        INSERT INTO municipio (codigo_ibge, nome, id_estado, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (codigo_ibge) DO NOTHING
        RETURNING id
    """
    with conn.cursor() as cur:
        mun_ids = []
        for cod, nome, sigla, lat, lng in MUNICIPIOS:
            cur.execute(sql, (cod, nome, sigla_to_id[sigla], lat, lng))
            row = cur.fetchone()
            if row:
                mun_ids.append(row[0])
            else:
                cur.execute("SELECT id FROM municipio WHERE codigo_ibge = %s", (cod,))
                mun_ids.append(cur.fetchone()[0])
    return mun_ids


def seed_series_anuais(conn):
    print("[+] Inserindo series anuais...")
    anos = [2022, 2023, 2024]
    sql = """
        INSERT INTO serie_temporal_anual (ano)
        VALUES (%s)
        ON CONFLICT (ano) DO NOTHING
        RETURNING id
    """
    with conn.cursor() as cur:
        ano_to_id = {}
        for ano in anos:
            cur.execute(sql, (ano,))
            row = cur.fetchone()
            if row:
                ano_to_id[ano] = row[0]
            else:
                cur.execute("SELECT id FROM serie_temporal_anual WHERE ano = %s", (ano,))
                ano_to_id[ano] = cur.fetchone()[0]
    return ano_to_id


def seed_series_mensais(conn, ano_to_id):
    print("[+] Inserindo series mensais...")
    sql = """
        INSERT INTO serie_temporal_mensal (id_serie_anual, ano, mes, competencia)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (ano, mes) DO NOTHING
        RETURNING id
    """
    periodo = [(2024, m) for m in range(1, 7)]  # Jan–Jun 2024
    with conn.cursor() as cur:
        serie_ids = []
        for ano, mes in periodo:
            comp = f"{ano}-{mes:02d}"
            cur.execute(sql, (ano_to_id[ano], ano, mes, comp))
            row = cur.fetchone()
            if row:
                serie_ids.append(row[0])
            else:
                cur.execute(
                    "SELECT id FROM serie_temporal_mensal WHERE ano = %s AND mes = %s",
                    (ano, mes)
                )
                serie_ids.append(cur.fetchone()[0])
    return serie_ids


def seed_operadoras(conn):
    """
    Retorna lista de IDs.
    Se fetch_real_data.py ja populou a tabela, apenas le os dados existentes.
    """
    existing = _count_rows(conn, "operadora")
    if existing > 0:
        print(f"  operadora: {existing} linhas ja existem (dados reais). Pulando seed ficticio.")
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM operadora")
            return [row[0] for row in cur.fetchall()]

    print("  operadora: sem dados reais. Inserindo operadoras ficticias...")
    operadoras = [
        ("302805", "33530486000129", "Amil Assistência Médica Internacional S/A",          "Amil",          "Medicina de Grupo",                      "SP"),
        ("326305", "01398053000171", "Bradesco Saúde S.A.",                                "Bradesco Saúde","Seguradora Especializada em Saúde",       "SP"),
        ("359017", "76437345000138", "Unimed do Brasil — Confederação Nacional",            "Unimed Brasil", "Cooperativa Médica",                      "SP"),
        ("005711", "00063507000153", "Hapvida Assistência Médica Ltda",                    "Hapvida",       "Medicina de Grupo",                      "CE"),
        ("368253", "19877411000140", "NotreDame Intermédica Saúde S.A.",                   "Intermédica",   "Medicina de Grupo",                      "SP"),
        ("339679", "02012862000126", "SulAmérica Seguro Saúde S.A.",                       "SulAmérica",    "Seguradora Especializada em Saúde",       "SP"),
        ("312282", "17246461000180", "Qualicorp Administradora de Benefícios S.A.",         "Qualicorp",     "Administradora de Benefícios",            "SP"),
        ("323080", "00000000000191", "Unimed Belo Horizonte Cooperativa de Trabalho Médico","Unimed BH",     "Cooperativa Médica",                      "MG"),
        ("329062", "00000000000272", "Unimed Rio Cooperativa de Trabalho Médico",           "Unimed Rio",    "Cooperativa Médica",                      "RJ"),
        ("328952", "00000000000353", "Unimed Curitiba Sociedade Cooperativa",               "Unimed Curitiba","Cooperativa Médica",                     "PR"),
    ]
    sql = """
        INSERT INTO operadora (registro_ans, cnpj, razao_social, nome_fantasia, modalidade, uf_sede, data_registro)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (registro_ans) DO NOTHING
        RETURNING id
    """
    with conn.cursor() as cur:
        op_ids = []
        for reg, cnpj, razao, fantasia, modal, uf in operadoras:
            cur.execute(sql, (reg, cnpj, razao, fantasia, modal, uf, date(2000, 1, 1)))
            row = cur.fetchone()
            if row:
                op_ids.append(row[0])
            else:
                cur.execute("SELECT id FROM operadora WHERE registro_ans = %s", (reg,))
                op_ids.append(cur.fetchone()[0])
    return op_ids


# FASE 3 — Entidades de negócio

def seed_produtos_saude(conn, op_ids):
    print("[+] Inserindo produtos de saude...")
    tipos = ["individual", "coletivo_empresarial", "coletivo_adesao"]
    segs  = ["ambulatorial", "hospitalar", "odontologico", "referencia"]
    coberturas = ["nacional", "estadual", "municipal"]

    produtos = []
    for i, op_id in enumerate(op_ids):
        for j in range(2):  # 2 planos por operadora → 20 total
            cod  = f"{900000 + i * 10 + j:012d}"
            nome = f"Plano {fake.word().capitalize()} {fake.word().capitalize()} {i+1}.{j+1}"
            tipo = tipos[(i + j) % len(tipos)]
            seg  = segs[(i + j) % len(segs)]
            cob  = coberturas[i % len(coberturas)]
            produtos.append((cod, nome, op_id, tipo, seg, cob, j % 2 == 0, True, date(2020, 1, 1)))

    sql = """
        INSERT INTO produto_saude
            (codigo_plano_ans, nome_plano, id_operadora, tipo_contratacao,
             segmentacao, cobertura, possui_copart, ativo, data_inicio_venda)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (codigo_plano_ans) DO NOTHING
        RETURNING id
    """
    with conn.cursor() as cur:
        prod_ids = []
        for p in produtos:
            cur.execute(sql, p)
            row = cur.fetchone()
            if row:
                prod_ids.append(row[0])
            else:
                cur.execute("SELECT id FROM produto_saude WHERE codigo_plano_ans = %s", (p[0],))
                prod_ids.append(cur.fetchone()[0])
    return prod_ids


def seed_abrangencia_plano(conn, prod_ids, mun_ids):
    print("[+] Inserindo abrangencias de plano...")
    sql = """
        INSERT INTO abrangencia_plano (id_produto_saude, id_municipio)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """
    with conn.cursor() as cur:
        for pid in prod_ids:
            # Cada plano cobre entre 3 e 8 municípios aleatórios
            cobertura = random.sample(mun_ids, k=min(random.randint(3, 8), len(mun_ids)))
            for mid in cobertura:
                cur.execute(sql, (pid, mid))


def seed_preco_faixa_etaria(conn, prod_ids, serie_ids):
    print("[+] Inserindo precos por faixa etaria...")
    faixas = ["00-18", "19-23", "24-28", "29-33", "34-38", "39-43", "44-48", "49-53", "54-58", "59+"]
    sql = """
        INSERT INTO preco_faixa_etaria (id_produto_saude, id_serie_mensal, faixa_etaria, valor_mensalidade, reajuste_percentual)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (id_produto_saude, id_serie_mensal, faixa_etaria) DO NOTHING
    """
    with conn.cursor() as cur:
        # Insere apenas para os 5 primeiros planos e 2 competências (protótipo)
        for pid in prod_ids[:5]:
            base = round(random.uniform(200, 600), 2)
            for sid in serie_ids[:2]:
                for i, faixa in enumerate(faixas):
                    valor = round(base * (1 + i * 0.08), 2)
                    reajuste = round(random.uniform(0.05, 0.15), 4)
                    cur.execute(sql, (pid, sid, faixa, valor, reajuste))


def seed_market_share(conn, mun_ids, serie_ids, op_ids):
    print("[+] Inserindo market share...")
    sql = """
        INSERT INTO market_share (id_municipio, id_serie_mensal, id_operadora, total_beneficiarios, percentual_market_share)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (id_municipio, id_serie_mensal, id_operadora) DO NOTHING
    """
    with conn.cursor() as cur:
        for mid in mun_ids[:6]:
            for sid in serie_ids[:2]:
                total_mun = random.randint(10000, 500000)
                restante = 1.0
                ops = random.sample(op_ids, k=min(5, len(op_ids)))
                for i, oid in enumerate(ops):
                    if i == len(ops) - 1:
                        pct = round(restante, 4)
                    else:
                        pct = round(random.uniform(0.05, restante * 0.6), 4)
                    restante -= pct
                    bens = int(total_mun * pct)
                    cur.execute(sql, (mid, sid, oid, bens, pct))


def seed_rede_credenciada(conn, prod_ids, mun_ids):
    print("[+] Inserindo rede credenciada sintetica...")
    tipos = ["hospital", "clinica_geral", "laboratorio", "UPA", "psicologia", "fisioterapia"]
    sql = """
        INSERT INTO rede_credenciada_sintetica (id_produto_saude, id_municipio, tipo_servico, especialidade, quantidade_estimada)
        VALUES (%s, %s, %s, %s, %s)
    """
    with conn.cursor() as cur:
        for pid in prod_ids[:8]:
            for mid in random.sample(mun_ids, k=min(4, len(mun_ids))):
                for tipo in random.sample(tipos, k=3):
                    esp = fake.job() if random.random() > 0.4 else None
                    qtd = random.randint(1, 50)
                    cur.execute(sql, (pid, mid, tipo, esp, qtd))


def seed_perfil_saude_publica(conn, mun_ids, ano_to_id):
    print("[+] Inserindo perfis de saude publica...")
    sql = """
        INSERT INTO perfil_saude_publica
            (id_municipio, id_serie_anual, populacao_estimada, idh, taxa_cobertura_plano_saude,
             renda_per_capita, taxa_mortalidade_infantil, indice_gini)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id_municipio, id_serie_anual) DO NOTHING
    """
    with conn.cursor() as cur:
        for mid in mun_ids:
            for ano, aid in ano_to_id.items():
                cur.execute(sql, (
                    mid, aid,
                    random.randint(50000, 12_000_000),
                    round(random.uniform(0.65, 0.95), 3),
                    round(random.uniform(0.10, 0.75), 4),
                    round(random.uniform(1200, 6000), 2),
                    round(random.uniform(5.0, 25.0), 2),
                    round(random.uniform(0.35, 0.65), 3),
                ))


def seed_usuarios(conn):
    print("[+] Inserindo usuarios...")
    sql = """
        INSERT INTO usuario (email, nome, senha_hash, perfil_busca)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (email) DO NOTHING
        RETURNING id
    """
    import json
    users = []
    for _ in range(15):
        nome  = fake.name()
        email = fake.unique.email()
        senha_hash = hashlib.sha256(fake.password().encode()).hexdigest()
        perfil = json.dumps({
            "faixa_etaria": random.choice(["00-18", "19-23", "29-33", "39-43", "59+"]),
            "renda_familiar": round(random.uniform(2000, 20000), 2),
            "tipo_plano": random.choice(["individual", "coletivo_empresarial"]),
        })
        users.append((email, nome, senha_hash, perfil))

    with conn.cursor() as cur:
        user_ids = []
        for u in users:
            cur.execute(sql, u)
            row = cur.fetchone()
            if row:
                user_ids.append(row[0])
            else:
                cur.execute("SELECT id FROM usuario WHERE email = %s", (u[0],))
                user_ids.append(cur.fetchone()[0])
    return user_ids


# FASE 4 — Tabelas transacionais

def seed_historico(conn, user_ids, mun_ids, prod_ids):
    print("[+] Inserindo historico de busca...")
    import json
    sql = """
        INSERT INTO historico_busca_recomendacao (id_usuario, id_municipio, filtros_utilizados, resultado_ids, canal_acesso)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """
    canais = ["web", "mobile", "api"]
    tipos  = ["individual", "coletivo_empresarial", "coletivo_adesao"]
    with conn.cursor() as cur:
        hist_ids = []
        for uid in user_ids[:12]:
            for _ in range(random.randint(1, 3)):
                mid = random.choice(mun_ids)
                filtros = json.dumps({
                    "tipo_plano":  random.choice(tipos),
                    "faixa_etaria": random.choice(["19-23", "29-33", "39-43", "59+"]),
                    "preco_max":   random.randint(500, 3000),
                    "segmentacao": random.choice(["ambulatorial", "hospitalar"]),
                })
                resultados = json.dumps(random.sample(prod_ids, k=min(5, len(prod_ids))))
                canal = random.choice(canais)
                cur.execute(sql, (uid, mid, filtros, resultados, canal))
                hist_ids.append(cur.fetchone()[0])
    return hist_ids


def seed_feedback(conn, hist_ids, prod_ids):
    print("[+] Inserindo feedbacks...")
    sql = """
        INSERT INTO feedback_usuario (id_historico, id_produto_saude, nota, comentario, util)
        VALUES (%s, %s, %s, %s, %s)
    """
    comentarios = [
        "Ótimo plano, atendimento rápido!", "Preço acima do esperado.",
        "Cobriu bem minhas necessidades.", "Muita burocracia para usar.",
        "Recomendo para família.", "Rede credenciada pequena na minha cidade.",
        "Excelente custo-benefício!", None, None, None,
    ]
    with conn.cursor() as cur:
        for hid in hist_ids:
            if random.random() > 0.4:  # 60% dos históricos têm feedback
                pid  = random.choice(prod_ids)
                nota = random.randint(1, 5)
                com  = random.choice(comentarios)
                util = random.choice([True, False, None])
                cur.execute(sql, (hid, pid, nota, com, util))


# Main

def main():
    print("=" * 60)
    print(" Milton PI API — Seed de Dados Fictícios")
    print("=" * 60)

    conn = connect()
    conn.autocommit = False

    try:
        # Fase 2
        sigla_to_id = seed_estados(conn)
        mun_ids     = seed_municipios(conn, sigla_to_id)
        ano_to_id   = seed_series_anuais(conn)
        serie_ids   = seed_series_mensais(conn, ano_to_id)
        op_ids      = seed_operadoras(conn)

        # Fase 3
        prod_ids    = seed_produtos_saude(conn, op_ids)
        seed_abrangencia_plano(conn, prod_ids, mun_ids)
        seed_preco_faixa_etaria(conn, prod_ids, serie_ids)
        seed_market_share(conn, mun_ids, serie_ids, op_ids)
        seed_rede_credenciada(conn, prod_ids, mun_ids)
        seed_perfil_saude_publica(conn, mun_ids, ano_to_id)
        user_ids    = seed_usuarios(conn)

        # Fase 4
        hist_ids    = seed_historico(conn, user_ids, mun_ids, prod_ids)
        seed_feedback(conn, hist_ids, prod_ids)

        conn.commit()
        print("\n[OK] Seed concluido com sucesso!")
        print("     Execute os SELECTs de validacao:")
        print("     SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY relname;")

    except Exception as e:
        conn.rollback()
        print(f"\n[ERRO] Erro durante o seed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
