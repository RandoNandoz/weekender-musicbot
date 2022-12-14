"""
Discord bot
"""

import datetime
import random
from os import environ
from collections import deque

import discord
import wavelink
from discord import option
from wavelink.ext import spotify

# set debug guild to THE ID THE BOT is in
bot = discord.Bot(command_prefix='/', debug_guilds=[1037132604408860732])

# create a deque to store songs in queue
music_queue = deque()

# head of the queue
now_playing = None


async def connect_nodes():
    """
    Connect to Lavalink node(s).
    :return: None
    """
    # wait for bot to be ready before audio connect
    await bot.wait_until_ready()
    # connect to node & spotify api
    await wavelink.NodePool.create_node(
        bot=bot,
        host='127.0.0.1',
        port=2333,
        password='youshallnotpass',
        spotify_client=spotify.SpotifyClient(
            client_id=environ.get('SPOTIFY_CLIENT_ID'),
            client_secret=environ.get('SPOTIFY_CLIENT_SECRET')
        )
    )


@bot.event
async def on_ready():
    # connect to lavalink nodes
    await connect_nodes()
    print('Bot is ready.')
    print(f'Logged in as {bot.user.name}#{bot.user.discriminator} ({bot.user.id})')


@bot.event
async def on_wavelink_node_ready(node: wavelink.Node):
    print(f"{node.identifier} is ready.")  # print a message


# on end of song, if the song finished normally, move to the next, unless the queue is empty
@bot.event
async def on_wavelink_track_end(player: wavelink.Player, track: wavelink.Track, reason):
    global now_playing
    if reason == 'FINISHED':
        if music_queue:
            now_playing = music_queue.popleft()
            await bot.voice_clients[0].play(now_playing)
        else:
            [await v.disconnect(force=True) for v in bot.voice_clients]


@bot.slash_command(name='play', description='Play a song.')
@option(name='query', description='Searches YouTube for a song name, or a YouTube link to a song.', required=True)
async def play(ctx, *, query: str):
    global now_playing
    voice_client = ctx.voice_client

    # if the bot is not in a voice channel, join the user's voice channel
    if not voice_client:
        try:
            voice_client = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        except:
            await ctx.send('You are not in a voice channel.')
            return

    # if the bot is in a voice channel, but not the same as the user's voice channel, send an error message
    if ctx.author.voice.channel.id != voice_client.channel.id:
        await voice_client.disconnect(force=True)
        voice_client = await ctx.author.voice.channel.connect(cls=wavelink.Player)


    song = await wavelink.YouTubeTrack.search(query=query, return_first=True)
    now_playing = song

    if not song:
        await ctx.respond('No results found.')
        return

    embed = discord.Embed(
        title='Currently playing',
        description=f'[{song.title}]({song.uri})',
        color=discord.Color.blurple(),
    )
    embed.add_field(name='Position: ', value='0:00')
    embed.add_field(name='Duration', value=datetime.datetime.utcfromtimestamp(song.length).strftime('%M:%S'))
    embed.add_field(name='Requested by', value=ctx.author.mention)
    embed.add_field(name='Next', value='Nothing' if not music_queue else music_queue[0].title)
    embed.set_thumbnail(url=song.thumbnail)

    await voice_client.play(song)
    await ctx.respond(embed=embed)


@bot.slash_command(name='play_spotify', description='Play a song from Spotify.')
@option(name='query', description='Plays a specific spotify song link', required=True)
async def play_spotify(ctx, *, query: str):
    global now_playing
    voice_client = ctx.voice_client

    if not voice_client:
        voice_client = await ctx.author.voice.channel.connect(cls=wavelink.Player)

    if ctx.author.voice.channel.id != voice_client.channel.id:
        await voice_client.disconnect(force=True)
        voice_client = await ctx.author.voice.channel.connect(cls=wavelink.Player)

    try:
        song = await spotify.SpotifyTrack.search(query=query, return_first=True)
    except spotify.SpotifyRequestError:
        await ctx.respond('No results found.')
        return
    now_playing = song

    if not song:
        await ctx.respond('No results found.')
        return

    embed = discord.Embed(
        title='Currently playing',
        description=f'[{song.title}]({song.uri})',
        color=discord.Color.blurple(),
    )
    embed.add_field(name='Position: ', value='0:00')
    embed.add_field(name='Duration', value=datetime.datetime.utcfromtimestamp(song.length).strftime('%M:%S'))
    embed.add_field(name='Requested by', value=ctx.author.mention)
    embed.add_field(name='Next', value='Nothing' if not music_queue else music_queue[0].title)
    embed.set_thumbnail(url=song.thumbnail)

    await voice_client.play(song)
    await ctx.respond(embed=embed)


