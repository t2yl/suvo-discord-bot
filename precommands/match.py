import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import asyncio
import time
import json
import os

# --- Constants ---
QUESTIONS_PER_GAME = 5
WORDS_FILE = 'words_game.json'
NUMBERS_FILE = 'num_wmg.json'
FOOD_FILE = 'food_wmg.json'
LEADERBOARD_FILE = 'leaderboard.json'
GAME_TIMEOUT = 60.0  # seconds

# --- Helper Function ---

def get_term(d: dict):
    """Safely get the definition, translation, or meaning from a word entry."""
    if not isinstance(d, dict):
        return None
    for key in ('definition', 'translation', 'meaning'):
        if key in d:
            return d[key]
    # Return None if no valid key is found, preventing crashes
    return None

# --- UI Views ---

class TimeoutView(View):
    """
    A View subclass that automatically cancels the game on timeout and
    updates the embed to reflect the timed-out state.
    """
    def __init__(self, session, timeout: float = GAME_TIMEOUT):
        super().__init__(timeout=timeout)
        self.session = session

    async def on_timeout(self):
        if not self.session.is_active:
            return  # Game already ended or cancelled

        self.session.is_active = False
        self.session.leaderboard['active_games'].pop(self.session.channel.id, None)

        # Disable all buttons
        for child in self.children:
            child.disabled = True

        # Create a new embed to show the game timed out
        timeout_embed = discord.Embed(
            title="⏰ Game Timed Out",
            description=f"The game started by {self.session.player.mention} was cancelled due to inactivity.",
            color=discord.Color.orange()
        )

        # Edit the original game message
        if self.session.message:
            try:
                await self.session.message.edit(embed=timeout_embed, view=self)
            except discord.NotFound:
                pass  # Message might have been deleted

