import discord
from discord.ext import commands
import config # Assuming config.py has EMBED_COLOR

# ────────────────────────────────────────────────────────────────────────── #
# Role Button (No changes needed)
# This class is perfect. It handles the logic for a single role button.
# ────────────────────────────────────────────────────────────────────────── #
class RoleButton(discord.ui.Button):
    def __init__(self, role_name: str):
        super().__init__(label=role_name, style=discord.ButtonStyle.secondary, custom_id=role_name)
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        role = discord.utils.get(guild.roles, name=self.role_name)
        if role is None:
            await interaction.response.send_message("Role not found.", ephemeral=True)
            return

        member = interaction.user
        action = None
        if role in member.roles:
            await member.remove_roles(role, reason="Self-role panel")
            action = "removed"
        else:
            await member.add_roles(role, reason="Self-role panel")
            action = "added"

        await interaction.response.send_message(
            f"Role **{self.role_name}** {action}.", ephemeral=True
        )


# ────────────────────────────────────────────────────────────────────────── #
# Role Button View (Now for Ephemeral Messages)
# This view now has a timeout. It's sent privately to the user when
# they select a category from the main panel.
# ────────────────────────────────────────────────────────────────────────── #
class SelfRoleView(discord.ui.View):
    def __init__(self, roles: list[str]):
        # 5-minute timeout for the ephemeral panel
        super().__init__(timeout=300) 
        for role in roles:
            # Discord allows max 25 buttons per view, 5 per row.
            self.add_item(RoleButton(role))


# ────────────────────────────────────────────────────────────────────────── #
# NEW: Category Select Dropdown
# This is the dropdown menu that will be part of the persistent panel.
# ────────────────────────────────────────────────────────────────────────── #
class CategorySelect(discord.ui.Select):
    def __init__(self, categories: dict[str, list[str]], emojis: dict[str, str]):
        self.categories = categories
        self.emojis = emojis

        options = []
        for name in categories.keys():
            options.append(
                discord.SelectOption(
                    label=f"{name.capitalize()} Roles",
                    value=name,
                    emoji=self.emojis.get(name, "🏷️") # Get emoji or use default
                )
            )

        super().__init__(
            placeholder="Select a category to get roles...",
            options=options,
            custom_id="persistent_category_select" # Static custom_id for persistence
        )

    async def callback(self, interaction: discord.Interaction):
        # Get the category name the user selected
        category_name = self.values[0]
        # Get the list of roles for that category
        roles = self.categories[category_name]

        # 1. Create a friendly embed for the ephemeral message
        embed = discord.Embed(
            title=f"{self.emojis.get(category_name, '🏷️')} {category_name.capitalize()} Roles",
            description="Click the buttons below to add or remove roles.\nThis message is just for you.",
            color=config.EMBED_COLOR
        )
        
        # 2. Create the view with the buttons for ONLY this category
        view = SelfRoleView(roles)

        # 3. Send the message ephemerally (privately)
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )


# ────────────────────────────────────────────────────────────────────────── #
# NEW: Persistent Role Menu View
# This is the main, persistent view that holds the CategorySelect dropdown.
# ────────────────────────────────────────────────────────────────────────── #
class RoleMenuView(discord.ui.View):
    def __init__(self, categories: dict[str, list[str]], emojis: dict[str, str]):
        super().__init__(timeout=None) # Persistent
        
        # Add the dropdown to this view
        self.add_item(CategorySelect(categories, emojis))


# ────────────────────────────────────────────────────────────────────────── #
# Cog (Updated)
# ────────────────────────────────────────────────────────────────────────── #
class SelfRoleCog(commands.Cog):
    """Manages the persistent, interactive self-role menu."""

    # Moved roles and emojis to class constants for easy access
    CATEGORY_ROLES: dict[str, list[str]] = {
        "study": [
            "🈶 Korean Learner",
            "🇺🇸 English Learner",
            "🧑‍🏫 Language Exchange",
            "📝 Daily Practice",
            "📖 Grammar Nerd",
            "🗣️ Speaking Partner",
        ],
        "community": [
            "🌱 New Member",
            "💬 Active Chatter",
            "🌟 Regular",
            "🐐 Veteran",
            "🎉 Event Participant",
            "😂 Meme Master",
        ],
        "notify": [
            "📢 Announcements",
            "📅 Event Updates",
            "🎁 Giveaway Alerts",
            "🎥 Stream/Study Session Alerts",
            "📊 Poll Participation",
        ],
        "interest": [
            "🎨 Art",
            "✍️ Writing",
            "📸 Photography",
            "👨‍💻 Tech & Programming",
            "🎧 Music",
            "📚 Study Group",
        ],
        "krdaily": [
            "📅 Korean Word of the Day",
            "📅 Korean Phrase of the Day",
        ],
        "engdaily": [
            "📅 English Word of the Day",
            "📅 English Phrase of the Day",
        ],
        "quizdaily": [
            "📝 Korean Quiz of the Day",
            "📝 English Quiz of the Day",
        ]
    }
    
    CATEGORY_EMOJIS: dict[str, str] = {
        "study": "📚",
        "community": "👥",
        "notify": "📢",
        "interest": "🎨",
        "krdaily": "🇰🇷",
        "engdaily": "🇺🇸",
        "quizdaily": "📝"
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # This one command replaces the old `selfrole` command.
    # It's admin-only and posts the single persistent panel.
    @commands.command(name="sendrolepanel")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def send_role_panel(self, ctx: commands.Context):
        """
        Sends the persistent self-role menu to this channel.
        (Admin Only)
        """
        
        embed = discord.Embed(
            title="Self-Role Menu",
            description=(
                "Select a category from the dropdown menu below to choose your roles.\n"
                "You will receive a private message with the buttons for that category."
            ),
            color=config.EMBED_COLOR
        )
        
        # Create the persistent view and pass the roles/emojis to it
        view = RoleMenuView(self.CATEGORY_ROLES, self.CATEGORY_EMOJIS)
        
        await ctx.send(embed=embed, view=view)

    @send_role_panel.error
    async def send_role_panel_error(self, ctx: commands.Context, error):
        """Error handler for the sendrolepanel command."""
        if isinstance(error, commands.MissingPermissions):
            # Send a private message if the user isn't an admin
            await ctx.author.send(
                f"You must be an administrator to use the `!sendrolepanel` command in {ctx.guild.name}."
            )
            # Silently delete the failed command attempt
            await ctx.message.delete()
        else:
            # Log other errors
            print(f"Error in send_role_panel: {error}")
            await ctx.send("An unexpected error occurred. Please check the console.")


# ────────────────────────────────────────────────────────────────────────── #
# Setup (Updated)
# ────────────────────────────────────────────────────────────────────────── #
async def setup(bot: commands.Bot):
    cog = SelfRoleCog(bot)
    await bot.add_cog(cog)
    
    # We must register the *one* persistent view on setup.
    # We pass the categories and emojis from the cog instance directly.
    # This allows the view to be reconstructed when the bot restarts.
    bot.add_view(RoleMenuView(cog.CATEGORY_ROLES, cog.CATEGORY_EMOJIS))