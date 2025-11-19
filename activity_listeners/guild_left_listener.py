import discord
from discord.ext import commands

LOG_CHANNEL_ID = 1378035972264165426  # channel to send member-leave logs

class MemberListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        # ignore bot accounts
        if member.bot:
            return

        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return

        embed = discord.Embed(
            title="Member Left the Server",
            color=discord.Color.dark_grey()
        )
        embed.add_field(name="User Mention", value=member.mention, inline=True)
        embed.add_field(name="Username", value=member.name, inline=True)
        embed.add_field(name="Display Name", value=member.display_name, inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberListener(bot))
