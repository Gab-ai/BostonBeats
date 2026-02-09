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

# --- NEW: Robust Audio Options ---
# This forces FFmpeg to handle the Opus encoding, which fixes the "Silence" bug on Linux
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}
# ---------------------------------

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
        # UPDATED PLAYER: Uses FFmpegOpusAudio instead of PCMAudio
        source = await discord.FFmpegOpusAudio.from_probe(
            audio_file,
            **FFMPEG_OPTIONS,
            executable="ffmpeg"
        )
        
        def after_playing(error):
            if error:
                print(f"Playback Error: {error}")
            print("Song finished.")
            asyncio.run_coroutine_threadsafe(play_next_song(ctx), bot.loop)

        ctx.voice_client.play(source, after=after_playing)
        await ctx.send(f"▶️ Now playing: **{os.path.basename(audio_file)}**")
        print(f"Attempting to play: {audio_file}")
        
    except Exception as e:
        print(f"CRITICAL PLAYBACK ERROR: {e}")
        await ctx.send(f"Error playing audio: {e}")
        await play_next_song(ctx)

async def add_to_queue(ctx, url):
    if "music.youtube.com" in url:
        url = url.replace("music.youtube.com", "www.youtube.com")
    
    msg = await ctx.send(f"Downloading... 🎧")
    audio_file = await async_download_audio(url)
    
    if not audio_file:
        await msg.edit(content="Could not download that song.")
        return

    await song_queue.put(audio_file)
    await msg.edit(content=f"Added to queue: **{os.path.basename(audio_file)}**")

    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("You need to be in a voice channel!")
            return

    if not ctx.voice_client.is_playing():
        await play_next_song(ctx)

@bot.command()
async def play(ctx, url):
    await add_to_queue(ctx, url)

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    else:
        await ctx.send("I'm not in a voice channel!")

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped! ⏭️")

bot.run(TOKEN)