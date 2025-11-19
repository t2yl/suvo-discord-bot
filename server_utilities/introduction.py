import discord
from discord.ext import commands
import datetime

# --- Configuration ---
# I've replaced 'config.py' with placeholder values.
# Replace these with your own channel/role IDs and colors.
EMBED_COLOR = 0xffffff  # Discord 'Blurple'
INTRODUCTION_CHANNEL_ID = 1377909277993468035  # FIXME: Replace with your public intro channel ID
STAFF_ROLE_ID = 1378004327008047197  # User's original ID
STAFF_CHANNEL_ID = 1378003806129885235  # User's original ID
# ---------------------

# Track user submission times to enforce rate limit
submissions: dict[int, datetime.datetime] = {}

# Persistent view: instruction panel with "Introduce Yourself" and "Staff Intro" buttons
class IntroductionView(discord.ui.View):
    """
    The persistent view that sits on the main intro panel.
    It just launches the ephemeral form for the user.
    """
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Introduce Yourself", style=discord.ButtonStyle.primary, custom_id="intro_btn")
    async def introduce_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check rate limit *before* sending the form
        user = interaction.user
        now = datetime.datetime.utcnow()
        last = submissions.get(user.id)
        if last and (now - last).total_seconds() < 600:
            return await interaction.response.send_message(
                f"You can only introduce once every 10 minutes. Please try again in {int((600 - (now - last).total_seconds()) / 60)} minutes.",
                ephemeral=True
            )
            
        form_view = FormView(self.bot)
        embed = form_view.build_embed(interaction.user)
        await interaction.response.send_message(embed=embed, view=form_view, ephemeral=True)

    @discord.ui.button(label="Staff Introduction", style=discord.ButtonStyle.secondary, custom_id="staff_intro_btn")
    async def staff_intro_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only allow users with the specific staff role
        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message(
                "You don't have permission to use this.", ephemeral=True
            )
            
        # Send to a different channel for staff intros
        form_view = FormView(self.bot, target_channel=STAFF_CHANNEL_ID)
        embed = form_view.build_embed(interaction.user)
        await interaction.response.send_message(embed=embed, view=form_view, ephemeral=True)

