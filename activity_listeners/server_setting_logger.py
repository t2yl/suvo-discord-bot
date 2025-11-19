import discord
from discord.ext import commands
import datetime

LOG_CHANNEL_ID = 1378260722470883389  # Channel to send all server-setting logs

class ServerSettingsLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_log_channel(self) -> discord.TextChannel | None:
        return self.bot.get_channel(LOG_CHANNEL_ID)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        log_channel = self._get_log_channel()
        if not log_channel:
            return

        # Fetch the latest guild_update audit-log entry
        entry = None
        async for e in before.audit_logs(limit=1, action=discord.AuditLogAction.guild_update):
            entry = e
            break

        changes: list[str] = []

        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if (before.description or "") != (after.description or ""):
            old = before.description or "<none>"
            new = after.description or "<none>"
            changes.append(f"**Description:** `{old}` → `{new}`")
        if before.icon_url != after.icon_url:
            changes.append("**Icon:** Changed")
        if before.banner_url != after.banner_url:
            changes.append("**Banner:** Changed")
        if before.splash_url != after.splash_url:
            changes.append("**Splash (Invite Background):** Changed")
        if before.verification_level != after.verification_level:
            changes.append(
                f"**Verification Level:** `{before.verification_level.name}` → `{after.verification_level.name}`"
            )
        if before.default_message_notifications != after.default_message_notifications:
            changes.append(
                f"**Default Notifications:** `{before.default_message_notifications.name}` → `{after.default_message_notifications.name}`"
            )
        if before.explicit_content_filter != after.explicit_content_filter:
            changes.append(
                f"**Explicit Content Filter:** `{before.explicit_content_filter.name}` → `{after.explicit_content_filter.name}`"
            )
        if before.afk_channel != after.afk_channel:
            old = before.afk_channel.mention if before.afk_channel else "<none>"
            new = after.afk_channel.mention if after.afk_channel else "<none>"
            changes.append(f"**AFK Channel:** {old} → {new}")
        if before.afk_timeout != after.afk_timeout:
            changes.append(f"**AFK Timeout:** `{before.afk_timeout}s` → `{after.afk_timeout}s`")
        # Note: discord.py ≥ 2.4 supports invites_disabled
        if hasattr(before, "invites_disabled") and before.invites_disabled != after.invites_disabled:
            changes.append(f"**Invites Disabled:** `{before.invites_disabled}` → `{after.invites_disabled}`")

        if not changes:
            return

        embed = discord.Embed(
            title="Server Settings Updated",
            description="\n".join(changes),
            color=discord.Color.dark_blue(),
            timestamp=datetime.datetime.utcnow()
        )
        if entry and entry.user:
            embed.set_author(
                name=f"{entry.user} ({entry.user.id})",
                icon_url=entry.user.display_avatar.url
            )
        await log_channel.send(embed=embed)

    # ------------- ROLE EVENTS -------------

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        log_channel = self._get_log_channel()
        if not log_channel:
            return

        # Fetch the latest role_create audit-log entry
        entry = None
        async for e in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
            if e.target.id == role.id:
                entry = e
                break

        embed = discord.Embed(
            title="Role Created",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Role Name", value=role.name, inline=True)
        embed.add_field(name="Role ID", value=role.id, inline=True)
        embed.add_field(name="Hoist", value=str(role.hoist), inline=True)
        embed.add_field(name="Mentionable", value=str(role.mentionable), inline=True)
        if entry and entry.user:
            embed.set_author(
                name=f"{entry.user} ({entry.user.id})",
                icon_url=entry.user.display_avatar.url
            )

        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        log_channel = self._get_log_channel()
        if not log_channel:
            return

        # Fetch the latest role_delete audit-log entry
        entry = None
        async for e in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            if e.target.id == role.id:
                entry = e
                break

        embed = discord.Embed(
            title="Role Deleted",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Role Name", value=role.name, inline=True)
        embed.add_field(name="Role ID", value=role.id, inline=True)
        if entry and entry.user:
            embed.set_author(
                name=f"{entry.user} ({entry.user.id})",
                icon_url=entry.user.display_avatar.url
            )

        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        log_channel = self._get_log_channel()
        if not log_channel:
            return

        changes: list[str] = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.color != after.color:
            changes.append(f"**Color:** `{before.color}` → `{after.color}`")
        if before.permissions != after.permissions:
            changes.append("**Permissions:** Changed")
        if before.hoist != after.hoist:
            changes.append(f"**Hoist:** `{before.hoist}` → `{after.hoist}`")
        if before.mentionable != after.mentionable:
            changes.append(f"**Mentionable:** `{before.mentionable}` → `{after.mentionable}`")
        if before.position != after.position:
            changes.append(f"**Position:** `{before.position}` → `{after.position}`")

        if not changes:
            return

        # Fetch the latest role_update audit-log entry
        entry = None
        async for e in before.guild.audit_logs(limit=5, action=discord.AuditLogAction.role_update):
            if e.target.id == after.id:
                entry = e
                break

        embed = discord.Embed(
            title="Role Updated",
            description="\n".join(changes),
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Role", value=f"{after.name} ({after.id})", inline=False)
        if entry and entry.user:
            embed.set_author(
                name=f"{entry.user} ({entry.user.id})",
                icon_url=entry.user.display_avatar.url
            )

        await log_channel.send(embed=embed)

    # ------------- EMOJI EVENTS -------------

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self,
        guild: discord.Guild,
        before: list[discord.Emoji],
        after: list[discord.Emoji]
    ):
        log_channel = self._get_log_channel()
        if not log_channel:
            return

        before_map = {e.id: e for e in before}
        after_map = {e.id: e for e in after}

        # Detect created emojis
        for emoji_id, emoji_obj in after_map.items():
            if emoji_id not in before_map:
                # Fetch audit-log entry for creation
                entry = None
                async for e in guild.audit_logs(limit=1, action=discord.AuditLogAction.emoji_create):
                    if e.target.id == emoji_id:
                        entry = e
                        break

                embed = discord.Embed(
                    title="Emoji Created",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.utcnow()
                )
                embed.set_thumbnail(url=emoji_obj.url)
                embed.add_field(name="Name", value=emoji_obj.name, inline=True)
                embed.add_field(name="ID", value=emoji_obj.id, inline=True)
                if entry and entry.user:
                    embed.set_author(
                        name=f"{entry.user} ({entry.user.id})",
                        icon_url=entry.user.display_avatar.url
                    )
                await log_channel.send(embed=embed)

        # Detect deleted emojis
        for emoji_id, emoji_obj in before_map.items():
            if emoji_id not in after_map:
                # Fetch audit-log entry for deletion
                entry = None
                async for e in guild.audit_logs(limit=1, action=discord.AuditLogAction.emoji_delete):
                    if e.target.id == emoji_id:
                        entry = e
                        break

                embed = discord.Embed(
                    title="Emoji Deleted",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.utcnow()
                )
                embed.add_field(name="Name", value=emoji_obj.name, inline=True)
                embed.add_field(name="ID", value=emoji_obj.id, inline=True)
                if entry and entry.user:
                    embed.set_author(
                        name=f"{entry.user} ({entry.user.id})",
                        icon_url=entry.user.display_avatar.url
                    )
                await log_channel.send(embed=embed)

        # Detect updated emojis (name change or roles)
        for emoji_id in set(before_map.keys()).intersection(after_map.keys()):
            before_emoji = before_map[emoji_id]
            after_emoji = after_map[emoji_id]
            changes: list[str] = []
            if before_emoji.name != after_emoji.name:
                changes.append(f"**Name:** `{before_emoji.name}` → `{after_emoji.name}`")
            # Roles property: roles that can use the emoji
            if hasattr(before_emoji, "roles") and before_emoji.roles != after_emoji.roles:
                before_roles = [r.name for r in before_emoji.roles]
                after_roles = [r.name for r in after_emoji.roles]
                changes.append(f"**Roles:** `{before_roles}` → `{after_roles}`")

            if not changes:
                continue

            entry = None
            async for e in guild.audit_logs(limit=5, action=discord.AuditLogAction.emoji_update):
                if e.target.id == emoji_id:
                    entry = e
                    break

            embed = discord.Embed(
                title="Emoji Updated",
                description="\n".join(changes),
                color=discord.Color.orange(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_thumbnail(url=after_emoji.url)
            embed.add_field(name="ID", value=emoji_id, inline=True)
            if entry and entry.user:
                embed.set_author(
                    name=f"{entry.user} ({entry.user.id})",
                    icon_url=entry.user.display_avatar.url
                )
            await log_channel.send(embed=embed)

    # ------------- STICKER EVENTS -------------

    @commands.Cog.listener()
    async def on_guild_stickers_update(
        self,
        guild: discord.Guild,
        before: list[discord.Sticker],
        after: list[discord.Sticker]
    ):
        log_channel = self._get_log_channel()
        if not log_channel:
            return

        before_map = {s.id: s for s in before}
        after_map = {s.id: s for s in after}

        # Created stickers
        for sticker_id, sticker_obj in after_map.items():
            if sticker_id not in before_map:
                entry = None
                async for e in guild.audit_logs(limit=1, action=discord.AuditLogAction.sticker_create):
                    if e.target.id == sticker_id:
                        entry = e
                        break

                embed = discord.Embed(
                    title="Sticker Created",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.utcnow()
                )
                embed.add_field(name="Name", value=sticker_obj.name, inline=True)
                embed.add_field(name="ID", value=sticker_obj.id, inline=True)
                if entry and entry.user:
                    embed.set_author(
                        name=f"{entry.user} ({entry.user.id})",
                        icon_url=entry.user.display_avatar.url
                    )
                await log_channel.send(embed=embed)

        # Deleted stickers
        for sticker_id, sticker_obj in before_map.items():
            if sticker_id not in after_map:
                entry = None
                async for e in guild.audit_logs(limit=1, action=discord.AuditLogAction.sticker_delete):
                    if e.target.id == sticker_id:
                        entry = e
                        break

                embed = discord.Embed(
                    title="Sticker Deleted",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.utcnow()
                )
                embed.add_field(name="Name", value=sticker_obj.name, inline=True)
                embed.add_field(name="ID", value=sticker_obj.id, inline=True)
                if entry and entry.user:
                    embed.set_author(
                        name=f"{entry.user} ({entry.user.id})",
                        icon_url=entry.user.display_avatar.url
                    )
                await log_channel.send(embed=embed)

        # Updated stickers (name, description, tags)
        for sticker_id in set(before_map.keys()).intersection(after_map.keys()):
            before_st = before_map[sticker_id]
            after_st = after_map[sticker_id]
            changes: list[str] = []
            if before_st.name != after_st.name:
                changes.append(f"**Name:** `{before_st.name}` → `{after_st.name}`")
            if before_st.description != after_st.description:
                old = before_st.description or "<none>"
                new = after_st.description or "<none>"
                changes.append(f"**Description:** `{old}` → `{new}`")
            if set(before_st.tags) != set(after_st.tags):
                changes.append(f"**Tags:** `{before_st.tags}` → `{after_st.tags}`")

            if not changes:
                continue

            entry = None
            async for e in guild.audit_logs(limit=5, action=discord.AuditLogAction.sticker_update):
                if e.target.id == sticker_id:
                    entry = e
                    break

            embed = discord.Embed(
                title="Sticker Updated",
                description="\n".join(changes),
                color=discord.Color.orange(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="ID", value=sticker_id, inline=True)
            if entry and entry.user:
                embed.set_author(
                    name=f"{entry.user} ({entry.user.id})",
                    icon_url=entry.user.display_avatar.url
                )
            await log_channel.send(embed=embed)

    # ------------- CHANNEL EVENTS -------------

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        log_channel = self._get_log_channel()
        if not log_channel:
            return

        entry = None
        async for e in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
            if e.target.id == channel.id:
                entry = e
                break

        embed = discord.Embed(
            title="Channel Created",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Name", value=channel.name, inline=True)
        embed.add_field(name="ID", value=channel.id, inline=True)
        embed.add_field(name="Type", value=type(channel).__name__, inline=True)
        if entry and entry.user:
            embed.set_author(
                name=f"{entry.user} ({entry.user.id})",
                icon_url=entry.user.display_avatar.url
            )
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        log_channel = self._get_log_channel()
        if not log_channel:
            return

        entry = None
        async for e in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            if e.target.id == channel.id:
                entry = e
                break

        embed = discord.Embed(
            title="Channel Deleted",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Name", value=channel.name, inline=True)
        embed.add_field(name="ID", value=channel.id, inline=True)
        embed.add_field(name="Type", value=type(channel).__name__, inline=True)
        if entry and entry.user:
            embed.set_author(
                name=f"{entry.user} ({entry.user.id})",
                icon_url=entry.user.display_avatar.url
            )
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel
    ):
        log_channel = self._get_log_channel()
        if not log_channel:
            return

        changes: list[str] = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if hasattr(before, "topic") and before.topic != after.topic:  # applies to TextChannels
            old = before.topic or "<none>"
            new = after.topic or "<none>"
            changes.append(f"**Topic:** `{old}` → `{new}`")
        if hasattr(before, "nsfw") and before.nsfw != after.nsfw:
            changes.append(f"**NSFW:** `{before.nsfw}` → `{after.nsfw}`")
        if hasattr(before, "bitrate") and before.bitrate != after.bitrate:  # VoiceChannel
            changes.append(f"**Bitrate:** `{before.bitrate}` → `{after.bitrate}`")
        if hasattr(before, "user_limit") and before.user_limit != after.user_limit:
            changes.append(f"**User Limit:** `{before.user_limit}` → `{after.user_limit}`")
        # Add more channel-specific fields as desired

        if not changes:
            return

        entry = None
        async for e in before.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_update):
            if e.target.id == after.id:
                entry = e
                break

        embed = discord.Embed(
            title="Channel Updated",
            description="\n".join(changes),
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Channel", value=f"{after.name} ({after.id})", inline=False)
        if entry and entry.user:
            embed.set_author(
                name=f"{entry.user} ({entry.user.id})",
                icon_url=entry.user.display_avatar.url
            )
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        log_channel = self._get_log_channel()
        if not log_channel or member.bot:
            return

        # Check if kicked via audit log
        async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
            if entry.target.id == member.id:
                embed = discord.Embed(
                    title="Member Kicked",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.utcnow()
                )
                embed.add_field(name="User", value=member.mention, inline=True)
                embed.add_field(name="By", value=entry.user.mention, inline=True)
                if entry.reason:
                    embed.add_field(name="Reason", value=entry.reason, inline=False)
                embed.set_thumbnail(url=member.display_avatar.url)
                await log_channel.send(embed=embed)
                return

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        log_channel = self._get_log_channel()
        if not log_channel or user.bot:
            return

        entry = None
        async for e in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if e.target.id == user.id:
                entry = e
                break

        embed = discord.Embed(
            title="Member Banned",
            color=discord.Color.dark_red(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="User", value=user.mention, inline=True)
        if entry and entry.user:
            embed.add_field(name="By", value=entry.user.mention, inline=True)
        if entry and entry.reason:
            embed.add_field(name="Reason", value=entry.reason, inline=False)
        embed.set_thumbnail(url=user.display_avatar.url if hasattr(user, "display_avatar") else discord.Embed.Empty)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        log_channel = self._get_log_channel()
        if not log_channel or before.bot:
            return

        # ----- Timeout (Communication Disabled) -----
        if (
            hasattr(before, "communication_disabled_until") and
            hasattr(after, "communication_disabled_until") and
            before.communication_disabled_until is None and
            after.communication_disabled_until is not None
        ):
            entry = None
            async for e in before.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                for change in e.changes:
                    if change.key == "communication_disabled_until" and e.target.id == after.id:
                        entry = e
                        break
                if entry:
                    break

            embed = discord.Embed(
                title="Member Timed Out",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="User", value=after.mention, inline=True)
            if entry and entry.user:
                embed.add_field(name="By", value=entry.user.mention, inline=True)
            until = after.communication_disabled_until.strftime("%Y-%m-%d %H:%M UTC")
            embed.add_field(name="Until", value=until, inline=False)
            if entry and entry.reason:
                embed.add_field(name="Reason", value=entry.reason, inline=False)
            embed.set_thumbnail(url=after.display_avatar.url)
            await log_channel.send(embed=embed)

        elif (
            hasattr(before, "communication_disabled_until") and
            hasattr(after, "communication_disabled_until") and
            before.communication_disabled_until is not None and
            after.communication_disabled_until is None
        ):
            entry = None
            async for e in before.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                for change in e.changes:
                    if change.key == "communication_disabled_until" and e.target.id == after.id:
                        entry = e
                        break
                if entry:
                    break

            embed = discord.Embed(
                title="Member Timeout Removed",
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="User", value=after.mention, inline=True)
            if entry and entry.user:
                embed.add_field(name="By", value=entry.user.mention, inline=True)
            if entry and entry.reason:
                embed.add_field(name="Reason", value=entry.reason, inline=False)
            embed.set_thumbnail(url=after.display_avatar.url)
            await log_channel.send(embed=embed)

        # ----- Nickname Changed -----
        if before.nick != after.nick:
            entry = None
            async for e in before.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_update):
                for change in e.changes:
                    if change.key == "nick" and e.target.id == after.id:
                        entry = e
                        break
                if entry:
                    break

            old_nick = before.nick or before.name
            new_nick = after.nick or after.name
            embed = discord.Embed(
                title="Nickname Changed",
                color=discord.Color.blurple(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="User", value=after.mention, inline=True)
            embed.add_field(name="Old Nickname", value=old_nick, inline=True)
            embed.add_field(name="New Nickname", value=new_nick, inline=True)
            if entry and entry.user:
                embed.add_field(name="Changed By", value=entry.user.mention, inline=False)
            embed.set_thumbnail(url=after.display_avatar.url)
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        log_channel = self._get_log_channel()
        if not log_channel or member.bot:
            return

        # Server Mute toggled
        if before.mute != after.mute:
            action = "Server Muted" if after.mute else "Server Unmuted"
            embed = discord.Embed(
                title=action,
                color=discord.Color.orange() if after.mute else discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(
                name="Channel",
                value=after.channel.mention if after.channel else before.channel.mention,
                inline=True
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await log_channel.send(embed=embed)

        # Server Deafen toggled
        elif before.deaf != after.deaf:
            action = "Server Deafened" if after.deaf else "Server Undeafened"
            embed = discord.Embed(
                title=action,
                color=discord.Color.orange() if after.deaf else discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(
                name="Channel",
                value=after.channel.mention if after.channel else before.channel.mention,
                inline=True
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        log_channel = self._get_log_channel()
        if not log_channel or user.bot:
            return

        entry = None
        async for e in guild.audit_logs(limit=1, action=discord.AuditLogAction.unban):
            if e.target.id == user.id:
                entry = e
                break

        embed = discord.Embed(
            title="Member Unbanned",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="User", value=user.mention, inline=True)
        if entry and entry.user:
            embed.add_field(name="By", value=entry.user.mention, inline=True)
        if entry and entry.reason:
            embed.add_field(name="Reason", value=entry.reason, inline=False)
        embed.set_thumbnail(url=user.display_avatar.url if hasattr(user, "display_avatar") else discord.Embed.Empty)
        await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSettingsLogger(bot))
