# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.10-slim

EXPOSE 8000

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    wget \
    gnupg2 \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Debug Chrome installation
RUN google-chrome --version

# Install chromedriver that matches Chrome version
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d'.' -f1) \
    && echo "Chrome version: $CHROME_VERSION" \
    && CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}") \
    && echo "Chromedriver version: $CHROMEDRIVER_VERSION" \
    && wget -q "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip" \
    && unzip chromedriver_linux64.zip \
    && mv chromedriver /app/ \
    && chmod +x /app/chromedriver \
    && rm chromedriver_linux64.zip

# Debug chromedriver installation
RUN ls -la /app/chromedriver && /app/chromedriver --version

# Additional dependencies that might be needed
RUN apt-get update && apt-get install -y \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Creates a non-root user first
RUN adduser --disabled-password --gecos "" appuser

# Copy project (excluding TLS certs)
COPY --chown=appuser:appuser . .

# Copy TLS certificates and chromedriver with correct permissions
COPY --chown=appuser:appuser client-2048.crt client-2048.key /app/
COPY --chown=appuser:appuser chromedriver.exe /app/
RUN chmod 600 /app/client-2048.* && \
    chmod +x /app/chromedriver.exe

# Set final permissions and switch to appuser
RUN chown -R appuser:appuser /app
USER appuser

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["sh", "-c", "cd scrape_server && python manage.py migrate && python create_superuser.py && python start.py"]
