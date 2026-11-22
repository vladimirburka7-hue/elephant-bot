from __future__ import annotations

import asyncio
import logging
import os
import time
import discord
from discord import app_commands, ui
from discord.ext import commands

from bot.emojis import emoji_object, emoji_tag
from bot.services.storage import get_settings, save_settings
from bot.ui.containers import ApplicationsPanelView, GuidePanelView
from bot.cogs.market import MarketPanel

log = logging.getLogger("community_bot.setup")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROLE_ICONS_DIR = os.path.join(ROOT_DIR, "assets", "role_icons")

ALLOWED_BUILDERS = {"thep1neyyy", "demoraale"}
MEDIA_COOLDOWN_SECONDS = 5 * 3600
MEDIA_LAST_POST: dict[int, float] = {}


def load_role_icon(filename: str | None) -> bytes | None:
    if not filename:
        return None
    path = os.path.join(ROLE_ICONS_DIR, filename)
    if os.path.isfile(path):
        with open(path, "rb") as f:
            return f.read()
    return None

class VerifyButton(ui.Button):
    def __init__(self) -> None:
        super().__init__(
            label="Верифицироваться",
            emoji=emoji_object("yes"),
            style=discord.ButtonStyle.secondary,
            custom_id="verify:btn",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Доступно только на сервере.", ephemeral=True)
            return

        settings = get_settings(interaction.guild.id)
        role_id = settings.get("member_role_id")
        role = interaction.guild.get_role(int(role_id)) if role_id else None
        if role is None:
            role = discord.utils.get(interaction.guild.roles, name="︲Мембер") or discord.utils.get(
                interaction.guild.roles, name="・Участник"
            )

        if role is None:
            await interaction.response.send_message(
                f"{emoji_tag('question')} Роль участника не найдена. Обратитесь к администрации.",
                ephemeral=True,
            )
            return

        if role in interaction.user.roles:
            await interaction.response.send_message(
                f"{emoji_tag('yes')} Вы уже верифицированы!",
                ephemeral=True,
            )
            return

        try:
            await interaction.user.add_roles(role, reason="Прохождение верификации")
            await interaction.response.send_message(
                f"{emoji_tag('yes')} Верификация пройдена! Вам выдана роль {role.mention}.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"{emoji_tag('question')} У бота не хватает прав выдать роль (поднимите роль бота выше роли участника).",
                ephemeral=True,
            )


class VerificationView(ui.LayoutView):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.MediaGallery(discord.MediaGalleryItem("attachment://verify.png")),
            ui.TextDisplay(f"# {emoji_tag('yes')} Верификация"),
            ui.TextDisplay(
                f"> {emoji_tag('key')} Нажми на кнопку ниже, чтобы подтвердить аккаунт и открыть доступ к каналам сервера."
            ),
            ui.ActionRow(VerifyButton()),
        ))


class MediaPostModal(ui.Modal, title="Опубликовать видео"):
    title_input = ui.TextInput(label="Название или описание", max_length=120, required=True)
    link_input = ui.TextInput(label="Ссылка на видео (YouTube, TikTok и т.д.)", max_length=300, required=True)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Публикация доступна только в текстовом канале.", ephemeral=True)
            return

        now = time.time()
        last = MEDIA_LAST_POST.get(interaction.user.id, 0.0)
        remaining = int(MEDIA_COOLDOWN_SECONDS - (now - last))
        if remaining > 0:
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            await interaction.response.send_message(
                f"{emoji_tag('question')} Вы уже публиковали видео. Следующая публикация будет доступна через **{hours} ч. {minutes} мин.**",
                ephemeral=True,
            )
            return

        title = discord.utils.escape_mentions(self.title_input.value.strip())
        link = discord.utils.escape_mentions(self.link_input.value.strip())

        post_view = ui.LayoutView(timeout=None)
        post_view.add_item(ui.Container(
            ui.TextDisplay(f"### {emoji_tag('star')} {title}"),
            ui.TextDisplay(
                f"> {emoji_tag('member')} **Автор:** {interaction.user.mention}\n"
                f"> {emoji_tag('flag')} **Видео:** {link}"
            ),
        ))

        await interaction.channel.send(
            view=post_view,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        MEDIA_LAST_POST[interaction.user.id] = now
        await interaction.response.send_message(f"{emoji_tag('yes')} Ваше видео опубликовано!", ephemeral=True)



class MediaPublishButton(ui.Button):
    def __init__(self) -> None:
        super().__init__(
            label="Опубликовать видео",
            emoji=emoji_object("boost"),
            style=discord.ButtonStyle.secondary,
            custom_id="media:publish",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(MediaPostModal())


class MediaPanelView(ui.LayoutView):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.MediaGallery(discord.MediaGalleryItem("attachment://media.png")),
            ui.TextDisplay(f"# {emoji_tag('star')} Медиа-лента"),
            ui.TextDisplay(
                f"> {emoji_tag('key')} Нажмите кнопку ниже, чтобы поделиться своим клипом или видео.\n"
                f"> {emoji_tag('gear')} Ограничение: **1 публикация раз в 5 часов** от одного участника."
            ),
            ui.ActionRow(MediaPublishButton()),
        ))




