import discord
from discord.ext import commands
import config

class MediaChannelListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore messages from bots or messages outside the specified media channel
        if message.author.bot or message.channel.id != config.MEDIA_CHANNEL_ID:
            return
        
        # --- MODIFIED LOGIC ---
        # Allow the message if it has attachments (is media) OR if it is a reply.
        # A message is a reply if 'message.reference' is not None.
        if message.attachments or message.reference is not None:
            return

        # If the code reaches here, the message is a top-level message with no attachments.
        # We will delete it and send a temporary warning.
        try:
            await message.delete()
        except discord.errors.NotFound:
            # The message might have been deleted by another mod/bot, so we just ignore the error.
            return

        # Send an updated error message that clarifies the new rule.
        # Using `delete_after` is a cleaner way to handle temporary messages.
        embed = discord.Embed(
            description="Please only send media files or reply to existing media in this channel.",
            color=config.EMBED_COLOR
        )
        await message.channel.send(embed=embed, delete_after=5)

async def setup(bot: commands.Bot):
    await bot.add_cog(MediaChannelListener(bot))