import discord
from discord import app_commands, ui
from discord.ext import commands
from bot.emojis import emoji_object, emoji_tag
from bot.services.storage import get_settings, save_settings


def format_user_tag(user: discord.abc.User) -> str:
    safe_name = discord.utils.escape_markdown(user.name)
    return f"{user.mention} · {safe_name} · `{user.id}`"


class RoleSelect(ui.Select):
    def __init__(self, roles):
        options = [discord.SelectOption(label=role.name, value=str(role.id), emoji=emoji_object("member")) for role in
                   roles[:25]]
        super().__init__(placeholder="Выберите роль для получения", options=options, custom_id="tk:role_select")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)

        if not role:
            await interaction.followup.send("Роль не найдена.", ephemeral=True)
            return

        try:
            await interaction.user.add_roles(role)
        except discord.Forbidden:
            await interaction.followup.send("У бота нет прав на выдачу этой роли.", ephemeral=True)
            return

        settings = get_settings(interaction.guild.id)
        cat_id = settings.get("tickets_category_id") or settings.get("ticket_category_id")
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        cat = interaction.guild.get_channel(int(cat_id)) if cat_id else None
        ch = await interaction.guild.create_text_channel(f"роль-{interaction.user.name}", category=cat,
                                                         overwrites=overwrites)

        view = ui.LayoutView()
        view.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('yes')} Роль выдана"),
            ui.TextDisplay(f"> {emoji_tag('member')} Пользователь: {format_user_tag(interaction.user)}"),
            ui.TextDisplay(f"> {emoji_tag('key')} Роль: {role.mention}"),
            ui.ActionRow(ui.Button(label="Закрыть", style=discord.ButtonStyle.secondary, custom_id="tk:close"))
        ))
        await ch.send(view=view)
        await interaction.followup.send(f"Роль {role.mention} выдана! Тикет: {ch.mention}", ephemeral=True)


class TicketCreate(ui.Button):
    def __init__(self):
        super().__init__(
            label="Создать тикет",
            emoji=emoji_object("staff"),
            style=discord.ButtonStyle.secondary,
            custom_id="tk:create"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        settings = get_settings(interaction.guild.id)
        cat_id = settings.get("tickets_category_id") or settings.get("ticket_category_id")
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        cat = interaction.guild.get_channel(int(cat_id)) if cat_id else None
        ch = await interaction.guild.create_text_channel(f"тикет-{interaction.user.name}", category=cat,
                                                         overwrites=overwrites)

        view = ui.LayoutView()
        view.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('question')} Тикет"),
            ui.TextDisplay(f"> {emoji_tag('member')} Автор: {format_user_tag(interaction.user)}"),
            ui.ActionRow(ui.Button(label="Закрыть", style=discord.ButtonStyle.secondary, custom_id="tk:close"))
        ))
        await ch.send(view=view)
        await interaction.followup.send(f"Тикет создан: {ch.mention}", ephemeral=True)


class TicketPanel(ui.LayoutView):
    def __init__(self, roles: list = None):
        super().__init__(timeout=None)
        items = [
            ui.TextDisplay(f"# {emoji_tag('question')} Поддержка"),
            ui.TextDisplay(f"> {emoji_tag('key')} Выберите действие ниже."),
            ui.ActionRow(TicketCreate())
        ]
        if roles:
            items.append(ui.Separator())
            items.append(ui.TextDisplay(f"### {emoji_tag('member')} Выдача ролей"))
            items.append(ui.ActionRow(RoleSelect(roles)))
        self.add_item(ui.Container(*items))


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(TicketPanel())

    @app_commands.command(name="setup_tickets", description="Создать панель тикетов и ролей")
    @app_commands.describe(roles="Роли через запятую (@Роль1, @Роль2)")
    async def setup_tickets(self, interaction: discord.Interaction, category: discord.CategoryChannel,
                            roles: str = None):
        settings = get_settings(interaction.guild.id)
        settings["tickets_category_id"] = category.id
        settings["ticket_category_id"] = category.id
        save_settings(interaction.guild.id, settings)

        role_objects = []
        if roles:
            for r_id in roles.split(","):
                r = interaction.guild.get_role(int(r_id.strip().replace("<@&", "").replace(">", "")))
                if r:
                    role_objects.append(r)

        await interaction.response.send_message(view=TicketPanel(role_objects))

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component and interaction.data.get("custom_id") == "tk:close":
            if interaction.user.guild_permissions.manage_channels:
                await interaction.response.send_message("Удаляю...", ephemeral=True)
                await interaction.channel.delete()
            else:
                await interaction.response.send_message("Только персонал может закрыть.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tickets(bot))