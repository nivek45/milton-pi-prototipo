"""Apply the complete schema to a fresh database, or atomic migrations to a legacy one."""
from pathlib import Path
from contextlib import closing
from backend.db import connect
ROOT=Path(__file__).resolve().parent

def migrate():
    with closing(connect()) as conn, conn:
        with conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(76290412)')
            cur.execute("SELECT to_regclass('public.estado')")
            fresh=cur.fetchone()[0] is None
            cur.execute('CREATE TABLE IF NOT EXISTS schema_migrations(name text PRIMARY KEY,applied_at timestamptz NOT NULL DEFAULT now())')
            if fresh:
                cur.execute((ROOT/'schema.sql').read_text(encoding='utf-8-sig'))
                cur.execute("INSERT INTO schema_migrations(name) VALUES('001_integrity.sql') ON CONFLICT DO NOTHING")
            else:
                for path in sorted((ROOT/'migrations').glob('*.sql')):
                    cur.execute('SELECT 1 FROM schema_migrations WHERE name=%s',(path.name,))
                    if cur.fetchone(): continue
                    cur.execute(path.read_text(encoding='utf-8'))
                    cur.execute('INSERT INTO schema_migrations(name) VALUES(%s)',(path.name,))
    print('Schema atualizado; dados existentes preservados.')

if __name__=='__main__': migrate()
