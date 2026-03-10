FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lmrs/ .

EXPOSE 7890

CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn lmrs.wsgi:application --bind 0.0.0.0:7890"]