class TempVoiceInfoView(ui.LayoutView):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('microphone')} Управление приватными комнатами"),
            ui.TextDisplay(
                f"> {emoji_tag('key')} Зайди в голосовой канал **└︱📡・Создать** ниже, чтобы создать свою личную комнату.\n"
                f"> {emoji_tag('gear')} Панель управления появится прямо в чате созданного голосового канала."
            ),
        ))


class StaffGuideView(ui.LayoutView):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('staff')} Команды настройки для персонала"),
            ui.TextDisplay(
                f"> {emoji_tag('gear')} `/set_channels` — вручную привязать каналы приветствия, памятки и заявок.\n"
                f"> {emoji_tag('flag')} `/setup_applications` — пересоздать каналы логов и обновить панель заявок.\n"
                f"> {emoji_tag('star')} `/setup_market` — опубликовать или обновить панель рынка в текущем канале.\n"
                f"> {emoji_tag('microphone')} `/setup_voice` — настроить канал создания приватных комнат."
            ),
        ))


class CommandsInfoView(ui.LayoutView):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('gamepad')} Команды бота"),
            ui.TextDisplay(
                f"> {emoji_tag('robot')} Раздел с мини-играми, экономикой и казино находится в разработке.\n"
                f"> {emoji_tag('star')} Все доступные слэш-команды можно посмотреть, введя `/` в поле ввода."
            ),
        ))


class StatusLayoutView(ui.LayoutView):
    def __init__(self, title_emoji: str, title: str, description: str) -> None:
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.TextDisplay(f"### {emoji_tag(title_emoji)} {title}"),
            ui.TextDisplay(description),
        ))
