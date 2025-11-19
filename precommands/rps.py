import random
import asyncio
import discord
from discord.ext import commands
from discord import ui, ButtonStyle, Color
import json
import os

# --- Configuration ---
# You can move this to your config.py if you want
# Using a default color if config.EMBED_COLOR isn't available
try:
    import config
    EMBED_COLOR = config.EMBED_COLOR
except ImportError:
    EMBED_COLOR = Color.blurple()

# --- Constants ---
LEADERBOARD_FILE = os.path.join(os.path.dirname(__file__), 'leaderboard_rps.json')
GAME_WIN_SCORE = 5  # First to 5 wins
CHOICES_MAP = {
    0: ("Rock", "🪨"),
    1: ("Paper", "📄"),
    2: ("Scissors", "✂️")
}

# --- Helper Functions for Leaderboard ---

def load_leaderboard() -> dict[str, int]:
    """Loads the leaderboard from its JSON file."""
    if os.path.isfile(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}  # Return empty if file is corrupt
    return {}

def save_leaderboard(leaderboard: dict[str, int]):
    """Saves the leaderboard to its JSON file."""
    try:
        with open(LEADERBOARD_FILE, 'w') as f:
            json.dump(leaderboard, f, indent=4)
    except IOError as e:
        print(f"Error saving RPS leaderboard: {e}")

# --- Game View ---

