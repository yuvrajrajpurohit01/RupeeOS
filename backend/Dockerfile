FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY data /app/data

RUN addgroup --system rupeeos && adduser --system --ingroup rupeeos rupeeos \
    && mkdir -p /var/lib/rupeeos \
    && chown -R rupeeos:rupeeos /app /var/lib/rupeeos

USER rupeeos
WORKDIR /app/backend

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
