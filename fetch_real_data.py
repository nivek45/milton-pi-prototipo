"""
fetch_real_data.py — Carga de dados REAIS do IBGE e ANS para o prototipo Milton PI API.

Popula as tabelas: estado, municipio, operadora
com dados publicos verificados em 17/08/2026.

AVISO: Este script nao foi testado ponta a ponta em ambiente sem acesso a rede.
       Validacao sintatica apenas. Roda ANTES do seed.py.

Dependencias:
    pip install psycopg2-binary requests

Uso:
    python fetch_real_data.py        # carrega tudo
    python fetch_real_data.py --only estados municipios
    python fetch_real_data.py --only operadoras

Variaveis de ambiente:
    MILTON_DB_HOST, MILTON_DB_PORT, MILTON_DB_NAME, MILTON_DB_USER, MILTON_DB_PASS

Fontes verificadas em 17/08/2026:
    IBGE Localidades (publica, sem auth):
      https://servicodados.ibge.gov.br/api/v1/localidades/estados
      https://servicodados.ibge.gov.br/api/v1/localidades/estados/{UF}/municipios

    ANS CADOP (publica, sem auth — caminho verificado):
      https://dadosabertos.ans.gov.br/FTP/PDA/operadoras_de_plano_de_saude_ativas/Relatorio_cadop.csv
      ATENCAO: caminho muda com frequencia; confirmar no indice
               https://dadosabertos.ans.gov.br/FTP/PDA/ antes de rodar.

    APIs que exigem autenticacao (NAO cobertas aqui):
      apidadosabertos.saude.gov.br  -> CNES, CADSUS, SISREG (auth obrigatoria)
      Base dos Dados / CNES BigQuery -> credencial GCP necessaria
"""

import os
import sys
import csv
import io
import argparse
import logging

import requests
import psycopg2

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Conexao
DB_CONFIG = {
    "host":     os.getenv("MILTON_DB_HOST",  "localhost"),
    "port":     int(os.getenv("MILTON_DB_PORT", 5432)),
    "dbname":   os.getenv("MILTON_DB_NAME",  "miltondb"),
    "user":     os.getenv("MILTON_DB_USER",  "milton"),
    "password": os.getenv("MILTON_DB_PASS",  "miltonpass"),
}

# Fontes
IBGE_ESTADOS_URL    = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
IBGE_MUNICIPIOS_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{sigla}/municipios"

# Caminho verificado em 17/08/2026 — pode mudar; checar indice antes de rodar:
# https://dadosabertos.ans.gov.br/FTP/PDA/
ANS_CADOP_URL = (
    "https://dadosabertos.ans.gov.br/FTP/PDA/"
    "operadoras_de_plano_de_saude_ativas/Relatorio_cadop.csv"
)

# Cabecalho real do CADOP verificado em 17/08/2026:
# REGISTRO_OPERADORA;CNPJ;Razao_Social;Nome_Fantasia;Modalidade;Logradouro;
# Numero;Complemento;Bairro;Cidade;UF;CEP;DDD;Telefone;Fax;
# Endereco_eletronico;Representante;Cargo_Representante;
# Regiao_de_Comercializacao;Data_Registro_ANS
CADOP_DELIMITER = ";"

# Mapeamento: coluna CSV -> coluna do banco
CADOP_FIELD_MAP = {
    "registro_ans":  "Registro_ANS",          # nome no CSV: REGISTRO_OPERADORA?
    # ATENCAO: o campo exato pode ser 'REGISTRO_OPERADORA' ou 'Registro_ANS'
    # confirmar lendo as primeiras linhas do CSV antes de integrar em producao.
    "cnpj":          "CNPJ",
    "razao_social":  "Razao_Social",
    "nome_fantasia": "Nome_Fantasia",
    "modalidade":    "Modalidade",
    "uf_sede":       "UF",
    "data_registro": "Data_Registro_ANS",
}

# Regiao por sigla da UF (fallback para quando o IBGE nao retornar regiao)
REGIAO_MAP = {
    "AC": "Norte",   "AM": "Norte",   "AP": "Norte",   "PA": "Norte",
    "RO": "Norte",   "RR": "Norte",   "TO": "Norte",
    "AL": "Nordeste","BA": "Nordeste","CE": "Nordeste","MA": "Nordeste",
    "PB": "Nordeste","PE": "Nordeste","PI": "Nordeste","RN": "Nordeste",
    "SE": "Nordeste",
    "DF": "Centro-Oeste","GO": "Centro-Oeste","MS": "Centro-Oeste","MT": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul",     "RS": "Sul",     "SC": "Sul",
}

HTTP_TIMEOUT = 30  # segundos


