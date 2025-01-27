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
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Creates a non-root user first
RUN adduser --disabled-password --gecos "" appuser

# Copy project
COPY . .

# Copy TLS certificates with correct permissions
COPY client-2048.crt client-2048.key /app/
RUN chmod 600 /app/client-2048.* && \
    chown appuser:appuser /app/client-2048.*

# Set final permissions and switch to appuser
RUN chown -R appuser:appuser /app
USER appuser

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["sh", "-c", "cd scrape_server && python manage.py migrate && python create_superuser.py && python start.py"]
