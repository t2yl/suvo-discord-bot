import discord
from discord.ext import commands
import config  # expects WELCOME_CHANNEL (int), EMBED_COLOR, and WELCOME_ROLE (int)

class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Assign the welcome role
        role = member.guild.get_role(config.WELCOME_ROLE)
        if role:
            try:
                await member.add_roles(role, reason="Automatic welcome role assignment")
            except discord.Forbidden:
                # Bot lacks permissions to assign roles
                pass

        # Send welcome message
        channel = self.bot.get_channel(config.WELCOME_CHANNEL)
        if channel is None:
            return  # channel not found or misconfigured

        embed = discord.Embed(
            title="Welcome to our Korean Study Group!",
            description=(
                "Hi! 안녕! 👋\n\n"
                "Looking forward to studying together! "
                "With sessions every week we will improve your language game together 💪🏻"
            ),
            color=config.EMBED_COLOR
        )
        embed.set_image(url=("https://media.discordapp.net/attachments/1377884306101374986/1377905054769610842/252be928a21941772f59f107ec5b4ed0.png?ex=683aa995&is=68395815&hm=23399f08d3633e1ac6068878fd39e66b138099516528ddfbf13c64aa5b6f1ee6&=&format=webp&quality=lossless&width=661&height=277"))

        await channel.send(f"Welcome, {member.mention}!", embed=embed)

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))