# Helpers

def get_json(url: str) -> list | dict:
    log.info("GET %s", url)
    resp = requests.get(url, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_csv_text(url: str, encoding: str = "latin-1") -> str:
    log.info("GET (CSV) %s", url)
    resp = requests.get(url, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.content.decode(encoding)


def count_rows(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]


# 1. Estados — IBGE Localidades (real, sem auth)

def fetch_estados(conn) -> dict:
    """
    Retorna dict: sigla -> id no banco.
    Pula insercao se a tabela ja tiver dados (idempotente).
    """
    existing = count_rows(conn, "estado")
    if existing > 0:
        log.info("estado: %d linhas ja existem, pulando insercao.", existing)
        with conn.cursor() as cur:
            cur.execute("SELECT sigla, id FROM estado")
            return {row[0]: row[1] for row in cur.fetchall()}

    log.info("Buscando estados do IBGE...")
    data = get_json(IBGE_ESTADOS_URL)
    # Cada item: {"id": 35, "sigla": "SP", "nome": "São Paulo", "regiao": {"sigla": "SE", "nome": "Sudeste"}}

    sql = """
        INSERT INTO estado (codigo_ibge, sigla, nome, regiao)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (sigla) DO NOTHING
        RETURNING sigla, id
    """
    sigla_to_id = {}
    with conn.cursor() as cur:
        for item in data:
            sigla   = item["sigla"]
            cod     = str(item["id"])
            nome    = item["nome"]
            regiao  = item.get("regiao", {}).get("nome") or REGIAO_MAP.get(sigla, "Desconhecido")
            cur.execute(sql, (cod, sigla, nome, regiao))
            row = cur.fetchone()
            if row:
                sigla_to_id[row[0]] = row[1]

    # Buscar os que ja existiam (ON CONFLICT DO NOTHING)
    with conn.cursor() as cur:
        cur.execute("SELECT sigla, id FROM estado")
        for row in cur.fetchall():
            sigla_to_id.setdefault(row[0], row[1])

    log.info("estados inseridos/confirmados: %d", len(sigla_to_id))
    return sigla_to_id


# 2. Municipios — IBGE Localidades (real, sem auth)

def fetch_municipios(conn, sigla_to_id: dict) -> list:
    """
    Retorna lista de IDs inseridos.
    Pula se a tabela ja tiver dados (idempotente).
    """
    existing = count_rows(conn, "municipio")
    if existing > 0:
        log.info("municipio: %d linhas ja existem, pulando insercao.", existing)
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM municipio")
            return [row[0] for row in cur.fetchall()]

    log.info("Buscando municipios do IBGE (pode demorar ~15s)...")
    # Busca todos os municipios de uma vez (endpoint mais eficiente)
    url  = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
    data = get_json(url)
    # Cada item:
    # {"id": 3550308, "nome": "São Paulo",
    #  "microrregiao": {"mesorregiao": {"UF": {"sigla": "SP", ...}}}}

    sql = """
        INSERT INTO municipio (codigo_ibge, nome, id_estado)
        VALUES (%s, %s, %s)
        ON CONFLICT (codigo_ibge) DO NOTHING
        RETURNING id
    """
    ids = []
    skipped = 0
    with conn.cursor() as cur:
        for item in data:
            cod   = str(item["id"])
            nome  = item["nome"]
            micro = item.get("microrregiao") or {}
            meso  = micro.get("mesorregiao") or {}
            uf    = meso.get("UF") or {}
            sigla = uf.get("sigla")
            
            # IBGE mudou algumas divisões, fallback para nova estrutura:
            if not sigla:
                reg_imed = item.get("regiao-imediata") or {}
                reg_int  = reg_imed.get("regiao-intermediaria") or {}
                uf       = reg_int.get("UF") or {}
                sigla    = uf.get("sigla")
            id_estado = sigla_to_id.get(sigla)
            if not id_estado:
                skipped += 1
                continue
            cur.execute(sql, (cod, nome, id_estado))
            row = cur.fetchone()
            if row:
                ids.append(row[0])

    if skipped:
        log.warning("municipios ignorados (UF nao mapeada): %d", skipped)

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM municipio")
        all_ids = [row[0] for row in cur.fetchall()]

    log.info("municipios inseridos/confirmados: %d", len(all_ids))
    return all_ids


# 3. Operadoras — ANS CADOP (real, sem auth)

def _parse_date(val: str):
    """Converte DD/MM/YYYY ou YYYY-MM-DD para date; retorna None se invalido."""
    if not val or val.strip() == "":
        return None
    val = val.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            from datetime import datetime as dt
            return dt.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def _clean_cnpj(val: str) -> str:
    """Remove pontuacao do CNPJ e retorna so digitos."""
    import re
    return re.sub(r"\D", "", val or "")


def fetch_operadoras(conn) -> list:
    """
    Retorna lista de IDs inseridos.
    Pula se a tabela ja tiver dados (idempotente).

    ATENCAO sobre o cabecalho real do CADOP (verificado 17/08/2026):
      REGISTRO_OPERADORA;CNPJ;Razao_Social;Nome_Fantasia;Modalidade;
      Logradouro;Numero;Complemento;Bairro;Cidade;UF;CEP;DDD;Telefone;Fax;
      Endereco_eletronico;Representante;Cargo_Representante;
      Regiao_de_Comercializacao;Data_Registro_ANS

    O campo de registro pode aparecer como 'REGISTRO_OPERADORA' (nao
    'Registro_ANS' como o documento de correlacao original indicava).
    O codigo abaixo tenta ambos os nomes.
    """
    existing = count_rows(conn, "operadora")
    if existing > 0:
        log.info("operadora: %d linhas ja existem, pulando insercao.", existing)
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM operadora")
            return [row[0] for row in cur.fetchall()]

    log.info("Baixando CADOP da ANS (%s)...", ANS_CADOP_URL)
    csv_text = get_csv_text(ANS_CADOP_URL, encoding="latin-1")

    reader = csv.DictReader(io.StringIO(csv_text), delimiter=CADOP_DELIMITER)

    sql = """
        INSERT INTO operadora
            (registro_ans, cnpj, razao_social, nome_fantasia, modalidade, uf_sede,
             situacao, data_registro)
        VALUES (%s, %s, %s, %s, %s, %s, 'ativa', %s)
        ON CONFLICT (registro_ans) DO NOTHING
        RETURNING id
    """

    ids      = []
    erros    = 0
    inseridos = 0

    with conn.cursor() as cur:
        for row in reader:
            # Tenta ambos os nomes possiveis para o campo de registro
            reg = (
                row.get("Registro_ANS")
                or row.get("REGISTRO_OPERADORA")
                or ""
            ).strip()

            cnpj = _clean_cnpj(row.get("CNPJ", ""))

            if not reg or not cnpj:
                erros += 1
                continue

            razao   = (row.get("Razao_Social") or "").strip()[:200]
            fantasia = (row.get("Nome_Fantasia") or "").strip()[:200] or None
            modal   = (row.get("Modalidade") or "").strip()[:60]
            uf      = (row.get("UF") or "").strip()[:2] or None
            dt_reg  = _parse_date(row.get("Data_Registro_ANS") or "")

            try:
                cur.execute(sql, (reg, cnpj, razao, fantasia, modal, uf, dt_reg))
                result = cur.fetchone()
                if result:
                    ids.append(result[0])
                    inseridos += 1
            except Exception as e:
                erros += 1
                conn.rollback()
                log.debug("Erro na linha reg=%s: %s", reg, e)

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM operadora")
        all_ids = [row[0] for row in cur.fetchall()]

    log.info(
        "operadoras: %d inseridas, %d conflito/erro, total no banco: %d",
        inseridos, erros, len(all_ids)
    )
    return all_ids


# Main

def parse_args():
    parser = argparse.ArgumentParser(
        description="Carga de dados reais IBGE/ANS para o prototipo Milton PI API."
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=["estados", "municipios", "operadoras"],
        default=["estados", "municipios", "operadoras"],
        help="Quais conjuntos carregar (default: todos)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("  fetch_real_data.py — Dados reais IBGE + ANS")
    print("=" * 60)
    print()
    print("ATENCAO: confirmar URL da ANS antes de rodar em producao:")
    print("         https://dadosabertos.ans.gov.br/FTP/PDA/")
    print()

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False

    sigla_to_id = {}

    try:
        if "estados" in args.only:
            sigla_to_id = fetch_estados(conn)
            conn.commit()

        if "municipios" in args.only:
            if not sigla_to_id:
                # Carrega do banco se estados nao foi buscado agora
                with conn.cursor() as cur:
                    cur.execute("SELECT sigla, id FROM estado")
                    sigla_to_id = {r[0]: r[1] for r in cur.fetchall()}
            fetch_municipios(conn, sigla_to_id)
            conn.commit()

        if "operadoras" in args.only:
            fetch_operadoras(conn)
            conn.commit()

        print()
        print("[OK] fetch_real_data.py concluido.")
        print("     Execute seed.py para completar as demais tabelas:")
        print("     python seed.py")

    except Exception as e:
        conn.rollback()
        log.error("Falha: %s", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
