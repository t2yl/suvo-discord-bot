import discord
from discord.ext import commands
from discord import ui
import config

# Modal for jumping to a specific page
class PageModal(ui.Modal):
    page_input = ui.TextInput(
        label="Page Number",
        placeholder="Enter page number to jump to",
        required=True,
        min_length=1,
        max_length=2
    )

    def __init__(self, view: ui.View):
        super().__init__(title="Jump to Page")
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page_input.value)
        except ValueError:
            await interaction.response.send_message("Please enter a valid number.", ephemeral=True)
            return

        if page < 1 or page > len(self.view.pages):
            await interaction.response.send_message(
                f"Page must be between 1 and {len(self.view.pages)}.",
                ephemeral=True
            )
            return

        self.view.current_page = page
        self.view.update_buttons()
        await interaction.response.edit_message(
            embed=self.view.get_page_embed(),
            view=self.view
        )

# Generic paginator view for embeds, with automatic disabling on timeout
class PaginatedView(ui.View):
    def __init__(self, pages: list[discord.Embed], timeout: int = 180, include_jump: bool = True):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current_page = 1
        self.include_jump = include_jump

        # Previous page button (arrow only)
        self.prev_button = ui.Button(
            label="◀",
            style=discord.ButtonStyle.primary,
            custom_id="help_prev"
        )
        self.prev_button.callback = self.on_prev
        self.add_item(self.prev_button)

        # Optional "Jump to Page" button
        if self.include_jump:
            self.jump_button = ui.Button(
                label="Jump to Page",
                style=discord.ButtonStyle.secondary,
                custom_id="help_jump"
            )
            self.jump_button.callback = self.on_jump
            self.add_item(self.jump_button)

        # Next page button (arrow only)
        self.next_button = ui.Button(
            label="▶",
            style=discord.ButtonStyle.primary,
            custom_id="help_next"
        )
        self.next_button.callback = self.on_next
        self.add_item(self.next_button)

        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = (self.current_page == 1)
        self.next_button.disabled = (self.current_page == len(self.pages))

    def get_page_embed(self) -> discord.Embed:
        embed = self.pages[self.current_page - 1]
        embed.set_footer(text=f"Page {self.current_page}/{len(self.pages)}")
        return embed

    async def on_prev(self, interaction: discord.Interaction):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    async def on_next(self, interaction: discord.Interaction):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    async def on_jump(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PageModal(self))

    async def on_timeout(self):
        # Disable all buttons when view times out
        for item in self.children:
            item.disabled = True
        if hasattr(self, "message"):
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context):
        # Build general help pages by category
        pages: list[discord.Embed] = []

        # Utilities page
        embed_utils = discord.Embed(
            title="Help — Utilities",
            color=config.EMBED_COLOR,
            description=(
                "• `!ping`: Check bot latency\n"
                "• `?tag [keyword]`: Lookup glossary/server term\n"
                "• `!fm [on|off]`: Toggle focus mode"
            )
        )
        pages.append(embed_utils)

        # Games page
        embed_games = discord.Embed(
            title="Help — Games",
            color=config.EMBED_COLOR,
            description=(
                "• `!tfstart`: Start True/False quiz\n"
                "• `!rps [@user]`: Rock, Paper, Scissors\n"
                "• `!ttt [@user]`: Tic-Tac-Toe\n"
                "• `!startwmg [num|animal]`: Word Match Game"
            )
        )
        pages.append(embed_games)

        # Leaderboards & Maintenance page
        embed_leader = discord.Embed(
            title="Help — Leaderboards & Maintenance",
            color=config.EMBED_COLOR,
            description=(
                "• `!msglb`: Message leaderboard\n"
                "• `!vclb`: Voice-channel leaderboard\n"
                "• `!cleardm`: Clear bot DMs"
            )
        )
        pages.append(embed_leader)

        # Create paginator without jump button for main help
        view = PaginatedView(pages, timeout=120, include_jump=False)

        # Add admin button if user has moderator/volunteer role
        if any(role.id in (config.MODERATOR_ROLE_ID, config.VOLUNTEER_ROLE_ID) for role in ctx.author.roles):
            view.add_item(
                ui.Button(
                    label="View Admin Commands",
                    style=discord.ButtonStyle.secondary,
                    custom_id="view_admin"
                )
            )

        # Send the help message and keep a reference for timeout disabling
        message = await ctx.send(embed=view.get_page_embed(), view=view)
        view.message = message

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        # Handle "View Admin Commands" click
        if (
            interaction.type is discord.InteractionType.component
            and interaction.data.get("custom_id") == "view_admin"
        ):
            # Build admin help pages
            pages: list[discord.Embed] = []

            embed1 = discord.Embed(
                title="Admin — True / False Questions",
                color=config.EMBED_COLOR,
                description=(
                    "• `!addtf <question>, <t/f>`: Add TF question\n"
                    "• `!viewtfall`: List all TF questions (paginated)\n"
                    "• `!removetf <id>`: Remove question by ID"
                )
            )
            pages.append(embed1)

            embed2 = discord.Embed(
                title="Admin — Tags",
                color=config.EMBED_COLOR,
                description=(
                    "• `!mtag <name> <message>`: Save tag (optional file)\n"
                    "• `!rmtag <name>`: Delete a tag\n"
                    "• `!renametag <old> <new>`: Rename a tag\n"
                    "• `!alltags`: List all tags"
                )
            )
            pages.append(embed2)

            embed3 = discord.Embed(
                title="Admin — Moderation",
                color=config.EMBED_COLOR,
                description=(
                    "• `@master suvo. [question]`: Ask master suvo\n"
                    "• `!sb`: Starboard a message\n"
                    "• `!purge [number] <user>`: Bulk-delete messages"
                )
            )
            pages.append(embed3)

            # Ephemeral admin view with jump button enabled
            admin_view = PaginatedView(pages, timeout=180, include_jump=True)
            await interaction.response.send_message(
                embed=admin_view.get_page_embed(),
                view=admin_view,
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(HelpCommand(bot))
