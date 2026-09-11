"""Bounded pool, read-only transactions, shared configuration for ETL."""
import atexit
import os
import threading
from pathlib import Path
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

# Same .env file used by Docker Compose; do not override explicitly exported values.
env_file=Path(__file__).resolve().parent.parent/'.env'
if env_file.exists():
    for line in env_file.read_text(encoding='utf-8-sig').splitlines():
        if line.strip().startswith('#') or '=' not in line:continue
        key,value=line.split('=',1);key=key.strip();value=value.strip()
        if len(value)>1 and value[0]==value[-1] and value[0] in "\"'":value=value[1:-1]
        if key.startswith('MILTON_'):os.environ.setdefault(key,value)

DB_CONFIG = {
    'host': os.getenv('MILTON_DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('MILTON_DB_PORT', '5432')),
    'dbname': os.getenv('MILTON_DB_NAME', 'miltondb'),
    'user': os.getenv('MILTON_DB_USER', 'milton'),
    'password': os.getenv('MILTON_DB_PASS', ''),
    'connect_timeout': 5,
    'application_name': 'milton-analytics',
}
_pool = None
_lock = threading.Lock()

def connect():
    return psycopg2.connect(**DB_CONFIG)

def pool():
    global _pool
    with _lock:
        if _pool is None:
            _pool = ThreadedConnectionPool(1, 8, **DB_CONFIG)
    return _pool

@contextmanager
def reader():
    p = pool()
    conn = p.getconn()
    try:
        conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            yield cursor
        conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)

def close_pool():
    global _pool
    with _lock:
        if _pool:
            _pool.closeall()
            _pool = None

atexit.register(close_pool)
