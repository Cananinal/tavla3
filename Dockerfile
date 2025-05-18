FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# PORT değişkenini tanımla
ENV PORT 8080

# Uygulama kullanıcısını oluştur
RUN useradd -m nonroot
USER nonroot

# Cloud Run, PORT ortam değişkenini dinler
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app 