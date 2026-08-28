from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.repositories.base import BaseRepository
from app.models.message import Message

class MessageRepository(BaseRepository[Message]):
    def __init__(self, db: AsyncSession):
        super().__init__(Message, db)

    async def get_by_conversation(self, conversation_id: int, limit: int = 50) -> List[Message]:
        """Return the most recent `limit` messages for a conversation, in
        chronological (ascending) order.

        Bug fix (Phase 3): this previously ordered ascending *before*
        applying LIMIT, which returned the oldest N messages instead of the
        most recent N once a conversation grew past the limit. Fixed by
        taking the most recent N (descending) and reversing back to
        chronological order for the caller.

        Bug fix (Phase 5 regression): the descending fetch above was still
        ordered by `created_at`, a Python-side default (originally
        `datetime.utcnow()`, now `utc_now()` - see app/utils/time.py)
        evaluated at flush time. On a fast in-memory test DB, several
        messages created in a tight loop can land on the exact same
        timestamp (the clock simply doesn't tick between calls), so
        `ORDER BY created_at DESC` has ties with no defined order between
        them - SQLite is free to return tied rows in whatever order its
        scan happens to visit them, which does not have to match insertion
        order. Reversing an already-scrambled tie group doesn't fix it, so
        the "most recent N" window could end up a message or two off,
        exactly like the observed failure (window starting one message too
        early, i.e. built from the wrong messages entirely rather than a
        simple boundary miss).

        Fixed by ordering on `id` instead. `id` is the autoincrement
        primary key, assigned strictly in insertion order by SQLite on
        every flush - unlike a wall-clock timestamp it cannot tie, so
        descending-then-reverse now reconstructs the true insertion
        (chronological) order every time, regardless of how fast messages
        are created.
        """
        result = await self.db.execute(
            select(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        recent_desc = result.scalars().all()
        return list(reversed(recent_desc))
