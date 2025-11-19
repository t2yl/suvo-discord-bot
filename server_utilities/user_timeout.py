import re
import discord
from discord.ext import commands
from datetime import datetime, timedelta

class TimeoutUser(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='timeout')
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, duration: str, *, note: str):
        """
        Usage: !timeout @user <time> <note>
        Time format: <number><s/m/h/d> (e.g., 30s, 10m, 2h, 1d)
        """
        # Parse duration
        match = re.match(r'^(\d+)([smhd])$', duration.lower())
        if not match:
            embed = discord.Embed(
                title="Invalid Time Format",
                description="Please specify the duration as `<number><s/m/h/d>`. For example: `30s`, `10m`, `2h`, or `1d`.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        value, unit = int(match.group(1)), match.group(2)
        if unit == 's':
            delta = timedelta(seconds=value)
        elif unit == 'm':
            delta = timedelta(minutes=value)
        elif unit == 'h':
            delta = timedelta(hours=value)
        else:  # 'd'
            delta = timedelta(days=value)

        # Attempt to timeout
        try:
            await member.timeout(delta, reason=note)
        except discord.Forbidden:
            embed = discord.Embed(
                title="Permission Denied",
                description="I do not have permission to timeout this user.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        except discord.HTTPException:
            embed = discord.Embed(
                title="Timeout Failed",
                description="An unexpected error occurred while trying to timeout the user.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        # Success embed
        expires_at = datetime.utcnow() + delta
        embed = discord.Embed(
            title="User Timed Out",
            color=discord.Color.orange()
        )
        embed.add_field(name="User", value=f"{member.mention}", inline=True)
        embed.add_field(name="Duration", value=f"{duration}", inline=True)
        embed.add_field(name="Reason", value=note, inline=False)
        embed.set_footer(text=f"Timed out by {ctx.author}")

        await ctx.send(embed=embed)

    @timeout.error
    async def timeout_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="Missing Arguments",
                description="Usage: `!timeout @user <time> <note>`\nExample: `!timeout @JaneDoe 10m Spamming`",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        if isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="Invalid User",
                description="Couldn't find that user. Please mention a valid member.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="Insufficient Permissions",
                description="You need the **Moderate Members** permission to use this command.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        # Fallback for other errors
        embed = discord.Embed(
            title="Error",
            description="An unexpected error occurred.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(TimeoutUser(bot))
