# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.11.4-slim-bullseye

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8080
ENV DISPLAY=:99
ENV PATH="/usr/local/bin:${PATH}"
ENV CHROME_PATH="/usr/bin/google-chrome"
ENV PYTHONPATH=/app:/app/scrape_server
ENV DJANGO_SETTINGS_MODULE=scrape_server.settings
WORKDIR /app

# Install essential system dependencies and build tools
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    gcc \
    python3-dev \
    build-essential \
    libpq-dev \
    curl \
    unzip \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome and ChromeDriver
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* \
    && LATEST_VERSION=$(wget -qO- https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE) \
    && wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${LATEST_VERSION}/linux64/chromedriver-linux64.zip" \
    && unzip chromedriver-linux64.zip \
    && mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf chromedriver-linux64.zip chromedriver-linux64

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .

CMD ["sh", "-c", "chmod +x /app/start.sh && /app/start.sh"]

EXPOSE ${PORT}