# Ephemeral form view: buttons to set each field and a submit button
class FormView(discord.ui.View):
    """
    The ephemeral view for building the introduction.
    Manages the draft embed and modal popups.
    """
    def __init__(self, bot: commands.Bot, target_channel: int = None):
        super().__init__(timeout=3600)  # 1 hour timeout for the form
        self.bot = bot
        self.target_channel = target_channel
        # Updated fields for a language exchange server
        self.data = {field: "*Not set*" for field in [
            "Name", "Age", "Native Language", "Target Language(s)",
            "Proficiency", "Reason for Learning", "Hobbies & Interests", "DM Preference", "About Me"
        ]}

    def build_embed(self, user: discord.Member) -> discord.Embed:
        """Helper function to build the draft embed."""
        embed = discord.Embed(title="📝 Your Introduction (Draft)", color=EMBED_COLOR)
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # Add fields from our data dict
        embed.add_field(name="Name", value=self.data["Name"], inline=True)
        embed.add_field(name="Age", value=self.data["Age"], inline=True)
        embed.add_field(name="Native Language", value=self.data["Native Language"], inline=True)
        embed.add_field(name="Target Language(s)", value=self.data["Target Language(s)"], inline=True)
        embed.add_field(name="Proficiency", value=self.data["Proficiency"], inline=True)
        embed.add_field(name="DM Preference", value=self.data["DM Preference"], inline=True)
        embed.add_field(name="Reason for Learning", value=self.data["Reason for Learning"], inline=False)
        embed.add_field(name="Hobbies & Interests", value=self.data["Hobbies & Interests"], inline=False)
        embed.add_field(name="About Me", value=self.data["About Me"], inline=False)
        
        embed.set_footer(text="Use the buttons below to fill each detail, then click Submit.")
        return embed

    # --- Row 1: Personal Info ---
    @discord.ui.button(label="Name", style=discord.ButtonStyle.secondary, custom_id="set_name", row=0)
    async def set_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SingleInputModal("Name", self, placeholder="What should we call you?"))

    @discord.ui.button(label="Age", style=discord.ButtonStyle.secondary, custom_id="set_age", row=0)
    async def set_age(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SingleInputModal("Age", self, placeholder="e.g., 25 or '20s' (optional)"))

    # --- Row 2: Language Info ---
    @discord.ui.button(label="Native Language", style=discord.ButtonStyle.secondary, custom_id="set_native", row=1)
    async def set_native(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SingleInputModal("Native Language", self, placeholder="e.g., English"))

    @discord.ui.button(label="Target Language(s)", style=discord.ButtonStyle.secondary, custom_id="set_target", row=1)
    async def set_target(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SingleInputModal("Target Language(s)", self, placeholder="e.g., Japanese, Spanish"))

    @discord.ui.button(label="Proficiency", style=discord.ButtonStyle.secondary, custom_id="set_proficiency", row=1)
    async def set_proficiency(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SingleInputModal("Proficiency", self, placeholder="e.g., Beginner, Intermediate, B2"))

    # --- Row 3: Details ---
    @discord.ui.button(label="Reason", style=discord.ButtonStyle.secondary, custom_id="set_reason", row=2)
    async def set_reason(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SingleInputModal("Reason for Learning", self, paragraph=True, placeholder="For travel, work, fun, etc."))

    @discord.ui.button(label="Hobbies", style=discord.ButtonStyle.secondary, custom_id="set_hobbies", row=2)
    async def set_hobbies(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SingleInputModal("Hobbies & Interests", self, paragraph=True, placeholder="Gaming, hiking, anime, coding..."))

    @discord.ui.button(label="DM Pref", style=discord.ButtonStyle.secondary, custom_id="set_dm", row=2)
    async def set_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SingleInputModal("DM Preference", self, placeholder="e.g., Open, Ask First, Closed"))

    # --- Row 4: About Me ---
    @discord.ui.button(label="About Me", style=discord.ButtonStyle.secondary, custom_id="set_about", row=3)
    async def set_about(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SingleInputModal("About Me", self, paragraph=True, placeholder="Anything else you'd like to share!"))

    # --- Row 5: Actions ---
    @discord.ui.button(label="Submit", style=discord.ButtonStyle.success, custom_id="submit_intro", row=4)
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        
        # Defer ephemeral response
        await interaction.response.defer(ephemeral=True)

        # Check for any "Not set" fields
        if any(value == "*Not set*" for value in self.data.values()):
            await interaction.edit_original_response(
                content="⚠️ **Error:** Please fill out all fields before submitting.",
                embed=self.build_embed(user),
                view=self
            )
            return

        # Passed checks, set rate limit
        submissions[user.id] = datetime.datetime.utcnow()

        # Build the public embed
        public_embed = discord.Embed(
            title=f"Welcome, {user.display_name}!",
            color=EMBED_COLOR,
            timestamp=datetime.datetime.utcnow()
        )
        avatar = user.display_avatar.url
        public_embed.set_thumbnail(url=avatar)

        # Add fields
        public_embed.add_field(name="Name", value=self.data["Name"], inline=True)
        public_embed.add_field(name="Age", value=self.data["Age"], inline=True)
        public_embed.add_field(name="Native Language", value=self.data["Native Language"], inline=True)
        public_embed.add_field(name="Target Language(s)", value=self.data["Target Language(s)"], inline=True)
        public_embed.add_field(name="Proficiency", value=self.data["Proficiency"], inline=True)
        public_embed.add_field(name="DM Preference", value=self.data["DM Preference"], inline=True)
        public_embed.add_field(name="Reason for Learning", value=self.data["Reason for Learning"], inline=False)
        public_embed.add_field(name="Hobbies & Interests", value=self.data["Hobbies & Interests"], inline=False)
        public_embed.add_field(name="About Me", value=self.data["About Me"], inline=False)
        
        public_embed.set_footer(text=f"User ID: {user.id}")

        # Determine where to send: default or staff channel
        channel_id = self.target_channel or INTRODUCTION_CHANNEL_ID
        channel = self.bot.get_channel(channel_id)
        
        if channel:
            try:
                # Ping the user outside the embed
                await channel.send(content=user.mention, embed=public_embed)
                # Confirm to user
                await interaction.edit_original_response(
                    content="✅ Success! Your introduction has been posted.",
                    embed=None,
                    view=None
                )
            except discord.Forbidden:
                await interaction.edit_original_response(
                    content="❌ Error: I don't have permission to send messages in the introductions channel.",
                    embed=None,
                    view=None
                )
        else:
            await interaction.edit_original_response(
                content=f"❌ Error: Could not find the introductions channel (ID: {channel_id}). Please contact an admin.",
                embed=None,
                view=None
            )
        
        self.stop() # Stop the view

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="cancel_intro", row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Introduction cancelled.", embed=None, view=None
        )
        self.stop() # Stop the view

    async def on_timeout(self):
        # This function is called if the view times out (1 hour)
        # You can't edit the original message if it's already been interacted with
        # (e.g., cancelled or submitted), so we use a try/except pass.
        try:
            # Get the original message
            message = await self.message.fetch()
            if message:
                await message.edit(content="This introduction form has expired.", embed=None, view=None)
        except (discord.NotFound, discord.HTTPException):
            pass # Message was already deleted or handled


