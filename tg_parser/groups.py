from typing import List
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat

from .models import GroupInfo


async def get_groups(client: TelegramClient) -> List[GroupInfo]:
    groups: List[GroupInfo] = []

    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        if isinstance(entity, Channel):
            # megagroup=True — супергруппа, broadcast=False — не канал
            if entity.megagroup or not entity.broadcast:
                groups.append(GroupInfo(
                    id=entity.id,
                    title=entity.title,
                    members_count=getattr(entity, "participants_count", None),
                    is_supergroup=bool(entity.megagroup),
                    entity=entity,
                ))
        elif isinstance(entity, Chat):
            # Обычная группа (legacy, до 200 участников)
            if not getattr(entity, "deactivated", False):
                groups.append(GroupInfo(
                    id=entity.id,
                    title=entity.title,
                    members_count=getattr(entity, "participants_count", None),
                    is_supergroup=False,
                    entity=entity,
                ))

    return groups
