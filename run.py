# run.py

from dotenv import load_dotenv
from waitress import serve
from app import app

# Cargar las variables de entorno desde el archivo .env ANTES de hacer cualquier otra cosa
load_dotenv()

if __name__ == '__main__':
    # Iniciar el servidor de producción Waitress
    serve(app, host='127.0.0.1', port=5000)