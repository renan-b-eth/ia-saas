# 1. Base com Python
FROM python:3.11-slim

# 2. Instala dependências de sistema como ROOT
USER root

RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    python3-dev \
    libcairo2-dev \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    redis-server \
    ffmpeg \
    imagemagick \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# 3. Configura ImageMagick (Desbloqueia escrita para o MoviePy)
RUN sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml || true
RUN sed -i 's/domain="path" rights="none" pattern="@\*"/domain="path" rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml || true

# 4. Cria o usuário ANTES de tentar usá-lo
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /app

# 5. Instala Python libs (Como o usuário 1000 para evitar erros de permissão)
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# 6. Copia o restante do código
COPY --chown=user . .

# Garante que a pasta /tmp (onde ficarão os vídeos) seja acessível
RUN chmod -R 777 /tmp

# Volta para o usuário comum (Requisito do Hugging Face)
USER user

# 7. Inicia Redis e App (Gunicorn configurado para o HF)
# 1. Base com Python
FROM python:3.11-slim

# 2. Instala dependências de sistema como ROOT
USER root

RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    python3-dev \
    libcairo2-dev \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    redis-server \
    ffmpeg \
    imagemagick \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# 3. Configura ImageMagick (Desbloqueia escrita para o MoviePy)
RUN sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml || true
RUN sed -i 's/domain="path" rights="none" pattern="@\*"/domain="path" rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml || true

# 4. Cria o usuário ANTES de tentar usá-lo
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /app

# 5. Instala Python libs (Como o usuário 1000 para evitar erros de permissão)
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# 6. Copia o restante do código
COPY --chown=user . .

# Garante que a pasta /tmp (onde ficarão os vídeos) seja acessível
RUN chmod -R 777 /tmp

# Volta para o usuário comum (Requisito do Hugging Face)
USER user

# 7. Inicia Redis e App (Gunicorn configurado para o HF)
CMD redis-server --daemonize yes && gunicorn app:app --bind 0.0.0.0:7860 --workers 2 --threads 4 --timeout 300