FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_PATH=/app/data/ajaia_docs.db
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static
COPY wsgi.py .
EXPOSE 8000
CMD ["sh", "-c", "gunicorn wsgi:app --workers 1 --threads 4 --bind 0.0.0.0:${PORT:-8000}"]
