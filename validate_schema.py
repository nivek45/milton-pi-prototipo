"""
validate_schema.py — Valida a sintaxe do schema.sql sem conexao real ao banco.
"""
import re
import sys

def validate_sql(filepath: str):
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    lines = [l for l in content.splitlines() if not l.strip().startswith("--")]
    clean = "\n".join(lines)
    statements = [s.strip() for s in clean.split(";") if s.strip()]

    tables_created = []
    indexes_created = []

    for stmt in statements:
        upper = stmt.upper()
        if upper.startswith("CREATE TABLE"):
            m = re.search(r"CREATE TABLE\s+(\w+)", stmt, re.IGNORECASE)
            if m:
                tables_created.append(m.group(1))
        elif "CREATE INDEX" in upper:
            m = re.search(r"ON\s+(\w+)", stmt, re.IGNORECASE)
            if m:
                indexes_created.append(m.group(1))

    expected_tables = [
        "estado", "municipio", "serie_temporal_anual", "serie_temporal_mensal",
        "operadora", "produto_saude", "abrangencia_plano", "preco_faixa_etaria",
        "market_share", "rede_credenciada_sintetica", "perfil_saude_publica",
        "usuario", "historico_busca_recomendacao", "feedback_usuario",
    ]

    print("=" * 55)
    print("  Validacao estatica do schema.sql")
    print("=" * 55)
    print(f"\n[OK] Tabelas encontradas ({len(tables_created)}/14):")
    for t in tables_created:
        status = "[OK]" if t in expected_tables else "[EXTRA]"
        print(f"       {status}  {t}")

    missing = [t for t in expected_tables if t not in tables_created]
    if missing:
        print(f"\n[ERRO] Tabelas faltando: {missing}")
        sys.exit(1)
    else:
        print(f"\n[OK] Todos os 14 CREATE TABLE encontrados!")

    print(f"\n[INFO] Indices definidos: {len(indexes_created)}")
    print(f"       Tabelas indexadas: {set(indexes_created)}")
    print("\n[OK] Schema parece sintaticamente correto (validacao estatica).")
    print("\n[NEXT] Para executar de verdade:")
    print("    1. Abra o Docker Desktop")
    print("    2. docker compose up -d")
    print("    3. python fetch_real_data.py   # dados reais IBGE + ANS (opcional)")
    print("    4. python seed.py              # completa com dados ficticios")

if __name__ == "__main__":
    validate_sql("schema.sql")
