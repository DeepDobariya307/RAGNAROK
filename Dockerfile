# ── RAGNAROK Dockerfile ───────────────────────────────────────────────────────
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Streamlit config — disable telemetry, set server options
RUN mkdir -p ~/.streamlit && echo "\
[general]\n\
email = \"\"\n\
\n\
[server]\n\
headless = true\n\
enableCORS = false\n\
enableXsrfProtection = false\n\
" > ~/.streamlit/config.toml

EXPOSE 8501

# Railway injects $PORT — Streamlit must bind to it
CMD streamlit run app.py \
    --server.port=${PORT:-8501} \
    --server.address=0.0.0.0
