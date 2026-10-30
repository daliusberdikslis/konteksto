FROM python:3.11-slim

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Application code and embedding matrix
COPY app ./app
COPY assets/embeddings ./assets/embeddings

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