class RPSGameView(ui.View):
    """
    Manages the UI and logic for an active RPS game.
    This view edits a single message to reflect the game state.
    """
    def __init__(self, player1: discord.Member, player2: discord.Member, embed: discord.Embed, ctx: commands.Context, timeout: int = 120):
        super().__init__(timeout=timeout)
        self.player1 = player1
        self.player2 = player2
        self.embed = embed
        self.ctx = ctx
        self.scores = {player1.id: 0, player2.id: 0}
        self.choices: dict[int, int] = {}
        self.last_round_summary: str = "No rounds played yet."
        self._lock = asyncio.Lock()
        self.message: discord.Message | None = None

    async def start_game(self, content: str | None = None):
        """Sends the initial game message."""
        await self.update_embed(status_override=f"Waiting on {self.player1.mention} and {self.player2.mention}...")
        self.message = await self.ctx.send(content=content, embed=self.embed, view=self)
        
        # If bot is playing, make its first move immediately
        if self.player2.bot:
            await self.make_bot_choice()

    async def make_bot_choice(self):
        """Handles the bot's turn."""
        async with self._lock:
            if self.player2.id not in self.choices:
                self.choices[self.player2.id] = random.choice([0, 1, 2])
        
        # If player 1 has also chosen, complete the round
        if len(self.choices) == 2:
            await self.round_complete()
        else:
            await self.update_embed() # Update to show bot has chosen

    async def update_embed(self, status_override: str | None = None):
        """Updates the game embed with the current state."""
        if not self.message:
            return  # Message not sent yet

        self.embed.clear_fields()
        
        # --- Scores Field ---
        score_text = (
            f"**{self.player1.display_name}**: {self.scores[self.player1.id]}\n"
            f"**{self.player2.display_name}**: {self.scores[self.player2.id]}"
        )
        self.embed.add_field(
            name=f"🏆 Scores (First to {GAME_WIN_SCORE})",
            value=score_text,
            inline=True
        )

        # --- Selections Field ---
        picks = []
        for m in (self.player1, self.player2):
            mark = "✅" if m.id in self.choices else "⏳"
            picks.append(f"{m.mention}: {mark}")
        self.embed.add_field(
            name="📝 Picks",
            value="\n".join(picks),
            inline=True
        )

        # --- Last Round Field ---
        self.embed.add_field(
            name="📜 Last Round",
            value=self.last_round_summary,
            inline=False
        )

        # --- Status Footer ---
        if status_override:
            self.embed.set_footer(text=status_override)
        else:
            waiting = [m.mention for m in (self.player1, self.player2) if m.id not in self.choices]
            if waiting:
                self.embed.set_footer(text=f"Waiting on {', '.join(waiting)} to make a move...")
            else:
                self.embed.set_footer(text="Both players have chosen. Resolving round...")
        
        try:
            await self.message.edit(embed=self.embed, view=self)
        except discord.NotFound:
            self.stop() # Stop view if message was deleted

    def decide_winner(self) -> discord.Member | None:
        """Determines the winner of the round based on choices."""
        a = self.choices[self.player1.id]
        b = self.choices[self.player2.id]
        outcome = (a - b) % 3
        if outcome == 1:
            return self.player1
        if outcome == 2:
            return self.player2
        return None # Draw

    def check_champion(self) -> discord.Member | None:
        """Checks if either player has reached the winning score."""
        if self.scores[self.player1.id] >= GAME_WIN_SCORE:
            return self.player1
        if self.scores[self.player2.id] >= GAME_WIN_SCORE:
            return self.player2
        return None

    async def round_complete(self):
        """Processes the round, updates scores, and checks for a winner."""
        p1_name, p1_emoji = CHOICES_MAP[self.choices[self.player1.id]]
        p2_name, p2_emoji = CHOICES_MAP[self.choices[self.player2.id]]
        winner = self.decide_winner()

        # Prepare last-round summary
        if winner:
            self.scores[winner.id] += 1
            result_text = f"➜ **{winner.display_name} wins the round!**"
        else:
            result_text = "➜ **It's a draw!**"

        self.last_round_summary = (
            f"{self.player1.display_name} ({p1_emoji}) vs {self.player2.display_name} ({p2_emoji})\n{result_text}"
        )

        # Clear choices for next round
        self.choices.clear()

        # Check for a game champion
        champ = self.check_champion()
        if champ:
            await self.end_game(champ)
        else:
            # Continue to next round, update embed
            await self.update_embed()
            # If bot is playing, make its next move
            if self.player2.bot:
                await asyncio.sleep(1) # Short delay for effect
                await self.make_bot_choice()

    async def end_game(self, champ: discord.Member):
        """Finalizes the game, declares a winner, and stops the view."""
        # Record win in leaderboard
        cog: RockPaperScissors = self.ctx.bot.get_cog("RockPaperScissors")
        if cog:
            cog.record_win(champ.id)

        # Disable buttons
        for btn in self.children:
            btn.disabled = True
        
        # Create final embed
        self.embed.title = f"🎉 {champ.display_name} wins the game! 🎉"
        self.embed.description = f"**Final Score:** {self.scores[self.player1.id]} – {self.scores[self.player2.id]}"
        self.embed.clear_fields()
        self.embed.add_field(name="📜 Final Round", value=self.last_round_summary, inline=False)
        self.embed.set_footer(text="Game Over!")
        self.embed.color = discord.Color.gold()
        
        if self.message:
            await self.message.edit(embed=self.embed, view=self)
        self.stop()

    async def handle_choice(self, interaction: discord.Interaction, choice: int):
        """Handles a player clicking a button."""
        user = interaction.user
        
        # --- Interaction Checks ---
        if user.id not in (self.player1.id, self.player2.id):
            await interaction.response.send_message("You are not part of this game.", ephemeral=True)
            return
        
        async with self._lock:
            if user.id in self.choices:
                await interaction.response.send_message("You have already chosen for this round.", ephemeral=True)
                return
            
            # Defer response first to avoid "interaction failed"
            await interaction.response.defer(ephemeral=True)
            
            # Record choice
            self.choices[user.id] = choice
            choice_name, choice_emoji = CHOICES_MAP[choice]
            await interaction.followup.send(f"You selected **{choice_name}** {choice_emoji}.", ephemeral=True)
        
        # --- Game Logic ---
        if len(self.choices) == 2:
            # Both players have chosen
            await self.round_complete()
        else:
            # One player has chosen, update embed
            await self.update_embed()

    @ui.button(label="Rock", style=ButtonStyle.primary, emoji="🪨")
    async def rock(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_choice(interaction, 0)

    @ui.button(label="Paper", style=ButtonStyle.success, emoji="📄")
    async def paper(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_choice(interaction, 1)

    @ui.button(label="Scissors", style=ButtonStyle.danger, emoji="✂️")
    async def scissors(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_choice(interaction, 2)

    async def on_timeout(self):
        """Handles the game timing out due to inactivity."""
        # Disable buttons
        for btn in self.children:
            btn.disabled = True
        
        self.embed.title += " (Timed Out ⌛)"
        self.embed.description = "Game ended due to inactivity."
        self.embed.color = discord.Color.dark_grey()
        self.embed.set_footer(text="Game Over!")
        
        if self.message:
            await self.message.edit(embed=self.embed, view=self)
        self.stop()

# --- Challenge View ---

class RPSChallengeView(ui.View):
    """
    Manages the invitation for an RPS game.
    """
    def __init__(self, player1: discord.Member, player2: discord.Member, ctx: commands.Context, embed: discord.Embed, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.player1 = player1
        self.player2 = player2
        self.ctx = ctx
        self.embed = embed
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Checks if the user interacting is the challenged player."""
        if interaction.user.id == self.player2.id:
            return True
        elif interaction.user.id == self.player1.id:
            await interaction.response.send_message("You are the one who sent the challenge!", ephemeral=True)
            return False
        else:
            await interaction.response.send_message("This challenge is not for you.", ephemeral=True)
            return False

    @ui.button(label="Accept", style=ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: ui.Button):
        """Called when the challenged player accepts."""
        # Disable buttons on this view
        for btn in self.children:
            btn.disabled = True
        
        # Update challenge message
        self.embed.title = "⚔️ Challenge Accepted! ⚔️"
        self.embed.description = f"{self.player2.display_name} accepted the challenge!"
        self.embed.set_footer(text="Starting game...")
        await interaction.response.edit_message(embed=self.embed, view=self)

        # Create and start the actual game
        game_embed = discord.Embed(
            title=f"RPS: {self.player1.display_name} vs {self.player2.display_name}",
            color=EMBED_COLOR
        )
        game_view = RPSGameView(self.player1, self.player2, game_embed, self.ctx)
        await game_view.start_game()
        
        self.stop()

    @ui.button(label="Decline", style=ButtonStyle.danger, emoji="✖️")
    async def decline(self, interaction: discord.Interaction, button: ui.Button):
        """Called when the challenged player declines."""
        # Disable buttons
        for btn in self.children:
            btn.disabled = True
            
        self.embed.title = "Challenge Declined"
        self.embed.description = f"{self.player2.display_name} declined the challenge."
        self.embed.color = discord.Color.red()
        self.embed.set_footer(text="Maybe next time.")
        
        await interaction.response.edit_message(content=f"{self.player1.mention}", embed=self.embed, view=self)
        self.stop()

    async def on_timeout(self):
        """Handles the challenge timing out."""
        # Disable buttons
        for btn in self.children:
            btn.disabled = True
            
        self.embed.title = "Challenge Expired"
        self.embed.description = f"{self.player2.mention} did not respond in time."
        self.embed.color = discord.Color.dark_grey()
        self.embed.set_footer(text="Challenge timed out.")

        if self.message:
            await self.message.edit(embed=self.embed, view=self)
        self.stop()

# --- Cog ---

class RockPaperScissors(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.leaderboard = load_leaderboard()

    def record_win(self, user_id: int):
        """Records a win in the leaderboard and saves to file."""
        key = str(user_id)
        self.leaderboard[key] = self.leaderboard.get(key, 0) + 1
        save_leaderboard(self.leaderboard)

    @commands.command(name="rps")
    @commands.guild_only()
    async def rps(self, ctx: commands.Context, opponent: discord.Member = None):
        """
        Challenge a member (or the bot) to Rock-Paper-Scissors!
        
        Usage:
        - `rps`: Play against the bot.
        - `rps @member`: Challenge another user to a game.
        """
        player1 = ctx.author
        player2 = opponent or ctx.guild.me
        
        # --- Pre-game checks ---
        if player1 == player2:
            await ctx.send("You can't play against yourself, silly.")
            return
            
        if player2.bot and player2 != ctx.guild.me:
            await ctx.send(f"You can't play against {player2.display_name}. You can only play against me or other humans.")
            return

        # --- Start Game ---
        if player2 == ctx.guild.me:
            # Playing against the bot
            embed = discord.Embed(
                title=f"RPS: {player1.display_name} vs {player2.display_name}",
                description="The game has begun! Make your choice.",
                color=EMBED_COLOR
            )
            view = RPSGameView(player1, player2, embed, ctx)
            await view.start_game()
        else:
            # Challenging another player
            embed = discord.Embed(
                title="⚔️ RPS Challenge! ⚔️",
                description=f"{player1.mention} has challenged {player2.mention} to a game of Rock-Paper-Scissors!",
                color=EMBED_COLOR
            )
            embed.set_footer(text=f"{player2.display_name} has 60 seconds to accept.")
            
            view = RPSChallengeView(player1, player2, ctx, embed)
            
            # Ping both players
            message = await ctx.send(content=f"{player1.mention} {player2.mention}", embed=embed, view=view)
            view.message = message

    @commands.command(name="rpslb")
    @commands.guild_only()
    async def rpslb(self, ctx: commands.Context):
        """Displays the Rock-Paper-Scissors leaderboard."""
        if not self.leaderboard:
            await ctx.send("No RPS games have been recorded yet.")
            return

        # Sort leaderboard
        top_players = sorted(self.leaderboard.items(), key=lambda item: item[1], reverse=True)[:20]

        lb_lines = []
        emoji_map = {0: "🥇", 1: "🥈", 2: "🥉"}

        for i, (user_id, wins) in enumerate(top_players):
            # Try to fetch user, fallback to ID
            user = self.bot.get_user(int(user_id))
            if not user:
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    user_name = user.display_name
                except discord.NotFound:
                    user_name = f"Unknown User ({user_id})"
            else:
                user_name = user.display_name
            
            prefix = emoji_map.get(i, f"**{i+1}.**")
            win_str = "win" if wins == 1 else "wins"
            lb_lines.append(f"{prefix} {user_name} — **{wins}** {win_str}")

        embed = discord.Embed(
            title="🏆 RPS Leaderboard (Top 20)",
            description="\n".join(lb_lines),
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RockPaperScissors(bot))