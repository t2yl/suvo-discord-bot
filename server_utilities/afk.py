import asyncio
import pathlib
import sqlite3
import discord
from discord.ext import commands
import config

AFK_PREFIX = "[AFK] "
MAX_NICK_LEN = 32  # Discord hard limit

DB_PATH = pathlib.Path(__file__).with_name("afk.db")

class AfkCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # One connection, thread-safe
        self.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.db:
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS afk (
                    user_id       INTEGER PRIMARY KEY,
                    message       TEXT,
                    original_nick TEXT
                )
                """
            )

    # ---------- COMMAND -----------------------------------------------------

    @commands.command(name="afk")
    async def afk(self, ctx: commands.Context, *, reason: str = ""):
        """
        !afk <optional message>
        Marks the author AFK.
        """
        def already_afk(uid: int) -> bool:
            cur = self.db.execute("SELECT 1 FROM afk WHERE user_id = ?", (uid,))
            return cur.fetchone() is not None

        if already_afk(ctx.author.id):
            await ctx.send(
                embed=discord.Embed(
                    description="You are already marked as AFK.",
                    color=config.EMBED_COLOR,
                ),
                delete_after=5,
            )
            return

        original_nick = ctx.author.nick  # may be None

        with self.db:
            self.db.execute(
                "INSERT INTO afk (user_id, message, original_nick) VALUES (?, ?, ?)",
                (ctx.author.id, reason, original_nick),
            )

        # Build safe nickname -------------------------------------------------
        base = original_nick or ctx.author.name
        new_nick = (AFK_PREFIX + base)[:MAX_NICK_LEN]

        try:
            await ctx.author.edit(nick=new_nick)
        except discord.Forbidden:
            await ctx.send(
                embed=discord.Embed(
                    description=(
                        "AFK status set, but I’m missing **Manage Nicknames** so "
                        "your nickname was unchanged."
                    ),
                    color=config.EMBED_COLOR,
                ),
                delete_after=5,
            )
            await ctx.message.add_reaction("💤")  # ← add this line
            
        else:
            await ctx.send(
                embed=discord.Embed(
                    description=f"You are now AFK{f': {reason}' if reason else ''}.",
                    color=config.EMBED_COLOR,
                ),
                delete_after=5,
            )
            await ctx.message.add_reaction("💤")  # ← add this line

    # ---------- LISTENER ----------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # ---- ignore the AFK command itself -------------------------------
        prefixes = await self.bot.get_prefix(message)
        if isinstance(prefixes, str):
            prefixes = [prefixes]

        if any(
            message.content.lower().startswith(p.lower() + "afk")
            for p in prefixes
        ):
            return

        # ---- 1) Author comes back ----------------------------------------
        row = self.db.execute(
            "SELECT original_nick FROM afk WHERE user_id = ?", (message.author.id,)
        ).fetchone()

        if row:
            original_nick = row["original_nick"]  # may be None
            try:
                await message.author.edit(nick=original_nick)
            except discord.Forbidden:
                pass

            with self.db:
                self.db.execute("DELETE FROM afk WHERE user_id = ?", (message.author.id,))

            await message.channel.send(
                embed=discord.Embed(
                    description=f"Welcome back, {message.author.mention}. AFK removed.",
                    color=config.EMBED_COLOR,
                ),
                delete_after=5,
            )

        # ---- 2) Notify people pinging AFK users ----------------------------
        afk_cache: dict[int, str] = {}

        # direct mentions
        for u in message.mentions:
            r = self.db.execute(
                "SELECT message FROM afk WHERE user_id = ?", (u.id,)
            ).fetchone()
            if r:
                afk_cache[u.id] = r["message"]

        # reply mention (needs extra fetch when not resolved)
        ref = message.reference
        if ref and not afk_cache:
            try:
                if isinstance(ref.resolved, discord.Message):
                    replied = ref.resolved
                else:
                    replied = await message.channel.fetch_message(ref.message_id)
                r = self.db.execute(
                    "SELECT message FROM afk WHERE user_id = ?", (replied.author.id,)
                ).fetchone()
                if r:
                    afk_cache[replied.author.id] = r["message"]
            except (discord.NotFound, AttributeError):
                pass

        for uid, note in afk_cache.items():
            member = message.guild.get_member(uid)
            if not member:
                continue

            desc = f"{member.mention} is AFK"
            if note:
                desc += f": {note}"

            await message.reply(
                embed=discord.Embed(description=desc, color=config.EMBED_COLOR),
                mention_author=True,
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
                delete_after=5,
            )

    # ---------- CLEAN-UP ----------------------------------------------------

    async def cog_unload(self):
        await asyncio.get_running_loop().run_in_executor(None, self.db.close)


async def setup(bot: commands.Bot):
    await bot.add_cog(AfkCog(bot))
