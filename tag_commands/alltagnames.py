# precommands/alltagnames.py   (rename if you like)

import discord
from discord.ext import commands
import sqlite3

class AllTags(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # keep the connection open for the lifetime of the cog
        self.db = sqlite3.connect("tags.db")
        self.cursor = self.db.cursor()

    # tidy-up when the cog is unloaded / bot shuts down
    def cog_unload(self):
        self.db.close()

    @commands.command(name="alltags", help="List all saved tag names.")
    async def alltags(self, ctx: commands.Context):
        self.cursor.execute("SELECT tag FROM tags")
        rows = self.cursor.fetchall()

        if not rows:
            await ctx.send("No tags found.")
            return

        tag_names = [row[0] for row in rows]
        description = "\n".join(tag_names)

        embed = discord.Embed(
            title="Available Tags",
            description=description,
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(AllTags(bot))
