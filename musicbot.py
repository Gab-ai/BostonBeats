import discord
from discord.ext import commands
import yt_dlp
import asyncio
import concurrent.futures
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

DOWNLOADS_DIR = './downloads'
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

song_queue = asyncio.Queue()

def download_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'outtmpl': f'{DOWNLOADS_DIR}/%(title)s.m4a',
        'noplaylist': True,
        'nocheckcertificate': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
        except Exception as e:
            print(f"Download Error: {e}")
            return None

async def async_download_audio(url):
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, download_audio, url)

async def play_next_song(ctx):
    if song_queue.empty():
        return

    audio_file = await song_queue.get()
    
    if not audio_file or not os.path.exists(audio_file):
        print(f"File missing: {audio_file}")
        await play_next_song(ctx)
        return

    try:
        # --- THE FIX IS HERE ---
        # We removed 'before_options' because you cannot use -reconnect on a local file.
        source = await discord.FFmpegOpusAudio.from_probe(
            audio_file,