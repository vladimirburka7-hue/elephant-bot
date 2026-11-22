import discord
from discord import app_commands, ui
from discord.ext import commands
from bot.emojis import emoji_tag

class MediaView(ui.LayoutView):
    def __init__(self, author: discord.Member, title: str, text: str, url: str):
        super().__init__(timeout=None)
        heading = ui.Section(
            ui.TextDisplay(f"# {emoji_tag('star')} {title}"),
            accessory=ui.Thumbnail(author.display_avatar.url)
        )
        self.add_item(ui.Container(
            heading,
            ui.TextDisplay(f"> {emoji_tag('member')} {author.mention}"),
            ui.Separator(spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay(text),
            ui.Separator(spacing=discord.SeparatorSpacing.large),
            ui.ActionRow(ui.Button(label="Перейти", url=url, style=discord.ButtonStyle.link, emoji="🔗"))
        ))

class Media(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="media", description="Красиво опубликовать медиа-пост")
    @app_commands.describe(title="Заголовок", text="Текст поста", url="Ссылка на медиа", channel="Канал (если не указан - текущий)")
    async def media_cmd(self, interaction: discord.Interaction, title: str, text: str, url: str, channel: discord.TextChannel = None):
        target = channel or interaction.channel
        view = MediaView(interaction.user, title, text, url)
        await target.send(view=view)
        await interaction.response.send_message(f"Опубликовано в {target.mention}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Media(bot))