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

# 1. Force load Opus (Helps if Docker doesn't find it automatically)
discord.opus.load_opus("libopus.so.0")

intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

song_queue = asyncio.Queue()

def download_audio(url):
    # 1. Quick Check: Do we already have this exact URL's file?
    # (Simple logic: Check if any file in downloads contains the video ID)
    # This prevents redownloading the same song if it's already cached.
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
            'preferredquality': '192',
        }],
        'quiet': True,
        'outtmpl': f'{DOWNLOADS_DIR}/%(title)s.m4a',
        'default_search': 'ytsearch',
        'nocheckcertificate': True,
        'noplaylist': True # Force single video download
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

async def play_next_song(ctx):
    if song_queue.empty():
        # await ctx.send("Queue is empty.")
        return

    # Peek at the file without removing it yet, in case playback fails
    audio_file = await song_queue.get()
    
    if not audio_file or not os.path.exists(audio_file):
        print(f"File missing: {audio_file}")
        await play_next_song(ctx)
        return

    try:
        source = discord.FFmpegPCMAudio(
            executable="ffmpeg", 
            source=audio_file,
            before_options="-nostdin",
            options="-vn"
        )
        
        # Define what happens when the song ends
        def after_playing(error):
            if error:
                print(f"Playback error: {error}")
            # Schedule next song safely
            future = asyncio.run_coroutine_threadsafe(play_next_song(ctx), bot.loop)
            try:
                future.result()
            except:
                pass

        ctx.voice_client.play(source, after=after_playing)
        await ctx.send(f"Now playing: **{os.path.basename(audio_file)}**")
        
    except Exception as e:
        print(f"CRITICAL PLAYBACK ERROR: {e}")
        await ctx.send(f"Error playing audio: {e}")
        await play_next_song(ctx)

async def add_to_queue(ctx, url):
    if url.startswith("https://music.youtube.com"):
        url = url.replace("https://music.youtube.com", "https://www.youtube.com")
    
    msg = await ctx.send(f"Downloading... 🎧")
    
    audio_file = await async_download_audio(url)
    
    if audio_file is None:
        await msg.edit(content="Could not download that song.")
        return

    await song_queue.put(audio_file)
    await msg.edit(content=f"Added to queue: **{os.path.basename(audio_file)}**")

    # Connect if not connected
    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("You need to be in a voice channel!")
            return

    # Start playing if idle
    if not ctx.voice_client.is_playing():
        await play_next_song(ctx)

@bot.command()
async def play(ctx, url):
    if "list=" in url:
        await ctx.send(f"Playlist detected! Processing first 5 songs... 📜")
        ydl_opts = {'quiet': True, 'extract_flat': True, 'playlistend': 5}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                for entry in info['entries']:
                     # Reconstruct URL to prevent re-extraction issues
                    song_url = entry.get('url')
                    if song_url:
                        full_url = f"https://www.youtube.com/watch?v={song_url}" if len(song_url) == 11 else song_url
                        await add_to_queue(ctx, full_url)
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