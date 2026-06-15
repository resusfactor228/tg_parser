import asyncio
import logging
from typing import List, Set, Callable, Awaitable

from telethon import TelegramClient
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import ChannelParticipantsSearch, Channel, Chat
from telethon.errors import FloodWaitError, ChatAdminRequiredError

from .models import GroupInfo, MemberRecord
from .state import load_state, save_state, get_fetched_ids

log = logging.getLogger(__name__)

# Задержка между запросами bio (секунды)
BIO_DELAY = 2.0
MAX_RETRIES = 5


async def _call_with_retry(coro_factory, *args, **kwargs):
    for attempt in range(MAX_RETRIES):
        try:
            return await coro_factory(*args, **kwargs)
        except FloodWaitError as e:
            wait = e.seconds + 5
            log.warning(f"FloodWaitError: ожидание {wait}с (попытка {attempt + 1}/{MAX_RETRIES})")
            await asyncio.sleep(wait)
    raise RuntimeError("Превышено максимальное количество повторов FloodWaitError")


async def fetch_members(
    client: TelegramClient,
    group: GroupInfo,
    on_progress: Callable[[int], Awaitable[None]] | None = None,
) -> List[MemberRecord]:
    """
    Проход 1: получение списка участников без bio.
    Возвращает список MemberRecord с bio=None.
    """
    records: List[MemberRecord] = []

    state = load_state(group.id)
    offset = 0  # всегда начинаем с 0 для актуального списка

    if isinstance(group.entity, Channel):
        limit = 200
        while True:
            try:
                result = await _call_with_retry(
                    client,
                    GetParticipantsRequest(
                        channel=group.entity,
                        filter=ChannelParticipantsSearch(""),
                        offset=offset,
                        limit=limit,
                        hash=0,
                    ),
                )
            except ChatAdminRequiredError:
                log.warning(f"Нет прав для получения участников группы '{group.title}' — пропускаем")
                return []

            if not result.users:
                break

            for user in result.users:
                records.append(MemberRecord(
                    user_id=user.id,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    username=user.username,
                    phone=user.phone,
                    bio=None,
                    is_bot=bool(user.bot),
                    is_deleted=bool(user.deleted),
                    group_id=group.id,
                    group_title=group.title,
                ))

            offset += len(result.users)
            if on_progress:
                await on_progress(len(records))

            # Небольшая пауза между страницами
            await asyncio.sleep(0.5)

    elif isinstance(group.entity, Chat):
        # Legacy группа — получаем всех участников одним запросом
        try:
            participants = await client.get_participants(group.entity)
        except ChatAdminRequiredError:
            log.warning(f"Нет прав для получения участников группы '{group.title}' — пропускаем")
            return []

        for user in participants:
            records.append(MemberRecord(
                user_id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                username=user.username,
                phone=user.phone,
                bio=None,
                is_bot=bool(user.bot),
                is_deleted=bool(user.deleted),
                group_id=group.id,
                group_title=group.title,
            ))
        if on_progress:
            await on_progress(len(records))

    # Сохраняем state (список user_id для инкрементального bio-прохода)
    fetched_ids = {r.user_id for r in records}
    save_state(group.id, offset, fetched_ids)

    return records


async def fetch_bios(
    client: TelegramClient,
    records: List[MemberRecord],
    group_id: int,
    on_progress: Callable[[int, int], Awaitable[None]] | None = None,
) -> None:
    """
    Проход 2: дополняет поле bio у каждого MemberRecord.
    Модифицирует список in-place. Пропускает уже известные bio из состояния.
    """
    already_fetched: Set[int] = get_fetched_ids(group_id)
    new_ids = {r.user_id for r in records} - already_fetched
    total = len(new_ids)
    done = 0

    by_id = {r.user_id: r for r in records}

    for user_id in new_ids:
        try:
            full = await _call_with_retry(client, GetFullUserRequest(id=user_id))
            by_id[user_id].bio = full.full_user.about
        except Exception as e:
            log.warning(f"Не удалось получить bio для user_id={user_id}: {e}")

        done += 1
        if on_progress:
            await on_progress(done, total)

        await asyncio.sleep(BIO_DELAY)

    # Обновляем state — теперь bio есть у всех
    all_ids = {r.user_id for r in records}
    state = load_state(group_id)
    save_state(group_id, state.get("last_offset", 0), all_ids)