@bot.slash_command(name='queue_spotify',
                   description='Add a playlist/album from Spotify to the queue. May be slow with large playlists.')
@option(name='query', description='A specific spotify playlist or album link', required=True)
@option(name='shuffle_pl', description='Shuffles the album/playlist', required=False)
async def queue_spotify(ctx, *, query: str, shuffle_pl: bool = False):
    tracks = []
    new_queue = deque()
    await ctx.defer()
    try:
        tracks = await spotify.SpotifyTrack.search(query=query)
    except spotify.SpotifyRequestError:
        await ctx.followup.send(
            'Invalid Spotify link. If this a personal playlist, your playlist & profile must be public.')
    for track in tracks:
        new_queue.append(track)
    if shuffle_pl:
        random.shuffle(new_queue)
    music_queue.extend(new_queue)
    await ctx.followup.send(f'Added {len(tracks)} songs to the queue.')


@bot.slash_command(name='status', description='Get the current status of the bot.')
async def status(ctx):
    if now_playing is not None:
        embed = discord.Embed(
            title='Current Song',
            description=f'[{now_playing.title}]({now_playing.uri})',
            color=discord.Color.blurple(),
        )
        embed.add_field(name='Position: ',
                        value=datetime.datetime.utcfromtimestamp(ctx.voice_client.position).strftime('%M:%S'))
        embed.add_field(name='Duration', value=datetime.datetime.utcfromtimestamp(now_playing.length).strftime('%M:%S'))
        embed.add_field(name='Requested by', value=ctx.author.mention)
        embed.add_field(name='Next', value='Nothing' if not music_queue else music_queue[0].title)
        embed.set_thumbnail(url=now_playing.thumbnail)
    else:
        embed = discord.Embed(
            title='Nothing is playing.',
            color=discord.Color.blurple(),
        )
    await ctx.respond(embed=embed)


@bot.slash_command(name='pause', description='Pause the current song.')
async def pause(ctx):
    voice_client = ctx.voice_client
    if not voice_client:
        await ctx.respond('I am not connected to a voice channel.')
        return
    if not voice_client.is_playing():
        await ctx.respond('I am not playing anything.')
        return
    await voice_client.pause()
    await ctx.respond('Paused.')
    await status(ctx)


@bot.slash_command(name='resume', description='Resume the current song.')
async def resume(ctx):
    voice_client = ctx.voice_client
    if not voice_client:
        await ctx.respond('I am not connected to a voice channel.')
        return

    await voice_client.resume()
    await ctx.respond('Resumed.')
    await status(ctx)


@bot.slash_command(name='show_queue', description='Display the current queue.')
async def show_queue(ctx):
    if not music_queue:
        await ctx.respond('Queue is empty.')
        return
    embed = discord.Embed(
        title=f'Queue (Total items: {len(music_queue)})',
        color=discord.Color.blurple(),
    )
    for i, song in enumerate(music_queue):
        embed.add_field(name=f'{i + 1}. {song.title}', value=f'[{song.uri}]({song.uri})', inline=False)
    await ctx.respond(embed=embed)


@bot.slash_command(name='remove', description='Remove a song from the queue.')
@option(name='index', description='The position of the song to remove.', required=True)
async def remove(ctx, index: int):
    if len(music_queue) == 0:
        await ctx.respond('The queue is empty.')
        return
    if index > len(music_queue):
        await ctx.respond('The index is out of range.')
        return
    song = music_queue[index - 1]
    music_queue.remove(song)
    await ctx.respond(f'Removed `{song.title}` from the queue.')


@bot.slash_command(name='remove_duplicates', description='Remove duplicate songs from the queue.')
async def remove_duplicates(ctx):
    global music_queue
    if len(music_queue) == 0:
        await ctx.respond('The queue is empty.')
        return
    music_queue = deque(dict.fromkeys(music_queue))
    await ctx.respond('Removed duplicate songs from the queue.')


