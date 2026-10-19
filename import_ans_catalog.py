"""Import a complete official ANS catalog atomically; never seed mock data.

Usage: python import_ans_catalog.py --directory PATH [--download]
Target database is the usual MILTON_DB_NAME. The app's Pessoa Comum reader
uses MILTON_COMMON_DB_NAME (default miltondb), independently of demo profiles.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import requests
from psycopg2.extras import execute_values
from backend.db import connect
from fetch_real_data import parse_operators, record_load, ANS_CADOP_URL

BASE='https://dadosabertos.ans.gov.br/FTP/PDA/'
SOURCES={
 'planos.csv':BASE+'caracteristicas_produtos_saude_suplementar-008/pda-008-caracteristicas_produtos_saude_suplementar.csv',
 'municipios-planos.csv':BASE+'caracteristicas_produtos_saude_suplementar-008/pda-008-tabela_auxiliar_de_detalhamento_de_municipios.csv',
 'cadop.csv':ANS_CADOP_URL,
}

def download(directory):
    directory.mkdir(parents=True,exist_ok=True)
    for name,url in SOURCES.items():
        target=directory/name; partial=target.with_suffix('.part')
        with requests.get(url,stream=True,timeout=(10,90)) as response:
            response.raise_for_status()
            with partial.open('wb') as output:
                for chunk in response.iter_content(1024*1024): output.write(chunk)
        partial.replace(target)

def rows(path,required):
    # ANS publishes these two PDA-008 CSVs as UTF-8. Fail on encoding/header
    # changes instead of silently replacing names or identifiers.
    with path.open(encoding='utf-8-sig',newline='') as handle:
        reader=csv.DictReader(handle,delimiter=';')
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f'Cabeçalho inesperado: {path.name}')
        yield from reader

def plan_row(row):
    return (int(row['ID_PLANO']),row['CD_PLANO'].strip(),row['NM_PLANO'].strip(),
      row['REGISTRO_OPERADORA'].strip().zfill(6),row['CONTRATACAO'],
      row['SGMT_ASSISTENCIAL'],row['ABRANGENCIA_COBERTURA'],row['ID_GEO_COBERTURA'] or None,
      row['FATOR_MODERADOR'],row['ACOMODACAO_HOSPITALAR'],row['SITUACAO_PLANO'],row['DT_ATUALIZACAO'])

def import_catalog(directory):
    plans=[plan_row(row) for row in rows(directory/'planos.csv',
      {'ID_PLANO','CD_PLANO','ID_GEO_COBERTURA','SITUACAO_PLANO','DT_ATUALIZACAO'})]
    if len(plans)<10000 or len({row[0] for row in plans})!=len(plans):
        raise ValueError('Catálogo incompleto ou identificadores duplicados; banco preservado.')
    content=(directory/'cadop.csv').read_bytes()
    try: content=content.decode('utf-8-sig')
    except UnicodeDecodeError: content=content.decode('latin-1')
    operators=parse_operators(content)
    if len(operators)<500: raise ValueError('Cadastro de operadoras incompleto.')
    conn=connect()
    try:
      with conn,conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(76290414)')
        cur.execute((Path(__file__).parent/'migrations/002_ans_catalog.sql').read_text(encoding='utf-8'))
        cur.execute('SELECT codigo_ibge FROM municipio WHERE NOT sintetico')
        codes={row[0][:6]:row[0] for row in cur.fetchall()}
        if len(codes)<5000: raise ValueError('Carregue a malha municipal real do IBGE primeiro.')
        execute_values(cur,"""INSERT INTO operadora(registro_ans,cnpj,razao_social,nome_fantasia,
          modalidade,uf_sede,data_registro,fonte,sintetico) VALUES %s
          ON CONFLICT(registro_ans) DO UPDATE SET cnpj=EXCLUDED.cnpj,razao_social=EXCLUDED.razao_social,
          nome_fantasia=EXCLUDED.nome_fantasia,modalidade=EXCLUDED.modalidade,uf_sede=EXCLUDED.uf_sede,
          data_registro=EXCLUDED.data_registro,fonte=EXCLUDED.fonte,sintetico=false,situacao='ativa'""",
          operators,template='(%s,%s,%s,%s,%s,%s,%s,%s,false)',page_size=1000)
        cur.execute("UPDATE operadora SET situacao='fora_do_cadastro' WHERE fonte=%s AND NOT registro_ans=ANY(%s)",
          (ANS_CADOP_URL,[row[0] for row in operators]))
        # Transactional DELETE permits old readers to finish seeing the previous
        # snapshot; a failed import rolls back the whole replacement.
        cur.execute('DELETE FROM ans_resumo; DELETE FROM ans_geo_estado; DELETE FROM ans_geografia; DELETE FROM ans_plano')
        execute_values(cur,'INSERT INTO ans_plano VALUES %s',plans,page_size=1000)
        buffer=io.StringIO(); count=0; unmatched=set()
        for row in rows(directory/'municipios-planos.csv',{'ID_DETALHE_AREA_GEOGRAFICA','CD_MUNICIPIO'}):
            code=row['CD_MUNICIPIO'].strip(); full=codes.get(code[:6])
            if not full: unmatched.add(code);continue
            buffer.write(row['ID_DETALHE_AREA_GEOGRAFICA']+'\t'+full+'\n');count+=1
        if count<10000 or unmatched:
            raise ValueError(f'Geografia incompleta ou códigos sem correspondência IBGE: {sorted(unmatched)[:20]}')
        buffer.seek(0)
        cur.execute('CREATE TEMP TABLE ans_geo_stage (geo_id text,codigo_ibge text) ON COMMIT DROP')
        cur.copy_from(buffer,'ans_geo_stage',columns=('geo_id','codigo_ibge'))
        cur.execute('INSERT INTO ans_geografia SELECT DISTINCT geo_id,codigo_ibge FROM ans_geo_stage')
        cur.execute('''INSERT INTO ans_geo_estado SELECT DISTINCT g.geo_id,e.sigla
          FROM ans_geografia g JOIN municipio m ON m.codigo_ibge=g.codigo_ibge JOIN estado e ON e.id=m.id_estado''')
        cur.execute('''INSERT INTO ans_resumo
          SELECT e.sigla,COUNT(DISTINCT p.id),COUNT(DISTINCT o.id)
          FROM estado e LEFT JOIN ans_geo_estado g ON g.uf=e.sigla
          LEFT JOIN (ans_plano p JOIN operadora o ON o.registro_ans=p.registro_operadora
            AND NOT o.sintetico AND o.situacao='ativa') ON p.geo_id=g.geo_id AND p.situacao='Ativo'
          GROUP BY e.sigla''')
        record_load(cur,'ans_catalogo',SOURCES['planos.csv'],len(plans))
        record_load(cur,'ans_geografia',SOURCES['municipios-planos.csv'],count)
        record_load(cur,'ans_operadoras',SOURCES['cadop.csv'],len(operators))
        cur.execute('ANALYZE ans_plano; ANALYZE ans_geografia; ANALYZE ans_geo_estado; ANALYZE ans_resumo')
      manifest={name:{'url':url,'sha256':hashlib.sha256((directory/name).read_bytes()).hexdigest()}
        for name,url in SOURCES.items()}
      (directory/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
      print(f'Importação confirmada: {len(plans)} planos, {count} relações geográficas, {len(operators)} operadoras.',flush=True)
    finally: conn.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--download',action='store_true')
    args=parser.parse_args()
    if args.download: download(args.directory)
    import_catalog(args.directory)
