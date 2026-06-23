FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_MAX_UPLOAD_SIZE=10240

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app ./app
COPY main.py ./main.py
COPY VERSION ./VERSION
COPY CHANGELOG.md ./CHANGELOG.md
COPY docs ./docs
COPY tests ./tests

RUN PYTHONPYCACHEPREFIX=/tmp/pycache python -m compileall -q app main.py \
    && rm -rf /tmp/pycache

RUN mkdir -p imports imports/archive cache config

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=3 \
    CMD curl -f http://127.0.0.1:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app/ui/dashboard.py"]
