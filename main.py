"""
Discord bot
"""

import datetime
import random
from collections import deque
from os import environ

import discord
import pymongo
import wavelink
from discord import option

bot = discord.Bot(command_prefix='/', debug_guilds=[1037132604408860732])

music_queue = deque()
now_playing = None


async def connect_nodes():
    """
    Connect to Lavalink node(s).
    :return: None
    """
    await bot.wait_until_ready()
    await wavelink.NodePool.create_node(
        bot=bot,
        host='127.0.0.1',
        port=2333,
        password='youshallnotpass'
    )

@bot.event
async def on_ready():
    await connect_nodes()
    print('Bot is ready.')
    print(f'Logged in as {bot.user.name}#{bot.user.discriminator} ({bot.user.id})')


@bot.event
async def on_wavelink_node_ready(node: wavelink.Node):
    print(f"{node.identifier} is ready.")  # print a message


@bot.slash_command(name='play', description='Play a song.')
@option(name='query', description='Searches YouTube for a song name, or a YouTube link to a song.', required=True)
async def play(ctx, *, query: str):
    global now_playing
    voice_client = ctx.voice_client

    if not voice_client:
        voice_client = await ctx.author.voice.channel.connect(cls=wavelink.Player)

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


@bot.slash_command(name='status', description='Get the current status of the bot.')
async def status(ctx):
    embed = None
    if now_playing is not None:
        embed = discord.Embed(
            title='Current Song',
            description=f'[{now_playing.title}]({now_playing.uri})',
            color=discord.Color.blurple(),
        )
        embed.add_field(name='Position: ',
                        value=datetime.datetime.utcfromtimestamp(ctx.voice_client.position).strftime(
                            '%M:%S') if ctx.voice_client.position else 'PAUSED')
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
    if not voice_client.is_playing:
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

    if voice_client.is_playing:
        await ctx.respond('I am not paused.')
        return

    await voice_client.resume()
    await ctx.respond('Resumed.')
    await status(ctx)


@bot.slash_command(name='show_queue', description='Display the current queue.')
async def show_queue(ctx):
    if len(music_queue) == 0:
        await ctx.respond('The queue is empty.')
        return
    embed = discord.Embed(
        title='Queue',
        color=discord.Color.blurple(),
    )
    for i, song in enumerate(music_queue):
        embed.add_field(name=f'{i + 1}. {song.title}', value=f'[{song.uri}]({song.uri})', inline=False)
    await ctx.respond(embed=embed)


@bot.slash_command(name='remove_queue', description='Remove a song from the queue.')
@option(name='index', description='The position of the song to remove.', required=True)
async def remove_queue(ctx, index: int):
    if len(music_queue) == 0:
        await ctx.respond('The queue is empty.')
        return
    if index > len(music_queue):
        await ctx.respond('The index is out of range.')
        return
    song = music_queue[index - 1]
    music_queue.remove(song)
    await ctx.respond(f'Removed `{song.title}` from the queue.')


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
    if not voice_client.is_playing:
        await ctx.respond('I am not playing anything.')
        return
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
    if not voice_client.is_playing:
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
    if not now_playing:
        try:
            now_playing = music_queue.popleft()
            await play(ctx, query=now_playing.title)
        except IndexError:
            await ctx.respond('The queue is empty.')
    else:
        await ctx.respond('The queue is already playing.')


@bot.slash_command(name='disconnect', description='Disconnect the bot from the voice channel and stop whatever is currently playing.')
async def disconnect(ctx):
    voice_client = ctx.voice_client
    await voice_client.disconnect(force=True)
    await ctx.respond('Disconnected.')


@bot.slash_command(name='help', description='Get help with the bot.')
async def help(ctx):
    embed = discord.Embed(
        title='Help',
        color=discord.Color.blurple(),
    )
    embed.add_field(name='play', value='Play a song.')
    embed.add_field(name='status', value='Get the current status of the bot.')
    embed.add_field(name='pause', value='Pause the current song.')
    embed.add_field(name='resume', value='Resume the current song.')
    embed.add_field(name='show_queue', value='Display the current queue.')
    embed.add_field(name='add', value='Add a song to the queue.')
    embed.add_field(name='skip', value='Skip the current song.')
    embed.add_field(name='stop', value='Stop the current song and clears the queue.')
    embed.add_field(name='disconnect', value='Disconnect the bot from the voice channel.')
    embed.add_field(name='help', value='Get help with the bot.')
    embed.add_field(name='version', value='Get the version of the bot.')
    await ctx.respond(embed=embed)


@bot.slash_command(name='version', description='Get the version of the bot.')
async def version(ctx):
    await ctx.respond('Version 0.0.1-pre-alpha')


bot.run(environ['DISCORD_TOKEN'])
