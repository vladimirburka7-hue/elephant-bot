from __future__ import annotations

import re
import discord
from discord import app_commands, ui
from discord.ext import commands
from datetime import datetime

from bot.emojis import emoji_object, emoji_tag
from bot.services.storage import (
    create_application, get_application, get_settings, list_pending_applications,
    set_application_message, update_application_status, log_staff_action, count_applications
)
from bot.ui.containers import QUESTION_SETS, clean_text

STATUS_TEXT = {"approved": "Одобрена", "rejected": "Отклонена", "resolved": "Рассмотрена"}
REJECT_REASONS = {
    "criteria": ("Несовпадение с критериями", "heart5"),
    "fake": ("Неправдивая анкета", "sword"),
    "circumstances": ("Другие обстоятельства", "question"),
    "other": ("Другое", "gear"),
}


class DecisionNoticeView(ui.LayoutView):
    def __init__(self, text: str, emoji_key: str = "yes"):
        super().__init__(timeout=None)
        self.add_item(ui.Container(ui.TextDisplay(f"{emoji_tag(emoji_key)} {clean_text(text, 1800)}")))


async def notify_applicant(bot: commands.Bot, guild_id: int, applicant_id: int, text: str, emoji_key: str) -> None:
    guild = bot.get_guild(guild_id)
    member = guild.get_member(applicant_id) if guild else None
    if member is None and guild:
        try:
            member = await guild.fetch_member(applicant_id)
        except:
            return
    if member:
        try:
            await member.send(view=DecisionNoticeView(text, emoji_key))
        except:
            pass


def can_review(interaction: discord.Interaction) -> bool:
    if not interaction.guild or not isinstance(interaction.user, discord.Member): return False
    settings = get_settings(interaction.guild.id)
    if interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild: return True
    role_id = settings.get("review_role_id")
    return bool(role_id and any(role.id == int(role_id) for role in interaction.user.roles))


