import discord
from discord.ext import commands
import os
import json
import asyncio
import random
import time

# ------------------------------------------------------------------
# VIEW 1: The "Take Proficiency" button (Persistent)
# ------------------------------------------------------------------

class TakeTestView(discord.ui.View):
    """
    A persistent view with a single button to start the proficiency test.
    This view is attached to the main rules embed.
    """
    def __init__(self, cog: 'ProficiencyTest'):
        super().__init__(timeout=None) # Persistent
        self.cog = cog

    @discord.ui.button(label="Take Proficiency Test", style=discord.ButtonStyle.success, custom_id="take_kor_proficiency")
    async def take_proficiency(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        user = interaction.user
        channel = interaction.channel

        # Acknowledge the interaction first
        await interaction.response.defer(ephemeral=True, thinking=True)

        # --- NEW: Check if user is already in a test ---
        if user.id in self.cog.active_tests:
            await interaction.followup.send(
                "❌ You already have a test in progress. Please complete that one first.",
                ephemeral=True
            )
            return

        # --- NEW: Add user to active test set ---
        # We MUST remove them if any step below fails
        self.cog.active_tests.add(user.id)

        # Load random question set (1 of 5 files)
        question_file = f"proficiency_questions_{random.randint(1, 5)}.json"
        try:
            with open(question_file, "r", encoding="utf-8") as f:
                questions = json.load(f)
            if not questions:
                await interaction.followup.send(
                    "⚠️ The test questions file is empty. Please contact an admin.",
                    ephemeral=True
                )
                self.cog.active_tests.discard(user.id) # --- UPDATED: Release user on error
                return
        except FileNotFoundError:
            await interaction.followup.send(
                f"⚠️ Failed to load test file ({question_file}). Please contact an admin.",
                ephemeral=True
            )
            self.cog.active_tests.discard(user.id) # --- UPDATED: Release user on error
            return
        except Exception as e:
            print(f"Error loading JSON: {e}")
            await interaction.followup.send(
                "⚠️ An error occurred while loading the test. Please try again later.",
                ephemeral=True
            )
            self.cog.active_tests.discard(user.id) # --- UPDATED: Release user on error
            return

        # Create public thread
        try:
            thread_type = discord.ChannelType.public_thread
                
            thread = await channel.create_thread(
                name=f"🎓 {user.name}'s Proficiency Test",
                type=thread_type,
                auto_archive_duration=60
            )
            
        except discord.Forbidden:
            await interaction.followup.send(
                "⚠️ I do not have permission to create threads in this channel.",
                ephemeral=True
            )
            self.cog.active_tests.discard(user.id) # --- UPDATED: Release user on error
            return
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"⚠️ Failed to create a thread (HTTP Error: {e.status}). Please try again.",
                ephemeral=True
            )
            self.cog.active_tests.discard(user.id) # --- UPDATED: Release user on error
            return

        # Send confirmation to the user who clicked
        await interaction.followup.send(
            f"✅ Your public test thread has been created! ➡️ {thread.mention}",
            ephemeral=True
        )

        # Add user to thread (this will ping them)
        try:
            await thread.add_user(user)
        except Exception:
            pass 

        # Send test details embed inside thread with a "Start Test" button
        details_embed = discord.Embed(
            title="🔖 Test Instructions",
            description=(
                f"Welcome, {user.mention}!\n\n"
                f"This test consists of **{len(questions)} questions**.\n\n"
                "• You will have **90 seconds** per question.\n"
                "• Click the button corresponding to your answer.\n"
                "• Once you answer, you cannot change it.\n\n"
                "Spectators can watch, but only you can answer.\n"
                "Click **Start Test** below to begin. This request will expire in 2 minutes."
            ),
            color=0x3498db # Blue
        )
        details_embed.set_footer(text="Make sure you're ready before clicking Start.")

        # --- UPDATED: Wrap in try/except to catch final failure point ---
        try:
            # Create the "Start Test" view and send it in the new thread
            view = StartTestView(self.cog, user, thread, questions)
            await thread.send(embed=details_embed, view=view)
        except Exception as e:
            print(f"Failed to send StartTestView message: {e}")
            # Try to clean up
            self.cog.active_tests.discard(user.id)
            try:
                await thread.delete()
            except Exception:
                pass
        
        # If we get here, the StartTestView is now responsible for timeout
        # or the run_test method is responsible for completion.


# ------------------------------------------------------------------
# VIEW 2: The "Start Test" button (Times out after 120s)
# ------------------------------------------------------------------

