from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)

from bot.services.storage import get_settings, save_settings
from bot.ui.containers import ApplicationsPanelView, GuidePanelView


def _message_has_component_id(message: discord.Message, component_id: str) -> bool:
    pending = list(message.components)
    while pending:
        component = pending.pop()
        if getattr(component, "custom_id", None) == component_id:
            return True
        pending.extend(getattr(component, "children", ()) or ())
    return False


async def _find_panel_message(
    channel: discord.TextChannel | discord.Thread,
    bot_user_id: int,
    marker: str,
) -> discord.Message | None:
    try:
        async for message in channel.history(limit=100):
            if message.author.id == bot_user_id and _message_has_component_id(message, marker):
                return message
    except (discord.Forbidden, discord.HTTPException):
        return None
    return None


def can_manage(interaction: discord.Interaction) -> bool:
    return bool(
        interaction.guild
        and isinstance(interaction.user, discord.Member)
        and interaction.user.guild_permissions.manage_guild
    )


async def create_application_log_channels(
    guild: discord.Guild, review_role: discord.Role | None
) -> tuple[discord.CategoryChannel, dict[str, discord.TextChannel]]:
    """Создаёт одну закрытую категорию и три канала логов; повторный запуск безопасен."""
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
    }
    if guild.me:
        overwrites[guild.me] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True,
            manage_channels=True, manage_messages=True,
        )
    if review_role:
        overwrites[review_role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True,
        )

    category = discord.utils.get(guild.categories, name="логи-заявок")
    if category is None:
        category = await guild.create_category(
            "логи-заявок", overwrites=overwrites,
            reason="Автоматическая настройка каналов заявок",
        )
    else:
        await category.edit(
            overwrites=overwrites,
            reason="Обновление приватных прав категории заявок",
        )

    names = {
        "squad": "логи-в-отряд",
        "staff": "логи-в-персонал",
        "complaint": "логи-жалобы",
    }
    result: dict[str, discord.TextChannel] = {}
    for key, name in names.items():
        channel = discord.utils.get(category.text_channels, name=name)
        if channel is None:
            channel = await guild.create_text_channel(
                name, category=category, overwrites=overwrites,
                reason="Автоматическое создание канала заявок",
            )
        elif channel.category_id != category.id or channel.permissions_synced is False:
            await channel.edit(category=category, sync_permissions=True)
        result[key] = channel
    return category, result


