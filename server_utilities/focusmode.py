import discord
from discord.ext import commands
import sqlite3
from datetime import datetime, timedelta
import config

class FocusMode(commands.Cog):
    FOCUS_CHANNEL_ID = 1379119364619632650
    COOLDOWN_SECONDS = 5           # Cooldown per user to avoid spamming warnings
    WARNING_THRESHOLD = 5          # Number of warnings before timeout (for focused users)
    MENTION_THRESHOLD = 5          # Number of mention warnings before timeout (for mentioners)
    TIMEOUT_DURATION = timedelta(hours=1)
    MENTION_TIMEOUT_DURATION = timedelta(minutes=5)

    def __init__(self, bot):
        self.bot = bot
        self.db = sqlite3.connect('focus.db')
        self.cursor = self.db.cursor()
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS focus (user_id INTEGER PRIMARY KEY)"
        )
        self.db.commit()

        self.cooldowns = {}               # maps focused user_id -> datetime of last warning
        self.warning_counts = {}          # maps focused user_id -> int warnings
        self.mention_warning_counts = {}  # maps mentioner user_id -> int mention warnings

    @commands.command(name='focusmode', aliases=['fm'])
    async def focusmode(self, ctx, mode: str):
        # Restrict command usage to the designated focus channel
        if ctx.channel.id != self.FOCUS_CHANNEL_ID:
            embed = discord.Embed(
                title="Invalid Channel",
                description=(
                    f"{ctx.author.mention} You can only use this command in "
                    f"<#{self.FOCUS_CHANNEL_ID}>."
                ),
                color=config.EMBED_COLOR
            )
            await ctx.send(embed=embed, delete_after=8.0)
            return

        user_id = ctx.author.id
        mode = mode.lower()

        # Handle "on" request
        if mode == 'on':
            # If already on, notify user
            if self.is_focusing(user_id):
                embed = discord.Embed(
                    title="Focus Mode Already On",
                    description=f"{ctx.author.mention} Your focus mode is already ON.",
                    color=config.EMBED_COLOR
                )
                await ctx.send(embed=embed)
                return

            # Insert into focus table
            self.cursor.execute(
                'INSERT OR IGNORE INTO focus (user_id) VALUES (?)',
                (user_id,)
            )
            self.db.commit()

            # Attempt to DM user
            try:
                await ctx.author.send(
                    "Focus mode is now ON. I will DM you any warnings while you're in focus mode."
                )
            except discord.errors.Forbidden:
                pass

            # Reset warning count for focused user
            self.warning_counts[user_id] = 0

            embed = discord.Embed(
                title="Focus Mode Activated",
                description=f"{ctx.author.mention} Your focus mode is now ON. My eyes are on you. Focus on your work.",
                color=config.EMBED_COLOR
            )
            await ctx.send(embed=embed)

        # Handle "off" request
        elif mode == 'off':
            # If already off, notify user
            if not self.is_focusing(user_id):
                embed = discord.Embed(
                    title="Focus Mode Already Off",
                    description=f"{ctx.author.mention} Your focus mode is already OFF.",
                    color=config.EMBED_COLOR
                )
                await ctx.send(embed=embed)
                return

            self.cursor.execute(
                'DELETE FROM focus WHERE user_id = ?',
                (user_id,)
            )
            self.db.commit()

            # Clear focused user's cooldown and warning count
            self.cooldowns.pop(user_id, None)
            self.warning_counts.pop(user_id, None)

            embed = discord.Embed(
                title="Focus Mode Deactivated",
                description=f"{ctx.author.mention} Your focus mode is now OFF. Take a break if you need it!",
                color=config.EMBED_COLOR
            )
            await ctx.send(embed=embed)

        # Invalid mode argument
        else:
            embed = discord.Embed(
                title="Invalid Focus Mode",
                description=f"{ctx.author.mention} Invalid mode. Use `!focusmode on` or `!focusmode off`.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)

    def is_focusing(self, user_id: int) -> bool:
        self.cursor.execute(
            'SELECT 1 FROM focus WHERE user_id = ?',
            (user_id,)
        )
        return self.cursor.fetchone() is not None

    def on_cooldown(self, user_id: int) -> bool:
        last = self.cooldowns.get(user_id)
        if not last:
            return False
        return (datetime.utcnow() - last) < timedelta(seconds=self.COOLDOWN_SECONDS)

    def update_cooldown(self, user_id: int):
        self.cooldowns[user_id] = datetime.utcnow()

    async def send_embed_warning(self, channel, user, message_text):
        """
        Send a warning embed (DM + in-channel), increment warning count for focused user,
        check if focused user needs timeout.
        """
        embed = discord.Embed(
            description=message_text,
            color=discord.Color.red()
        )

        # Send DM warning to focused user
        try:
            await user.send(embed=embed)
        except discord.errors.Forbidden:
            pass

        # Send warning in the channel
        await channel.send(content=user.mention, embed=embed, delete_after=8.0)

        # Increment warning count for focused user
        count = self.warning_counts.get(user.id, 0) + 1
        self.warning_counts[user.id] = count

        # If threshold reached, timeout focused user
        if count >= self.WARNING_THRESHOLD:
            self.warning_counts[user.id] = 0
            try:
                until = datetime.utcnow() + self.TIMEOUT_DURATION
                await user.timeout(self.TIMEOUT_DURATION)
            except Exception:
                pass

            focus_channel = self.bot.get_channel(self.FOCUS_CHANNEL_ID)
            if focus_channel:
                timeout_embed = discord.Embed(
                    title="User Timed Out",
                    description=(
                        f"{user.mention} has received {self.WARNING_THRESHOLD} warnings "
                        f"during focus mode and has been timed out for 1 hour."
                    ),
                    color=discord.Color.dark_red()
                )
                await focus_channel.send(embed=timeout_embed)

    async def send_mention_warning(self, message: discord.Message, focused_user_id: int):
        """
        Warn the user who mentioned a focused user. Increment mention warning count
        and timeout mentioner if threshold reached.
        """
        mentioner = message.author
        focused_user = self.bot.get_user(focused_user_id)
        embed = discord.Embed(
            description=(
                f"You mentioned {focused_user.mention}, who is currently in focus mode.\n"
                "Please refrain from mentioning them."
            ),
            color=discord.Color.red()
        )

        # Reply to the offending message
        await message.reply(embed=embed, delete_after=8.0)

        # Increment mention warning count
        count = self.mention_warning_counts.get(mentioner.id, 0) + 1
        self.mention_warning_counts[mentioner.id] = count

        # If threshold reached, timeout the mentioner
        if count >= self.MENTION_THRESHOLD:
            self.mention_warning_counts[mentioner.id] = 0
            try:
                await mentioner.timeout(self.MENTION_TIMEOUT_DURATION)
            except Exception:
                pass

            focus_channel = self.bot.get_channel(self.FOCUS_CHANNEL_ID)
            if focus_channel:
                timeout_embed = discord.Embed(
                    title="User Timed Out for Excessive Mentions",
                    description=(
                        f"{mentioner.mention} mentioned focused users "
                        f"{self.MENTION_THRESHOLD} times and has been timed out for 5 minutes."
                    ),
                    color=discord.Color.dark_red()
                )
                await focus_channel.send(embed=timeout_embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # 1) Check if this message mentions or replies to a focused user
        focused_mentioned = set()

        # Check explicit mentions
        for u in message.mentions:
            if self.is_focusing(u.id):
                focused_mentioned.add(u.id)

        # Check replies (reference)
        if message.reference and message.reference.message_id:
            try:
                orig = await message.channel.fetch_message(message.reference.message_id)
                if self.is_focusing(orig.author.id):
                    focused_mentioned.add(orig.author.id)
            except Exception:
                pass

        # Handle mention warnings
        if focused_mentioned:
            focused_user_id = next(iter(focused_mentioned))
            await self.send_mention_warning(message, focused_user_id)
            return

        # 2) If this is a bot command, skip focus warnings
        if message.content.startswith(self.bot.command_prefix):
            return

        # 3) If the author is in focus mode, warn and delete their message
        if self.is_focusing(message.author.id):
            if not self.on_cooldown(message.author.id):
                self.update_cooldown(message.author.id)
                try:
                    await message.delete()
                except discord.errors.Forbidden:
                    pass
                await self.send_embed_warning(
                    message.channel,
                    message.author,
                    "You're in focus mode. I deleted your message. Focus on your work, my eyes are on you."
                )

    @commands.Cog.listener()
    async def on_typing(self, channel: discord.TextChannel, user: discord.User, when):
        if user.bot:
            return

        if self.is_focusing(user.id) and not self.on_cooldown(user.id):
            self.update_cooldown(user.id)
            await self.send_embed_warning(
                channel,
                user,
                "You're typing. Remember, focus mode is on. My eyes are on you."
            )

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot:
            return

        if self.is_focusing(user.id) and not self.on_cooldown(user.id):
            self.update_cooldown(user.id)
            try:
                await reaction.message.remove_reaction(reaction.emoji, user)
            except discord.errors.Forbidden:
                pass
            await self.send_embed_warning(
                reaction.message.channel,
                user,
                "You're in focus mode. Removing your reaction. Focus on your work."
            )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        if member.bot:
            return

        if before.channel is None and after.channel is not None:
            if self.is_focusing(member.id) and not self.on_cooldown(member.id):
                self.update_cooldown(member.id)

                try:
                    await member.move_to(None)
                except discord.errors.Forbidden:
                    pass

                embed = discord.Embed(
                    title="Focus Mode Violation",
                    description="You joined a voice channel while in focus mode. You have been disconnected.",
                    color=discord.Color.red()
                )

                try:
                    await member.send(embed=embed)
                except discord.errors.Forbidden:
                    pass

                sys_channel = member.guild.system_channel
                if sys_channel:
                    await sys_channel.send(content=member.mention, embed=embed)

                focus_channel = self.bot.get_channel(self.FOCUS_CHANNEL_ID)
                if focus_channel:
                    await focus_channel.send(content=member.mention, embed=embed)

                # Count this as a warning
                await self.send_embed_warning(
                    focus_channel or member.guild.system_channel,
                    member,
                    "You joined a voice channel while in focus mode."
                )

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        if before.status == discord.Status.offline and after.status in (
            discord.Status.online,
            discord.Status.idle,
            discord.Status.dnd
        ):
            if self.is_focusing(after.id) and not self.on_cooldown(after.id):
                self.update_cooldown(after.id)

                embed = discord.Embed(
                    description=f"Status changed to **{after.status}** while focus mode is on.\nStay focused! My eyes are on you 👀",
                    color=discord.Color.red()
                )

                try:
                    await after.send(embed=embed)
                except discord.Forbidden:
                    pass

                focus_channel = self.bot.get_channel(self.FOCUS_CHANNEL_ID)
                if focus_channel:
                    await focus_channel.send(content=after.mention, embed=embed)

                # Count this as a warning
                await self.send_embed_warning(
                    focus_channel or after.guild.system_channel,
                    after,
                    f"Status changed to **{after.status}** while in focus mode."
                )

async def setup(bot: commands.Bot):
    await bot.add_cog(FocusMode(bot))
