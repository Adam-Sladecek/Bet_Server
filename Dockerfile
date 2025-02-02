# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.10-slim

EXPOSE 8000

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

# Set work directory
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

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy TLS certificates and chromedriver with correct permissions
COPY client-2048.crt client-2048.key /app/
RUN chmod 600 /app/client-2048.*

# Copy project files
COPY . .

# Add these before the CMD line
ENV PATH="/usr/local/bin:${PATH}"
ENV CHROME_PATH="/usr/bin/google-chrome"

CMD ["sh", "-c", "Xvfb :99 -screen 0 1920x1080x16 & cd scrape_server && python manage.py migrate && python create_superuser.py && python start.py"]
