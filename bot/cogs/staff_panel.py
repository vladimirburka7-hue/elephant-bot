import discord
from discord import app_commands, ui
from discord.ext import commands
from bot.emojis import emoji_object, emoji_tag
from bot.services.storage import get_settings, save_settings
import datetime


# ==========================================
# 1. МОДАЛКА ДЛЯ МУТА (Только она осталась)
# ==========================================

class MuteModal(ui.Modal):
    def __init__(self, target: discord.Member):
        super().__init__(title=f"Мут: {target.name}"[:45])
        self.target = target
        self.minutes = ui.TextInput(label="На сколько минут", default="15", max_length=5)
        self.reason = ui.TextInput(label="Причина", required=False, max_length=200)
        self.add_item(self.minutes)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            mins = int(self.minutes.value)
            until = discord.utils.utcnow() + datetime.timedelta(minutes=mins)
            await self.target.timeout(until, reason=self.reason.value or "Мут от персонала")
            await interaction.response.send_message(
                f"{emoji_tag('yes')} {self.target.mention} в муте на **{mins} мин**.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Введите число.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("У бота нет прав на мут.", ephemeral=True)


class SelectUserForMute(ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="Выберите пользователя для мута", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MuteModal(self.values[0]))


# ==========================================
# 2. ВЫБОР КАНАЛОВ И РОЛЕЙ (Списки вместо ID)
# ==========================================

class MarketChannelSelect(ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="Канал для Рынка", channel_types=[discord.ChannelType.text])

    async def callback(self, interaction: discord.Interaction):
        settings = get_settings(interaction.guild.id)
        settings["market_channel_id"] = self.values[0].id
        save_settings(interaction.guild.id, settings)
        await interaction.response.send_message(f"{emoji_tag('yes')} Рынок установлен в {self.values[0].mention}",
                                                ephemeral=True)


class WelcomeChannelSelect(ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="Канал для Приветствий", channel_types=[discord.ChannelType.text])

    async def callback(self, interaction: discord.Interaction):
        settings = get_settings(interaction.guild.id)
        settings["welcome_channel_id"] = self.values[0].id
        save_settings(interaction.guild.id, settings)
        await interaction.response.send_message(
            f"{emoji_tag('yes')} Приветствия установлены в {self.values[0].mention}", ephemeral=True)


class TicketCategorySelect(ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="Категория для Тикетов", channel_types=[discord.ChannelType.category])

    async def callback(self, interaction: discord.Interaction):
        settings = get_settings(interaction.guild.id)
        settings["ticket_category_id"] = self.values[0].id
        save_settings(interaction.guild.id, settings)
        await interaction.response.send_message(
            f"{emoji_tag('yes')} Тикеты будут создаваться в категории {self.values[0].name}", ephemeral=True)


class VoiceChannelSelect(ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="Канал 'Создать' для войсов", channel_types=[discord.ChannelType.voice])

    async def callback(self, interaction: discord.Interaction):
        settings = get_settings(interaction.guild.id)
        settings["temp_voice_creator_id"] = self.values[0].id
        save_settings(interaction.guild.id, settings)
        await interaction.response.send_message(
            f"{emoji_tag('yes')} Временные войсы привязаны к {self.values[0].mention}", ephemeral=True)


class ReviewerRoleSelect(ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Роль Проверяющего (Заявки)")

    async def callback(self, interaction: discord.Interaction):
        settings = get_settings(interaction.guild.id)
        settings["review_role_id"] = self.values[0].id
        save_settings(interaction.guild.id, settings)
        await interaction.response.send_message(f"{emoji_tag('yes')} Роль проверяющего: {self.values[0].mention}",
                                                ephemeral=True)


class StaffRoleSelect(ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Роль Персонала (Тикеты)")

    async def callback(self, interaction: discord.Interaction):
        settings = get_settings(interaction.guild.id)
        settings["ticket_staff_role_id"] = self.values[0].id
        save_settings(interaction.guild.id, settings)
        await interaction.response.send_message(f"{emoji_tag('yes')} Роль персонала: {self.values[0].mention}",
                                                ephemeral=True)


# ==========================================
# 3. ГЛАВНОЕ МЕНЮ
# ==========================================

class BigMenuSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Настроить каналы", description="Рынок, тикеты, войсы", value="setup_channels",
                                 emoji=emoji_object("key")),
            discord.SelectOption(label="Настроить роли", description="Проверяющий, персонал", value="setup_roles",
                                 emoji=emoji_object("medal")),
            discord.SelectOption(label="Выдать мут", description="Наказать нарушителя", value="mod_mute",
                                 emoji=emoji_object("microphone")),
            discord.SelectOption(label="Создать Рынок", description="Панель объявлений", value="panel_market",
                                 emoji=emoji_object("diamond")),
            discord.SelectOption(label="Создать Тикеты", description="Панель поддержки", value="panel_tickets",
                                 emoji=emoji_object("staff")),
        ]
        super().__init__(placeholder="Выберите пункт из списка...", options=options, custom_id="big_menu")

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]

        if val == "setup_channels":
            view = ui.LayoutView()
            view.add_item(ui.Container(
                ui.TextDisplay(f"# {emoji_tag('gear')} Выбор каналов"),
                ui.TextDisplay(f"> {emoji_tag('key')} Выберите каналы из списков ниже."),
                ui.ActionRow(MarketChannelSelect()),
                ui.ActionRow(WelcomeChannelSelect()),
                ui.ActionRow(TicketCategorySelect()),
                ui.ActionRow(VoiceChannelSelect())
            ))
            await interaction.response.send_message(view=view, ephemeral=True)

        elif val == "setup_roles":
            view = ui.LayoutView()
            view.add_item(ui.Container(
                ui.TextDisplay(f"# {emoji_tag('medal')} Выбор ролей"),
                ui.TextDisplay(f"> {emoji_tag('key')} Выберите роли из списков ниже."),
                ui.ActionRow(ReviewerRoleSelect()),
                ui.ActionRow(StaffRoleSelect())
            ))
            await interaction.response.send_message(view=view, ephemeral=True)

        elif val == "mod_mute":
            view = ui.LayoutView()
            view.add_item(ui.Container(
                ui.TextDisplay(f"# {emoji_tag('member')} Выберите нарушителя"),
                ui.ActionRow(SelectUserForMute())
            ))
            await interaction.response.send_message(view=view, ephemeral=True)

        elif val == "panel_market":
            from bot.cogs.market import MarketPanel
            await interaction.channel.send(view=MarketPanel())
            await interaction.response.send_message("Панель рынка создана!", ephemeral=True)

        elif val == "panel_tickets":
            from bot.cogs.tickets import TicketPanel
            await interaction.channel.send(view=TicketPanel())
            await interaction.response.send_message("Панель тикетов создана!", ephemeral=True)


# ==========================================
# 4. ОСНОВНОЙ КЛАСС
# ==========================================

class StaffPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Меню управления сервером")
    @app_commands.default_permissions(administrator=True)
    async def setup_menu(self, interaction: discord.Interaction):
        view = ui.LayoutView()
        view.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('gear')} Меню управления"),
            ui.TextDisplay(f"> {emoji_tag('key')} Выберите пункт ниже."),
            ui.ActionRow(BigMenuSelect())
        ))
        await interaction.response.send_message(view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffPanel(bot))