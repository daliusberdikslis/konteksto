FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

RUN python -c "import stanza; stanza.download('lt', processors='tokenize,pos,lemma')"

COPY app ./app

# Download Lithuanian fastText vectors at build time (avoids 1 GB HF repo storage limit).
RUN mkdir -p assets \
    && curl -fsSL -o assets/cc.lt.300.bin.gz \
        https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.lt.300.bin.gz \
    && gzip -dc assets/cc.lt.300.bin.gz > assets/cc.lt.300.bin \
    && rm assets/cc.lt.300.bin.gz

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
