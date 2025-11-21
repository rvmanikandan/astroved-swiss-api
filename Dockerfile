FROM python:3.12-slim

# Fix the libsqlite3 error permanently
RUN apt-get update && apt-get install -y libsqlite3-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "${PORT:-8080}"]
