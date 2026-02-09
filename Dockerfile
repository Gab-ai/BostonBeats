FROM python:3.11-slim

# 1. Install FFmpeg and Git (git is needed for some yt-dlp dependencies)
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. Set up the working directory
WORKDIR /app

# 3. Copy your requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of your code
COPY . .

# 5. The command to start your bot
CMD ["python", "musicbot.py"]
