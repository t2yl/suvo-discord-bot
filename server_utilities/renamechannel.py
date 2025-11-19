import discord
from discord.ext import commands
import asyncio
import config  # for EMBED_COLOR, optional

async def safe_edit(coro, *, retries=3):
    """
    Executes a coroutine that performs an HTTP request. If a 429 rate-limit occurs,
    waits for the `retry_after` duration and retries up to `retries` times.
    """
    for attempt in range(retries):
        try:
            return await coro
        except discord.HTTPException as e:
            # Handle rate limit
            if hasattr(e, 'status') and e.status == 429 and hasattr(e, 'retry_after'):
                wait = e.retry_after
                await asyncio.sleep(wait)
            else:
                raise
    # Final attempt
    return await coro

class ChannelManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="rename")
    @commands.has_permissions(administrator=True)
    async def rename_command(self, ctx, channel: discord.TextChannel, *, new_name: str):
        """
        Renames the specified text channel with rate-limit handling.
        Usage: !rename #channel new-name
        Requires: Administrator permission
        """
        old_name = channel.name
        try:
            # Use safe_edit to handle rate limits
            await safe_edit(channel.edit(name=new_name, reason=f"Renamed by {ctx.author}"))
            # Small pause to avoid triggering additional rate limits
            await asyncio.sleep(1.0)
        except discord.Forbidden:
            return await ctx.send(embed=discord.Embed(
                title="Permission Denied",
                description="I don’t have permission to rename that channel.",
                color=config.EMBED_COLOR
            ))
        except Exception as e:
            return await ctx.send(embed=discord.Embed(
                title="Error",
                description=f"Something went wrong: {e}",
                color=config.EMBED_COLOR
            ))

        embed = discord.Embed(
            title="Channel Renamed",
            description=f"🔄 **{old_name}** → **{new_name}**",
            color=config.EMBED_COLOR
        )
        await ctx.send(embed=embed)

    @rename_command.error
    async def rename_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=discord.Embed(
                title="Missing Permissions",
                description="You need the **Administrator** permission to use this command.",
                color=config.EMBED_COLOR
            ))
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=discord.Embed(
                title="Invalid Argument",
                description="Be sure to mention the channel (e.g. `#general`) and provide a valid new name.",
                color=config.EMBED_COLOR
            ))
        else:
            # Fallback for other errors
            await ctx.send(embed=discord.Embed(
                title="Error",
                description=str(error),
                color=config.EMBED_COLOR
            ))

async def setup(bot):
    await bot.add_cog(ChannelManagement(bot))
