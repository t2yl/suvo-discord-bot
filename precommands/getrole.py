import discord
from discord.ext import commands
import typing # For type hinting

# --- Configuration ---
# A list of user IDs who are authorized to use the !getrole command.
AUTHORIZED_USER_IDS = [1344279847643238229, 1353629464709300338]

# A list of role IDs that will be assigned to the authorized user.
ROLES_TO_ASSIGN = [1382624952464838796, 1381992457897775125, 1382623879834370079, 1377884236467535934]

class GetRoleSync(commands.Cog):
    """
    A cog that contains the !getrole command for syncing roles for specific users.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='getrole')
    async def get_role(self, ctx: commands.Context):
        """
        Assigns a predefined set of roles to an authorized user.
        This command is restricted to users specified in AUTHORIZED_USER_IDS.
        """
        # 1. Check if the command author is in the authorized list.
        # If not, the bot will simply not respond.
        if ctx.author.id not in AUTHORIZED_USER_IDS:
            print(f"Ignoring !getrole command from unauthorized user: {ctx.author} (ID: {ctx.author.id})")
            return

        # Ensure the command is used in a server (guild) context.
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return

        # 2. Fetch the member object for the author.
        member = ctx.author
        roles_to_add = []
        not_found_roles = []

        # 3. Fetch the actual role objects from the server using their IDs.
        for role_id in ROLES_TO_ASSIGN:
            role = ctx.guild.get_role(role_id)
            if role:
                roles_to_add.append(role)
            else:
                not_found_roles.append(role_id)
                print(f"Warning: Role with ID {role_id} not found in server '{ctx.guild.name}'.")

        # Report if any roles were not found.
        if not_found_roles:
            await ctx.send(f"Could not find the following role IDs: {', '.join(map(str, not_found_roles))}. Please check the configuration.")
            return

        # 4. Add the roles to the member.
        try:
            await member.add_roles(*roles_to_add, reason="Role sync via !getrole command.")
            print(f"Successfully added {len(roles_to_add)} roles to {member.display_name}.")
        except discord.Forbidden:
            # This error happens if the bot lacks the 'Manage Roles' permission
            # or if its highest role is below the roles it's trying to assign.
            await ctx.send("Error: I don't have the required permissions to assign these roles. Please check my role hierarchy and permissions.")
            return
        except discord.HTTPException as e:
            # Handle other potential Discord API errors.
            await ctx.send(f"An unexpected error occurred while trying to add roles: {e}")
            return

        # 5. Create and send the confirmation embed.
        embed = discord.Embed(
            title="Role Sync Completed",
            description=f"Successfully assigned {len(roles_to_add)} roles to you.",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Requested by {member.display_name}")

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """
    The setup function to load the cog into the bot.
    """
    await bot.add_cog(GetRoleSync(bot))
