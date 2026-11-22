import discord
from discord import app_commands, ui
from discord.ext import commands
from datetime import datetime, timedelta
import sqlite3
from bot.emojis import emoji_object, emoji_tag
from bot.services.storage import DB_PATH, get_settings, save_settings


class MarketModal(ui.Modal):
    def __init__(self, m_type: str):
        super().__init__(title=f"{m_type}"[:45])
        self.m_type = m_type
        self.title_in = ui.TextInput(label="Заголовок", max_length=50)
        self.desc_in = ui.TextInput(label="Описание", style=discord.TextStyle.paragraph, max_length=500)
        self.price_in = ui.TextInput(label="Цена", max_length=30, required=False)
        for i in [self.title_in, self.desc_in, self.price_in]:
            self.add_item(i)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        settings = get_settings(interaction.guild.id)
        ch_id = settings.get("market_channel_id")
        if not ch_id:
            return await interaction.followup.send("Канал не настроен.", ephemeral=True)

        ch = interaction.guild.get_channel(int(ch_id))
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO market (guild_id, author_id, type, title, description, price, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(interaction.guild.id), str(interaction.user.id), self.m_type, self.title_in.value,
                 self.desc_in.value, self.price_in.value, (datetime.utcnow() + timedelta(days=1)).isoformat()))
            conn.commit()
            post_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        view = MarketPostView(post_id, interaction.user, self.m_type, self.title_in.value, self.desc_in.value,
                              self.price_in.value)
        msg = await ch.send(view=view)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE market SET message_id=? WHERE id=?", (str(msg.id), post_id))
            conn.commit()
        await interaction.followup.send("Опубликовано!", ephemeral=True)


class MarketPostView(ui.LayoutView):
    def __init__(self, pid, author, mtype, title, desc, price):
        super().__init__(timeout=None)
        heading = ui.Section(ui.TextDisplay(f"# {emoji_tag('diamond')} {title}"),
                             accessory=ui.Thumbnail(author.display_avatar.url))
        self.add_item(ui.Container(
            heading, ui.TextDisplay(f"> {emoji_tag('member')} {author.mention} | {mtype}"),
            ui.Separator(), ui.TextDisplay(desc), ui.Separator(),
            ui.TextDisplay(f"> {emoji_tag('star')} Цена: {price or 'Договорная'}"),
            ui.ActionRow(MarketRespondButton(author.id), MarketCloseButton(pid, author.id))
        ))


class MarketRespondButton(ui.Button):
    def __init__(self, author_id):
        super().__init__(label="Откликнуться", emoji=emoji_object("heart5"), style=discord.ButtonStyle.secondary)
        self.author_id = author_id

    async def callback(self, interaction):
        author = interaction.guild.get_member(self.author_id)
        if author:
            try:
                await author.send(
                    f"**{emoji_tag('heart5')} Отклик!** {interaction.user.mention} откликнулся на ваше объявление.")
                await interaction.response.send_message("Автору отправлено ЛС!", ephemeral=True)
            except:
                await interaction.response.send_message("У автора закрыты ЛС.", ephemeral=True)


class MarketCloseButton(ui.Button):
    def __init__(self, pid, aid):
        super().__init__(label="Закрыть", style=discord.ButtonStyle.secondary)
        self.pid = pid
        self.aid = aid

    async def callback(self, interaction):
        if interaction.user.id != self.aid and not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("Нет прав.", ephemeral=True)
        await interaction.message.edit(view=ui.LayoutView(view=ui.Container(ui.TextDisplay("❌ Закрыто."))))
        await interaction.response.send_message("Закрыто.", ephemeral=True)


class MarketPanel(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.MediaGallery(discord.MediaGalleryItem("attachment://market.png")),
            ui.TextDisplay(f"# {emoji_tag('diamond')} Рынок"),
            ui.TextDisplay(f"> {emoji_tag('key')} Выберите тип объявления:"),
            ui.ActionRow(
                ui.Button(label="Предлагаю", emoji=emoji_object("boost"), style=discord.ButtonStyle.secondary,
                          custom_id="mk:offer"),
                ui.Button(label="Ищу", emoji=emoji_object("key"), style=discord.ButtonStyle.secondary,
                          custom_id="mk:search")
            )
        ))


class Market(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(MarketPanel())

    @app_commands.command(name="setup_market", description="Создать панель рынка")
    async def setup_market(self, interaction):
        settings = get_settings(interaction.guild.id)
        settings["market_channel_id"] = interaction.channel_id
        save_settings(interaction.guild.id, settings)
        file = discord.File("assets/market.png", filename="market.png")
        await interaction.response.send_message(view=MarketPanel(), file=file)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            cid = interaction.data.get("custom_id", "")
            if cid == "mk:offer":
                await interaction.response.send_modal(MarketModal("Предлагаю"))
            elif cid == "mk:search":
                await interaction.response.send_modal(MarketModal("Ищу"))


async def setup(bot):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS market (id INTEGER PRIMARY KEY, guild_id TEXT, author_id TEXT, message_id TEXT, type TEXT, title TEXT, description TEXT, price TEXT, expires_at TEXT, is_active INTEGER DEFAULT 1)")
        conn.commit()
    await bot.add_cog(Market(bot))