class StartTestView(discord.ui.View):
    """
    A view with a "Start Test" button, sent in the new thread.
    Times out after 2 minutes if not clicked.
    """
    def __init__(self, cog: 'ProficiencyTest', user: discord.Member, thread: discord.Thread, questions: list):
        super().__init__(timeout=120.0)
        self.cog = cog
        self.user = user
        self.thread = thread
        self.questions = questions
        self.test_started = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only allow the original user to start the test
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "❌ Only the user who created this test can start it.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Start Test", style=discord.ButtonStyle.success, custom_id="start_kor_test")
    async def start_test(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.test_started = True
        await interaction.response.defer() 

        # Disable the button to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        # Begin the test
        await self.cog.run_test(self.user, self.thread, self.questions)

    async def on_timeout(self):
        # If the user didn't start, lock and archive the thread
        if not self.test_started:
            
            # --- NEW: Release user from active test set ---
            self.cog.active_tests.discard(self.user.id)
            
            try:
                timeout_embed = discord.Embed(
                    title="⌛ Test Expired",
                    description="You did not start the test within the time limit. This thread will now be archived.",
                    color=discord.Color.orange()
                )
                await self.thread.send(embed=timeout_embed)
                await self.thread.edit(locked=True, archived=True)
            except discord.NotFound:
                pass # Thread was likely deleted manually
            except Exception:
                pass # Permissions error, etc.


# ------------------------------------------------------------------
# VIEW 3: The Question & Answer Buttons (Times out after 90s)
# ------------------------------------------------------------------

class QuestionView(discord.ui.View):
    """
    A view that dynamically creates answer buttons for a single question.
    Times out after 90 seconds.
    """
    def __init__(self, user: discord.Member, indexed_options: list, original_correct_index: int):
        super().__init__(timeout=90.0)
        self.user = user
        self.value = None # Stores True (correct), False (incorrect), or None (timeout)
        self.q_start = time.time()
        self.q_time = 0.0
        self.message: discord.Message = None
        self.chosen_option_label = None
        self.correct_option_label = None 
        
        self.correct_answer_index = -1 

        for i, (original_idx, option_text) in enumerate(indexed_options):
            
            if original_idx == original_correct_index:
                self.correct_answer_index = i
                self.correct_option_label = option_text 
            
            label = f"{i + 1}. {option_text}"
            if len(label) > 80:
                label = label[:77] + "..."
                
            button = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.secondary,
                custom_id=str(i) 
            )
            button.callback = self.button_callback
            self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "❌ This is not your test! Only the test-taker can answer.",
                ephemeral=True
            )
            return False
        return True

    async def button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.stop() 
        
        user_choice_index = int(interaction.data['custom_id'])
        
        self.q_time = time.time() - self.q_start

        clicked_button = None
        correct_button = None

        for item in self.children:
            if not isinstance(item, discord.ui.Button):
                continue
                
            item.disabled = True
            
            item_index = int(item.custom_id) 
            
            if item_index == user_choice_index:
                clicked_button = item
            
            if item_index == self.correct_answer_index:
                correct_button = item

        if clicked_button:
            self.chosen_option_label = clicked_button.label

        if user_choice_index == self.correct_answer_index:
            self.value = True
            if clicked_button:
                clicked_button.style = discord.ButtonStyle.success
        else:
            self.value = False
            if clicked_button:
                clicked_button.style = discord.ButtonStyle.danger
            if correct_button:
                correct_button.style = discord.ButtonStyle.success
        
        await interaction.message.edit(view=self)


    async def on_timeout(self):
        self.value = None 
        self.q_time = 90.0
        
        for item in self.children:
            if not isinstance(item, discord.ui.Button):
                continue
                
            item.disabled = True
            if item.custom_id == str(self.correct_answer_index):
                item.style = discord.ButtonStyle.success
        
        if self.message: 
            try:
                await self.message.edit(
                    content=f"*{self.message.content or ''}\n\n⏰ This question timed out.*", 
                    view=self
                )
            except discord.NotFound:
                pass 


# ------------------------------------------------------------------
# THE MAIN COG: ProficiencyTest
# ------------------------------------------------------------------

