"""
Matching Engine - manages the waiting queue and user pairing logic.
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from database.db import Database

logger = logging.getLogger(__name__)

IDENTITIES = [
    ("🦁", "Lion"),
    ("🐼", "Panda"),
    ("🚀", "Astronaut"),
    ("🎮", "Gamer"),
    ("🐉", "Dragon"),
    ("🦊", "Fox"),
    ("🐺", "Wolf"),
    ("🦋", "Butterfly"),
    ("🐬", "Dolphin"),
    ("🦄", "Unicorn"),
    ("🐸", "Frog"),
    ("🦅", "Eagle"),
    ("🐯", "Tiger"),
    ("🦁", "Lion"),
    ("🌙", "Moonwalker"),
    ("⚡", "Thunder"),
    ("🔥", "Phoenix"),
    ("❄️", "Blizzard"),
    ("🌊", "Wave"),
    ("🎭", "Phantom"),
]

INTERESTS_LIST = [
    "Gaming", "Cricket", "Movies", "Anime", "Coding",
    "Relationships", "College Life", "Memes", "Technology",
    "Music", "Travel", "Food", "Sports", "Art", "Books",
    "Fitness", "Politics", "Fashion", "Business", "Science"
]


@dataclass
class WaitingUser:
    user_id: int
    joined_at: datetime = field(default_factory=datetime.utcnow)
    interests: List[str] = field(default_factory=list)
    interest_mode: bool = False  # True = must match interests


@dataclass
class ActiveSession:
    session_id: int
    user1_id: int
    user2_id: int
    user1_identity: str
    user2_identity: str
    matched_interests: List[str]
    messages_count: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)


class MatchingEngine:
    """
    In-memory matching engine for fast O(1) lookups.
    Manages: waiting queue, active sessions, user state tracking.
    """

    def __init__(self, db: Database):
        self.db = db
        self._waiting: Dict[int, WaitingUser] = {}  # user_id -> WaitingUser
        self._sessions: Dict[int, ActiveSession] = {}  # session_id -> ActiveSession
        self._user_to_session: Dict[int, int] = {}  # user_id -> session_id
        self._used_identities: Dict[int, Set[str]] = {}  # session_id -> set of identities used
        self._lock = asyncio.Lock()

    async def add_to_queue(self, user_id: int, interests: Optional[List[str]] = None,
                            interest_mode: bool = False) -> None:
        """Add user to the waiting queue."""
        async with self._lock:
            self._waiting[user_id] = WaitingUser(
                user_id=user_id,
                interests=interests or [],
                interest_mode=interest_mode,
            )

    async def remove_from_queue(self, user_id: int) -> bool:
        """Remove user from queue. Returns True if was in queue."""
        async with self._lock:
            return self._waiting.pop(user_id, None) is not None

    async def get_session_for_user(self, user_id: int) -> Optional[ActiveSession]:
        """Get the active session a user is in."""
        session_id = self._user_to_session.get(user_id)
        if session_id is not None:
            return self._sessions.get(session_id)
        return None

    async def is_in_queue(self, user_id: int) -> bool:
        return user_id in self._waiting

    async def get_partner_id(self, user_id: int) -> Optional[int]:
        """Get the partner's user_id in an active session."""
        session = await self.get_session_for_user(user_id)
        if not session:
            return None
        return session.user2_id if session.user1_id == user_id else session.user1_id

    async def try_match(self, new_user_id: int) -> Optional[Tuple[int, int, List[str]]]:
        """
        Try to find a match for new_user_id.
        Returns (partner_id, session_id, matched_interests) or None.
        """
        async with self._lock:
            if new_user_id not in self._waiting:
                return None

            new_user = self._waiting[new_user_id]
            best_match: Optional[Tuple[int, List[str]]] = None
            best_score = -1

            for candidate_id, candidate in list(self._waiting.items()):
                if candidate_id == new_user_id:
                    continue

                # Check if blocked
                if await self.db.is_blocked(new_user_id, candidate_id):
                    continue

                # Calculate interest overlap
                common = list(set(new_user.interests) & set(candidate.interests))
                score = len(common)

                # If interest mode, skip zero-match candidates
                if new_user.interest_mode and score == 0:
                    continue
                if candidate.interest_mode and score == 0:
                    continue

                if score > best_score:
                    best_score = score
                    best_match = (candidate_id, common)

            # Fallback to any user if not in strict interest mode
            if best_match is None and not new_user.interest_mode:
                for candidate_id in self._waiting:
                    if candidate_id == new_user_id:
                        continue
                    if await self.db.is_blocked(new_user_id, candidate_id):
                        continue
                    if not self._waiting[candidate_id].interest_mode:
                        best_match = (candidate_id, [])
                        break

            if best_match is None:
                return None

            partner_id, matched_interests = best_match

            # Remove both from queue
            del self._waiting[new_user_id]
            del self._waiting[partner_id]

            # Generate identities
            id1 = self._generate_identity(set())
            id2 = self._generate_identity({id1})

            # Create DB session
            session_id = await self.db.create_chat_session(
                new_user_id, partner_id,
                id1, id2,
                matched_interests
            )

            # Store active session
            session = ActiveSession(
                session_id=session_id,
                user1_id=new_user_id,
                user2_id=partner_id,
                user1_identity=id1,
                user2_identity=id2,
                matched_interests=matched_interests,
            )
            self._sessions[session_id] = session
            self._user_to_session[new_user_id] = session_id
            self._user_to_session[partner_id] = session_id

            return partner_id, session_id, matched_interests

    async def end_session(self, user_id: int) -> Optional[Tuple[int, int, int]]:
        """
        End a user's active session.
        Returns (session_id, partner_id, messages_count) or None.
        """
        async with self._lock:
            session_id = self._user_to_session.get(user_id)
            if not session_id:
                return None

            session = self._sessions.get(session_id)
            if not session:
                return None

            partner_id = session.user2_id if session.user1_id == user_id else session.user1_id
            messages_count = session.messages_count

            # Cleanup
            self._sessions.pop(session_id, None)
            self._user_to_session.pop(user_id, None)
            self._user_to_session.pop(partner_id, None)

            # End in DB
            await self.db.end_chat_session(session_id, user_id, messages_count)

            return session_id, partner_id, messages_count

    async def increment_messages(self, user_id: int) -> None:
        session_id = self._user_to_session.get(user_id)
        if session_id and session_id in self._sessions:
            self._sessions[session_id].messages_count += 1

    def get_identity_for_user(self, user_id: int) -> str:
        session_id = self._user_to_session.get(user_id)
        if not session_id:
            return "🎭 Mystery"
        session = self._sessions.get(session_id)
        if not session:
            return "🎭 Mystery"
        if session.user1_id == user_id:
            return session.user1_identity
        return session.user2_identity

    def get_partner_identity(self, user_id: int) -> str:
        session_id = self._user_to_session.get(user_id)
        if not session_id:
            return "🎭 Mystery"
        session = self._sessions.get(session_id)
        if not session:
            return "🎭 Mystery"
        if session.user1_id == user_id:
            return session.user2_identity
        return session.user1_identity

    def _generate_identity(self, used: Set[str]) -> str:
        available = [f"{emoji} {name}" for emoji, name in IDENTITIES]
        random.shuffle(available)
        for identity in available:
            if identity not in used:
                tag = str(random.randint(1000, 9999))
                return f"{identity} #{tag}"
        emoji, name = random.choice(IDENTITIES)
        return f"{emoji} {name} #{random.randint(1000, 9999)}"

    async def get_queue_count(self) -> int:
        return len(self._waiting)

    async def get_active_sessions_count(self) -> int:
        return len(self._sessions)

    async def get_matched_interests(self, user_id: int) -> List[str]:
        session = await self.get_session_for_user(user_id)
        if not session:
            return []
        return session.matched_interests