class SetupGroup(app_commands.Group):
    def __init__(self) -> None:
        super().__init__(name="build", description="Автоматическая настройка и сборка сервера")

    async def _build_server_structure(self, interaction: discord.Interaction, wipe_existing: bool) -> None:
        guild = interaction.guild
        if not guild:
            return

        if interaction.user.name.lower() not in ALLOWED_BUILDERS:
            await interaction.response.send_message(
                view=StatusLayoutView("question", "Нет доступа", f"{emoji_tag('key')} Эта команда доступна только разработчикам бота."),
                ephemeral=True,
            )
            return

        settings = get_settings(guild.id)
        if not settings.get("is_active"):
            await interaction.response.send_message(
                view=StatusLayoutView("question", "Доступ закрыт", f"{emoji_tag('key')} Бот не активирован. Используйте `/activate <ключ>`."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            view=StatusLayoutView("gear", "Запуск настройки", f"{emoji_tag('robot')} Начинаю сборку структуры сервера. Это займёт около 20 секунд..."),
            ephemeral=True,
        )

        if wipe_existing:
            for channel in list(guild.channels):
                try:
                    await channel.delete(reason="Полная пересборка сервера (/build server)")
                    await asyncio.sleep(0.2)
                except discord.HTTPException:
                    pass

        can_use_icons = guild.premium_tier >= 2

        roles_spec = [
            ("︲Владелец", discord.Color.from_rgb(241, 196, 15), discord.Permissions(administrator=True), True, "owner.png"),
            ("︲Совладелец", discord.Color.from_rgb(243, 156, 18), discord.Permissions(administrator=True), True, "owner.png"),
            ("︲Администрация", discord.Color.from_rgb(231, 76, 60), discord.Permissions(administrator=True), True, "admin.png"),
            ("︲Модерация", discord.Color.from_rgb(52, 152, 219), discord.Permissions(
                manage_messages=True, kick_members=True, ban_members=True, moderate_members=True, mute_members=True, move_members=True
            ), True, "mod.png"),
            ("︲Хелпер", discord.Color.from_rgb(26, 188, 156), discord.Permissions(
                manage_messages=True, moderate_members=True, mute_members=True
            ), True, "helper.png"),

            ("︲Фейм", discord.Color.from_rgb(255, 215, 0), discord.Permissions.none(), True, "vip.png"),
            ("︲Медиа", discord.Color.from_rgb(233, 30, 99), discord.Permissions.none(), True, "vip.png"),
            ("︲ВИП", discord.Color.from_rgb(244, 127, 255), discord.Permissions.none(), True, "vip.png"),
            ("︲Альянс", discord.Color.from_rgb(46, 204, 113), discord.Permissions.none(), True, "member.png"),

            ("︲Капитаны отряда", discord.Color.from_rgb(230, 126, 34), discord.Permissions(
                move_members=True, mute_members=True, priority_speaker=True
            ), True, "commander.png"),
            ("︲Кэп 1-го отряда", discord.Color.from_rgb(211, 84, 0), discord.Permissions(
                move_members=True, mute_members=True
            ), False, "commander.png"),
            ("︲Кэп 2-го отряда", discord.Color.from_rgb(211, 84, 0), discord.Permissions(
                move_members=True, mute_members=True
            ), False, "commander.png"),
            ("︲Кэп 3-го отряда", discord.Color.from_rgb(211, 84, 0), discord.Permissions(
                move_members=True, mute_members=True
            ), False, "commander.png"),

            ("︲Клан", discord.Color.from_rgb(155, 89, 182), discord.Permissions.none(), True, "member.png"),
            ("︲1-ый отряд", discord.Color.from_rgb(46, 204, 113), discord.Permissions.none(), False, "squad1.png"),
            ("︲2-ой отряд", discord.Color.from_rgb(155, 89, 182), discord.Permissions.none(), False, "squad2.png"),
            ("︲3-ий отряд", discord.Color.from_rgb(52, 73, 94), discord.Permissions.none(), False, "squad3.png"),

            ("︲Мембер", discord.Color.from_rgb(149, 165, 166), discord.Permissions(
                view_channel=True, send_messages=True, connect=True, speak=True, read_message_history=True
            ), False, "member.png"),
        ]

        roles: dict[str, discord.Role] = {}
        for r_name, r_color, r_perms, r_hoist, icon_file in roles_spec:
            icon_bytes = load_role_icon(icon_file) if can_use_icons else None
            existing_role = discord.utils.get(guild.roles, name=r_name)

            if existing_role:
                roles[r_name] = existing_role
                if can_use_icons and icon_bytes:
                    try:
                        await existing_role.edit(display_icon=icon_bytes)
                    except discord.HTTPException:
                        pass
            else:
                create_kwargs = {
                    "name": r_name,
                    "color": r_color,
                    "permissions": r_perms,
                    "hoist": r_hoist,
                    "mentionable": True,
                }
                if can_use_icons and icon_bytes:
                    create_kwargs["display_icon"] = icon_bytes

                try:
                    roles[r_name] = await guild.create_role(**create_kwargs)
                except discord.HTTPException:
                    create_kwargs.pop("display_icon", None)
                    roles[r_name] = await guild.create_role(**create_kwargs)
                await asyncio.sleep(0.25)

        everyone = guild.default_role
        admin_role = roles["︲Администрация"]
        mod_role = roles["︲Модерация"]
        helper_role = roles["︲Хелпер"]
        cmd_role = roles["︲Капитаны отряда"]
        cap1_role = roles["︲Кэп 1-го отряда"]
        cap2_role = roles["︲Кэп 2-го отряда"]
        cap3_role = roles["︲Кэп 3-го отряда"]
        sq1_role = roles["︲1-ый отряд"]
        sq2_role = roles["︲2-ой отряд"]
        sq3_role = roles["︲3-ий отряд"]
        member_role = roles["︲Мембер"]

        verify_overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True),
            member_role: discord.PermissionOverwrite(view_channel=False),
        }
        read_only_overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            member_role: discord.PermissionOverwrite(view_channel=True, send_messages=False, add_reactions=True),
            mod_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True),
        }
        public_chat_overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            member_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True, speak=True),
        }
        staff_overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True, speak=True),
            mod_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True, speak=True),
            helper_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True, speak=True),
        }
        squads_hq_overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            cmd_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            cap1_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            cap2_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            cap3_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }


        ch_verify = await guild.create_text_channel("🎯︱・верификация", overwrites=verify_overwrites)
        await ch_verify.send(
            view=VerificationView(),
            file=discord.File("assets/verify.png", filename="verify.png"),
        )

        # ——・Информация
        cat_info = await guild.create_category("——・Информация", overwrites=read_only_overwrites)
        ch_welcome = await cat_info.create_text_channel("┌︱👋・приветствие")

        ch_guide = await cat_info.create_text_channel("🔖︱├・памятка")
        guide_msg = await ch_guide.send(view=GuidePanelView(settings, guild.name))

        ch_media = await cat_info.create_text_channel("🎬︱├・медиа")
        media_msg = await ch_media.send(
            view=MediaPanelView(),
            file=discord.File("assets/media.png", filename="media.png"),
        )
        try:
            await media_msg.pin()
        except discord.HTTPException:
            pass

        ch_apps = await cat_info.create_text_channel("🎓︱├・заявки")
        apps_msg = await ch_apps.send(
            view=ApplicationsPanelView(settings),
            file=discord.File("assets/apply.png", filename="apply.png"),
        )

        ch_market = await cat_info.create_text_channel("🛒︱├・рынок")
        market_msg = await ch_market.send(
            view=MarketPanel(),
            file=discord.File("assets/market.png", filename="market.png"),
        )
        try:
            await market_msg.pin()
        except discord.HTTPException:
            pass

        await cat_info.create_text_channel("🎲︱├・события")
        await cat_info.create_text_channel("🔗︱├・партнеры")
        await cat_info.create_text_channel("└︱📫・новости")

        # ——・Чаты
        cat_chats = await guild.create_category("——・Чаты", overwrites=public_chat_overwrites)
        ch_general = await cat_chats.create_text_channel("┌︱💭・общение", slowmode_delay=5)
        ch_photo = await cat_chats.create_text_channel("🔗︱├・фото", slowmode_delay=5)
        ch_commands = await cat_chats.create_text_channel("└︱🎰・команды", slowmode_delay=5)
        cmd_msg = await ch_commands.send(view=CommandsInfoView())
        try:
            await cmd_msg.pin()
        except discord.HTTPException:
            pass

        # ——・Приватные
        cat_priv = await guild.create_category("——・Приватные", overwrites=public_chat_overwrites)
        ch_voice_ctrl = await cat_priv.create_text_channel("┌︱⚪・управление", overwrites=read_only_overwrites)
        await ch_voice_ctrl.send(view=TempVoiceInfoView())
        ch_voice_create = await cat_priv.create_voice_channel("└︱📡・Создать")

        # ——・КОМНАТЫ
        cat_rooms = await guild.create_category("——・КОМНАТЫ", overwrites=public_chat_overwrites)
        room_limits = list((20, 20, 15, 15, 10, 10, 5, 5, 2, 2))
        for idx, limit in enumerate(room_limits, start=1):
            await cat_rooms.create_voice_channel(f"⚪・Комната {idx}", user_limit=limit)
            await asyncio.sleep(0.15)

        # ——・Персонал
        cat_staff = await guild.create_category("——・Персонал", overwrites=staff_overwrites)
        ch_staff_chat = await cat_staff.create_text_channel("┌︱🛡️・чат-персонала")
        ch_staff_cfg = await cat_staff.create_text_channel("⚙️︱├・настройка-персонала")
        staff_cfg_msg = await ch_staff_cfg.send(view=StaffGuideView())
        try:
            await staff_cfg_msg.pin()
        except discord.HTTPException:
            pass
        ch_squad_apps = await cat_staff.create_text_channel("⚔️︱├・заявки-в-отряд")
        ch_staff_apps = await cat_staff.create_text_channel("🎖️︱├・заявки-в-персонал")
        ch_reports = await cat_staff.create_text_channel("⚖️︱├・жалобы")
        await cat_staff.create_voice_channel("└︱🔊・Войс персонала")

        # ——・Отряды 1-3
        cat_squads = await guild.create_category(
            "——・Отряды 1-3",
            overwrites={everyone: discord.PermissionOverwrite(view_channel=False)},
        )
        await cat_squads.create_text_channel("┌︱🎖️・штаб-отрядов", overwrites=squads_hq_overwrites)

        squad_specs = [
            ("1️⃣", 1, sq1_role, cap1_role, False),
            ("2️⃣", 2, sq2_role, cap2_role, False),
            ("3️⃣", 3, sq3_role, cap3_role, True),
        ]
        for emoji_num, num, sq_role, cap_role, _ in squad_specs:
            sq_ow = {
                everyone: discord.PermissionOverwrite(view_channel=False),
                admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True, speak=True),
                cmd_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True, speak=True),
                cap_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True, speak=True),
                sq_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True, speak=True),
            }
            await cat_squads.create_text_channel(f"{emoji_num}︱├・чат-отряд-{num}", overwrites=sq_ow)

        for emoji_num, num, sq_role, cap_role, is_last in squad_specs:
            prefix = "└︱" if is_last else ""
            suffix = "" if is_last else "︱├"
            sq_ow = {
                everyone: discord.PermissionOverwrite(view_channel=False),
                admin_role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
                cmd_role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
                cap_role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
                sq_role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
            }
            await cat_squads.create_voice_channel(f"{prefix}{emoji_num}{suffix}・Войс Отряд {num}", user_limit=15, overwrites=sq_ow)

        # ——・Логи
        cat_logs = await guild.create_category("——・Логи", overwrites=staff_overwrites)
        log_squad = await cat_logs.create_text_channel("┌︱📋・логи-в-отряд")
        log_staff = await cat_logs.create_text_channel("📋︱├・логи-в-персонал")
        log_complaint = await cat_logs.create_text_channel("└︱📋・логи-жалобы")

        settings.update({
            "member_role_id": member_role.id,
            "admin_role_id": admin_role.id,
            "mod_role_id": mod_role.id,
            "helper_role_id": helper_role.id,
            "review_role_id": mod_role.id,
            "verify_channel_id": ch_verify.id,
            "welcome_channel_id": ch_welcome.id,
            "guide_channel_id": ch_guide.id,
            "guide_message_id": guide_msg.id,
            "application_channel_id": ch_apps.id,
            "application_panel_message_id": apps_msg.id,
            "application_category_id": cat_logs.id,
            "application_log_channels": {
                "squad": log_squad.id,
                "staff": log_staff.id,
                "complaint": log_complaint.id,
            },
            "market_channel_id": ch_market.id,
            "general_channel_id": ch_general.id,
            "media_channel_id": ch_photo.id,
            "voice_create_channel_id": ch_voice_create.id,
            "temp_voice_creator_id": ch_voice_create.id,
            "voice_category_id": cat_priv.id,
            "staff_chat_channel_id": ch_staff_chat.id,
            "squad_apps_channel_id": ch_squad_apps.id,
            "staff_apps_channel_id": ch_staff_apps.id,
            "reports_channel_id": ch_reports.id,
        })
        save_settings(guild.id, settings)

        icons_note = (
            f"{emoji_tag('yes')} Пиксельные значки ролей установлены (уровень буста: {guild.premium_tier})."
            if can_use_icons
            else f"{emoji_tag('question')} Значки ролей пропущены (нужен 2-й уровень бустов)."
        )

        try:
            await interaction.followup.send(
                view=StatusLayoutView(
                    "yes",
                    "Настройка сервера завершена!",
                    f"Все категории, каналы, роли, логи и панели успешно созданы и настроены.\n> {icons_note}",
                ),
                ephemeral=True,
            )
        except discord.HTTPException:
            pass


    @app_commands.command(name="server", description="Полная пересборка сервера (удалит старые каналы и создаст новые)")
    @app_commands.default_permissions(administrator=True)
    async def setup_server(self, interaction: discord.Interaction) -> None:
        await self._build_server_structure(interaction, wipe_existing=True)

    @app_commands.command(name="channels", description="Создать недостающие каналы и роли без удаления текущих")
    @app_commands.default_permissions(administrator=True)
    async def setup_channels(self, interaction: discord.Interaction) -> None:
        await self._build_server_structure(interaction, wipe_existing=False)


class SetupSystemCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.setup_group = SetupGroup()

    async def cog_load(self) -> None:
        self.bot.add_view(VerificationView())
        self.bot.add_view(MediaPanelView())
        self.bot.tree.add_command(self.setup_group)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.setup_group.name, type=self.setup_group.type)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type == discord.InteractionType.component and interaction.data:
            if interaction.data.get("custom_id") == "media:publish":
                await interaction.response.send_modal(MediaPostModal())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SetupSystemCog(bot))
