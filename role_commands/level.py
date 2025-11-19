import discord
from discord.ext import commands, tasks
import sqlite3
import random
import math
from datetime import datetime, timedelta

# --- CONFIGURATION ---
DATABASE_FILE = "leveling.db"
MESSAGE_COOLDOWN_SECONDS = 60
XP_PER_MESSAGE_RANGE = (15, 25)
XP_PER_VOICE_MINUTE = 10
LEADERBOARD_PER_PAGE = 10 # Number of users per leaderboard page

# Channels where users will NOT gain XP. Add your channel IDs here.
BLACKLISTED_CHANNELS = [
    0, # Example: 123456789012345678 (a bot command channel)
]

# Roles that grant an XP multiplier. Add Role ID: multiplier. 1.5 is a 50% boost.
XP_BOOSTER_ROLES = {
    0: 1.25, # Example: 123456789012345678: 1.25 (for a +25% boost)
    0: 1.5,  # Example: 123456789012345679: 1.5 (for a +50% boost)
}

# Role IDs for different level milestones.
LEVEL_ROLES = {
    1: 1416858247482179682,
    5: 1416858250464333844,
    10: 1416858252695572600,
    15: 1416858254943719528,
    20: 1416858257657692191,
    30: 1416858259549323397,
    40: 1416858261721976943,
    50: 1416858264359927960,
    60: 1416858266256019597,
    70: 1416858268487127072,
    80: 1416858271322607909,
    90: 1416858273616887900,
    100: 1416858275588210878
}

# --- UI CONFIGURATION ---
BAR_LENGTH = 12
BAR_FILLED = "█"
BAR_EMPTY = "░"
# --- END CONFIGURATION ---