class ApplicationModal(ui.Modal):
    def __init__(self, category: str):
        self.category = category
        self.fields: list[tuple[str, ui.TextInput]] = []
        config = QUESTION_SETS[category]
        super().__init__(title=config["title"][:45], timeout=300)
        for index, (label, placeholder, style) in enumerate(config["questions"]):
            field = ui.TextInput(
                custom_id=f"application_{category}_{index}",
                placeholder=placeholder[:100],
                style=style,
                required=True,
                max_length=600,
            )
            self.add_item(ui.Label(text=label[:45], component=field))
            self.fields.append((label, field))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None: return
        settings = get_settings(interaction.guild.id)

        # ПРОВЕРКА ЛИМИТОВ ДЛЯ БЕСПЛАТНОЙ ВЕРСИИ
        if not settings.get("is_active"):
            if count_applications(interaction.guild.id, self.category) >= 5:
                await interaction.response.send_message(
                    "Достигнут лимит бесплатных заявок (5 на категорию). Купите Premium-ключ для снятия ограничений.",
                    ephemeral=True)
                return

        channel_ids = settings.get("application_log_channels", {})
        channel_id = channel_ids.get(self.category) or settings.get("application_inbox_id")
        if not channel_id:
            await interaction.response.send_message("Каналы заявок не настроены.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(int(channel_id))
        if not isinstance(channel, discord.TextChannel):
            try:
                fetched = await interaction.client.fetch_channel(int(channel_id))
                channel = fetched if isinstance(fetched, discord.TextChannel) else None
            except:
                channel = None

        if channel is None:
            await interaction.response.send_message("Канал не найден.", ephemeral=True)
            return

        payload = {
            "server": interaction.guild.name,
            "username": interaction.user.name,
            "display_name": interaction.user.display_name,
            "answers": [(label, clean_text(field.value, 600)) for label, field in self.fields],
        }
        application_id = create_application(interaction.guild.id, interaction.user.id, self.category, payload)
        view = ApplicationReviewView(interaction.client, application_id, interaction.guild.id, interaction.user.id,
                                     self.category, payload, "pending")

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            message = await channel.send(view=view, allowed_mentions=discord.AllowedMentions.none())
        except:
            update_application_status(application_id, "failed")
            await interaction.followup.send("Ошибка отправки в лог-канал.", ephemeral=True)
            return

        set_application_message(application_id, channel.id, message.id)
        interaction.client.add_view(view, message_id=message.id)
        await interaction.followup.send("Заявка отправлена персоналу. Спасибо!", ephemeral=True)


class ApplicationReviewView(ui.LayoutView):
    def __init__(self, bot: commands.Bot, application_id: int, guild_id: int, applicant_id: int, category: str,
                 payload: dict, status: str = "pending"):
        super().__init__(timeout=None)
        self.bot = bot
        self.application_id = application_id
        self.guild_id = guild_id
        self.applicant_id = applicant_id
        self.category = category
        self.payload = payload
        self.status = status

        title = QUESTION_SETS.get(category, {}).get("title", "Заявка")

        lines = [
            f"# {emoji_tag('microphone')} {title} | `#{application_id}`",
            f"> {emoji_tag('member')} **Заявитель:** <@{applicant_id}> · {discord.utils.escape_markdown(payload.get('username', payload.get('display_name', 'Участник')))} · `{applicant_id}`",
            f"> {emoji_tag('key')} **Сервер:** {discord.utils.escape_markdown(payload.get('server', ''))}",
            ""
        ]

        for label, answer in payload.get("answers", []):
            lines.append(f"> {emoji_tag('gear')} **{discord.utils.escape_markdown(label)}:** {clean_text(answer, 600)}")

        lines.append("")
        if status == "pending":
            lines.append(f"> {emoji_tag('question')} **Статус:** Ожидает рассмотрения")
        else:
            lines.append(f"> {emoji_tag('yes')} **Статус:** {STATUS_TEXT.get(status, status)}")

        self.add_item(ui.Container(ui.TextDisplay("\n".join(lines)[:3900])))

        if status == "pending":
            if category in ("squad", "staff"):
                row = ui.ActionRow(
                    ReviewButton("interview", "Вызвать на собеседование", "boost", application_id),
                    ReviewButton("approve", "Одобрить", "yes", application_id),
                    ReviewButton("reject", "Отклонить", "sword", application_id),
                )
            else:
                row = ui.ActionRow(
                    ReviewButton("resolve", "Закрыть жалобу", "yes", application_id),
                    ReviewButton("reject", "Отклонить", "sword", application_id),
                )
            self.add_item(ui.Container(row))

    async def handle_action(self, interaction: discord.Interaction, action: str) -> None:
        if interaction.guild is None or interaction.guild.id != self.guild_id:
            await interaction.response.send_message("Эта кнопка доступна только на исходном сервере.", ephemeral=True)
            return
        if not can_review(interaction):
            await interaction.response.send_message("🚫 Недостаточно прав.", ephemeral=True)
            return

        if action == "approve":
            await interaction.response.send_message(view=RolePickerView(self), ephemeral=True,
                                                    allowed_mentions=discord.AllowedMentions.none())
        elif action == "reject":
            await interaction.response.send_message(view=RejectReasonView(self), ephemeral=True,
                                                    allowed_mentions=discord.AllowedMentions.none())
        elif action == "interview":
            await interaction.response.send_message(view=InterviewChoiceView(self), ephemeral=True,
                                                    allowed_mentions=discord.AllowedMentions.none())
        elif action == "resolve":
            await self.complete(interaction, "resolved", "Жалоба успешно закрыта.")

    async def complete(self, interaction: discord.Interaction, status: str, feedback: str) -> None:
        update_application_status(self.application_id, status)
        await refresh_application_message(self.bot, self.application_id)
        if not interaction.response.is_done():
            await interaction.response.send_message(feedback, ephemeral=True)
        else:
            await interaction.followup.send(feedback, ephemeral=True)


class ReviewButton(ui.Button):
    def __init__(self, action: str, label: str, emoji_key: str, application_id: int, disabled: bool = False):
        super().__init__(label=label, emoji=emoji_object(emoji_key), style=discord.ButtonStyle.secondary,
                         custom_id=f"community:application:{application_id}:{action}", disabled=disabled)
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, ApplicationReviewView):
            await view.handle_action(interaction, self.action)