@bot.slash_command(name='swap_queue', description='Swap two songs in the queue.')
@option(name='index1', description='The position of the first song to swap.', required=True)
@option(name='index2', description='The position of the second song to swap.', required=True)
async def swap_queue(ctx, index1: int, index2: int):
    if len(music_queue) == 0:
        await ctx.respond('The queue is empty.')
        return
    if index1 > len(music_queue) or index2 > len(music_queue):
        await ctx.respond('One of the indexes is out of range.')
        return
    song1 = music_queue[index1 - 1]
    song2 = music_queue[index2 - 1]
    music_queue[index1 - 1] = song2
    music_queue[index2 - 1] = song1
    await ctx.respond(f'Swapped `{song1.title}` with `{song2.title}`.')


@bot.slash_command(name='add', description='Add a song to the queue.')
@option(name='query', description='Searches YouTube for a song name, or a YouTube link to a song.', required=True)
async def add(ctx, *, query: str):
    song = await wavelink.YouTubeTrack.search(query=query, return_first=True)
    if not song:
        await ctx.respond('No results found.')
        return
    music_queue.append(song)
    await ctx.respond(f'Added {song.title} to the queue.')


@bot.slash_command(name='add_top', description='Add a song to the top of the queue.')
@option(name='query', description='Searches YouTube for a song name, or a YouTube link to a song.', required=True)
async def add_top(ctx, *, query: str):
    song = await wavelink.YouTubeTrack.search(query=query, return_first=True)
    if not song:
        await ctx.respond('No results found.')
        return
    music_queue.insert(0, song)
    await ctx.respond(f'Added {song.title} to the top of the queue.')


@bot.slash_command(name='shuffle', description='Shuffle the queue.')
async def shuffle(ctx):
    random.shuffle(music_queue)
    await ctx.respond('Shuffled the queue.')


@bot.slash_command(name='skip', description='Skip the current song.')
async def skip(ctx):
    global now_playing
    voice_client = ctx.voice_client
    if not voice_client:
        await ctx.respond('I am not connected to a voice channel.')
        return
    # if not voice_client.is_playing():
    #     await ctx.respond('I am not playing anything.')
    #     return
    await voice_client.stop()
    await ctx.respond('Skipped.')
    try:
        now_playing = music_queue.popleft()
        await play(ctx, query=now_playing.title)
    except IndexError:
        now_playing = None
        await disconnect(ctx)


@bot.slash_command(name='stop', description='Stop the current song and clears the queue.')
async def stop(ctx):
    voice_client = ctx.voice_client
    if not voice_client:
        await ctx.respond('I am not connected to a voice channel.')
        return
    if not voice_client.is_playing():
        await ctx.respond('I am not playing anything.')
        return
    await voice_client.stop()
    await ctx.respond('Stopped.')
    global now_playing
    now_playing = None
    music_queue.clear()


@bot.slash_command(name='start_queue', description='Start the queue.')
async def start_queue(ctx):
    global now_playing
    if ctx.author.voice is None:
        await ctx.respond('You are not connected to a voice channel.')
        return
    if not now_playing:
        try:
            now_playing = music_queue.popleft()
            await play(ctx, query=now_playing.title)
        except IndexError:
            await ctx.respond('The queue is empty.')
    else:
        await ctx.respond('The queue is already playing.')


@bot.slash_command(name='disconnect',
                   description='Disconnect the bot from the voice channel and stop whatever is currently playing.')
async def disconnect(ctx):
    voice_client = ctx.voice_client
    if voice_client is not None:
        await voice_client.disconnect(force=True)
    else:
        await ctx.respond('I am not connected to a voice channel.')
        return
    await ctx.respond('Disconnected.')


@bot.slash_command(name='help', description='Displays help')
async def help(ctx):
    ctx.respond(
        'Commands:\n'
        'play - Play a song.\n'
        'queue - Display the queue.\n'
        'clear_queue - Clear the queue.\n'
        'remove - Remove a song from the queue.\n'
        'remove_duplicates - Remove duplicate songs from the queue.\n'
        'swap_queue - Swap two songs in the queue.\n'
        'add - Add a song to the queue.\n'
        'add_top - Add a song to the top of the queue.\n'
        'shuffle - Shuffle the queue.\n'
        'skip - Skip the current song.\n'
        'stop - Stop the current song and clears the queue.\n'
        'start_queue - Start the queue.\n'
        'disconnect - Disconnect the bot from the voice channel and stop whatever is currently playing.\n'
        'help - Displays help.'
    )


bot.run(environ['DISCORD_TOKEN'])
