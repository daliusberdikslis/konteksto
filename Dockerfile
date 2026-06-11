# --- Stage 1: VDU Morphological Analyzer (native binary) ---
FROM semantikadocker.vdu.lt/v2/morph:0.2 AS morph-stage

# --- Stage 2: VDU Lexical Segmenter (Spring Boot Java app) ---
FROM semantikadocker.vdu.lt/lex:latest AS lex-stage

# --- Stage 3: Final image ---
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies: JRE for lex, supervisord, curl, Qt5 for hmorphd2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    supervisor \
    default-jre-headless \
    libqt5network5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire morph filesystem into /opt/morph and keep the binary in place
COPY --from=morph-stage / /opt/morph-root/

# Symlink the morph binary and set up library path via wrapper script
RUN printf '#!/bin/sh\nLD_LIBRARY_PATH=/opt/morph-root/usr/lib/x86_64-linux-gnu:/opt/morph-root/lib/x86_64-linux-gnu:/opt/morph-root/usr/lib:/opt/morph-root/lib exec /opt/morph-root/usr/bin/hmorphd2 "$@"\n' > /usr/local/bin/run-morph \
    && chmod +x /usr/local/bin/run-morph

# Copy VDU lex (Spring Boot app)
COPY --from=lex-stage /app /opt/lex

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Application code
COPY app ./app

# Supervisord config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Download Lithuanian fastText vectors at build time
RUN mkdir -p assets \
    && curl -fsSL -o assets/cc.lt.300.bin.gz \
        https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.lt.300.bin.gz \
    && gzip -dc assets/cc.lt.300.bin.gz > assets/cc.lt.300.bin \
    && rm assets/cc.lt.300.bin.gz

EXPOSE 7860

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
