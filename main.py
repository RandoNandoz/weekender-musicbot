"""
Discord bot
"""

from os import environ

import discord

bot = discord.Bot(command_prefix='/')


@bot.command(description='Sends the bot\'s latency')
async def ping(ctx):
    await ctx.respond(f'Pong! {bot.latency}ms!')


bot.run(environ['DISCORD_TOKEN'])
