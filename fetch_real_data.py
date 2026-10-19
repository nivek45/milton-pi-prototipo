"""Atomic, repeatable imports of public territorial/operator registries only."""
import argparse
import csv
import io
import re
from datetime import datetime
import requests
from psycopg2.extras import execute_values
from backend.db import connect

IBGE_ESTADOS_URL='https://servicodados.ibge.gov.br/api/v1/localidades/estados'
IBGE_MUNICIPIOS_URL='https://servicodados.ibge.gov.br/api/v1/localidades/municipios'
ANS_CADOP_URL='https://dadosabertos.ans.gov.br/FTP/PDA/operadoras_de_plano_de_saude_ativas/Relatorio_cadop.csv'

def response(url):
    res=requests.get(url,timeout=(5,45));res.raise_for_status();return res

def record_load(cur,name,source,count):
    cur.execute("""INSERT INTO dataset_carga(nome,fonte,sintetico,notas) VALUES(%s,%s,false,%s)
      ON CONFLICT(nome) DO UPDATE SET fonte=EXCLUDED.fonte,sintetico=false,
      atualizado_em=now(),notas=EXCLUDED.notas""",(name,source,f'{count} registros processados atomicamente.'))

def fetch_estados(conn):
    rows=[(str(x['id']),x['sigla'],x['nome'],x['regiao']['nome'],IBGE_ESTADOS_URL) for x in response(IBGE_ESTADOS_URL).json()]
    if len(rows)!=27: raise ValueError('Carga de UFs incompleta; banco preservado.')
    with conn.cursor() as cur:
        execute_values(cur,"""INSERT INTO estado(codigo_ibge,sigla,nome,regiao,fonte,sintetico) VALUES %s
          ON CONFLICT(codigo_ibge) DO UPDATE SET sigla=EXCLUDED.sigla,nome=EXCLUDED.nome,
          regiao=EXCLUDED.regiao,fonte=EXCLUDED.fonte,sintetico=false""",rows,template='(%s,%s,%s,%s,%s,false)')
        record_load(cur,'estado',IBGE_ESTADOS_URL,len(rows))
    return len(rows)

def fetch_municipios(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT codigo_ibge,id FROM estado');states=dict(cur.fetchall())
    rows=[]
    for item in response(IBGE_MUNICIPIOS_URL).json():
        code=str(item['id']);state=states.get(code[:2])
        if state is None: raise ValueError(f'UF não carregada para município {code}; importe estados primeiro.')
        rows.append((code,item['nome'],state,IBGE_MUNICIPIOS_URL))
    if len(rows)<5000: raise ValueError('Carga municipal incompleta; banco preservado.')
    with conn.cursor() as cur:
        execute_values(cur,"""INSERT INTO municipio(codigo_ibge,nome,id_estado,fonte,sintetico) VALUES %s
          ON CONFLICT(codigo_ibge) DO UPDATE SET nome=EXCLUDED.nome,id_estado=EXCLUDED.id_estado,
          fonte=EXCLUDED.fonte,sintetico=false""",rows,template='(%s,%s,%s,%s,false)',page_size=500)
        record_load(cur,'municipio',IBGE_MUNICIPIOS_URL,len(rows))
    return len(rows)

def parse_operators(content):
    reader=csv.DictReader(io.StringIO(content.lstrip('\ufeff')),delimiter=';')
    if reader.fieldnames:reader.fieldnames=[key.strip().upper() for key in reader.fieldnames]
    if not reader.fieldnames or not {'CNPJ','RAZAO_SOCIAL','MODALIDADE'}.issubset(reader.fieldnames):
        raise ValueError('Cabeçalho CADOP não reconhecido; nenhuma linha será gravada.')
    rows=[]
    for line,item in enumerate(reader,2):
        reg=(item.get('REGISTRO_ANS') or item.get('REGISTRO_OPERADORA') or '').strip()
        cnpj=re.sub(r'[^A-Z0-9]','',(item.get('CNPJ') or '').upper())
        if not reg.isdigit() or len(reg)>6 or len(cnpj)!=14:
            raise ValueError(f'Identificador inválido na linha {line}; lote cancelado.')
        day=(item.get('DATA_REGISTRO_ANS') or '').strip();date=None
        if day:
            for fmt in ('%d/%m/%Y','%Y-%m-%d'):
                try: date=datetime.strptime(day,fmt).date();break
                except ValueError: pass
            if date is None: raise ValueError(f'Data inválida na linha {line}.')
        rows.append((reg.zfill(6),cnpj,item['RAZAO_SOCIAL'].strip(),
          (item.get('NOME_FANTASIA') or '').strip() or None,item['MODALIDADE'].strip(),
          (item.get('UF') or '').strip() or None,date,ANS_CADOP_URL))
    if not rows: raise ValueError('CADOP vazio; banco preservado.')
    return rows

def fetch_operadoras(conn):
    content=response(ANS_CADOP_URL).content
    try:text=content.decode('utf-8-sig')
    except UnicodeDecodeError:text=content.decode('latin-1')
    rows=parse_operators(text)
    with conn.cursor() as cur:
        execute_values(cur,"""INSERT INTO operadora(registro_ans,cnpj,razao_social,nome_fantasia,
          modalidade,uf_sede,data_registro,fonte,sintetico) VALUES %s ON CONFLICT(registro_ans)
          DO UPDATE SET cnpj=EXCLUDED.cnpj,razao_social=EXCLUDED.razao_social,nome_fantasia=EXCLUDED.nome_fantasia,
          modalidade=EXCLUDED.modalidade,uf_sede=EXCLUDED.uf_sede,data_registro=EXCLUDED.data_registro,
          fonte=EXCLUDED.fonte,sintetico=false,situacao='ativa'""",rows,template='(%s,%s,%s,%s,%s,%s,%s,%s,false)',page_size=500)
        regs=[r[0] for r in rows]
        cur.execute("UPDATE operadora SET situacao='fora_do_cadastro' WHERE fonte=%s AND NOT registro_ans=ANY(%s)", (ANS_CADOP_URL,regs))
        record_load(cur,'operadora',ANS_CADOP_URL,len(rows))
    return len(rows)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--only',nargs='+',choices=['estados','municipios','operadoras'],default=['estados','municipios','operadoras'])
    args=parser.parse_args()
    for key,fn in [('estados',fetch_estados),('municipios',fetch_municipios),('operadoras',fetch_operadoras)]:
        if key not in args.only: continue
        conn=connect()
        try:
            with conn:
                with conn.cursor() as cur: cur.execute('SELECT pg_advisory_xact_lock(76290413)')
                count=fn(conn)
            print(f'{key}: {count} registros confirmados.')
        finally: conn.close()

if __name__=='__main__':main()
