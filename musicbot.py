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
intents.message_content = True  # Required for !play to work
bot = commands.Bot(command_prefix="!", intents=intents)

# --- NEW: Queue, Loop, and Volume State Variables ---
song_queue = asyncio.Queue()
is_looping = False
current_song = None
current_volume = 1.0  # 1.0 is 100% volume
# --------------------------------------------------

def download_audio(url):
    # 1. Get the info first WITHOUT downloading to see the filename
    ydl_opts_info = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestaudio/best',
    }
    
    with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            filename = ydl.prepare_filename(info).replace('.webm', '.m4a').replace('.opus', '.m4a')
            
            # Check if we already have this file in our ./downloads folder
            if os.path.exists(filename):
                print(f"--- Cache Hit: {filename} ---")
                return filename
        except:
            pass # If info fetch fails, we'll try the full download anyway

    # 2. If not in cache, proceed with the download
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
            'preferredquality': '192',
        }],
        'ffmpeg_location': 'ffmpeg', 
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
    
    await ctx.send(f"Searching and downloading... 🎧")
    
    # Download the song
    audio_file = await async_download_audio(url)
    
    # CRITICAL CHECK: If download failed, stop here. Don't crash!
    if audio_file is None:
        await ctx.send("Could not download that song. Try a different link.")
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
    global is_looping, current_song, current_volume

    # If we are NOT looping, or we don't have a song saved yet, grab the next one
    if not is_looping or current_song is None:
        if song_queue.empty():
            current_song = None # Clear memory when queue finishes
            return
        current_song = await song_queue.get()

    audio_file = current_song
        
    # Double check file exists
    if not audio_file or not os.path.exists(audio_file):
        print(f"File missing: {audio_file}")
        is_looping = False # Force loop off if file is broken
        await play_next_song(ctx) # Skip to next
        return

    try:
        # Create the raw FFmpeg audio source
        ffmpeg_source = discord.FFmpegPCMAudio(
            executable="ffmpeg",
            source=audio_file,
            before_options="-nostdin",
            options="-vn"
        )
        
        # --- NEW: Wrap it in a Volume Transformer ---
        source = discord.PCMVolumeTransformer(ffmpeg_source, volume=current_volume)
        
        def after_playing(error):
            if error:
                print(f"Playback Error: {error}")
            # Schedule next song safely
            asyncio.run_coroutine_threadsafe(play_next_song(ctx), bot.loop)

        ctx.voice_client.play(source, after=after_playing)
        
        # Only announce "Now playing" if we just started the song, not every time it loops
        if not is_looping:
            await ctx.send(f"▶️ Now playing: **{os.path.basename(audio_file)}**")
            
    except Exception as e:
        print(f"CRITICAL PLAYBACK ERROR: {e}")
        await ctx.send(f"Error playing audio: {e}")
        is_looping = False
        await play_next_song(ctx)

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()
        await ctx.send("Joined!")
    else:
        await ctx.send("Join a voice channel first.")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        # Cleanup files
        for file in os.listdir(DOWNLOADS_DIR):
            try:
                os.remove(os.path.join(DOWNLOADS_DIR, file))
            except:
                pass
    else:
        await ctx.send("I'm not in a voice channel!")

@bot.command()
async def play(ctx, url):
    # 1. Handle YouTube Music Playlist Links
    if "music.youtube.com" in url and "list=" in url:
        url = url.replace("music.youtube.com", "www.youtube.com")

    # 2. Check if it's a Playlist
    if "list=" in url:
        await ctx.send(f"playlist detected! processing... 📜")
        
        ydl_opts = {
            'quiet': True,
            'extract_flat': True, 
            'dump_single_json': True,
            'playlistend': 20 # SAFETY LIMIT
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    songs = info['entries']
                    await ctx.send(f"Found {len(songs)} songs. Adding to queue...")
                    
                    for song in songs:
                        song_url = song.get('url')
                        if not song_url.startswith('http'):
                            song_url = f"https://www.youtube.com/watch?v={song_url}"
                        await add_to_queue(ctx, song_url)
                else:
                    await add_to_queue(ctx, url)
            except Exception as e:
                await ctx.send(f"Error processing playlist: {str(e)}")
    else:
        # 3. Not a playlist? Just play normally
        await add_to_queue(ctx, url)

@bot.command()
async def loop(ctx):
    global is_looping
    is_looping = not is_looping # Toggles between True and False
    
    if is_looping:
        await ctx.send("🔁 **Looping enabled!** The current song will play forever.")
    else:
        await ctx.send("➡️ **Looping disabled!** The queue will continue normally.")

@bot.command()
async def skip(ctx):
    global is_looping
    if ctx.voice_client and ctx.voice_client.is_playing():
        # If we skip while looping, turn looping off automatically
        if is_looping:
            is_looping = False
            await ctx.send("Loop disabled by skip.")
            
        ctx.voice_client.stop()
        await ctx.send("Skipped! ⏭️")
    else:
        await ctx.send("Nothing is currently playing to skip.")

# --- NEW COMMAND: volume ---
@bot.command()
async def volume(ctx, vol: int):
    global current_volume
    
    # Restrict volume to prevent blowing out speakers
    if vol < 0 or vol > 200:
        return await ctx.send("Please choose a volume between 0 and 200.")
    
    # Convert percentage (e.g., 50) to float (0.5)
    current_volume = vol / 100.0
    
    # If a song is currently playing, adjust its volume immediately
    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = current_volume
        
    await ctx.send(f"🔊 Volume set to **{vol}%**")

bot.run(TOKEN)