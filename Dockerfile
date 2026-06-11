# --- Stage 1: VDU Morphological Analyzer (native binary) ---
FROM semantikadocker.vdu.lt/v2/morph:0.2 AS morph-stage

# --- Stage 2: VDU Lexical Segmenter (Spring Boot Java app) ---
FROM semantikadocker.vdu.lt/lex:latest AS lex-stage

# --- Stage 3: Final image ---
FROM python:3.11-slim

WORKDIR /app

# Runtime deps for lex (JRE), process manager, and hmorphd2 (bundled Ubuntu 18.04 libs below)
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# hmorphd2 is built for Ubuntu 18.04 / Qt 5.9 — copy only its binary and matching libs.
# Do NOT install Debian Qt packages or copy the full morph rootfs (glibc/ICU conflicts).
COPY --from=morph-stage /usr/bin/hmorphd2 /usr/local/bin/hmorphd2
COPY --from=morph-stage /etc/hmorph2.ini /etc/hmorph2.ini
COPY --from=morph-stage /usr/local/share/hs_dictionaries /usr/local/share/hs_dictionaries
COPY --from=morph-stage /usr/lib/x86_64-linux-gnu/libQt5Core.so.5.9.5 /usr/local/lib/morph/
COPY --from=morph-stage /usr/lib/x86_64-linux-gnu/libQt5Network.so.5.9.5 /usr/local/lib/morph/
COPY --from=morph-stage /usr/lib/x86_64-linux-gnu/libdouble-conversion.so.1 /usr/local/lib/morph/
COPY --from=morph-stage /usr/lib/x86_64-linux-gnu/libglib-2.0.so.0.5600.4 /usr/local/lib/morph/
COPY --from=morph-stage /usr/lib/x86_64-linux-gnu/libicudata.so.60 /usr/local/lib/morph/
COPY --from=morph-stage /usr/lib/x86_64-linux-gnu/libicui18n.so.60 /usr/local/lib/morph/
COPY --from=morph-stage /usr/lib/x86_64-linux-gnu/libicuuc.so.60 /usr/local/lib/morph/

RUN set -eux; \
    mkdir -p /var/log; \
    cd /usr/local/lib/morph; \
    ln -sf libQt5Core.so.5.9.5 libQt5Core.so.5; \
    ln -sf libQt5Network.so.5.9.5 libQt5Network.so.5; \
    ln -sf libglib-2.0.so.0.5600.4 libglib-2.0.so.0; \
    echo "/usr/local/lib/morph" > /etc/ld.so.conf.d/morph.conf; \
    ldconfig; \
    ldd /usr/local/bin/hmorphd2; \
    test -z "$(ldd /usr/local/bin/hmorphd2 | grep 'not found' || true)"

# Copy VDU lex (Spring Boot app)
COPY --from=lex-stage /app /opt/lex

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Application code and precomputed game data
COPY app ./app
COPY games ./games

# Supervisord config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 7860

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
