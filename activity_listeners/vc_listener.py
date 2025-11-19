import discord
from discord.ext import commands

LOG_CHANNEL_ID = 1378035836578435206  # channel to send activity logs

class ActivityListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if not log_channel or member.bot:
            return

        old = before.channel
        new = after.channel

        # Joined a channel
        if old is None and new is not None:
            if isinstance(new, discord.StageChannel):
                title = "Stage Channel Joined"
            else:
                title = "Voice Channel Joined"
            embed = discord.Embed(title=title, color=discord.Color.green())
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="Channel", value=new.mention, inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            await log_channel.send(embed=embed)

        # Left a channel
        elif old is not None and new is None:
            if isinstance(old, discord.StageChannel):
                title = "Stage Channel Left"
            else:
                title = "Voice Channel Left"
            embed = discord.Embed(title=title, color=discord.Color.dark_red())
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="Channel", value=old.mention, inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            await log_channel.send(embed=embed)

        # Moved between channels (optional)
        elif old is not None and new is not None and old != new:
            # treat as leave old + join new
            # leave old
            if isinstance(old, discord.StageChannel):
                title_old = "Stage Channel Left"
            else:
                title_old = "Voice Channel Left"
            embed_old = discord.Embed(title=title_old, color=discord.Color.dark_red())
            embed_old.add_field(name="User", value=member.mention, inline=True)
            embed_old.add_field(name="Channel", value=old.mention, inline=True)
            embed_old.set_thumbnail(url=member.display_avatar.url)
            await log_channel.send(embed=embed_old)

            # join new
            if isinstance(new, discord.StageChannel):
                title_new = "Stage Channel Joined"
            else:
                title_new = "Voice Channel Joined"
            embed_new = discord.Embed(title=title_new, color=discord.Color.green())
            embed_new.add_field(name="User", value=member.mention, inline=True)
            embed_new.add_field(name="Channel", value=new.mention, inline=True)
            embed_new.set_thumbnail(url=member.display_avatar.url)
            await log_channel.send(embed=embed_new)

async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityListener(bot))
