"""
start.py - Orquestrador para rodar o projeto do zero com 1 comando.
Uso: python start.py
"""
import os
import sys
import time
import subprocess
import webbrowser
import psycopg2

DB_CONFIG = {
    "host":     os.getenv("MILTON_DB_HOST",  "localhost"),
    "port":     int(os.getenv("MILTON_DB_PORT", 5432)),
    "dbname":   os.getenv("MILTON_DB_NAME",  "miltondb"),
    "user":     os.getenv("MILTON_DB_USER",  "milton"),
    "password": os.getenv("MILTON_DB_PASS",  "miltonpass"),
}

def run_cmd(cmd, check=True):
    print(f"\n🚀 Executando: {cmd}")
    subprocess.run(cmd, shell=True, check=check)

def wait_for_db(timeout=30):
    print(f"\n⏳ Aguardando PostgreSQL aceitar conexoes (timeout: {timeout}s)...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.close()
            print("✅ Banco de dados esta pronto e respondendo!")
            return True
        except psycopg2.OperationalError:
            time.sleep(1.5)
    
    print("❌ Erro: Tempo limite esgotado esperando o banco de dados.")
    sys.exit(1)

def main():
    print("=" * 60)
    print("   Milton PI API — One-Click Start")
    print("=" * 60)

    run_cmd("docker compose up -d")

    wait_for_db()


    print("\n🌐 Deseja baixar dados REAIS (IBGE/ANS)?")
    print("   Isso baixa as operadoras atuais da ANS e todos os municipios.")
    print("   (Demora aprox. 15-20 segundos)")
    resposta = input("Baixar dados reais? [S/n]: ").strip().lower()

    if resposta != 'n':
        run_cmd(f'"{sys.executable}" fetch_real_data.py')
    else:
        print("⏩ Pulando carga de dados da internet. Usaremos apenas dados amostrais.")

    print("\n🌱 Gerando dados complementares...")
    run_cmd(f'"{sys.executable}" seed.py')

    print("\n✅ Preparacao concluida!")
    print("🚀 Abrindo o Dashboard...")
    
    import threading
    def open_browser():
        time.sleep(2.5)
        webbrowser.open("http://localhost:5001")
    threading.Thread(target=open_browser, daemon=True).start()

    run_cmd(f'"{sys.executable}" api.py')

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Processo interrompido pelo usuario. Dashboard desligado.")
    except Exception as e:
        print(f"\n❌ Falha fatal: {e}")
