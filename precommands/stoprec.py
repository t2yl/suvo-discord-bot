import discord
from discord.ext import commands

class StopRec(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='stoprec')
    @commands.has_permissions(administrator=True)
    async def stoprec(self, ctx: commands.Context, recording_key: str):
        """
        Manually stop an ongoing recording with the given <recording_key> before 60 minutes elapse.
        """
        # Retrieve the RecordText cog
        record_cog = self.bot.get_cog('RecordText')
        if not record_cog:
            return await ctx.send('Recording functionality is not loaded.')

        # Check if the key is active
        if recording_key not in record_cog.active_recordings:
            return await ctx.send(f'No active recording found for key `{recording_key}`.')

        # Stop recording
        record_cog.active_recordings.pop(recording_key)
        await ctx.send(f'Recording `{recording_key}` has been manually stopped. Stored messages remain retrievable via `!sendrec {recording_key}`.')

async def setup(bot: commands.Bot):
    await bot.add_cog(StopRec(bot))
