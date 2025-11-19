import discord
from discord.ext import commands
import config

class SuvoFilter(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.target_id = 1353629464709300338
        # IDs allowed to bypass the filter
        self.bypass_ids = {
            1344279847647838229,
            1309181593448874076,
            1121362897424109578,
            435057784971853825,
            1384767261897789441,
            999383672299995357,
            1386008493676302378,
            1353629464709300338,
            878183497880186880
            # add more IDs here
        }

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ignore bots and bypassed users
        if message.author.bot or message.author.id in self.bypass_ids:
            return

        # check for reply-to
        is_reply_to_target = (
            message.reference 
            and isinstance(message.reference.resolved, discord.Message) 
            and message.reference.resolved.author.id == self.target_id
        )
        # check for direct mention
        mentions_target = any(u.id == self.target_id for u in message.mentions)

        if is_reply_to_target or mentions_target:
            # delete the offending message
            await message.delete()

            # warn embed
            embed = discord.Embed(
                description=(
                    "Random users are not allowed to ping <@{0}> as they have enabled qi 36."
                ).format(self.target_id),
                color=config.EMBED_COLOR
            )

            warn = await message.channel.send(
                embed=embed,
                reference=message.to_reference(fail_if_not_exists=False),
                mention_author=False
            )
            # auto-delete the warning after 10 seconds
            await warn.delete(delay=10)

# this will be picked up by bot.load_extension or bot.startup
async def setup(bot: commands.Bot):
    await bot.add_cog(SuvoFilter(bot))
