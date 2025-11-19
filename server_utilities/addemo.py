import discord
from discord.ext import commands
import re
import aiohttp
import asyncio

CUSTOM_EMOJI_RE = re.compile(r"<(a?):(\w+):(\d+)>")

class Addemo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Prevent concurrent emoji-creates in the same process
        self._emoji_lock = asyncio.Lock()

    @commands.command(name="addemo")
    @commands.has_permissions(manage_emojis=True)
    @commands.cooldown(1, 10, commands.BucketType.guild)   # 1 every 10 s per guild
    async def addemo(self, ctx: commands.Context, emoji_input: str | None = None):
        # If the command was used as a reply, grab that content
        if ctx.message.reference and not emoji_input:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                emoji_input = ref.content.strip()
            except Exception:
                return await ctx.send("Couldn't fetch the replied-to message.")

        if not emoji_input:
            return await ctx.send("Give me a custom emoji or reply to one.")

        m = CUSTOM_EMOJI_RE.fullmatch(emoji_input)
        if not m:
            return await ctx.send("That doesn't look like a custom emoji.")

        is_animated, name, emoji_id = m.groups()
        ext = "gif" if is_animated else "png"
        url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"

        if len(ctx.guild.emojis) >= ctx.guild.emoji_limit:
            return await ctx.send("Server emoji limit reached – delete one first.")

        async with self._emoji_lock:             # one create at a time
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            return await ctx.send("Couldn't download that emoji.")
                        img_bytes = await resp.read()

                # First attempt
                new_emoji = await self._safe_create(ctx, name, img_bytes)
                await ctx.send(f"Added `{new_emoji.name}` {new_emoji}")

            except discord.HTTPException as e:
                await ctx.send(f"Failed to add emoji: {e}")

    async def _safe_create(self, ctx: commands.Context, name: str, img_bytes: bytes):
        """
        Try to create the emoji once; if we hit a 429, honour Retry-After
        and make exactly one retry.
        """
        try:
            return await ctx.guild.create_custom_emoji(
                name=name,
                image=img_bytes,
                reason=f"Added by {ctx.author} ({ctx.author.id})"
            )
        except discord.HTTPException as e:
            if e.status != 429:
                raise
            retry_after = float(e.response.headers.get("Retry-After", 0))
            await ctx.send(f"Rate-limited, retrying in {int(retry_after)} s…")
            await asyncio.sleep(retry_after + 1)           # pad by 1 s
            # second (and last) attempt – propagate errors if it still fails
            return await ctx.guild.create_custom_emoji(
                name=name,
                image=img_bytes,
                reason=f"Retried add by {ctx.author} ({ctx.author.id})"
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Addemo(bot))
