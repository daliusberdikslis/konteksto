FROM python:3.11-slim

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Application code, embedding matrix, morphology dicts, legacy game data
COPY app ./app
COPY assets/embeddings ./assets/embeddings
COPY assets/hunspell ./assets/hunspell
COPY games ./games

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
