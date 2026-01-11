# ============================================
# Stage 1: Builder do CSS (DaisyUI Standalone)
# ============================================
FROM debian:bookworm-slim AS css-builder

WORKDIR /build

# 1. Instala curl para baixar o executável
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 2. Baixa o binário do Tailwind+DaisyUI e dá permissão de execução
RUN curl -sL https://github.com/dospinacoz/tailwindcss-daisyui/releases/latest/download/tailwindcss-linux-x64 -o tailwindcss \
    && chmod +x tailwindcss

# 3. CRUCIAL: Copia o projeto TODO para o builder
# O Tailwind precisa ler TODOS os seus .html para gerar o CSS
COPY . .

# 4. Compila o CSS
# Ajuste os caminhos abaixo se sua estrutura de pastas for diferente de 'baboom/static/...'
# -i: Onde está seu input.css (fonte)
# -o: Onde vai salvar o output.css (destino)
RUN ./tailwindcss -i baboom/static/css/input.css -o output.css --minify


# ============================================
# Stage 2: Aplicação Python (Final)
# ============================================
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências do OS
RUN apt-get update && apt-get install -y \
    libpq-dev gcc gettext \
    && rm -rf /var/lib/apt/lists/*

# Usuário de segurança
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Instala Python Libs
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código do projeto
COPY . /app/

# --- AQUI É A CORREÇÃO ---
# Copia o arquivo gerado no Stage 1 para a pasta exata onde o Django espera
COPY --from=css-builder /build/output.css /app/baboom/static/css/output.css

# Permissões
RUN chown -R appuser:appuser /app
USER appuser

# Agora o collectstatic vai funcionar porque o arquivo output.css EXISTE fisicamente
RUN python manage.py compilemessages --ignore=.venv || true
RUN python manage.py collectstatic --noinput --clear

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && gunicorn --bind 0.0.0.0:8000 --workers 3 --access-logfile - baboom.wsgi:application"]