"""Portable entry point: no implicit imports, installs, or seeds."""
import argparse
import os
from migrate import migrate

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--init-db',action='store_true',help='Apply schema and migrations')
    parser.add_argument('--demo',action='store_true',help='Seed a demonstration database explicitly')
    args=parser.parse_args()
    if args.init_db:migrate()
    if args.demo:
        from backend.db import connect
        from seed import seed_demo
        conn=connect()
        try:
            with conn:seed_demo(conn)
        finally:conn.close()
    from api import app
    from waitress import serve
    host=os.getenv('MILTON_HOST','127.0.0.1');port=int(os.getenv('MILTON_PORT','5001'))
    print(f'Milton Analytics: http://{host}:{port}',flush=True)
    serve(app,host=host,port=port,threads=4)

if __name__=='__main__':main()