class RejectReasonSelect(ui.Select):
    def __init__(self, review_view: ApplicationReviewView):
        self.review_view = review_view
        options = [discord.SelectOption(label=name, value=key, emoji=emoji_object(emoji_key)) for key, (name, emoji_key)
                   in REJECT_REASONS.items()]
        super().__init__(placeholder="Выберите причину отказа", options=options,
                         custom_id=f"reject_reason:{review_view.application_id}")

    async def callback(self, interaction: discord.Interaction):
        reason_name, emoji_key = REJECT_REASONS[self.values[0]]
        date_str = datetime.utcnow().strftime("%d.%m.%Y")

        text = (
            f"**{emoji_tag('sword')} Ваша заявка отклонена**\n\n"
            f"> {emoji_tag('key')} **Дата:** `{date_str}`\n"
            f"> {emoji_tag('member')} **Сервер:** `{self.review_view.payload.get('server', 'Неизвестно')}`\n"
            f"> {emoji_tag('gear')} **Тема:** `{QUESTION_SETS[self.review_view.category]['title']}`\n"
            f"> {emoji_tag('question')} **Причина:** `{reason_name}`\n"
            f"> {emoji_tag('staff')} **Проверяющий:** `{interaction.user.name}`\n\n"
            f"*Приносим свои извинения за предоставленные неудобства.*\n"
            f"-# Справа подпись: The p1neyy"
        )

        await self.review_view.complete(interaction, "rejected", f"Заявка отклонена. Причина: {reason_name}")
        await notify_applicant(self.review_view.bot, self.review_view.guild_id, self.review_view.applicant_id, text,
                               "sword")
        log_staff_action(self.review_view.guild_id, interaction.user.id, "Отказ в заявке",
                         f"Пользователь {self.review_view.applicant_id}")
        if self.view: self.view.stop()


class RejectReasonView(ui.LayoutView):
    def __init__(self, review_view: ApplicationReviewView):
        super().__init__(timeout=180)
        self.add_item(ui.Container(
            ui.TextDisplay(f"{emoji_tag('sword')} **Выберите причину отказа:**"),
            ui.ActionRow(RejectReasonSelect(review_view))
        ))


