# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.11.4-slim-bullseye

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99
ENV CHROME_PATH="/usr/bin/google-chrome"

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

# Install pip
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

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


WORKDIR /app
COPY . /app

ENV PYTHONPATH=/app

# CMD ["gunicorn", "--bind", "0.0.0.0:8000", "scrape_server.wsgi:application"]