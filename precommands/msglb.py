import os
import json
from discord.ext import commands
import discord
import config

class MessageLeaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        base_dir = os.path.dirname(__file__)
        self.data_file = os.path.join(base_dir, "messages.json")
        self._load_data()
        # listen to all messages
        self.bot.add_listener(self._on_message, 'on_message')

    def _load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                self.msg_counts = json.load(f)
        else:
            self.msg_counts = {}
            self._save_data()

    def _save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.msg_counts, f, indent=4)

    async def _on_message(self, message: discord.Message):
        # ignore bots and webhooks
        if message.author.bot:
            return
        uid = str(message.author.id)
        self.msg_counts[uid] = self.msg_counts.get(uid, 0) + 1
        self._save_data()

    @commands.command(name='msglb')
    async def msglb(self, ctx: commands.Context):
        """Show the top 10 users by message count."""
        embed = discord.Embed(
            title="Message Leaderboard",
            color=config.EMBED_COLOR
        )
        if not self.msg_counts:
            embed.description = "No message data yet."
        else:
            # sort by count descending
            sorted_items = sorted(self.msg_counts.items(), key=lambda kv: kv[1], reverse=True)
            for idx, (uid_str, count) in enumerate(sorted_items[:10], start=1):
                user = ctx.guild.get_member(int(uid_str)) or self.bot.get_user(int(uid_str))
                name = user.display_name if isinstance(user, discord.Member) else getattr(user, 'name', uid_str)
                embed.add_field(name=f"{idx}. {name}", value=f"{count} messages", inline=False)

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(MessageLeaderboard(bot))
