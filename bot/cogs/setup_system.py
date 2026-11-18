from __future__ import annotations

import asyncio
import logging
import discord
from discord import app_commands, ui
from discord.ext import commands

from bot.emojis import emoji_object, emoji_tag
from bot.services.storage import get_settings, save_settings
from bot.ui.containers import ApplicationsPanelView, GuidePanelView
from bot.cogs.tickets import TicketPanel
from bot.cogs.market import MarketPanel

log = logging.getLogger("community_bot.setup")


# =====================================================================
# V2 LAYOUT VIEWS (Строго с вашими белыми пиксельными эмодзи)
# =====================================================================

class VerificationView(ui.LayoutView):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('yes')} Верификация"),
            ui.TextDisplay(f"> {emoji_tag('key')} Нажми на кнопку ниже, чтобы подтвердить аккаунт и открыть доступ к каналам сервера."),
            ui.ActionRow(
                ui.Button(
                    label="Верифицироваться",
                    emoji=emoji_object("yes"),
                    style=discord.ButtonStyle.secondary,
                    custom_id="verify:btn"
                )
            )
        ))


class TempVoiceInfoView(ui.LayoutView):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('microphone')} Управление приватными комнатами"),
            ui.TextDisplay(
                f"> {emoji_tag('key')} Зайди в голосовой канал **└︱📡・Создать** ниже, чтобы создать свою личную комнату.\n"
                f"> {emoji_tag('gear')} После создания ты сможешь настроить лимит, название и доступ для друзей."
            )
        ))


class RulesPanelView(ui.LayoutView):
    def __init__(self, server_name: str) -> None:
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('star')} Правила сообщества {server_name}"),
            ui.TextDisplay(
                f"**{emoji_tag('num1')} Уважение.** Запрещены оскорбления, травля, токсичность и провокации участников.\n"
                f"**{emoji_tag('num2')} Адекватность.** Запрещен спам, флуд, злоупотребление капсом и пингами.\n"
                f"**{emoji_tag('num3')} Контент и реклама.** Запрещен NSFW/18+ контент и любая сторонняя реклама без согласования.\n"
                f"**{emoji_tag('flag')} Голосовые каналы.** Не мешайте общению (саундпады, крики и смена голоса без согласия).\n\n"
                f"> {emoji_tag('staff')} *Незнание правил не освобождает от ответственности. Решение персонала является окончательным.*"
            )
        ))


class StatusLayoutView(ui.LayoutView):
    def __init__(self, title_emoji: str, title: str, description: str) -> None:
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.TextDisplay(f"### {emoji_tag(title_emoji)} {title}"),
            ui.TextDisplay(description)
        ))


# =====================================================================
# КОМАНДЫ НАСТРОЙКИ (/setup server и /setup channels)
# =====================================================================

