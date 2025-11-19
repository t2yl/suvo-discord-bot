import discord
from discord.ext import commands
import json
import os
import uuid
from datetime import datetime

class Warnings(commands.Cog):
    """A cog for handling user warnings."""

    def __init__(self, bot):
        self.bot = bot
        self.warnings_file = "warnings.json"
        self.warnings = self._load_warnings()

    # --- HELPER FUNCTIONS FOR DATA HANDLING ---

    def _load_warnings(self):
        """Loads warnings from the JSON file."""
        if os.path.exists(self.warnings_file):
            with open(self.warnings_file, 'r') as f:
                # Check if file is empty
                if os.path.getsize(self.warnings_file) == 0:
                    return {}
                return json.load(f)
        return {}

    def _save_warnings(self):
        """Saves the current warnings dictionary to the JSON file."""
        with open(self.warnings_file, 'w') as f:
            json.dump(self.warnings, f, indent=4)

    # --- COMMANDS ---

    @commands.command(name="warn", help="Warns a user. Usage: !warn <@user> [reason]")
    @commands.has_permissions(kick_members=True)
    async def warn_user(self, ctx, member: discord.Member, *, reason: str = "No reason provided."):
        """Adds a warning to a specified user."""
        if member.bot:
            await ctx.send("You cannot warn a bot.")
            return
        
        if member == ctx.author:
            await ctx.send("You cannot warn yourself.")
            return

        # Role hierarchy check: prevent warning users with higher or equal roles
        if member.top_role >= ctx.author.top_role and ctx.guild.owner != ctx.author:
            await ctx.send("You cannot warn a member with a higher or equal role than you.")
            return

        guild_id = str(ctx.guild.id)
        user_id = str(member.id)
        
        # Generate a unique warning ID
        warn_id = str(uuid.uuid4().hex[:8])

        new_warning = {
            "warn_id": warn_id,
            "moderator_id": ctx.author.id,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason
        }

        # Add warning to the data structure
        if guild_id not in self.warnings:
            self.warnings[guild_id] = {}
        if user_id not in self.warnings[guild_id]:
            self.warnings[guild_id][user_id] = []
        
        self.warnings[guild_id][user_id].append(new_warning)
        self._save_warnings()

        # Send confirmation message
        embed = discord.Embed(
            title="User Warned",
            description=f"**{member.mention}** has been warned.",
            color=0xff0000
        )
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        embed.add_field(name="Warning ID", value=f"`{warn_id}`", inline=False)
        embed.set_footer(text=f"This is warning #{len(self.warnings[guild_id][user_id])} for this user.")

        await ctx.send(embed=embed)
        
        # Optionally, DM the user who was warned
        try:
            dm_embed = discord.Embed(
                title=f"You have been warned in {ctx.guild.name}",
                color=0xff0000
            )
            dm_embed.add_field(name="Reason", value=reason)
            dm_embed.add_field(name="Warning ID", value=f"`{warn_id}`")
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            await ctx.send(f"Could not DM {member.mention} about their warning.", delete_after=10)


    @commands.command(name="warnlist", help="Shows all warnings for a user. Usage: !warnlist <@user>")
    async def list_warnings(self, ctx, member: discord.Member):
        """Displays all warnings for a given user."""
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        if guild_id not in self.warnings or user_id not in self.warnings[guild_id] or not self.warnings[guild_id][user_id]:
            await ctx.send(f"{member.mention} has no warnings.")
            return

        user_warnings = self.warnings[guild_id][user_id]
        
        embed = discord.Embed(
            title=f"Warnings for {member.display_name}",
            color=0xffffff
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)

        for warn in user_warnings:
            moderator = self.bot.get_user(warn['moderator_id']) or f"ID: {warn['moderator_id']}"
            timestamp_dt = datetime.fromisoformat(warn['timestamp'])
            # Format timestamp for better readability
            formatted_time = timestamp_dt.strftime("%Y-%m-%d %H:%M UTC")

            embed.add_field(
                name=f"ID: `{warn['warn_id']}`",
                value=f"**Reason:** {warn['reason']}\n**Moderator:** {moderator}\n**Date:** {formatted_time}",
                inline=False
            )
        
        await ctx.send(embed=embed)


    @commands.command(name="removewarn", aliases=['delwarn', 'rmwarn'], help="Removes a specific warning. Usage: !removewarn <@user> <warn_id>")
    @commands.has_permissions(kick_members=True)
    async def remove_warning(self, ctx, member: discord.Member, warn_id: str):
        """Removes a warning from a user by its ID."""
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        if guild_id not in self.warnings or user_id not in self.warnings[guild_id]:
            await ctx.send(f"{member.mention} has no warnings to remove.")
            return

        # Find the warning to remove
        warning_to_remove = None
        for warn in self.warnings[guild_id][user_id]:
            if warn['warn_id'] == warn_id:
                warning_to_remove = warn
                break
        
        if not warning_to_remove:
            await ctx.send(f"Could not find a warning with ID `{warn_id}` for {member.mention}.")
            return
            
        # --- ROLE HIERARCHY CHECK ---
        original_mod_id = warning_to_remove['moderator_id']
        remover = ctx.author
        
        # A user can always remove their own warnings
        if original_mod_id != remover.id:
            try:
                # Fetch the member object of the moderator who gave the warning
                original_mod = await ctx.guild.fetch_member(original_mod_id)
                # A user with a lower or equal top role cannot remove the warning
                if remover.top_role <= original_mod.top_role and ctx.guild.owner != remover:
                    await ctx.send(f"You do not have permission to remove this warning. It was issued by {original_mod.mention}, who has a higher or equal role.")
                    return
            except discord.NotFound:
                # If the original moderator is no longer in the server, allow removal by any authorized user
                pass

        # Remove the warning and save
        self.warnings[guild_id][user_id].remove(warning_to_remove)
        
        # If the user has no more warnings, remove their entry
        if not self.warnings[guild_id][user_id]:
            del self.warnings[guild_id][user_id]
        if not self.warnings[guild_id]:
            del self.warnings[guild_id]

        self._save_warnings()
        
        embed = discord.Embed(
            title="Warning Removed",
            description=f"Successfully removed warning `{warn_id}` from {member.mention}.",
            color=0xffffff
        )
        await ctx.send(embed=embed)

    # --- ERROR HANDLING ---
    
    @warn_user.error
    @list_warnings.error
    @remove_warning.error
    async def warning_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You do not have permission to use this command.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("Could not find the specified member. Please make sure you mention them correctly.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"You are missing a required argument. Please check the command usage with `!help {ctx.command.name}`.")
        else:
            print(f"An error occurred in a warning command: {error}")
            await ctx.send("An unexpected error occurred. Please try again later.")


# This function is required for the bot to load the cog
async def setup(bot):
    await bot.add_cog(Warnings(bot))