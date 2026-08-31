"""
api.py - Backend Flask para o dashboard Milton PI API
Rode com: python api.py
Acesse:   http://localhost:5001
"""
import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
import psycopg2.extras

app = Flask(__name__, static_folder=".")
CORS(app)

DB_CONFIG = {
    "host":     os.getenv("MILTON_DB_HOST",  "localhost"),
    "port":     int(os.getenv("MILTON_DB_PORT", 5432)),
    "dbname":   os.getenv("MILTON_DB_NAME",  "miltondb"),
    "user":     os.getenv("MILTON_DB_USER",  "milton"),
    "password": os.getenv("MILTON_DB_PASS",  "miltonpass"),
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def query(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    finally:
        conn.close()

@app.route("/")
def index():
    return send_from_directory(".", "dashboard.html")

@app.route("/api/stats")
def stats():
    rows = query("""
        SELECT relname AS tabela, n_live_tup AS linhas
        FROM pg_stat_user_tables
        ORDER BY relname
    """)
    return jsonify(list(rows))

@app.route("/api/estados-summary")
def estados_summary():
    rows = query("""
        SELECT
            e.sigla                                         AS uf,
            e.nome                                          AS nome_estado,
            e.regiao                                        AS regiao,
            COALESCE(SUM(ms.total_beneficiarios), 0)        AS total_beneficiarios,
            COUNT(DISTINCT ms.id_operadora)                 AS total_operadoras,
            COUNT(DISTINCT m.id)                            AS total_municipios,
            ROUND(AVG(p.taxa_cobertura_plano_saude) * 100, 1) AS cobertura_media_pct,
            ROUND(AVG(p.idh)::numeric, 3)                  AS idh_medio,
            ROUND(AVG(p.renda_per_capita)::numeric, 2)     AS renda_media
        FROM estado e
        LEFT JOIN municipio m            ON m.id_estado = e.id
        LEFT JOIN market_share ms        ON ms.id_municipio = m.id
        LEFT JOIN perfil_saude_publica p ON p.id_municipio  = m.id
        GROUP BY e.id, e.sigla, e.nome, e.regiao
        ORDER BY total_beneficiarios DESC
    """)
    result = []
    for r in rows:
        row = dict(r)
        for k, v in row.items():
            if hasattr(v, "__float__"):
                row[k] = float(v)
        result.append(row)
    return jsonify(result)

@app.route("/api/market-share")
def market_share():
    rows = query("""
        SELECT
            m.nome           AS municipio,
            e.sigla          AS uf,
            o.nome_fantasia  AS operadora,
            s.competencia,
            ms.total_beneficiarios,
            ROUND(ms.percentual_market_share * 100, 2) AS pct_mercado
        FROM market_share ms
        JOIN municipio m  ON m.id  = ms.id_municipio
        JOIN estado e     ON e.id  = m.id_estado
        JOIN operadora o  ON o.id  = ms.id_operadora
        JOIN serie_temporal_mensal s ON s.id = ms.id_serie_mensal
        ORDER BY ms.total_beneficiarios DESC
        LIMIT 20
    """)
    return jsonify(list(rows))

@app.route("/api/market-share/<uf>")
def market_share_uf(uf):
    rows = query("""
        SELECT
            m.nome           AS municipio,
            e.sigla          AS uf,
            o.nome_fantasia  AS operadora,
            s.competencia,
            ms.total_beneficiarios,
            ROUND(ms.percentual_market_share * 100, 2) AS pct_mercado
        FROM market_share ms
        JOIN municipio m  ON m.id  = ms.id_municipio
        JOIN estado e     ON e.id  = m.id_estado
        JOIN operadora o  ON o.id  = ms.id_operadora
        JOIN serie_temporal_mensal s ON s.id = ms.id_serie_mensal
        WHERE e.sigla = %s
        ORDER BY ms.total_beneficiarios DESC
        LIMIT 20
    """, (uf.upper(),))
    return jsonify(list(rows))

@app.route("/api/planos")
def planos():
    rows = query("""
        SELECT
            ps.nome_plano,
            ps.tipo_contratacao,
            ps.segmentacao,
            ps.cobertura,
            ps.possui_copart,
            o.nome_fantasia   AS operadora,
            COUNT(ap.id_municipio) AS municipios_cobertos
        FROM produto_saude ps
        JOIN operadora o ON o.id = ps.id_operadora
        LEFT JOIN abrangencia_plano ap ON ap.id_produto_saude = ps.id
        WHERE ps.ativo = true
        GROUP BY ps.id, o.nome_fantasia
        ORDER BY municipios_cobertos DESC
        LIMIT 20
    """)
    return jsonify(list(rows))

@app.route("/api/operadoras")
def operadoras():
    rows = query("""
        SELECT
            o.nome_fantasia,
            o.modalidade,
            o.uf_sede,
            COUNT(DISTINCT ps.id) AS total_planos,
            COALESCE(SUM(ms.total_beneficiarios), 0) AS total_beneficiarios
        FROM operadora o
        LEFT JOIN produto_saude ps ON ps.id_operadora = o.id
        LEFT JOIN market_share ms ON ms.id_operadora = o.id
        GROUP BY o.id
        ORDER BY total_beneficiarios DESC
    """)
    return jsonify(list(rows))

@app.route("/api/historico")
def historico():
    rows = query("""
        SELECT
            u.nome AS usuario,
            m.nome AS municipio,
            h.filtros_utilizados,
            h.canal_acesso,
            h.created_at,
            COUNT(f.id) AS feedbacks
        FROM historico_busca_recomendacao h
        JOIN usuario u ON u.id = h.id_usuario
        JOIN municipio m ON m.id = h.id_municipio
        LEFT JOIN feedback_usuario f ON f.id_historico = h.id
        GROUP BY h.id, u.nome, m.nome
        ORDER BY h.created_at DESC
        LIMIT 15
    """)
    result = []
    for r in rows:
        row = dict(r)
        if row.get("filtros_utilizados"):
            import json
            if isinstance(row["filtros_utilizados"], str):
                row["filtros_utilizados"] = json.loads(row["filtros_utilizados"])
        if row.get("created_at"):
            row["created_at"] = row["created_at"].isoformat()
        result.append(row)
    return jsonify(result)

@app.route("/api/perfil-saude")
def perfil_saude():
    rows = query("""
        SELECT
            m.nome AS municipio,
            e.sigla AS uf,
            p.populacao_estimada,
            p.idh,
            ROUND(p.taxa_cobertura_plano_saude * 100, 1) AS cobertura_pct,
            p.renda_per_capita,
            p.indice_gini,
            sa.ano
        FROM perfil_saude_publica p
        JOIN municipio m ON m.id = p.id_municipio
        JOIN estado e ON e.id = m.id_estado
        JOIN serie_temporal_anual sa ON sa.id = p.id_serie_anual
        WHERE sa.ano = (SELECT MAX(ano) FROM serie_temporal_anual)
        ORDER BY p.idh DESC NULLS LAST
        LIMIT 12
    """)
    result = []
    for r in rows:
        row = dict(r)
        for k, v in row.items():
            if hasattr(v, "__float__"):
                row[k] = float(v)
        result.append(row)
    return jsonify(result)

if __name__ == "__main__":
    print("=" * 50)
    print("  Milton PI API — Dashboard")
    print("  http://localhost:5001")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5001, debug=False)