class Panels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup_applications", description="Создать каналы логов и опубликовать панель заявок")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        panel_channel="Канал, куда отправить сообщение с кнопками подачи заявок",
        review_role="Роль персонала, которая сможет видеть логи и проверять заявки",
    )
    async def setup_applications(
        self,
        interaction: discord.Interaction,
        panel_channel: discord.TextChannel,
        review_role: discord.Role | None = None,
    ) -> None:
        if not can_manage(interaction) or interaction.guild is None:
            await interaction.response.send_message("Нужны права «Управление сервером». ", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            category, created_channels = await create_application_log_channels(interaction.guild, review_role)
            settings = get_settings(interaction.guild.id)
            old_channel_id = settings.get("application_channel_id")
            old_message_id = settings.get("application_panel_message_id")
            settings["application_channel_id"] = panel_channel.id
            settings["application_category_id"] = category.id
            settings["application_log_channels"] = {key: channel.id for key, channel in created_channels.items()}
            settings["review_role_id"] = review_role.id if review_role else None
            message = None
            if old_message_id and old_channel_id and int(old_channel_id) == panel_channel.id:
                try:
                    message = await panel_channel.fetch_message(int(old_message_id))
                except discord.NotFound:
                    message = None
            if message is None and self.bot.user is not None:
                message = await _find_panel_message(
                    panel_channel, self.bot.user.id, "community:apply:squad"
                )
            file = discord.File("assets/apply.png", filename="apply.png")
            if message is not None:
                await message.edit(
                    view=ApplicationsPanelView(settings),
                    attachments=[file],
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            else:
                message = await panel_channel.send(
                    view=ApplicationsPanelView(settings),
                    file=file,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

            settings["application_panel_message_id"] = message.id
            save_settings(interaction.guild.id, settings)
        except discord.Forbidden:
            await interaction.followup.send(
                "Не хватило прав. Дай боту «Управлять каналами», «Просматривать каналы» "
                "и «Отправлять сообщения», затем повтори команду.", ephemeral=True,
            )
            return
        except discord.HTTPException as exc:
            await interaction.followup.send(f"Discord не выполнил настройку: {exc}", ephemeral=True)
            return
        except Exception:
            log.exception("Unexpected error while setting up application channels")
            await interaction.followup.send(
                "Настройка не завершилась из-за ошибки. Подробности есть в окне консоли бота; "
                "после исправления можно повторить команду.",
                ephemeral=True,
            )
            return
        channels_text = " · ".join(channel.mention for channel in created_channels.values())
        await interaction.followup.send(
            f"Панель опубликована в {panel_channel.mention} (сообщение `{message.id}`).\n"
            f"Созданы/проверены закрытые каналы в категории {category.name}: {channels_text}\n"
            f"Роль проверки: {review_role.mention if review_role else 'только администраторы с правом «Управление сервером»'}.\n"
            "Повторный запуск обновит панель и использует те же каналы.",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="set_channels", description="Настроить каналы бота вручную")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        application_panel="Канал для публичной панели подачи заявок",
        application_inbox="Запасной канал для заявок, если отдельные логи не настроены",
        guide_panel="Канал для публичной памятки сервера",
        welcome_channel="Канал для приветствий новых участников",
    )
    async def set_channels(
        self,
        interaction: discord.Interaction,
        application_panel: discord.TextChannel | None = None,
        application_inbox: discord.TextChannel | None = None,
        guide_panel: discord.TextChannel | None = None,
        welcome_channel: discord.TextChannel | None = None,
    ) -> None:
        if not can_manage(interaction):
            await interaction.response.send_message("Нужны права «Управление сервером».", ephemeral=True)
            return
        if interaction.guild is None:
            return
        channels = {
            "application_channel_id": application_panel,
            "application_inbox_id": application_inbox,
            "guide_channel_id": guide_panel,
            "welcome_channel_id": welcome_channel,
        }
        settings = get_settings(interaction.guild.id)
        changed = []
        for key, channel in channels.items():
            if channel is not None:
                settings[key] = channel.id
                changed.append(channel.mention)
        if not changed:
            await interaction.response.send_message("Укажи хотя бы один канал.", ephemeral=True)
            return
        save_settings(interaction.guild.id, settings)
        await interaction.response.send_message(
            "Настройки каналов сохранены: " + ", ".join(changed), ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def _post_panel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None,
        setting_key: str,
        view_type: type[discord.ui.LayoutView],
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        settings = get_settings(interaction.guild.id)
        stored_id = settings.get(setting_key)
        target = channel or (self.bot.get_channel(int(stored_id)) if stored_id else None) or interaction.channel
        if not isinstance(target, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("Не удалось определить текстовый канал.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            if view_type in (GuidePanelView, ApplicationsPanelView):
                is_guide = view_type is GuidePanelView
                channel_key = "guide_channel_id" if is_guide else "application_channel_id"
                message_key = "guide_message_id" if is_guide else "application_panel_message_id"
                message = None
                saved_message_id = settings.get(message_key)
                saved_channel_id = settings.get(channel_key)
                if saved_message_id and saved_channel_id and int(saved_channel_id) == target.id:
                    try:
                        message = await target.fetch_message(int(saved_message_id))
                    except discord.NotFound:
                        message = None
                if message is None and self.bot.user:
                    marker = "community:guide:rules" if is_guide else "community:apply:squad"
                    message = await _find_panel_message(target, self.bot.user.id, marker)
                new_view = (
                    GuidePanelView(settings, interaction.guild.name)
                    if is_guide else ApplicationsPanelView(settings)
                )
                if message is None:
                    message = await target.send(
                        view=new_view,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                else:
                    await message.edit(
                        view=new_view,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                settings[channel_key] = target.id
                settings[message_key] = message.id
                save_settings(interaction.guild.id, settings)
            else:
                await target.send(view=view_type(settings), allowed_mentions=discord.AllowedMentions.none())
        except discord.Forbidden:
            await interaction.followup.send("У бота нет прав отправлять сообщения в этот канал.", ephemeral=True)
            return
        await interaction.followup.send(f"Панель отправлена/обновлена в {target.mention}.", ephemeral=True)

    @app_commands.command(name="post_applications", description="Опубликовать панель подачи заявок")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Канал публикации; если не указан, используется сохранённый канал")
    async def post_applications(
        self, interaction: discord.Interaction, channel: discord.TextChannel | None = None
    ) -> None:
        if not can_manage(interaction):
            await interaction.response.send_message("Нужны права «Управление сервером».", ephemeral=True)
            return
        await self._post_panel(interaction, channel, "application_channel_id", ApplicationsPanelView)

    @app_commands.command(name="post_guide", description="Опубликовать памятку сервера")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Канал публикации; в заголовок автоматически подставится название сервера")
    async def post_guide(
        self, interaction: discord.Interaction, channel: discord.TextChannel | None = None
    ) -> None:
        if not can_manage(interaction):
            await interaction.response.send_message("Нужны права «Управление сервером».", ephemeral=True)
            return
        await self._post_panel(interaction, channel, "guide_channel_id", GuidePanelView)

    @app_commands.command(name="set_application_text", description="Настроить тексты панели подачи заявок")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(title="Заголовок панели", intro="Текст-инструкция", note="Короткая памятка для заявителя")
    async def set_application_text(
        self, interaction: discord.Interaction, title: str, intro: str, note: str
    ) -> None:
        if not can_manage(interaction):
            await interaction.response.send_message("Нужны права «Управление сервером».", ephemeral=True)
            return
        if interaction.guild is None:
            return
        if max(map(len, (title, intro, note))) > 850:
            await interaction.response.send_message("Каждое поле должно быть не длиннее 850 символов.", ephemeral=True)
            return
        settings = get_settings(interaction.guild.id)
        settings.update({"application_title": title, "application_intro": intro, "application_note": note})
        save_settings(interaction.guild.id, settings)
        await interaction.response.send_message(
            "Тексты сохранены. Чтобы отправить обновлённую панель, используй /post_applications.", ephemeral=True
        )

    @app_commands.command(name="set_guide_text", description="Настроить основной текст памятки")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        title="Заголовок; используй {server}, чтобы автоматически подставить название сервера",
        intro="Вводный текст памятки",
        activity="Текст раздела «Чем мы занимаемся?»",
        important="Текст раздела важных правил",
    )
    async def set_guide_text(
        self, interaction: discord.Interaction, title: str, intro: str, activity: str, important: str
    ) -> None:
        if not can_manage(interaction):
            await interaction.response.send_message("Нужны права «Управление сервером».", ephemeral=True)
            return
        if interaction.guild is None:
            return
        if max(map(len, (title, intro, activity, important))) > 850:
            await interaction.response.send_message("Каждое поле должно быть не длиннее 850 символов.", ephemeral=True)
            return
        settings = get_settings(interaction.guild.id)
        settings.update({
            "guide_title": title,
            "guide_intro": intro,
            "guide_activity": activity,
            "guide_important": important,
        })
        save_settings(interaction.guild.id, settings)
        await interaction.response.send_message(
            "Текст памятки сохранён. Опубликуй обновление командой /post_guide.", ephemeral=True
        )

    async def _refresh_guide(self, guild: discord.Guild) -> None:
        settings = get_settings(guild.id)
        channel_id = settings.get("guide_channel_id")
        message_id = settings.get("guide_message_id")
        if not channel_id:
            return
        channel = guild.get_channel(int(channel_id)) or guild.get_thread(int(channel_id))
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(int(channel_id))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                return
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return
        try:
            message = None
            if message_id:
                try:
                    message = await channel.fetch_message(int(message_id))
                except discord.NotFound:
                    message = None
            if message is None and self.bot.user is not None:
                message = await _find_panel_message(channel, self.bot.user.id, "community:guide:rules")
            if message is not None:
                await message.edit(
                    view=GuidePanelView(settings, guild.name),
                    allowed_mentions=discord.AllowedMentions.none(),
                )


        except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
            log.exception("Could not refresh guide message for guild %s", guild.id)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        if before.name != after.name:
            await self._refresh_guide(after)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        # Обновляет также памятки, если название сервера изменили, пока бот был выключен.
        for guild in self.bot.guilds:
            await self._refresh_guide(guild)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Panels(bot))
