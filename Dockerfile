# Gebruik Python 3.12 base image
FROM python:3.12-slim

# Installeer systeem dependencies voor Chromium en Selenium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    apt-transport-https \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Installeer Chromium
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Stel werk directory in
WORKDIR /app

# Kopieer requirements eerst (voor caching)
COPY requirements.txt .

# Installeer Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Kopieer alle applicatie bestanden
COPY . .

# Stel environment variables in
ENV CHROME_BIN=/usr/bin/chromium
ENV PYTHONUNBUFFERED=1

# Expose poort (Railway zet PORT automatisch)
EXPOSE 5000

# Start commando - gebruik PORT environment variable van Railway
CMD python app.py

