import discord
from discord.ext import commands
import asyncio

class PingOnJoin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Channels to post the ping in:
        self.channel_ids = [
            1377921397015445566,
            1377884295124881439
        ]

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        for cid in self.channel_ids:
            channel = self.bot.get_channel(cid)
            if not channel:
                continue

            try:
                # send a mention of the new member
                msg = await channel.send(member.mention)
                # wait 2 seconds, then delete
                await asyncio.sleep(2)
                await msg.delete()
            except discord.Forbidden:
                # missing permissions (send/delete)
                pass
            except discord.HTTPException:
                # message send/delete failed
                pass

async def setup(bot):
    await bot.add_cog(PingOnJoin(bot))
