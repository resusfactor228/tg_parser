from dataclasses import dataclass, field, asdict
from typing import Optional
import datetime


@dataclass
class MemberRecord:
    user_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]
    phone: Optional[str]
    bio: Optional[str]
    is_bot: bool
    is_deleted: bool
    group_id: int
    group_title: str
    fetched_at: str = field(
        default_factory=lambda: datetime.datetime.utcnow().isoformat()
    )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GroupInfo:
    id: int
    title: str
    members_count: Optional[int]
    is_supergroup: bool
    entity: object  # raw Telethon entity, не сериализуется
