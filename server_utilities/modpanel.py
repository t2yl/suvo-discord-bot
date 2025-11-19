import discord
from discord.ext import commands
from discord.ui import View, Modal, TextInput
import datetime
import config

class ReportModal(Modal, title="Report a User"):
    user_ids = TextInput(label="User ID(s)", placeholder="Separate with commas if more than one")
    usernames = TextInput(label="Username(s)", placeholder="Separate with commas if more than one")
    links = TextInput(label="Message/Screenshot Link(s)", placeholder="Separate with commas if more than one")
    explanation = TextInput(label="Explain the Situation", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="User Report",
            color=discord.Colour.red(),
        )
        embed.add_field(name="User ID(s)", value=self.user_ids.value, inline=False)
        embed.add_field(name="Username(s)", value=self.usernames.value, inline=False)
        embed.add_field(name="Link(s)", value=self.links.value, inline=False)
        embed.add_field(name="Explanation", value=self.explanation.value, inline=False)
        if interaction.user.avatar:
            embed.set_thumbnail(url=interaction.user.avatar.url)
        ts = int(datetime.datetime.utcnow().timestamp())
        embed.add_field(name="Reported", value=f"<t:{ts}:R>", inline=False)

        channel = interaction.client.get_channel(1377962794376499200)
        if channel:
            await channel.send(embed=embed)
            await interaction.response.send_message("✅ Report submitted.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Report channel not found.", ephemeral=True)

class FeedbackModal(Modal, title="Leave Feedback"):
    feedback = TextInput(label="Feedback/Suggestion", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="New Feedback",
            description=self.feedback.value,
            color=0x00ff00,
        )
        embed.set_footer(text=f"{interaction.user}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        channel = interaction.client.get_channel(1377961670126866602)
        if channel:
            msg = await channel.send(embed=embed)
            await msg.add_reaction("👍")
            await interaction.response.send_message("✅ Feedback submitted.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Feedback channel not found.", ephemeral=True)

class ModPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Report a User", style=discord.ButtonStyle.danger, custom_id="mod_report")
    async def report_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReportModal())

    @discord.ui.button(label="Leave Feedback", style=discord.ButtonStyle.primary, custom_id="mod_feedback")
    async def feedback_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FeedbackModal())

class ModPanelCog(commands.Cog):
    """Cog to send a moderator panel with report and feedback options."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="modpanel")
    @commands.has_permissions(manage_guild=True)
    async def modpanel(self, ctx: commands.Context):
        embed = discord.Embed(  
            description=(
                "**Moderator Panel**\n\n"
                "This panel allows you to perform two important actions:\n\n"
                "**## Report a User**\n"
                "If you encounter any member violating server rules, use this option to submit a detailed report. "
                "Include relevant user information and any supporting evidence such as message links or screenshots.\n\n"
                "**## Leave Feedback**\n"
                "Share your thoughts or suggestions to help improve the server. Whether it's about moderation, events, or general experience, "
                "all feedback is welcome and reviewed by the moderation team.\n\n"
                "Use the buttons below to proceed with either option."
            ),
            color=config.EMBED_COLOR
        )
        view = ModPanelView()
        await ctx.send(embed=embed, view=view)

async def setup(bot: commands.Bot):
    cog = ModPanelCog(bot)
    await bot.add_cog(cog)
    # register persistent buttons so they survive a restart
    bot.add_view(ModPanelView())

