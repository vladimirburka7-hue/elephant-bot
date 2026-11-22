import discord
from discord import app_commands, ui
from discord.ext import commands
from bot.emojis import emoji_object, emoji_tag


class RoleButton(ui.Button):
    def __init__(self, role: discord.Role):
        super().__init__(label=role.name, style=discord.ButtonStyle.secondary, custom_id=f"rr:{role.id}")
        self.role_id = role.id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if not role: return
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"Роль {role.mention} снята.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"Роль {role.mention} выдана.", ephemeral=True)


class ReactionRolesPanel(ui.LayoutView):
    def __init__(self, roles: list[discord.Role]):
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('member')} Выбор ролей"),
            ui.TextDisplay(f"> {emoji_tag('key')} Нажмите на кнопку, чтобы получить или снять роль."),
            ui.ActionRow(*[RoleButton(r) for r in roles[:5]])  # Максимум 5 кнопок в ряд
        ))


class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup_roles", description="Создать панель выдачи ролей")
    @app_commands.default_permissions(administrator=True)
    async def setup_roles(self, interaction: discord.Interaction, channel: discord.TextChannel, roles: str):
        # roles передаются через запятую: @Role1,@Role2
        role_objects = []
        for r_id in roles.split(","):
            r = interaction.guild.get_role(int(r_id.strip().replace("<@&", "").replace(">", "")))
            if r: role_objects.append(r)

        if not role_objects:
            await interaction.response.send_message("Не удалось найти роли. Укажите ID или упоминания.", ephemeral=True)
            return

        await channel.send(view=ReactionRolesPanel(role_objects))
        await interaction.response.send_message("Панель ролей создана.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))