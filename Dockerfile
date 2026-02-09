FROM python:3.11-slim

# Install system dependencies
# ffmpeg: For audio conversion
# git: For yt-dlp dependencies
# libopus-dev: REQUIRED for Discord voice audio
# libffi-dev & libsodium-dev: Required for PyNaCl (voice encryption)
# nodejs: Fixes the yt-dlp "JavaScript" warning and speeds up downloads
RUN apt-get update && \
    apt-get install -y ffmpeg git libopus-dev libffi-dev libsodium-dev nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "musicbot.py"]
