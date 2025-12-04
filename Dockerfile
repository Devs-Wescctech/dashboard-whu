FROM python:3.11-slim

# Evita .pyc e força logs sem buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY . .

# Porta interna do container
EXPOSE 5000

# app.py com app = Flask(__name__)
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