class SetupGroup(app_commands.Group):
    def __init__(self) -> None:
        super().__init__(name="setup", description="Автоматическая настройка и сборка сервера")

    async def _build_server_structure(self, interaction: discord.Interaction, wipe_existing: bool) -> None:
        guild = interaction.guild
        if not guild:
            return

        settings = get_settings(guild.id)
        if not settings.get("is_active"):
            await interaction.response.send_message(
                view=StatusLayoutView("question", "Доступ закрыт", f"{emoji_tag('key')} Бот не активирован. Используйте `/activate <ключ>`."),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            view=StatusLayoutView("gear", "Запуск настройки", f"{emoji_tag('robot')} Начинаю сборку структуры сервера. Это займет около 15–20 секунд..."),
            ephemeral=True
        )

        # 1. Очистка старых каналов (только при /setup server)
        if wipe_existing:
            for channel in list(guild.channels):
                try:
                    await channel.delete(reason="Полная пересборка сервера (/setup server)")
                    await asyncio.sleep(0.2)
                except discord.HTTPException:
                    pass

        # 2. Создание иерархии ролей с цветами и правами
        roles_spec = [
            ("👑・Владелец", discord.Color.from_rgb(241, 196, 15), discord.Permissions(administrator=True), True),
            ("🛡️・Администратор", discord.Color.from_rgb(231, 76, 60), discord.Permissions(administrator=True), True),
            ("🔨・Модератор", discord.Color.from_rgb(52, 152, 219), discord.Permissions(
                manage_messages=True, kick_members=True, ban_members=True, moderate_members=True, mute_members=True, move_members=True
            ), True),
            ("🎗️・Хелпер", discord.Color.from_rgb(26, 188, 156), discord.Permissions(
                manage_messages=True, moderate_members=True, mute_members=True
            ), True),
            ("⚔️・Командир отряда", discord.Color.from_rgb(230, 126, 34), discord.Permissions(
                move_members=True, mute_members=True, priority_speaker=True
            ), True),
            ("1️⃣・Отряд 1", discord.Color.from_rgb(46, 204, 113), discord.Permissions.none(), False),
            ("2️⃣・Отряд 2", discord.Color.from_rgb(155, 89, 182), discord.Permissions.none(), False),
            ("3️⃣・Отряд 3", discord.Color.from_rgb(233, 30, 99), discord.Permissions.none(), False),
            ("💎・VIP", discord.Color.from_rgb(244, 127, 255), discord.Permissions.none(), True),
            ("👤・Участник", discord.Color.from_rgb(149, 165, 166), discord.Permissions(
                view_channel=True, send_messages=True, connect=True, speak=True, read_message_history=True
            ), False),
        ]

        roles: dict[str, discord.Role] = {}
        for r_name, r_color, r_perms, r_hoist in roles_spec:
            existing_role = discord.utils.get(guild.roles, name=r_name)
            if existing_role:
                roles[r_name] = existing_role
            else:
                roles[r_name] = await guild.create_role(
                    name=r_name, color=r_color, permissions=r_perms, hoist=r_hoist, mentionable=True
                )
                await asyncio.sleep(0.25)

        everyone = guild.default_role
        admin_role = roles["🛡️・Администратор"]
        mod_role = roles["🔨・Модератор"]
        helper_role = roles["🎗️・Хелпер"]
        cmd_role = roles["⚔️・Командир отряда"]
        sq1_role = roles["1️⃣・Отряд 1"]
        sq2_role = roles["2️⃣・Отряд 2"]
        sq3_role = roles["3️⃣・Отряд 3"]
        member_role = roles["👤・Участник"]

        # Базовые права доступа
        # Новички без роли Участник видят только верификацию
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

        # 3. Канал верификации (вне категорий)
        ch_verify = await guild.create_text_channel("┌︱✅・верификация", overwrites=verify_overwrites)

        # 4. Категория: ——・Информация
        cat_info = await guild.create_category("——・Информация", overwrites=read_only_overwrites)
        ch_rules = await guild.create_text_channel("┌︱📖・правила", category=cat_info)
        ch_guide = await guild.create_text_channel("🔖︱├・памятка", category=cat_info)
        ch_giveaways = await guild.create_text_channel("🎉︱├・розыгрыши", category=cat_info)
        ch_apps = await guild.create_text_channel("🎓︱├・заявки", category=cat_info)
        ch_events = await guild.create_text_channel("🎲︱├・события", category=cat_info)
        ch_partners = await guild.create_text_channel("🔗︱├・партнеры", category=cat_info)
        ch_news = await guild.create_text_channel("└︱📬・новости", category=cat_info)

        # 5. Категория: ——・Чаты
        cat_chats = await guild.create_category("——・Чаты", overwrites=public_chat_overwrites)
        ch_welcome = await guild.create_text_channel("┌︱👋・приветствие", category=cat_chats, overwrites=read_only_overwrites)
        ch_chat = await guild.create_text_channel("💭︱├・общение", category=cat_chats)
        ch_media = await guild.create_text_channel("🔗︱├・фото", category=cat_chats)
        ch_market = await guild.create_text_channel("🛒︱├・рынок", category=cat_chats)
