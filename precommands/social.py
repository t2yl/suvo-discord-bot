import discord
from discord.ext import commands
import config

class SocialsCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="social")
    async def social_command(self, ctx):
        embed = discord.Embed(
            title="Connect with Suvo",
            description=(
                "Stay up to date with Suvo:"
            ),
            color=config.EMBED_COLOR
        )
        embed.add_field(
            name="Instagram",
            value="[@durlm](https://instagram.com/durlm)",
            inline=True
        )
        embed.add_field(
            name="X (Twitter)",
            value="[@durflm](https://twitter.com/durflm)",
            inline=True
        )

        view = discord.ui.View()
        # Instagram button
        view.add_item(discord.ui.Button(
            label="Instagram",
            style=discord.ButtonStyle.link,
            url="https://instagram.com/durlm",
            emoji="<:suvo_instagram:1376990127540142151>"
        ))
        # Twitter/X button
        view.add_item(discord.ui.Button(
            label="X",
            style=discord.ButtonStyle.link,
            url="https://twitter.com/durflm",
            emoji="<:suvo_twitter_x:1376980632688922775>"
        ))

        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(SocialsCommand(bot))
