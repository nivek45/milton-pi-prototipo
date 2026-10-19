"""Run the public dashboard on loopback with a production WSGI server."""
import os
from backend.routes import app

if __name__ == '__main__':
    from waitress import serve
    serve(app, host=os.getenv('MILTON_HOST', '127.0.0.1'),
          port=int(os.getenv('MILTON_PORT', '5001')), threads=4)
