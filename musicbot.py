import discord
from discord.ext import commands
import yt_dlp
import asyncio
import concurrent.futures
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Ensure the downloads directory exists
DOWNLOADS_DIR = './downloads'
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Define the bot
intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

song_queue = asyncio.Queue()

def download_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
            'preferredquality': '192',
        }],
        # DELETED: 'ffmpeg_location' (Let Railway find it automatically)
        # DELETED: 'ffprobe_location'
        'quiet': True,
        'outtmpl': f'{DOWNLOADS_DIR}/%(title)s.m4a', # FIXED: Relative path
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
        await ctx.send("Could not download that song.")
        return

    await song_queue.put(audio_file)
    await ctx.send(f"Added to queue!")

    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("You need to be in a voice channel!")
            return

    if not ctx.voice_client.is_playing():
        await play_next_song(ctx)

async def play_next_song(ctx):
    if not song_queue.empty():
        audio_file = await song_queue.get()
        
        if not audio_file or not os.path.exists(audio_file):
            await play_next_song(ctx)
            return

        source = discord.FFmpegPCMAudio(
            executable="ffmpeg", # FIXED: Removed /usr/bin/
            source=audio_file,
            before_options="-nostdin",
            options="-vn"
        )

        ctx.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next_song(ctx), bot.loop))
    else:
        await ctx.send("Queue is empty.")

@bot.command()
async def play(ctx, url):
    # Added your playlist support back in
    if "list=" in url:
        await ctx.send(f"Playlist detected! Processing first 10 songs... 📜")
        ydl_opts = {'quiet': True, 'extract_flat': True, 'playlistend': 10}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                for entry in info.get('entries', []):
                    song_url = entry.get('url')
                    if song_url:
                        if not song_url.startswith('http'):
                            song_url = f"https://www.youtube.com/watch?v={song_url}"
                        await add_to_queue(ctx, song_url)
            except Exception as e:
                await ctx.send(f"Playlist error: {e}")
    else:
        await add_to_queue(ctx, url)

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        for file in os.listdir(DOWNLOADS_DIR):
            try: os.remove(os.path.join(DOWNLOADS_DIR, file))
            except: pass
    else:
        await ctx.send("I'm not in a voice channel!")

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped! ⏭️")

bot.run(TOKEN)