FROM python:3.11-slim

# Install system dependencies
# ca-certificates: Ensures secure connections to YouTube
# nodejs: Required for yt-dlp to run signature descrambling scripts
RUN apt-get update && \
    apt-get install -y ffmpeg git libopus-dev libffi-dev libsodium-dev nodejs ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ensure downloads directory is ready and writeable
RUN mkdir -p downloads && chmod 777 downloads

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "musicbot.py"]