# Modal for single-field input
class SingleInputModal(discord.ui.Modal):
    def __init__(self, field_name: str, form_view: FormView, paragraph: bool = False, placeholder: str = None):
        super().__init__(title=f"Update: {field_name}")
        self.field_name = field_name
        self.form_view = form_view
        style = discord.TextStyle.paragraph if paragraph else discord.TextStyle.short
        
        self.input = discord.ui.TextInput(
            label=field_name,
            style=style,
            placeholder=placeholder,
            required=True,
            max_length=1024 if paragraph else 100
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        self.form_view.data[self.field_name] = self.input.value
        embed = self.form_view.build_embed(interaction.user)
        # Edit the ephemeral message with the updated draft
        await interaction.response.edit_message(embed=embed, view=self.form_view)

# Cog to register the persistent view and manual refresh command
class IntroductionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # We create the view instance here.
        # We need to do this *before* add_cog,
        # or else the bot.add_view() in setup won't find it.
        self.sticky = IntroductionView(bot)
        
    @commands.Cog.listener()
    async def on_ready(self):
        # We register the view here to ensure it persists on cog reloads
        self.bot.add_view(self.sticky)
        print("IntroductionCog: Ready and persistent view registered.")

    @commands.command(name="intro")
    @commands.has_permissions(administrator=True)
    async def intro_command(self, ctx: commands.Context):
        """Posts the persistent introduction panel."""
        
        embed = discord.Embed(
            title = "👋 Welcome to the Server!",
            description = (
                "Ready to make your grand entrance? Click the button below to fill out a quick form and introduce yourself to the community!\n\n"
                "Here are the questions we'll ask:"
            ),
            color=EMBED_COLOR
        )
        
        embed.add_field(
            name="Fields to Fill",
            value = (
                "**Name**\n"
                "-# What should we call you?\n\n"
                "**Age**\n"
                "-# Your age or age range (optional).\n\n"
                "**Native Language**\n"
                "-# The language you're most fluent in.\n\n"
                "**Target Language(s)**\n"
                "-# The language(s) you're here to learn.\n\n"
                "**Proficiency**\n"
                "-# Your current level (e.g., Beginner, B1, etc.).\n\n"
                "**Reason for Learning**\n"
                "-# Why are you learning this language?\n\n"
                "**Hobbies & Interests**\n"
                "-# Find people with similar hobbies!\n\n"
                "**DM Preference**\n"
                "-# Are you open to DMs? (e.g., Open, Ask First, Closed)\n\n"
                "**About Me**\n"
                "-# Anything else you'd like to share!"
            ),

            inline=False
        )
        
        # You can use your original image or find a new one
        embed.set_image(url=(
            "https://media.discordapp.net/attachments/1377884306101374986/1378052741858852924/draw-banner-cute-bunny-easter-spring_45130-1604.png?ex=683b3320&is=6839e1a0&hm=d4d88631a6714743fd4ed61e02bf099725ca91e889a2b5752238d87bc1ba1c0c&=&format=webp&quality=lossless&width=563&height=220"
        ))
        
        await ctx.send(embed=embed, view=self.sticky)
        
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.HTTPException):
            await ctx.send("✅ Introduction panel posted!", delete_after=10)

async def setup(bot: commands.Bot):
    cog = IntroductionCog(bot)
    await bot.add_cog(cog)
    # This is crucial: This re-registers the view on cog load/reload.
    # We add it *after* adding the cog.
    bot.add_view(cog.sticky)