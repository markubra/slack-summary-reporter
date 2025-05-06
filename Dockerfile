FROM python:3.12-slim

RUN addgroup --system reporter && adduser --system --ingroup reporter reporter

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R reporter:reporter /app

USER reporter

CMD ["python", "main.py"]