class ProficiencyTest(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config_file = "panel_config.json"
        self.panel_data = {} # Will hold {'channel_id': ID, 'message_id': ID}
        self.active_tests = set() # --- NEW: Track active test-takers by user ID
        
        self.rules_embed = discord.Embed(
            title="📘 Korean Proficiency Test",
            description=(
                "Welcome to the Korean Proficiency Test!\n\n"
                "**Rules & Regulations:**\n"
                "• Click the button to start a **public** test thread.\n"
                "• Spectators can watch, but only you can participate.\n"
                "• You will have **90 seconds** per question.\n"
                "• Answer by clicking the button with your chosen option.\n"
                "• At the end, you will receive your score, level, and answer key.\n\n"
                "Click **Take Proficiency Test** below to begin!"
            ),
            color=0xffffff # White
        )
        self.rules_embed.set_footer(text="Only one test per session. Make sure you are ready.")
        
        # Load panel config on startup
        self.load_panel_config()
        
        # Register persistent view
        self.bot.add_view(TakeTestView(self))

    # --- NEW: Helper functions for panel management ---

    def load_panel_config(self):
        """Loads panel channel/message ID from the config file."""
        try:
            with open(self.config_file, "r") as f:
                self.panel_data = json.load(f)
            if "channel_id" not in self.panel_data or "message_id" not in self.panel_data:
                 self.panel_data = {"channel_id": None, "message_id": None}
        except FileNotFoundError:
            self.panel_data = {"channel_id": None, "message_id": None}
        except json.JSONDecodeError:
            print("Error decoding panel_config.json. Resetting.")
            self.panel_data = {"channel_id": None, "message_id": None}

    def save_panel_config(self):
        """Saves the current panel channel/message ID to the config file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.panel_data, f, indent=4)
        except Exception as e:
            print(f"Failed to save panel config: {e}")

    async def delete_previous_panel(self):
        """Finds and deletes the old panel message, if it exists."""
        channel_id = self.panel_data.get("channel_id")
        message_id = self.panel_data.get("message_id")
        
        if not channel_id or not message_id:
            return # Nothing to delete

        try:
            channel = self.bot.get_channel(channel_id)
            if channel:
                message = await channel.fetch_message(message_id)
                await message.delete()
        except (discord.NotFound, discord.Forbidden):
            # Message or channel was already deleted, which is fine.
            pass
        except Exception as e:
            print(f"Error deleting old panel: {e}")
        finally:
            # Clear the stored data regardless of success
            self.panel_data = {"channel_id": None, "message_id": None}
            self.save_panel_config()

    # --- NEW: Event listener to move panel on thread creation ---

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        """
        Listens for new threads. If one is created in the panel's channel,
        delete and resend the panel to keep it at the bottom.
        """
        panel_channel_id = self.panel_data.get("channel_id")
        
        # Check if a panel is set and if the new thread is in that panel's channel
        if not panel_channel_id or thread.parent_id != panel_channel_id:
            return
        
        # A thread was created in our channel. Resend the panel.
        channel = thread.parent
        if not channel:
            return

        await self.delete_previous_panel()
        
        try:
            msg = await channel.send(embed=self.rules_embed, view=TakeTestView(self))
            # Save the new message's info
            self.panel_data = {"channel_id": channel.id, "message_id": msg.id}
            self.save_panel_config()
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"Failed to resend panel in on_thread_create: {e}")

    # --- UPDATED: Admin command ---

    @commands.command(name="proficiency-test")
    @commands.has_permissions(administrator=True)
    async def proficiency_test(self, ctx: commands.Context):
        """
        Admin-only command. Deletes any old panel and sends a new one.
        This sets the channel for the proficiency test.
        """
        # Delete any existing panel first
        await self.delete_previous_panel()
        
        # Send the new panel
        try:
            msg = await ctx.send(embed=self.rules_embed, view=TakeTestView(self))
            
            # Save the new panel's location
            self.panel_data = {"channel_id": ctx.channel.id, "message_id": msg.id}
            self.save_panel_config()
            
        except (discord.Forbidden, discord.HTTPException) as e:
            await ctx.send(f"⚠️ Failed to send panel: {e}", ephemeral=True)

    @proficiency_test.error
    async def proficiency_test_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need **Administrator** permissions to use this command.")

    # --- Core Test Logic (Unchanged) ---

    async def run_test(self, user: discord.Member, thread: discord.Thread, questions: list):
        """
        Core test logic: ask questions, collect answers via views, calculate score.
        """
        # --- NEW: Wrap entire test in try/finally to ensure user is released ---
        try:
            intro = discord.Embed(
                title="🏁 Test Started!",
                description=(
                    f"{user.mention}, the test is now live.\n\n"
                    "⏱️ You have **90 seconds** per question.\n"
                    "✅ Click the button corresponding to your answer.\n\n"
                    "Good luck!"
                ),
                color=0x5865F2 # Discord Blurple
            )
            await thread.send(embed=intro)
            await asyncio.sleep(3) # Give them a moment to read

            score = 0
            total_questions = len(questions) # Store original total
            valid_questions_count = 0 # Count only valid questions
            answer_key_details = []
            time_per_question = []

            for idx, q in enumerate(questions, start=1):
                question_text = q.get("question")
                options = q.get("options", [])
                answer_idx = q.get("answer_index") # This is the *original* index
                
                if not question_text or not options or answer_idx is None or answer_idx >= len(options) or answer_idx < 0:
                    await thread.send(f"⚠️ Skipping malformed question {idx} (invalid data)...")
                    continue
                
                valid_questions_count += 1
                
                # --- Shuffle the options ---
                indexed_options = list(enumerate(options))
                random.shuffle(indexed_options)
                
                embed = discord.Embed(
                    title=f"❓ Question {valid_questions_count}/{total_questions}",
                    description=f"```{question_text}```",
                    color=0x3498db # Blue
                )
                embed.set_footer(text="Select your answer below within 90 seconds.")
                
                view = QuestionView(user, indexed_options, answer_idx)
                
                msg = await thread.send(embed=embed, view=view)
                view.message = msg
                
                await view.wait()
                
                time_per_question.append(view.q_time)
                
                correct_answer_label = f"{view.correct_answer_index + 1}. {view.correct_option_label}"
                
                if view.value is True:
                    score += 1
                    response_embed = discord.Embed(
                        description=f"✅ **Correct!** (Answered in {view.q_time:.1f}s)",
                        color=discord.Color.green()
                    )
                    await thread.send(embed=response_embed)
                    answer_key_details.append(f"✅ **Q{idx}:** Correct!")
                
                elif view.value is False:
                    response_embed = discord.Embed(
                        description=f"❌ **Incorrect!** The correct answer was:\n**{correct_answer_label}**",
                        color=discord.Color.red()
                    )
                    await thread.send(embed=response_embed)
                    answer_key_details.append(f"❌ **Q{idx}:** Incorrect. (Correct: *{correct_answer_label}*)")
                
                else: # Timeout (value is None)
                    response_embed = discord.Embed(
                        description=f"⏰ **Time's up!** The correct answer was:\n**{correct_answer_label}**",
                        color=discord.Color.orange()
                    )
                    await thread.send(embed=response_embed)
                    answer_key_details.append(f"⏰ **Q{idx}:** Timed Out. (Correct: *{correct_answer_label}*)")
                
                await asyncio.sleep(2) 

            # --- Test Finished ---
            if valid_questions_count <= 0:
                await thread.send("The test could not be completed as no valid questions were found.")
                return # Still hits the finally block

            await thread.send(embed=discord.Embed(title="--- Test Complete ---", color=0xAAAAAA))
            
            percent = (score / valid_questions_count) * 100
            if percent <= 40:
                level = "Beginner (초급)"
                level_color = 0xE74C3C # Red
            elif percent <= 75:
                level = "Intermediate (중급)"
                level_color = 0xF1C40F # Yellow
            else:
                level = "Advanced (고급)"
                level_color = 0x2ECC71 # Green

            total_time = sum(time_per_question)

            result_embed = discord.Embed(
                title="🏆 Test Results",
                description=f"Here's how you did, {user.mention}!",
                color=level_color
            )
            result_embed.add_field(name="📊 Score", value=f"**{score}/{valid_questions_count}** ({percent:.1f}%)", inline=True)
            result_embed.add_field(name="📈 Level", value=f"**{level}**", inline=True)
            result_embed.add_field(name="⏱️ Total Time", value=f"{total_time:.1f} seconds", inline=False)
            await thread.send(embed=result_embed)

            time_details = "\n".join([f"**Q{i+1}:** {t:.1f}s" for i, t in enumerate(time_per_question)])
            time_embed = discord.Embed(
                title="⏱️ Time per Question",
                description=time_details,
                color=0xAAAAAA
            )
            await thread.send(embed=time_embed)

            answer_key_str = "\n".join(answer_key_details)
            key_embed = discord.Embed(
                title="🔑 Answer Key",
                description=answer_key_str,
                color=0xAAAAAA
            )
            await thread.send(embed=key_embed)

            try:
                await thread.send("This test is complete. This thread will now be locked and archived.")
                await thread.edit(locked=True, archived=True)
            except Exception:
                pass 
        
        finally:
            # --- NEW: This block always runs, releasing the user ---
            self.active_tests.discard(user.id)
            print(f"Test for user {user.id} concluded. Releasing lock.")


async def setup(bot: commands.Bot):
    await bot.add_cog(ProficiencyTest(bot))