# --- LEADERBOARD PAGINATION VIEW ---
class LeaderboardView(discord.ui.View):
    def __init__(self, bot, ctx, guild_id, total_users):
        super().__init__(timeout=180)
        self.bot = bot
        self.ctx = ctx
        self.guild_id = guild_id
        self.current_page = 1
        self.total_users = total_users
        self.max_pages = math.ceil(total_users / LEADERBOARD_PER_PAGE)
        self.db = sqlite3.connect(DATABASE_FILE)
        self.cursor = self.db.cursor()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except discord.NotFound:
            pass
        self.db.close()

    async def get_page_data(self, page):
        offset = (page - 1) * LEADERBOARD_PER_PAGE
        self.cursor.execute(
            "SELECT user_id, xp, level FROM users WHERE guild_id = ? ORDER BY xp DESC LIMIT ? OFFSET ?",
            (self.guild_id, LEADERBOARD_PER_PAGE, offset)
        )
        return self.cursor.fetchall()

    async def create_embed(self, page_data):
        embed = discord.Embed(
            title=f"🏆 Leaderboard for {self.ctx.guild.name}",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Page {self.current_page} of {self.max_pages} | Requested by {self.ctx.author.display_name}", icon_url=self.ctx.author.display_avatar.url)

        description = ""
        rank_start = (self.current_page - 1) * LEADERBOARD_PER_PAGE + 1
        
        for i, (user_id, xp, level) in enumerate(page_data, start=rank_start):
            member = self.ctx.guild.get_member(user_id)
            name = member.display_name if member else f"User (ID: {user_id})"
            
            rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"**{i}.**")
            description += f"{rank_emoji} **{name}**\n`Level: {level:<3} | Total XP: {xp:>7,}`\n"
        
        if not description:
            description = "No users found on this page."
            
        embed.description = description
        return embed

    async def update_message(self):
        """Updates the message with the new embed and button states."""
        page_data = await self.get_page_data(self.current_page)
        embed = await self.create_embed(page_data)
        
        # Update button states
        self.prev_button.disabled = self.current_page == 1
        self.next_button.disabled = self.current_page == self.max_pages
        
        await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="< Previous", style=discord.ButtonStyle.primary, row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("You can't control this leaderboard.", ephemeral=True)
        
        if self.current_page > 1:
            self.current_page -= 1
            await self.update_message()
        await interaction.response.defer()

    @discord.ui.button(label="Next >", style=discord.ButtonStyle.primary, row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("You can't control this leaderboard.", ephemeral=True)
            
        if self.current_page < self.max_pages:
            self.current_page += 1
            await self.update_message()
        await interaction.response.defer()

    async def send_initial_message(self):
        """Sends the first page of the leaderboard."""
        page_data = await self.get_page_data(self.current_page)
        if not page_data:
            self.db.close()
            return await self.ctx.send("The leaderboard is currently empty.")
            
        embed = await self.create_embed(page_data)
        self.prev_button.disabled = True
        self.next_button.disabled = self.current_page == self.max_pages
        
        self.message = await self.ctx.send(embed=embed, view=self)


class LevelSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = sqlite3.connect(DATABASE_FILE)
        self.cursor = self.db.cursor()
        self.setup_database()
        self.message_cooldowns = {}
        self.vc_xp_loop.start()
        self.prune_data_loop.start()

    def cog_unload(self):
        """Cog unload handler."""
        self.vc_xp_loop.cancel()
        self.prune_data_loop.cancel()
        self.db.close()

    def setup_database(self):
        """Creates the necessary database tables if they don't exist."""
        # This table stores user XP and level. Schema is UNCHANGED.
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                guild_id INTEGER,
                user_id INTEGER,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        # NEW TABLE: Stores guild-specific settings, like the level-up channel.
        # This does NOT affect your existing user data.
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                levelup_channel_id INTEGER DEFAULT NULL
            )
        ''')
        self.db.commit()

    # --- DATABASE HELPER METHODS ---
    def get_user_data(self, guild_id, user_id):
        """Retrieves user data, creating a new entry if one doesn't exist."""
        self.cursor.execute("SELECT xp, level FROM users WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        result = self.cursor.fetchone()
        if result is None:
            self.cursor.execute("INSERT INTO users (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
            self.db.commit()
            return 0, 0
        return result

    def update_user_data(self, guild_id, user_id, xp, level):
        """Updates a user's XP and level."""
        self.cursor.execute("UPDATE users SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?", (xp, level, guild_id, user_id))
        self.db.commit()

    def get_user_rank(self, guild_id, user_id):
        """Gets the server-wide rank of a user."""
        self.cursor.execute("""
            SELECT COUNT(*) + 1 
            FROM users 
            WHERE guild_id = ? AND xp > (SELECT xp FROM users WHERE guild_id = ? AND user_id = ?)
        """, (guild_id, guild_id, user_id))
        rank = self.cursor.fetchone()[0]
        return rank

    def get_levelup_channel(self, guild_id):
        """Gets the configured level-up channel ID for a guild."""
        self.cursor.execute("SELECT levelup_channel_id FROM guild_settings WHERE guild_id = ?", (guild_id,))
        result = self.cursor.fetchone()
        if result and result[0]:
            return self.bot.get_channel(result[0])
        return None

    def set_levelup_channel(self, guild_id, channel_id):
        """Sets the level-up channel for a guild."""
        self.cursor.execute(
            "INSERT INTO guild_settings (guild_id, levelup_channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET levelup_channel_id = excluded.levelup_channel_id",
            (guild_id, channel_id)
        )
        self.db.commit()

    # --- LEVELING LOGIC ---
    def calculate_xp_for_level(self, level):
        """Calculates the CUMULATIVE XP required to reach the next level (level + 1).
        This formula is unchanged to preserve existing user levels."""
        return 5 * (level ** 2) + 50 * level + 100

    def calculate_level_from_xp(self, xp):
        """Calculates the level a user should be at for a given amount of XP.
        This logic is unchanged to preserve existing user levels."""
        level = 0
        while True:
            xp_needed = self.calculate_xp_for_level(level)
            if xp < xp_needed:
                return level
            level += 1

    async def grant_xp(self, member, amount):
        """Grants XP to a user and handles level-ups."""
        if member.bot: return

        # Apply XP boosters
        multiplier = 1.0
        for role_id, boost in XP_BOOSTER_ROLES.items():
            if role_id == 0: continue
            role = member.guild.get_role(role_id)
            if role and role in member.roles:
                multiplier = max(multiplier, boost) # Use the highest boost they have
        
        xp_to_add = int(amount * multiplier)
        if xp_to_add == 0: return

        guild_id, user_id = member.guild.id, member.id
        current_xp, current_level = self.get_user_data(guild_id, user_id)
        new_xp = current_xp + xp_to_add
        new_level = self.calculate_level_from_xp(new_xp)
        
        self.update_user_data(guild_id, user_id, new_xp, new_level)

        if new_level > current_level:
            await self.handle_level_up(member, new_level, current_level)
            
    async def handle_level_up(self, member, new_level, old_level):
        """Handles level-up announcements and role rewards."""
        
        # --- Create Embed ---
        embed = discord.Embed(
            title="🎉 Level Up! 🎉",
            description=f"Congratulations {member.mention}, you have reached **Level {new_level}**!",
            color=discord.Color.gold()
        ).set_thumbnail(url=member.display_avatar.url)

        # Check for new roles awarded
        newly_awarded_role = None
        for lvl in range(old_level + 1, new_level + 1):
            if role_id := LEVEL_ROLES.get(lvl):
                if role := member.guild.get_role(role_id):
                    newly_awarded_role = role # Get the highest new role
        
        if newly_awarded_role:
             embed.add_field(name="Role Awarded!", value=f"You've earned the {newly_awarded_role.mention} role!", inline=False)
        
        # --- Find Channel and Send ---
        # 1. Try custom configured channel
        channel_to_send = self.get_levelup_channel(member.guild.id)
        
        # 2. If no custom channel, try system channel
        if not channel_to_send:
             channel_to_send = member.guild.system_channel
        
        # 3. If no system channel, try first channel bot can speak in
        if not channel_to_send:
            channel_to_send = next((c for c in member.guild.text_channels if c.permissions_for(member.guild.me).send_messages), None)

        try:
            if channel_to_send:
                await channel_to_send.send(embed=embed)
        except discord.Forbidden:
            print(f"Could not send level-up message in {member.guild.name}. Missing permissions.")
        except AttributeError:
             print(f"Could not find a suitable channel to send level-up message in {member.guild.name}.")
        
        # Handle role rewards
        await self.update_level_roles(member, new_level)
        
    async def update_level_roles(self, member, new_level):
        """
        Atomically updates a user's roles.
        Removes all level roles they shouldn't have and adds all they should.
        This correctly handles "stacking" roles, promotions, and demotions.
        """
        try:
            guild_level_role_ids = {role_id for role_id in LEVEL_ROLES.values() if role_id != 0}
            if not guild_level_role_ids: return # No roles configured

            user_role_ids = {role.id for role in member.roles}
            
            # Roles the user currently has that are in the level system
            current_level_roles = user_role_ids & guild_level_role_ids

            # Roles the user *should* have based on their new level
            target_level_role_ids = set()
            for lvl, role_id in LEVEL_ROLES.items():
                if lvl <= new_level and role_id in guild_level_role_ids:
                    target_level_role_ids.add(role_id)

            # Calculate the difference
            roles_to_add_ids = target_level_role_ids - current_level_roles
            roles_to_remove_ids = current_level_roles - target_level_role_ids

            # Add new roles
            if roles_to_add_ids:
                roles_to_add = [member.guild.get_role(role_id) for role_id in roles_to_add_ids if member.guild.get_role(role_id)]
                if roles_to_add:
                    await member.add_roles(*roles_to_add, reason=f"Reached Level {new_level}")
            
            # Remove old roles
            if roles_to_remove_ids:
                roles_to_remove = [member.guild.get_role(role_id) for role_id in roles_to_remove_ids if member.guild.get_role(role_id)]
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason=f"Level changed to {new_level}")

        except discord.Forbidden:
            print(f"Error: Bot lacks permissions to manage roles for {member.name} in {member.guild.name}.")
        except Exception as e:
            print(f"An error occurred while updating roles for {member.name}: {e}")


    # --- EVENT LISTENERS & TASKS ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild or message.channel.id in BLACKLISTED_CHANNELS:
            return

        user_id, guild_id = message.author.id, message.guild.id
        now = datetime.utcnow()

        cooldown_key = (guild_id, user_id)
        if cooldown_key in self.message_cooldowns and now < self.message_cooldowns[cooldown_key]:
            return
        
        self.message_cooldowns[cooldown_key] = now + timedelta(seconds=MESSAGE_COOLDOWN_SECONDS)
        xp_to_add = random.randint(*XP_PER_MESSAGE_RANGE)
        await self.grant_xp(message.author, xp_to_add)

    @tasks.loop(seconds=60)
    async def vc_xp_loop(self):
        """
        Grants XP to users in voice channels.
        IMPROVED: Iterates over voice channels instead of all guild members for efficiency.
        """
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                # Filter members in the channel
                active_members = [
                    m for m in channel.members 
                    if not m.bot 
                    and not m.voice.afk 
                    and not m.voice.self_mute 
                    and not m.voice.self_deaf
                ]
                
                # Only grant XP if there are at least 2 active (non-bot) users
                if len(active_members) > 1:
                    for member in active_members:
                        await self.grant_xp(member, XP_PER_VOICE_MINUTE)

    @tasks.loop(hours=24)
    async def prune_data_loop(self):
        """Removes data for users who are no longer in any shared servers."""
        all_bot_members = {m.id for g in self.bot.guilds for m in g.members}
        self.cursor.execute("SELECT DISTINCT user_id FROM users")
        db_users = {row[0] for row in self.cursor.fetchall()}
        
        users_to_prune = db_users - all_bot_members
        if users_to_prune:
            self.cursor.executemany("DELETE FROM users WHERE user_id = ?", [(uid,) for uid in users_to_prune])
            self.db.commit()
            print(f"Pruned data for {len(users_to_prune)} users who have left all servers.")

    @vc_xp_loop.before_loop
    @prune_data_loop.before_loop
    async def before_loops(self):
        await self.bot.wait_until_ready()

    # --- USER COMMANDS ---
    @commands.command(name="rank", aliases=["level"])
    async def rank(self, ctx, member: discord.Member = None):
        """Shows your current level, XP, and server rank."""
        member = member or ctx.author
        if member.bot:
            return await ctx.send("Bots don't have levels!")

        xp, level = self.get_user_data(ctx.guild.id, member.id)
        rank = self.get_user_rank(ctx.guild.id, member.id)
        
        xp_for_current_level = self.calculate_xp_for_level(level - 1) if level > 0 else 0
        xp_for_next_level = self.calculate_xp_for_level(level)
        
        xp_needed_for_level = xp_for_next_level - xp_for_current_level
        current_xp_in_level = xp - xp_for_current_level

        # --- Build Progress Bar ---
        progress_percentage = (current_xp_in_level / xp_needed_for_level) if xp_needed_for_level > 0 else 0
        filled_length = math.floor(progress_percentage * BAR_LENGTH)
        empty_length = BAR_LENGTH - filled_length
        progress_bar = f"{BAR_FILLED * filled_length}{BAR_EMPTY * empty_length}"
        
        # --- Build Embed ---
        embed = discord.Embed(color=member.color)
        embed.set_author(name=f"Rank for {member.display_name}", icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(name="Total XP", value=f"**{xp:,}**", inline=True)
        embed.add_field(name="Server Rank", value=f"**#{rank}**", inline=True)
        
        embed.add_field(
            name=f"Progress to Level {level + 1}",
            value=f"`{progress_bar}`\n`{current_xp_in_level:,} / {xp_needed_for_level:,} XP`",
            inline=False
        )
        embed.set_footer(text="Gain XP by sending messages and talking in voice channels.")
        await ctx.send(embed=embed)

    @commands.command(name="ranklb", aliases=["topranks", "lb"])
    async def leaderboard(self, ctx):
        """Displays the server's top 10 users in a paginated leaderboard."""
        self.cursor.execute("SELECT COUNT(*) FROM users WHERE guild_id = ?", (ctx.guild.id,))
        total_users = self.cursor.fetchone()[0]

        if total_users == 0:
            return await ctx.send("The leaderboard is currently empty.")

        # Create and send the paginated view
        view = LeaderboardView(self.bot, ctx, ctx.guild.id, total_users)
        await view.send_initial_message()

    # --- ADMIN COMMANDS ---
    @commands.group(name="adminlevel", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def adminlevel(self, ctx):
        """Admin command group for managing user levels and XP."""
        embed = discord.Embed(title="Admin Level Commands", color=discord.Color.red())
        embed.add_field(name=f"`{ctx.prefix}adminlevel addxp <@user> <amount>`", value="Adds XP to a user.", inline=False)
        embed.add_field(name=f"`{ctx.prefix}adminlevel removexp <@user> <amount>`", value="Removes XP from a user.", inline=False)
        embed.add_field(name=f"`{ctx.prefix}adminlevel setlevel <@user> <level>`", value="Sets a user's level.", inline=False)
        embed.add_field(name=f"`{ctx.prefix}adminlevel reset <@user>`", value="Resets a user's level and XP to 0.", inline=False)
        embed.add_field(name=f"`{ctx.prefix}adminlevel setchannel <#channel>`", value="Sets the channel for level-up messages.", inline=False)
        embed.add_field(name=f"`{ctx.prefix}adminlevel disablechannel`", value="Disables the custom level-up channel.", inline=False)
        await ctx.send(embed=embed)

    @adminlevel.command(name="addxp")
    @commands.has_permissions(manage_guild=True)
    async def adminlevel_addxp(self, ctx, member: discord.Member, amount: int):
        if amount <= 0: return await ctx.send("Amount must be a positive number.")
        await self.grant_xp(member, amount)
        await ctx.send(f"✅ Successfully added `{amount:,}` XP to {member.mention}.")

    @adminlevel.command(name="removexp")
    @commands.has_permissions(manage_guild=True)
    async def adminlevel_removexp(self, ctx, member: discord.Member, amount: int):
        if amount <= 0: return await ctx.send("Amount must be a positive number.")
        
        current_xp, _ = self.get_user_data(member.guild.id, member.id)
        new_xp = max(0, current_xp - amount)
        new_level = self.calculate_level_from_xp(new_xp)
        
        self.update_user_data(member.guild.id, member.id, new_xp, new_level)
        await self.update_level_roles(member, new_level) # Update roles after level change
        await ctx.send(f"✅ Successfully removed `{amount:,}` XP from {member.mention}. They are now at level `{new_level}`.")

    @adminlevel.command(name="setlevel")
    @commands.has_permissions(manage_guild=True)
    async def adminlevel_setlevel(self, ctx, member: discord.Member, level: int):
        if level < 0: return await ctx.send("Level must be 0 or greater.")
        
        # We set XP to the *minimum* required for that level
        xp_for_level = self.calculate_xp_for_level(level - 1) if level > 0 else 0
        
        self.update_user_data(member.guild.id, member.id, xp_for_level, level)
        await self.update_level_roles(member, level) # Update roles after level change
        await ctx.send(f"✅ Successfully set {member.mention} to **Level {level}**.")

    @adminlevel.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    async def adminlevel_reset(self, ctx, member: discord.Member):
        self.update_user_data(member.guild.id, member.id, 0, 0)
        
        # Remove all level roles
        await self.update_level_roles(member, 0)
            
        await ctx.send(f"✅ Successfully reset all level progress for {member.mention}.")

    @adminlevel.command(name="setchannel")
    @commands.has_permissions(manage_guild=True)
    async def adminlevel_setchannel(self, ctx, channel: discord.TextChannel):
        """Sets the channel for level-up announcements."""
        self.set_levelup_channel(ctx.guild.id, channel.id)
        await ctx.send(f"✅ Level-up announcements will now be sent to {channel.mention}.")

    @adminlevel.command(name="disablechannel")
    @commands.has_permissions(manage_guild=True)
    async def adminlevel_disablechannel(self, ctx):
        """Disables the custom level-up channel, reverting to default behavior."""
        self.set_levelup_channel(ctx.guild.id, None)
        await ctx.send("✅ Custom level-up channel disabled. Messages will revert to the system channel (if available).")


async def setup(bot):
    await bot.add_cog(LevelSystem(bot))