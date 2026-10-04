from waitress import serve
from src.restikls import create_app

if __name__ == '__main__':
    serve(create_app(), host='127.0.0.1', port=5000, threads=4)
