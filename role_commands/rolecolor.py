import discord
from discord.ext import commands

# ────────────────────────────────────────────────────────────────────────── #
# Cog
# ────────────────────────────────────────────────────────────────────────── #
class RoleColorCog(commands.Cog):
    """Cog to let users self-assign exclusive colour roles via a button that opens an ephemeral dropdown."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Define all available colours here.
        # This can now safely handle more than 25!
        self.basic_colors = [
            "White", "Black", "Gray", "Red", "Green", "Blue",
            "Yellow", "Cyan", "Magenta", "Orange", "Pink",
            "Purple", "Brown", "Light Gray", "Dark Gray",
            "Light Blue", "Dark Blue", "Lime Green", "Olive",
            "Teal", "Navy", "Maroon", "Gold", "Beige", "Coral",
            "Mint" # Added a 27th color to demonstrate pagination
        ]
        # Register the persistent button view so it never expires
        bot.add_view(RoleColorButtonView(self.basic_colors))

    @commands.command(name="rolecolor")
    @commands.has_permissions(administrator=True) # <-- CRITICAL: Only admins can post the panel
    @commands.guild_only()
    async def rolecolor(self, ctx: commands.Context):
        """Sends an embed with a persistent button. (Admin Only)"""
        embed = discord.Embed(
            title="🎨 Colour Roles",
            description="Click the button below to choose your personal name color.",
            color=discord.Colour.light_gray()
        )
        await ctx.send(embed=embed, view=RoleColorButtonView(self.basic_colors))

    @rolecolor.error
    async def rolecolor_error(self, ctx: commands.Context, error):
        """Handles errors for the rolecolor command."""
        if isinstance(error, commands.MissingPermissions):
            try:
                # Silently delete the failed command attempt
                await ctx.message.delete()
                # Notify the user privately
                await ctx.author.send("You must be an Administrator to run the `!rolecolor` command.")
            except discord.Forbidden:
                pass # Bot lacks permissions to delete messages or DM
        else:
            print(f"Error in rolecolor command: {error}")
            await ctx.send("An unexpected error occurred.")


# ────────────────────────────────────────────────────────────────────────── #
# Persistent Button View & Button
# ────────────────────────────────────────────────────────────────────────── #
class RoleColorButtonView(discord.ui.View):
    """Persistent view containing the 'Choose your colour' button."""
    def __init__(self, colors: list[str]):
        super().__init__(timeout=None)
        # Pass the full color list to the button
        self.add_item(ChooseColorButton(colors))

class ChooseColorButton(discord.ui.Button):
    def __init__(self, colors: list[str]):
        super().__init__(
            label="Choose your colour",
            style=discord.ButtonStyle.primary,
            custom_id="persistent_choose_color_button",
            emoji="🎨"
        )
        self.colors = colors

    async def callback(self, interaction: discord.Interaction):
        # When clicked, send an ephemeral view containing the paginated dropdowns
        await interaction.response.send_message(
            "Select your colour from the dropdown(s) below:",
            view=ColorSelectView(self.colors), # Pass the full list
            ephemeral=True
        )

# ────────────────────────────────────────────────────────────────────────── #
# Ephemeral Dropdown View & Dropdown
# ────────────────────────────────────────────────────────────────────────── #
class ColorSelectView(discord.ui.View):
    """
    Non-persistent view containing one or more dropdowns. Sent ephemerally.
    This view automatically paginates the color list if it exceeds 25 items.
    """
    def __init__(self, colors: list[str]):
        super().__init__(timeout=180) # 3-minute timeout
        
        # Store the master set of all color names for the removal logic
        all_colors_set = set(colors) 
        
        # Chunk the colors into lists of 25 (max per dropdown)
        chunks = [colors[i:i + 25] for i in range(0, len(colors), 25)]
        
        if not chunks:
            # Failsafe in case the color list is empty
            return

        # Create a separate dropdown (ColorSelect) for each chunk
        for i, chunk in enumerate(chunks):
            placeholder = f"Select your colour... (Page {i+1}/{len(chunks)})"
            self.add_item(ColorSelect(chunk, placeholder, all_colors_set))

class ColorSelect(discord.ui.Select):
    """
    A single dropdown menu. It is aware of *all* color roles
    so it can properly remove old ones.
    """
    def __init__(self, colors_chunk: list[str], placeholder: str, all_defined_colors: set[str]):
        options = [discord.SelectOption(label=color) for color in colors_chunk]
        
        # Store the *complete* set of all color roles for the removal logic
        self.all_defined_colors = all_defined_colors 
        
        super().__init__(
            placeholder=placeholder,
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        chosen_colour = self.values[0]
        member = interaction.user
        guild = interaction.guild

        # Remove any *other* colour roles from our master list
        to_remove = [role for role in member.roles if role.name in self.all_defined_colors]
        
        if to_remove:
            await member.remove_roles(*to_remove, reason="Switching colour role")

        # Find the new Role object by name
        role = discord.utils.get(guild.roles, name=chosen_colour)
        if role:
            await member.add_roles(role, reason="Assigned via dropdown")
            # Edit the original ephemeral message to show success
            await interaction.response.edit_message(
                content=f":art: Your colour role is now **{chosen_colour}**.",
                view=None # Remove the dropdowns
            )
        else:
            # Edit the original ephemeral message to show failure
            await interaction.response.edit_message(
                content=f":x: Role **{chosen_colour}** not found. Contact an admin.",
                view=None # Remove the dropdowns
            )

# ────────────────────────────────────────────────────────────────────────── #
# Setup
# ────────────────────────────────────────────────────────────────────────── #
async def setup(bot: commands.Bot):
    cog = RoleColorCog(bot)
    await bot.add_cog(cog)
    # The persistent view is already registered in the Cog's __init__