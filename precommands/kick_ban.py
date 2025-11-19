import discord
from discord.ext import commands

class KickBanCommmands(commands.Cog):
    """A cog for handling moderation commands like kick and ban."""

    def __init__(self, bot):
        self.bot = bot

    # --- KICK COMMAND ---
    @commands.command(name="kick", help="Kicks a user from the server. Usage: !kick <@user> [reason]")
    @commands.has_permissions(kick_members=True)
    async def kick_user(self, ctx, member: discord.Member, *, reason: str = "No reason provided."):
        """Kicks a specified user from the server."""
        # Prevent kicking the bot itself
        if member.id == self.bot.user.id:
            await ctx.send("I cannot kick myself.")
            return

        # Prevent a user from kicking themselves
        if member == ctx.author:
            await ctx.send("You cannot kick yourself.")
            return

        # Role hierarchy check: prevent kicking users with higher or equal roles
        # The server owner is exempt from this check.
        if member.top_role >= ctx.author.top_role and ctx.guild.owner != ctx.author:
            await ctx.send("You cannot kick a member with a higher or equal role than you.")
            return

        # Attempt to DM the user before kicking them
        try:
            dm_embed = discord.Embed(
                title=f"You have been kicked from {ctx.guild.name}",
                description=f"Reason: {reason}",
                color=discord.Color.orange()
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            # This happens if the user has DMs disabled or has blocked the bot.
            await ctx.send(f"Could not DM {member.mention}, but proceeding with kick.", delete_after=10)
        except Exception as e:
            print(f"Failed to DM user before kick: {e}")


        # Kick the user
        try:
            await member.kick(reason=f"Kicked by {ctx.author.name}. Reason: {reason}")
            
            # Send confirmation message
            embed = discord.Embed(
                title="User Kicked",
                description=f"**{member.mention}** has been kicked from the server.",
                color=discord.Color.green()
            )
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)
            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send("I do not have the necessary permissions to kick this user.")
        except Exception as e:
            await ctx.send(f"An error occurred while trying to kick the user: {e}")


    # --- BAN COMMAND ---
    @commands.command(name="ban", help="Bans a user from the server. Usage: !ban <@user> [reason]")
    @commands.has_permissions(ban_members=True)
    async def ban_user(self, ctx, member: discord.Member, *, reason: str = "No reason provided."):
        """Bans a specified user from the server."""
        # Prevent banning the bot itself
        if member.id == self.bot.user.id:
            await ctx.send("I cannot ban myself.")
            return

        # Prevent a user from banning themselves
        if member == ctx.author:
            await ctx.send("You cannot ban yourself.")
            return

        # Role hierarchy check
        if member.top_role >= ctx.author.top_role and ctx.guild.owner != ctx.author:
            await ctx.send("You cannot ban a member with a higher or equal role than you.")
            return

        # Attempt to DM the user before banning them
        try:
            dm_embed = discord.Embed(
                title=f"You have been banned from {ctx.guild.name}",
                description=f"Reason: {reason}",
                color=discord.Color.red()
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            await ctx.send(f"Could not DM {member.mention}, but proceeding with ban.", delete_after=10)
        except Exception as e:
            print(f"Failed to DM user before ban: {e}")


        # Ban the user
        try:
            await member.ban(reason=f"Banned by {ctx.author.name}. Reason: {reason}")
            
            # Send confirmation message
            embed = discord.Embed(
                title="User Banned",
                description=f"**{member.mention}** has been permanently banned from the server.",
                color=discord.Color.red()
            )
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)
            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send("I do not have the necessary permissions to ban this user.")
        except Exception as e:
            await ctx.send(f"An error occurred while trying to ban the user: {e}")

    # --- ERROR HANDLING for this Cog ---
    @kick_user.error
    @ban_user.error
    async def moderation_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You do not have the required permissions to use this command.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("Could not find the specified member. Please make sure you mention them correctly.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"You are missing a required argument. Use `!help {ctx.command.name}` for details.")
        else:
            print(f"An error occurred in a moderation command: {error}")
            await ctx.send("An unexpected error occurred. Please check the console for more details.")


# This function is required for the bot to load the cog
async def setup(bot):
    await bot.add_cog(KickBanCommmands(bot))
