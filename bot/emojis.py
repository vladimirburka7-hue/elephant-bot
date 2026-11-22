"""Application emojis от пользователя; все иконки берутся из этого списка."""
import discord

EMOJI_DATA: dict[str, tuple[str, int]] = {
    "boost": ("boost_new", 1571290251375415376),
    "heart5": ("5_", 1571218203466530926),
    "question": ("question", 1571217488526577674),
    "staff": ("staff", 1571218782817624074),
    "gamepad": ("11", 1571218334677213264),
    "flag": ("6_", 1571218228288426054),
    "heart": ("423717discordheart", 1571219443613310976),
    "key": ("key", 1571218607592054826),
    "yes": ("yes", 1571218648239046717),
    "sprout": ("4_", 1571218164216238203),
    "diamond": ("VIP", 1571218676172984553),
    "star": ("star", 1571218618036002856),
    "robot": ("robot", 1571218666597519400),
    "member": ("3_", 1571218142523556003),
    "trophy": ("10", 1571218308081127576),
    "microphone": ("2_", 1571218111070343328),
    "sword": ("293394sword", 1571219198766485505),
    "medal": ("76245medalla", 1571219053979107338),
    "owner": ("owner", 1571218638445478049),
    "gear": ("1_", 1571218070775529544),
    "num1": ("_1", 1571218726882254999),
    "num2": ("_2", 1571218737598562366),
    "num3": ("_3", 1571218747010719784),
}


def emoji_tag(key: str) -> str:
    name, emoji_id = EMOJI_DATA[key]
    return f"<:{name}:{emoji_id}>"


def emoji_object(key: str) -> discord.PartialEmoji:
    name, emoji_id = EMOJI_DATA[key]
    return discord.PartialEmoji(name=name, id=emoji_id)




