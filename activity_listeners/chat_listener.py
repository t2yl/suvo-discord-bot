import discord
from discord.ext import commands
import datetime

LOG_CHANNEL_ID = 1378035725752209478  # ID of the channel to send logs

class MessageLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.first_edited_content: dict[int, str] = {}

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"✅ MessageLogger loaded as {self.bot.user} (ID: {self.bot.user.id})")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild:
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        if (now - message.created_at).total_seconds() > 48 * 3600:
            return

        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return

        # Embed 1: who deleted and where
        embed1 = discord.Embed(title="Message Deleted", color=discord.Color.red())
        embed1.add_field(name="User Mention", value=message.author.mention, inline=True)
        embed1.add_field(name="Username", value=message.author.name, inline=True)
        embed1.add_field(name="Display Name", value=message.author.display_name, inline=True)
        embed1.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed1.set_thumbnail(url=message.author.display_avatar.url)
        await log_channel.send(embed=embed1)

        # Embed 2: attachments, embeds, or content
        if message.attachments:
            for att in message.attachments:
                # image attachments
                if att.content_type and att.content_type.startswith("image"):
                    embed2 = discord.Embed(title="Deleted Image", color=discord.Color.dark_red())
                    embed2.set_image(url=att.url)
                    embed2.set_footer(text=att.filename)
                    await log_channel.send(embed=embed2)
                # video or other files
                else:
                    embed2 = discord.Embed(
                        title="Deleted Attachment",
                        description=f"[{att.filename}]({att.url})",
                        color=discord.Color.dark_red()
                    )
                    await log_channel.send(embed=embed2)
        elif message.embeds:
            for e in message.embeds:
                await log_channel.send(embed=e)
        else:
            content = message.content or "<no content>"
            embed2 = discord.Embed(description=content, color=discord.Color.dark_red())
            await log_channel.send(embed=embed2)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.content == after.content:
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        if (now - before.created_at).total_seconds() > 48 * 3600:
            return

        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return

        # Determine the "original" content to show
        if before.id not in self.first_edited_content:
            original = before.content
            self.first_edited_content[before.id] = after.content
        else:
            original = self.first_edited_content[before.id]

        # Embed 1: who edited
        embed1 = discord.Embed(title="Message Edited", color=discord.Color.orange())
        embed1.add_field(name="User Mention", value=before.author.mention, inline=True)
        embed1.add_field(name="Username", value=before.author.name, inline=True)
        embed1.add_field(name="Display Name", value=before.author.display_name, inline=True)
        embed1.set_thumbnail(url=before.author.display_avatar.url)
        await log_channel.send(embed=embed1)

        # Embed 2: original vs edited
        desc = f"**Original Message:**\n{original}\n\n**Edited Message:**\n{after.content}"
        embed2 = discord.Embed(description=desc, color=discord.Color.blue())
        await log_channel.send(embed=embed2)

async def setup(bot: commands.Bot):
    await bot.add_cog(MessageLogger(bot))
