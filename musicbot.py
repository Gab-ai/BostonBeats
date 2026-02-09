import discord
from discord.ext import commands
import yt_dlp
import asyncio
import concurrent.futures
import os
import shutil  # <--- NEW: This tool finds installed programs
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Ensure the downloads directory exists
DOWNLOADS_DIR = './downloads'
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# --- THE FIX: Find FFmpeg automatically ---
FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"
# Print it to the logs so we can verify it was found
print(f"------------------------------------------------")
print(f"SYSTEM CHECK: FFmpeg found at: {FFMPEG_PATH}")
print(f"------------------------------------------------")
# ------------------------------------------

intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

song_queue = asyncio.Queue()

def download_audio(url):
    # 1. Check Cache
    ydl_opts_info = {'quiet': True, 'no_warnings': True, 'format': 'bestaudio/best'}
    with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'song').replace('/', '_')
            expected_file = os.path.join(DOWNLOADS_DIR, f"{title}.m4a")
            if os.path.exists(expected_file):
                print(f"--- Cache Hit: {expected_file} ---")
                return expected_file
        except:
            pass

    # 2. Download
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
            'preferredquality': '192',
        }],
        # USE THE FOUND PATH HERE
        'ffmpeg_location': FFMPEG_PATH, 
        'quiet': True,
        'outtmpl': f'{DOWNLOADS_DIR}/%(title)s.m4a',
        'default_search': 'ytsearch',
        'nocheckcertificate': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
        except Exception as e:
            print(f"Error downloading audio: {e}")
            return None

async def async_download_audio(url):
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, download_audio, url)

async def add_to_queue(ctx, url):
    if url.startswith("https://music.youtube.com"):
        url = url.replace("https://music.youtube.com", "https://www.youtube.com")
    
    await ctx.send(f"Processing... 🎧")
    audio_file = await async_download_audio(url)
    
    if audio_file is None:
        await ctx.send("Could not download that song. (Check logs for ffmpeg error)")
        return

    await song_queue.put(audio_file)
    await ctx.send(f"Added to queue!")

    if ctx.voice_client is None:
        if ctx.author.voice: