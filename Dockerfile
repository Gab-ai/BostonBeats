FROM python:3.11-slim

# Install system dependencies
# nodejs: Required for yt-dlp to bypass bot detection
# ffmpeg: For audio processing
# libopus-dev: Required for Discord voice
RUN apt-get update && \
    apt-get install -y ffmpeg nodejs git libopus-dev libsodium-dev ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ensure downloads folder is ready
RUN mkdir -p downloads && chmod 777 downloads

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Force a check to see where ffmpeg is during build
RUN which ffmpeg && which node

CMD ["python", "musicbot.py"]
