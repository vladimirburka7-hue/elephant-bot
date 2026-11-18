"""Компоненты V2: панели заявок, памятка, приветствие и карточки заявок."""
from __future__ import annotations

import discord
from discord import ui

from bot.emojis import emoji_object, emoji_tag
from bot.services.storage import DEFAULT_SETTINGS

QUESTION_SETS = {
    "squad": {
        "title": "Заявка в отряд",
        "questions": [
            ("Ваш игровой ник", "Укажите игровой ник", discord.TextStyle.short),
            ("Ваш возраст", "Укажите возраст", discord.TextStyle.short),
            ("Еженедельный онлайн", "Сколько часов в неделю вы играете?", discord.TextStyle.short),
            ("Опыт игры и кланы", "Расскажите об игровом опыте", discord.TextStyle.paragraph),
            ("Почему хотите вступить?", "Почему хотите именно к нам?", discord.TextStyle.paragraph),
        ],
    },
    "staff": {
        "title": "Заявка в персонал",
        "questions": [
            ("Ваш ник", "Укажите никнейм", discord.TextStyle.short),
            ("Ваш возраст", "Укажите возраст", discord.TextStyle.short),
            ("Опыт персонала", "Где и кем работали? Укажите опыт", discord.TextStyle.paragraph),
            ("Ваш онлайн", "Сколько часов в неделю вы доступны?", discord.TextStyle.short),
            ("Почему вы подходите?", "Расскажите о мотивации и навыках", discord.TextStyle.paragraph),
        ],
    },
    "complaint": {
        "title": "Жалоба",
        "questions": [
            ("На кого жалоба?", "Укажите никнейм и, если знаете, ID", discord.TextStyle.short),
            ("Что произошло?", "Опишите ситуацию подробно", discord.TextStyle.paragraph),
            ("Когда это произошло?", "Дата и примерное время", discord.TextStyle.short),
            ("Есть ли свидетели?", "Укажите участников или напишите «нет»", discord.TextStyle.short),
            ("Доказательства", "Ссылки на скриншоты/видео или описание", discord.TextStyle.paragraph),
        ],
    },
}


def clean_text(value: str, max_length: int = 900) -> str:
    value = discord.utils.escape_mentions(value.strip())
    return value[:max_length] if value else "—"


def replace_server(text: str, server_name: str) -> str:
    return text.replace("{server}", discord.utils.escape_markdown(server_name))


class RulesView(ui.LayoutView):
    """Эфемерные правила из присланного образца; видны только нажавшему."""
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(ui.Container(
            ui.TextDisplay(
                f"# {emoji_tag('owner')} Правилам подчиняются все\n"
                "Исключений нет. Администрация вправе действовать по своему усмотрению. "
                "Если вас не устраивает выданный мут, предупреждение и т. д., "
                "обращайтесь к администрации сервера."
            ),
            ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay(
                f"## {emoji_tag('num1')} · Общее поведение\n"
                "> Относитесь ко всем участникам с уважением.\n"
                "> Оскорбления, травля и провокации запрещены.\n"
                "> Дискриминация и разжигание вражды запрещены.\n"
                "> Конфликты решайте спокойно, при необходимости — через администрацию.\n"
                "> Решения руководства не обсуждаются в общих каналах."
            ),
            ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay(
                f"## {emoji_tag('num2')} · Чат и контент\n"
                "> Пишите в каналах строго по теме.\n"
                "> Спам, флуд, капс и злоупотребление упоминаниями запрещены.\n"
                "> Реклама сторонних серверов, сайтов и услуг запрещена.\n"
                "> NSFW, шок-контент, угрозы и призывы к насилию запрещены.\n"
                "> Чужие личные данные и переписки нельзя публиковать без согласия."
            ),
            ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay(
                f"## {emoji_tag('num3')} · Ответственность\n"
                "> Соблюдайте правила. Незнание правил не освобождает от наказания. "
                "При повторных нарушениях наказание может быть строже."
            ),
        ))


class RolesView(ui.LayoutView):
    """Эфемерный актуальный список ролей текущего сервера."""
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=180)
        role_lines = []
        for role in reversed(guild.roles):
            if role.is_default() or role.managed:
                continue
            line = f"<@&{role.id}>"
            if sum(map(len, role_lines)) + len(line) + 1 > 3500:
                role_lines.append("… список сокращён, слишком много ролей.")
                break
            role_lines.append(line)
        body = "\n".join(role_lines) if role_lines else "На сервере пока нет ролей."
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('yes')} Роли сервера\n{body}")
        ))


class AboutView(ui.LayoutView):
    """Эфемерная справка о боте в стиле присланного образца."""
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(ui.Container(
            ui.TextDisplay(
                f"# {emoji_tag('boost')} Elephant. Платный бот. Действует система ключей."
            ),
            ui.TextDisplay(
                f"> {emoji_tag('gear')} Действует система ключей. Без ключа доступ к боту будет невозможен. "
                "Бот не предназначен для разрушения серверов или действий против них — "
                "он создан для вспомогательных целей."
            ),
            ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay(
                f"> {emoji_tag('member')} Discord создателя: **thep1neyyy**. "
                "Если у вас есть замечания или предложения, обратитесь к владельцу бота "
                "и укажите, по какому именно вопросу пишете."
            ),
            ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay(
                f"> {emoji_tag('robot')} Благодарим за внимание! Покупка ключей проходит только у владельца. "
                "На данный момент магазинов, серверов или сайтов для покупки нет. "
                "Если бот временно не работает, вероятно, идут обновление или исправление ошибок."
            ),
        ))


