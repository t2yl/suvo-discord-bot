import discord
from discord.ext import commands
import time

class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx):
        """
        Checks the bot's latency and Discord API latency.
        """
        start_time = time.time()
        message = await ctx.send("Pinging...")
        end_time = time.time()

        bot_latency = round(self.bot.latency * 1000)
        roundtrip_latency = round((end_time - start_time) * 1000)

        embed = discord.Embed(title="Pong!", color=0xffffff)
        embed.add_field(name="Bot Latency", value=f"{bot_latency}ms", inline=False)
        embed.add_field(name="Discord API Latency", value=f"{roundtrip_latency}ms", inline=False)
        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url)

        await message.edit(content=None, embed=embed)  # Remove "Pinging..." and send the embed


async def setup(bot):
    await bot.add_cog(Ping(bot))