class RoleSelect(ui.RoleSelect):
    def __init__(self, review_view: ApplicationReviewView):
        super().__init__(placeholder="Выберите роли", min_values=1, max_values=25,
                         custom_id=f"community:application:{review_view.application_id}:roles")
        self.review_view = review_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None or not can_review(interaction): return
        member = interaction.guild.get_member(self.review_view.applicant_id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(self.review_view.applicant_id)
            except:
                return
        try:
            await member.add_roles(*self.values, reason=f"Одобрена заявка №{self.review_view.application_id}")
            if self.view: self.view.stop()
        except:
            return
        role_names = ", ".join(role.name for role in self.values)
        await self.review_view.complete(interaction, "approved", f"Одобрено. Роли: {role_names}.")
        await notify_applicant(self.review_view.bot, self.review_view.guild_id, self.review_view.applicant_id,
                               f"Заявка №{self.review_view.application_id} одобрена. Роли: {role_names}.", "yes")
        log_staff_action(self.review_view.guild_id, interaction.user.id, "Одобрение заявки",
                         f"Пользователь {self.review_view.applicant_id}")


class RolePickerView(ui.LayoutView):
    def __init__(self, review_view: ApplicationReviewView):
        super().__init__(timeout=180)
        self.add_item(
            ui.Container(ui.TextDisplay(f"{emoji_tag('yes')} Выберите роли:"), ui.ActionRow(RoleSelect(review_view))))


class InterviewChoiceButton(ui.Button):
    def __init__(self, kind: str, label: str, emoji_key: str, review_view: ApplicationReviewView):
        super().__init__(label=label, emoji=emoji_object(emoji_key), style=discord.ButtonStyle.secondary,
                         custom_id=f"community:interview:{review_view.application_id}:{kind}")
        self.kind = kind
        self.review_view = review_view

    async def callback(self, interaction: discord.Interaction):
        view = self.review_view
        if interaction.guild is None or not can_review(interaction): return
        settings = get_settings(interaction.guild.id)
        category_id = settings.get("application_category_id")
        category = interaction.guild.get_channel(int(category_id)) if category_id else None
        if not isinstance(category, discord.CategoryChannel): return
        applicant = interaction.guild.get_member(view.applicant_id)
        if not applicant: return
        prefix = "беседа" if self.kind == "text" else "собеседование"
        numbers = [int(m.group(1)) for ch in category.channels if (m := re.fullmatch(rf"{prefix}-0-(\d+)", ch.name))]
        name = f"{prefix}-0-{max(numbers, default=0) + 1}"

        is_text = self.kind == "text"
        is_voice = self.kind == "voice"
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            applicant: discord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=is_text,
                                                   connect=is_voice, speak=is_voice),
            interaction.user: discord.PermissionOverwrite(view_channel=True, read_message_history=True,
                                                          send_messages=is_text, connect=is_voice, speak=is_voice),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True,
                                                              speak=True),
        }
        try:
            if self.kind == "text":
                created = await interaction.guild.create_text_channel(name=name, category=category,
                                                                      overwrites=overwrites)
            else:
                created = await interaction.guild.create_voice_channel(name=name, category=category,
                                                                       overwrites=overwrites)
        except:
            await interaction.response.send_message("Ошибка создания канала.", ephemeral=True)
            return

        if self.view: self.view.stop()
        await interaction.response.send_message(f"Создан канал {created.mention}", ephemeral=True)


class InterviewChoiceView(ui.LayoutView):
    def __init__(self, review_view: ApplicationReviewView):
        super().__init__(timeout=180)
        self.add_item(ui.Container(
            ui.TextDisplay("Выберите формат собеседования:"),
            ui.ActionRow(
                InterviewChoiceButton("text", "Текстовый чат", "staff", review_view),
                InterviewChoiceButton("voice", "Голосовой канал", "microphone", review_view),
            ),
        ))


async def refresh_application_message(bot: commands.Bot, application_id: int) -> None:
    record = get_application(application_id)
    if not record or not record.get("channel_id") or not record.get("message_id"): return
    guild = bot.get_guild(int(record["guild_id"]))
    channel = guild.get_channel(int(record["channel_id"])) if guild else None
    if not isinstance(channel, discord.TextChannel): return
    try:
        message = await channel.fetch_message(int(record["message_id"]))
        view = ApplicationReviewView(bot, application_id, int(record["guild_id"]), int(record["applicant_id"]),
                                     record["category"], record["payload"], record["status"])
        await message.edit(view=view)
    except:
        return


class Applications(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def open_modal(self, interaction: discord.Interaction, category: str) -> None:
        await interaction.response.send_modal(ApplicationModal(category))

    async def restore_pending_views(self) -> None:
        for record in list_pending_applications():
            try:
                application = get_application(int(record["id"]))
                if not application: continue
                view = ApplicationReviewView(self.bot, int(application["id"]), int(application["guild_id"]),
                                             int(application["applicant_id"]), application["category"],
                                             application["payload"], application["status"])
                self.bot.add_view(view, message_id=int(application["message_id"]))
            except:
                continue


async def setup(bot: commands.Bot) -> None:
    cog = Applications(bot)
    await bot.add_cog(cog)
    await cog.restore_pending_views()