class ApplyButton(ui.Button):
    def __init__(self, label: str, emoji_key: str, category: str):
        super().__init__(
            label=label,
            emoji=emoji_object(emoji_key),
            style=discord.ButtonStyle.secondary,
            custom_id=f"community:apply:{category}",
        )
        self.category = category

    async def callback(self, interaction: discord.Interaction) -> None:
        cog = interaction.client.get_cog("Applications")
        if cog is None:
            await interaction.response.send_message("Сейчас формы недоступны. Попробуйте позже.", ephemeral=True)
            return
        await cog.open_modal(interaction, self.category)


class GuideButton(ui.Button):
    def __init__(self, label: str, emoji_key: str, detail_key: str):
        super().__init__(
            label=label, emoji=emoji_object(emoji_key), style=discord.ButtonStyle.secondary,
            custom_id=f"community:guide:{detail_key}",
        )
        self.detail_key = detail_key

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Кнопка доступна только на сервере.", ephemeral=True)
            return
        if self.detail_key == "rules":
            view = RulesView()
        elif self.detail_key == "roles":
            view = RolesView(interaction.guild)
        else:
            view = AboutView()
        await interaction.response.send_message(
            view=view,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


class ApplicationsPanelView(ui.LayoutView):
    def __init__(self, settings: dict | None = None):
        super().__init__(timeout=None)
        settings = settings or DEFAULT_SETTINGS
        title = clean_text(settings.get("application_title", "Подача заявок"), 100)
        intro = clean_text(settings.get("application_intro", DEFAULT_SETTINGS["application_intro"]), 850)
        note = clean_text(settings.get("application_note", DEFAULT_SETTINGS["application_note"]), 850)
        buttons = ui.ActionRow(
            ApplyButton("Отряд", "gamepad", "squad"),
            ApplyButton("Персонал", "boost", "staff"),
            ApplyButton("Жалоба", "question", "complaint"),
        )
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('flag')} {title}"),
            ui.TextDisplay(f"> {emoji_tag('key')} {intro}"),
            ui.TextDisplay(f"> {emoji_tag('yes')} {note}"),
            ui.Separator(spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay(f"> {emoji_tag('heart5')} Спасибо за заполнение анкеты. Мы рассмотрим её как можно скорее."),
            ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            buttons,
        ))


class GuidePanelView(ui.LayoutView):
    def __init__(self, settings: dict | None = None, server_name: str = "Наш сервер"):
        super().__init__(timeout=None)
        settings = settings or DEFAULT_SETTINGS
        server_name = discord.utils.escape_markdown(server_name)
        configured_title = settings.get("guide_title", "{server}").strip()
        if configured_title.casefold() in {"название сервера", "{server}", ""}:
            configured_title = "{server}"
        title = replace_server(configured_title, server_name)
        intro = replace_server(settings.get("guide_intro", DEFAULT_SETTINGS["guide_intro"]), server_name)
        activity = replace_server(settings.get("guide_activity", DEFAULT_SETTINGS["guide_activity"]), server_name)
        important = replace_server(settings.get("guide_important", DEFAULT_SETTINGS["guide_important"]), server_name)
        buttons = ui.ActionRow(
            GuideButton("Правила", "flag", "rules"),
            GuideButton("Роли", "yes", "roles"),
            GuideButton("О боте", "robot", "about"),
        )
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('sprout')} {clean_text(title, 100)}"),
            ui.TextDisplay(f"> {emoji_tag('key')} {clean_text(intro, 850)}"),
            ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay(f"## {emoji_tag('diamond')} Чем мы занимаемся?"),
            ui.TextDisplay(f"> {clean_text(activity, 850)}"),
            ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay(f"## {emoji_tag('star')} Важные моменты!"),
            ui.TextDisplay(f"> {clean_text(important, 850)}"),
            ui.Separator(spacing=discord.SeparatorSpacing.large),
            buttons,
        ))


class SubmissionView(ui.LayoutView):
    """Старая совместимая карточка; интерактивная карточка находится в cogs/applications.py."""
    def __init__(self, text: str):
        super().__init__(timeout=None)
        self.add_item(ui.Container(ui.TextDisplay(text[:3900])))


class WelcomeView(ui.LayoutView):
    def __init__(self, member: discord.Member, join_number: int, member_count: int, boost_count: int):
        super().__init__(timeout=None)
        created = int(member.created_at.timestamp())
        safe_name = discord.utils.escape_markdown(member.display_name)
        heading = ui.Section(
            ui.TextDisplay(f"{emoji_tag('member')} **{safe_name}, снова с нами!**"),
            accessory=ui.Thumbnail(member.display_avatar.url),
        )
        self.add_item(ui.Container(
            heading,
            ui.TextDisplay(f"{emoji_tag('trophy')} В Discord с <t:{created}:D> (<t:{created}:R>)"),
            ui.TextDisplay(f"{emoji_tag('microphone')} Уже присоединялся **{join_number} раз!**"),
            ui.TextDisplay(
                f"{emoji_tag('sprout')} Сейчас с нами **{member_count} участников** и "
                f"**{boost_count}** {emoji_tag('boost')} бустов"
            ),
            ui.Separator(spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay(f"{discord.utils.escape_markdown(member.name)} · `{member.id}`"),
        ))
