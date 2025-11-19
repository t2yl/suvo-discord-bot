import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import ButtonStyle
import random
import json
import os
from uuid import uuid4

# --- LEADERBOARD FUNCTIONS (Unchanged) ---
LEADERBOARD_FILE = "leaderboard_ttt.json"

def load_leaderboard():
    if os.path.isfile(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_leaderboard(data):
    tmp = LEADERBOARD_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp, LEADERBOARD_FILE)


# --- Challenge View (Unchanged) ---
class TicTacToeChallengeView(View):
    """A view to handle 1v1 challenges."""
    def __init__(self, challenger: discord.Member, opponent: discord.Member, bot: commands.Bot):
        super().__init__(timeout=60.0) # 60 seconds to accept
        self.challenger = challenger
        self.opponent = opponent
        self.bot = bot
        self.message: discord.Message | None = None

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(
            description=f"{self.challenger.mention}'s challenge to {self.opponent.mention} expired. ⌛",
            color=discord.Color.orange()
        )
        if self.message:
            await self.message.edit(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Accept", style=ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.opponent:
            await interaction.response.send_message("You are not the one challenged!", ephemeral=True)
            return
        
        self.stop()
        
        view = TicTacToeView(self.challenger, self.opponent, self.bot)
        desc, color = view.get_game_status()
        embed = discord.Embed(title=view.title, description=desc, color=color)
        
        await interaction.response.edit_message(content="", embed=embed, view=view)
        view.message = interaction.message

    @discord.ui.button(label="Decline", style=ButtonStyle.danger, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: Button):
        if interaction.user not in (self.challenger, self.opponent):
            await interaction.response.send_message("You are not part of this challenge!", ephemeral=True)
            return
        
        self.stop()
        for item in self.children:
            item.disabled = True
        
        if interaction.user == self.challenger:
            desc = f"{self.challenger.mention} cancelled the challenge."
        else:
            desc = f"{self.opponent.mention} declined the challenge from {self.challenger.mention}."

        embed = discord.Embed(description=desc, color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=self)


# --- UPDATED: Game View (bot_move is changed) ---
class TicTacToeView(View):
    def __init__(self, player1: discord.Member, player2: discord.Member, bot: commands.Bot):
        super().__init__(timeout=180.0)
        self.player1 = player1
        self.player2 = player2
        self.bot_user = bot.user
        self.is_vs_bot = player2.bot and player2 == bot.user

        self.board: list[list[discord.Member | None]] = [[None]*3 for _ in range(3)]
        self.moves = 0
        self.game_id = uuid4().hex
        self.title = f"Tic Tac Toe: {player1.display_name} vs {player2.display_name}"

        if self.is_vs_bot:
            self.current_player = random.choice([player1, player2])
        else:
            self.current_player = player1

        for row in range(3):
            for col in range(3):
                self.add_item(TicTacToeButton(row, col, self.game_id))

        self.message: discord.Message | None = None

    def get_game_status(self) -> tuple[str, discord.Color]:
        """Returns the description and color for the current game state."""
        winner = self.check_winner()
        if winner:
            return f"{winner.mention} wins! 🎉", discord.Color.green()
        if self.moves >= 9:
            return "It's a draw! 🤝", discord.Color.gold()
        
        is_player1_turn = self.current_player == self.player1
        current_player_name = self.player1.mention if is_player1_turn else self.player2.mention
        symbol = "❌" if is_player1_turn else "⭕"
        color = discord.Color.red() if is_player1_turn else discord.Color.blue()
        
        return f"{current_player_name}'s turn ({symbol})", color

    async def update_message(self, interaction: discord.Interaction | None = None):
        """Edits the message to reflect the current game state."""
        desc, color = self.get_game_status()
        embed = discord.Embed(title=self.title, description=desc, color=color)
        
        winner = self.check_winner()
        if winner or self.moves >= 9:
            self.disable_all()
            self.stop()
            
            if winner:
                data = load_leaderboard()
                uid = str(winner.id)
                data[uid] = data.get(uid, 0) + 1
                save_leaderboard(data)

        if interaction:
            await interaction.edit_original_response(embed=embed, view=self)
        elif self.message:
            await self.message.edit(embed=embed, view=self)

    async def on_timeout(self):
        self.disable_all()
        embed = discord.Embed(
            title=self.title, 
            description="Game ended due to inactivity. ⌛",
            color=discord.Color.orange()
        )
        if self.message:
            await self.message.edit(embed=embed, view=self)

    def check_winner(self) -> discord.Member | None:
        lines = [
            [(0,0),(0,1),(0,2)], [(1,0),(1,1),(1,2)], [(2,0),(2,1),(2,2)],
            [(0,0),(1,0),(2,0)], [(0,1),(1,1),(2,1)], [(0,2),(1,2),(2,2)],
            [(0,0),(1,1),(2,2)], [(0,2),(1,1),(2,0)],
        ]
        for (a,b,c) in lines:
            if self.board[a[0]][a[1]] and \
               self.board[a[0]][a[1]] == self.board[b[0]][b[1]] == self.board[c[0]][c[1]]:
                return self.board[a[0]][a[1]]
        return None

    def disable_all(self):
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True

    # --- MINIMAX LOGIC (Unchanged) ---
    def evaluate(self) -> int:
        winner = self.check_winner()
        if winner == self.player2: return +1
        if winner == self.player1: return -1
        return 0

    def minimax(self, is_maximizing: bool, alpha: float = -float('inf'), beta: float = float('inf')) -> int:
        score = self.evaluate()
        if score != 0 or self.moves >= 9:
            return score

        if is_maximizing:
            max_eval = -float('inf')
            for r in range(3):
                for c in range(3):
                    if self.board[r][c] is None:
                        self.board[r][c] = self.player2
                        self.moves += 1
                        eval_score = self.minimax(False, alpha, beta)
                        self.board[r][c] = None
                        self.moves -= 1
                        max_eval = max(max_eval, eval_score)
                        alpha = max(alpha, eval_score)
                        if beta <= alpha or max_eval == 1:
                            return max_eval
            return max_eval
        else:
            min_eval = float('inf')
            for r in range(3):
                for c in range(3):
                    if self.board[r][c] is None:
                        self.board[r][c] = self.player1
                        self.moves += 1
                        eval_score = self.minimax(True, alpha, beta)
                        self.board[r][c] = None
                        self.moves -= 1
                        min_eval = min(min_eval, eval_score)
                        beta = min(beta, eval_score)
                        if beta <= alpha or min_eval == -1:
                            return min_eval
            return min_eval

    # --- UPDATED: bot_move ---
    async def bot_move(self):
        # Find all available moves
        available_moves = []
        for r in range(3):
            for c in range(3):
                if self.board[r][c] is None:
                    available_moves.append((r, c))
        
        if not available_moves:
            return # No moves left

        final_move = None
        MISTAKE_CHANCE = 0.30 # 30% chance to make a "mistake" (a random move)

        # Decide whether to make a perfect move or a random "human" error
        if random.random() < MISTAKE_CHANCE:
            # "Human" error: pick a random available spot
            final_move = random.choice(available_moves)
        else:
            # "Perfect" move: use Minimax
            best_score = -float('inf')
            best_move = None
            
            # Iterate through available moves to find the best one
            for r, c in available_moves:
                self.board[r][c] = self.player2
                self.moves += 1
                score = self.minimax(False)
                self.board[r][c] = None
                self.moves -= 1
                
                if score > best_score:
                    best_score = score
                    best_move = (r, c)
                    if best_score == 1: # Found a winning move, no need to search more
                        break
            
            final_move = best_move
        
        # Apply the chosen move (whether random or perfect)
        if final_move:
            r, c = final_move
            for item in self.children:
                if isinstance(item, TicTacToeButton) and (item.row, item.col) == (r, c):
                    item.style = ButtonStyle.primary
                    item.label = "⭕"
                    item.disabled = True
                    break
            
            self.board[r][c] = self.player2
            self.moves += 1
        
        # Check for winner and update state
        winner = self.check_winner()
        if not winner and self.moves < 9:
            self.current_player = self.player1
        
        await self.update_message()


# --- UPDATED: Button Class (Unchanged from your version) ---
class TicTacToeButton(Button):
    def __init__(self, row: int, col: int, game_id: str):
        super().__init__(
            style=ButtonStyle.secondary,
            label="\u200b",
            row=row,
            custom_id=f"ttt_{game_id}_{row}_{col}"
        )
        self.row = row
        self.col = col

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view # type: ignore
        user = interaction.user

        if user not in (view.player1, view.player2):
            return await interaction.response.send_message("You're not part of this game!", ephemeral=True)
        if user != view.current_player:
            return await interaction.response.send_message("It's not your turn!", ephemeral=True)

        await interaction.response.defer()

        # Apply human move
        if view.current_player == view.player1:
            self.style = ButtonStyle.danger
            self.label = "❌"
        else:
            self.style = ButtonStyle.primary
            self.label = "⭕"
        self.disabled = True
        view.board[self.row][self.col] = view.current_player
        view.moves += 1

        winner = view.check_winner()
        if winner or view.moves >= 9:
            await view.update_message(interaction)
            return

        if view.is_vs_bot:
            view.current_player = view.player2
            desc, color = view.get_game_status()
            embed = discord.Embed(title=view.title, description=desc, color=color)
            
            await interaction.edit_original_response(embed=embed, view=view)
            
            # Call bot_move *after* updating the message to show "Bot's turn"
            await view.bot_move()
        else:
            view.current_player = view.player2 if view.current_player == view.player1 else view.player1
            await view.update_message(interaction)


# --- Cog Class (Unchanged) ---
class TicTacToe(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="ttt")
    async def start_ttt(self, ctx: commands.Context, opponent: discord.Member = None):
        """Start a 1v1 Tic Tac Toe game. If no opponent is given, play against the bot."""
        if opponent is None:
            opponent = self.bot.user
        
        if opponent == ctx.author:
            return await ctx.send("You can't play against yourself! 😅")
        
        if opponent.bot and opponent != self.bot.user:
             return await ctx.send("You can only play against me, not other bots. 🤖")

        if opponent == self.bot.user:
            view = TicTacToeView(ctx.author, opponent, self.bot)
            desc, color = view.get_game_status()
            embed = discord.Embed(title=view.title, description=desc, color=color)
            content = f"{ctx.author.mention} vs {opponent.mention}"
            view.message = await ctx.send(content=content, embed=embed, view=view)

            if view.is_vs_bot and view.current_player == opponent:
                await view.bot_move()
        
        else:
            view = TicTacToeChallengeView(ctx.author, opponent, self.bot)
            embed = discord.Embed(
                title="⚔️ Tic Tac Toe Challenge! ⚔️",
                description=f"{opponent.mention}, {ctx.author.mention} has challenged you to a game!\n"
                            f"You have 60 seconds to accept.",
                color=discord.Color.blurple()
            )
            content = f"{ctx.author.mention} {opponent.mention}"
            view.message = await ctx.send(content=content, embed=embed, view=view)

    @commands.command(name="tttlb")
    async def ttt_leaderboard(self, ctx: commands.Context):
        """Show top 20 players by Tic Tac Toe wins."""
        data = load_leaderboard()
        if not data:
            return await ctx.send("No games recorded yet.")
        
        sorted_players = sorted(data.items(), key=lambda kv: kv[1], reverse=True)[:20]
        
        embed = discord.Embed(
            title="🏆 Tic Tac Toe Leaderboard 🏆", 
            color=discord.Color.gold()
        )
        
        desc_lines = []
        for i, (uid, wins) in enumerate(sorted_players, start=1):
            user = self.bot.get_user(int(uid))
            if not user:
                try:
                    user = await self.bot.fetch_user(int(uid))
                except discord.NotFound:
                    pass

            name = user.display_name if user else f"Unknown User ({uid})"
            
            if i == 1: emoji = "🥇"
            elif i == 2: emoji = "🥈"
            elif i == 3: emoji = "🥉"
            else: emoji = f"**{i}.**"
            
            win_str = "win" if wins == 1 else "wins"
            desc_lines.append(f"{emoji} **{name}** - {wins} {win_str}")
        
        embed.description = "\n".join(desc_lines)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicTacToe(bot))