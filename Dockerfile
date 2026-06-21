FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends nginx && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Nginx serves the metrics file
RUN echo 'server { listen 9100; root /app/metrics; location / { types {} default_type text/plain; index index.html; try_files $uri $uri/ /index.html; } }' > /etc/nginx/sites-available/default

RUN mkdir -p /app/metrics && echo "" > /app/metrics/index.html

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 9100

CMD ["/entrypoint.sh"]