class CategorySelectView(View):
    """
    A View that presents buttons for the user to select a game category.
    This is shown by the main !startwmg command.
    """
    def __init__(self, cog, author):
        super().__init__(timeout=60.0)  # Short timeout for category selection
        self.cog = cog
        self.author = author
        self.selection_made = False

    async def handle_selection(self, interaction: discord.Interaction, category_key: str, category_name: str):
        """Shared logic for handling a button press."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This is not your game selection!", ephemeral=True)
            return

        self.selection_made = True
        
        # Disable all buttons
        for child in self.children:
            child.disabled = True
        
        # Update the message to show the selection
        await interaction.response.edit_message(
            content=f"Starting a **{category_name}** game for {self.author.mention}...",
            embed=None, 
            view=self
        )
        
        # Start the actual game session
        await self.cog._start_game_session(interaction, category_key)

    @discord.ui.button(label="Animal", style=discord.ButtonStyle.primary, emoji="🐼")
    async def animal_button(self, interaction: discord.Interaction, button: Button):
        await self.handle_selection(interaction, 'animal', 'Animal')

    @discord.ui.button(label="Number", style=discord.ButtonStyle.primary, emoji="🔢")
    async def number_button(self, interaction: discord.Interaction, button: Button):
        await self.handle_selection(interaction, 'number', 'Number')

    @discord.ui.button(label="Food", style=discord.ButtonStyle.primary, emoji="🍔")
    async def food_button(self, interaction: discord.Interaction, button: Button):
        await self.handle_selection(interaction, 'food', 'Food')

    @discord.ui.button(label="Random", style=discord.ButtonStyle.secondary, emoji="🎲")
    async def random_button(self, interaction: discord.Interaction, button: Button):
        category_key = random.choice(['animal', 'number', 'food'])
        await self.handle_selection(interaction, category_key, f"Random ({category_key.capitalize()})")

    async def on_timeout(self):
        if self.selection_made:
            return  # Selection was made, no need to time out

        # Disable all buttons
        for child in self.children:
            child.disabled = True
        
        # Edit the original message to show it expired
        if self.message:
            try:
                await self.message.edit(
                    content="Game selection expired.", 
                    embed=None, 
                    view=self
                )
            except discord.NotFound:
                pass

# --- Game Logic Class ---

class GameSession:
    def __init__(self, channel, player, words, leaderboard, save_leaderboard, category):
        self.channel = channel
        self.player = player
        self.words = words
        self.leaderboard = leaderboard
        self.save_leaderboard = save_leaderboard
        self.category = category.capitalize()

        self.questions_asked = 0
        self.total_reaction_time = 0.0
        self.current_word_data = None
        self.correct_index = -1
        self.start_time = None
        self.is_active = True
        self.message = None  # This will store the single game message we edit
        self.asked_words = set()

    async def start_game(self):
        """Sends the intro message and the first question."""
        embed = discord.Embed(
            title=f"🎉 {self.category} Match Game Starting!",
            description=f"Hey {self.player.mention}! Get ready for {QUESTIONS_PER_GAME} questions.",
            color=discord.Color.blue()
        )
        await self.channel.send(embed=embed)
        await asyncio.sleep(1.5)
        await self.next_question()

    async def next_question(self):
        """Prepares and sends/edits the message for the next question."""
        if self.questions_asked >= QUESTIONS_PER_GAME:
            return await self.end_game()

        self.questions_asked += 1

        # --- Word Selection ---
        available = [
            w for w in self.words
            if (w.get('word') or w.get('korean')) not in self.asked_words
            and get_term(w) is not None  # Ensure the word has a valid term
        ]
        
        if not available:
            # All words asked, or no valid words left. Reset asked_words.
            available = [w for w in self.words if get_term(w) is not None]
            if not available:
                # This should not happen if file loading is correct
                await self.channel.send("Error: No valid words found in the category.")
                return await self.cancel_game_internal()
            self.asked_words.clear()

        self.current_word_data = random.choice(available)
        word_key = self.current_word_data.get('word') or self.current_word_data.get('korean')
        self.asked_words.add(word_key)
        
        correct_term = get_term(self.current_word_data)

        # --- Option Generation ---
        others = list({
            get_term(w)
            for w in self.words
            if get_term(w) is not None and get_term(w) != correct_term
        })
        
        # Ensure we have enough wrong options
        if len(others) < 3:
            # Fallback: just use any other terms, even if they're simple
            others.extend(["Wrong Answer 1", "Wrong Answer 2", "Wrong Answer 3"])
            
        random.shuffle(others)
        wrongs = others[:3]

        options = [correct_term] + wrongs
        random.shuffle(options)
        self.correct_index = options.index(correct_term)

        # --- View and Embed Creation ---
        view = TimeoutView(self, timeout=GAME_TIMEOUT)
        
        for idx, label in enumerate(options):
            btn = Button(
                label=str(label)[:80],  # Button labels have an 80-char limit
                custom_id=f"match_{self.channel.id}_{idx}",
                style=discord.ButtonStyle.primary
            )
            
            # Use a wrapper to correctly capture loop variables
            btn.callback = self.create_callback(idx, view)
            view.add_item(btn)

        word_to_guess = self.current_word_data.get('word') or self.current_word_data.get('korean') or "<Error: Unknown Word>"
        
        embed = discord.Embed(
            title=f"{self.category} Match: Question {self.questions_asked}/{QUESTIONS_PER_GAME}",
            description=f"What is the meaning of:\n\n# {word_to_guess}",
            color=discord.Color.default()
        )
        embed.set_footer(text="Select the correct option below.")

        # --- Send or Edit Message ---
        self.start_time = time.time()
        
        if self.message is None:
            # First question, send new message
            self.message = await self.channel.send(embed=embed, view=view)
        else:
            # Subsequent questions, edit existing message
            try:
                await self.message.edit(embed=embed, view=view)
            except discord.NotFound:
                # User might have deleted the message, send a new one
                self.message = await self.channel.send(embed=embed, view=view)

    def create_callback(self, idx, view):
        """Factory function to create a button callback with the correct scope."""
        async def button_callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.id:
                return await interaction.response.send_message("This is not your game!", ephemeral=True)
            if not self.is_active:
                return await interaction.response.send_message("The game is over.", ephemeral=True)

            # --- Correct Answer ---
            if idx == self.correct_index:
                rt = round(time.time() - self.start_time, 2)
                self.total_reaction_time += rt
                view.stop()  # Stop the timeout

                # Style buttons for feedback
                for i, child in enumerate(view.children):
                    child.disabled = True
                    if i == self.correct_index:
                        child.style = discord.ButtonStyle.success
                    else:
                        child.style = discord.ButtonStyle.danger

                word_to_guess = self.current_word_data.get('word') or self.current_word_data.get('korean')
                correct_answer = get_term(self.current_word_data)
                
                embed = discord.Embed(
                    title=f"✅ Question {self.questions_asked} Correct!",
                    description=f"**{word_to_guess}** means **{correct_answer}**.",
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"Answered in {rt:.2f}s. Loading next question...")
                
                await interaction.response.edit_message(embed=embed, view=view)
                await asyncio.sleep(1.5)  # Pause to let user read feedback
                await self.next_question()

            # --- Wrong Answer ---
            else:
                # Find the button that was clicked and disable it
                for child in view.children:
                    if child.custom_id == f"match_{self.channel.id}_{idx}":
                        child.disabled = True
                        child.style = discord.ButtonStyle.danger
                
                # Edit the message to show the disabled button
                await interaction.message.edit(view=view)
                await interaction.response.send_message("❌ Wrong! Try again.", ephemeral=True)
        
        return button_callback

    async def end_game(self):
        """Ends the game, calculates score, and updates leaderboard."""
        self.is_active = False
        self.leaderboard['active_games'].pop(self.channel.id, None)

        final_time = round(self.total_reaction_time, 2)
        
        # Create final embed
        embed = discord.Embed(
            title="🎉 Game Over! 🎉",
            description=f"**Congratulations {self.player.mention}!**",
            color=discord.Color.gold()
        )
        embed.add_field(name="Category", value=self.category, inline=True)
        embed.add_field(name="Total Time", value=f"{final_time:.2f}s", inline=True)

        # Update leaderboard
        uid = str(self.player.id)
        category_key = self.category.lower()
        best_time = self.leaderboard['data'][category_key].get(uid)
        
        if best_time is None or final_time < best_time:
            self.leaderboard['data'][category_key][uid] = final_time
            self.save_leaderboard()
            embed.set_footer(text="✨ New Personal Best! ✨")
        else:
            embed.set_footer(text=f"Your best is {best_time:.2f}s")
        
        # Edit the game message for the last time
        if self.message:
            try:
                await self.message.edit(embed=embed, view=None)  # Remove all buttons
            except discord.NotFound:
                # If message was deleted, send the final embed as a new message
                await self.channel.send(embed=embed)
        else:
            await self.channel.send(embed=embed)

    async def cancel_game_internal(self):
        """Internal method to stop a game, e.g., on error."""
        self.is_active = False
        self.leaderboard['active_games'].pop(self.channel.id, None)
        if self.message and getattr(self.message, 'view', None):
            for child in self.message.view.children:
                child.disabled = True
            try:
                await self.message.edit(view=self.message.view)
            except discord.NotFound:
                pass

# --- Main Cog Class ---

class MatchGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # active_games is now stored in the leaderboard dict
        self.leaderboard = {
            'data': {
                'animal': {},
                'number': {},
                'food': {}
            },
            'active_games': {}  # Stores {channel_id: GameSession}
        }
        self.words_animal = []
        self.words_number = []
        self.words_food = []
        self.load_all_data()

    def load_all_data(self):
        """Loads all word and leaderboard data from JSON files."""
        self.words_animal = self._load_word_file(WORDS_FILE)
        self.words_number = self._load_word_file(NUMBERS_FILE)
        self.words_food = self._load_word_file(FOOD_FILE)
        self.load_leaderboard()
        print("MatchGame data loaded.")

    def _load_word_file(self, file_path):
        """Helper to load a single word JSON file safely."""
        if not os.path.exists(file_path):
            print(f"Warning: Word file not found: {file_path}")
            return []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    # Filter out any bad entries now
                    valid_data = [d for d in data if get_term(d) is not None]
                    if len(valid_data) < len(data):
                        print(f"Warning: Filtered {len(data) - len(valid_data)} bad entries from {file_path}")
                    return valid_data
                else:
                    print(f"Error: Word file {file_path} is not a JSON list.")
                    return []
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {file_path}")
            return []
        except Exception as e:
            print(f"An unexpected error occurred loading {file_path}: {e}")
            return []

    def load_leaderboard(self):
        """Loads leaderboard data, ensuring all categories exist."""
        default_data = {'animal': {}, 'number': {}, 'food': {}}
        if os.path.exists(LEADERBOARD_FILE):
            try:
                with open(LEADERBOARD_FILE, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    if isinstance(loaded_data, dict):
                        # Merge loaded data into default, ensuring all keys exist
                        for key in default_data:
                            if key in loaded_data and isinstance(loaded_data[key], dict):
                                default_data[key].update(loaded_data[key])
            except (json.JSONDecodeError, IOError):
                pass  # On error, just use the default structure
        self.leaderboard['data'] = default_data

    def save_leaderboard(self):
        """Saves only the 'data' part of the leaderboard."""
        try:
            with open(LEADERBOARD_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.leaderboard['data'], f, indent=4)
        except IOError as e:
            print(f"Error saving leaderboard: {e}")

    async def _start_game_session(self, interaction: discord.Interaction, category_key: str):
        """Internal function to create and start a game session."""
        
        word_map = {
            'animal': self.words_animal,
            'number': self.words_number,
            'food': self.words_food
        }
        words = word_map.get(category_key)
        
        # Check for minimum number of words
        if len(words) < 4:  # Need at least 1 correct + 3 wrong
            await interaction.followup.send(
                f"Sorry, the **{category_key.capitalize()}** category doesn't have enough words to play (requires at least 4).", 
                ephemeral=True
            )
            return

        session = GameSession(
            interaction.channel,
            interaction.user,
            words,
            self.leaderboard,
            self.save_leaderboard,
            category_key
        )
        self.leaderboard['active_games'][interaction.channel.id] = session
        await session.start_game()

    @commands.command(name='startwmg')
    async def startmatch(self, ctx):
        """Starts a Word Match Game by showing a category selection."""
        if ctx.channel.id in self.leaderboard['active_games']:
            return await ctx.send(
                "A game is already active in this channel!",
                delete_after=10
            )

        embed = discord.Embed(
            title="Start a New Word Match Game",
            description=f"{ctx.author.mention}, please select a category to begin:",
            color=discord.Color.dark_green()
        )
        view = CategorySelectView(self, ctx.author)
        view.message = await ctx.send(embed=embed, view=view)

    @commands.command(name='wmglb')
    async def leaderboard_cmd(self, ctx, category: str = None):
        """Shows the Word Match Game leaderboard in a single embed."""
        
        categories_to_show = []
        if category:
            cat = category.lower()
            if cat in ('num', 'number'):
                categories_to_show = [('number', 'Number 🔢')]
            elif cat == 'animal':
                categories_to_show = [('animal', 'Animal 🐼')]
            elif cat == 'food':
                categories_to_show = [('food', 'Food 🍔')]
            else:
                return await ctx.send("Invalid category. Use 'number', 'animal', 'food', or leave blank for all.", delete_after=10)
        else:
            categories_to_show = [
                ('animal', 'Animal 🐼'),
                ('number', 'Number 🔢'),
                ('food', 'Food 🍔')
            ]

        embed = discord.Embed(
            title="🏆 Word Match Leaderboard 🏆",
            color=discord.Color.purple()
        )

        if not any(self.leaderboard['data'].get(key) for key, _ in categories_to_show):
             embed.description = "No one has played yet. Be the first!"
             return await ctx.send(embed=embed)

        for key, title in categories_to_show:
            data = self.leaderboard['data'].get(key, {})
            if not data:
                field_value = "No winners yet."
            else:
                sorted_lb = sorted(data.items(), key=lambda x: x[1])
                lines = []
                for i, (uid, time_) in enumerate(sorted_lb[:10], start=1):
                    try:
                        user = await self.bot.fetch_user(int(uid))
                        name = user.display_name
                    except discord.NotFound:
                        name = "Unknown User"
                    
                    emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
                    lines.append(f"{emoji} {name}: {time_:.2f}s")
                field_value = "\n".join(lines)
            
            embed.add_field(name=f"**{title}**", value=field_value, inline=False)
            
        await ctx.send(embed=embed)

    @commands.command(name='cancelgame')
    async def cancelgame(self, ctx):
        """Cancels the active game in the channel."""
        session = self.leaderboard['active_games'].get(ctx.channel.id)
        if not session or not session.is_active:
            return await ctx.send("No active game to cancel.", delete_after=10)
        
        if ctx.author.id != session.player.id:
            return await ctx.send("Only the game starter can cancel the game.", delete_after=10)

        session.is_active = False
        self.leaderboard['active_games'].pop(ctx.channel.id, None)

        if session.message and getattr(session.message, 'view', None):
            for child in session.message.view.children:
                child.disabled = True
            
            embed = discord.Embed(
                title="Game Cancelled",
                description=f"The game was manually cancelled by {ctx.author.mention}.",
                color=discord.Color.red()
            )
            try:
                await session.message.edit(embed=embed, view=session.message.view)
            except discord.NotFound:
                pass  # Message was deleted
        
        await ctx.send(f"Game cancelled by {ctx.author.mention}.")

async def setup(bot):
    await bot.add_cog(MatchGame(bot))