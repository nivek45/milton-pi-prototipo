"""Validate real DDL in an isolated PostgreSQL schema, always rolled back."""
from pathlib import Path
from uuid import uuid4
from psycopg2 import sql
from backend.db import connect

def validate_sql(filepath=None):
    conn=connect()
    try:
        with conn.cursor() as cur:
            name='validate_'+uuid4().hex
            cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(name)))
            cur.execute(sql.SQL('SET LOCAL search_path TO {},public').format(sql.Identifier(name)))
            cur.execute(Path(filepath or Path(__file__).with_name('schema.sql')).read_text(encoding='utf-8-sig'))
        print('DDL executado com sucesso no PostgreSQL; transação de validação desfeita.')
    finally:conn.rollback();conn.close()

if __name__=='__main__':validate_sql()
