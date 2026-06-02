"""
Database module - SQLite with aiosqlite for async operations.
Handles all DB initialization, queries, and migrations.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT NOT NULL,
    language_code TEXT DEFAULT 'en',
    gender TEXT DEFAULT 'unknown',
    is_banned INTEGER DEFAULT 0,
    ban_reason TEXT,
    is_premium INTEGER DEFAULT 0,
    referral_code TEXT UNIQUE,
    referred_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

-- Interests table
CREATE TABLE IF NOT EXISTS interests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    interest TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    UNIQUE(user_id, interest)
);

-- Chat sessions
CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user1_id INTEGER NOT NULL,
    user2_id INTEGER NOT NULL,
    user1_identity TEXT,
    user2_identity TEXT,
    matched_interests TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    messages_count INTEGER DEFAULT 0,
    duration_seconds INTEGER DEFAULT 0,
    ended_by INTEGER,
    FOREIGN KEY (user1_id) REFERENCES users(user_id),
    FOREIGN KEY (user2_id) REFERENCES users(user_id)
);

-- Friend requests
CREATE TABLE IF NOT EXISTS friend_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id INTEGER NOT NULL,
    to_user_id INTEGER NOT NULL,
    session_id INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (from_user_id) REFERENCES users(user_id),
    FOREIGN KEY (to_user_id) REFERENCES users(user_id)
);

-- Friendships
CREATE TABLE IF NOT EXISTS friendships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user1_id INTEGER NOT NULL,
    user2_id INTEGER NOT NULL,
    friend_code TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user1_id) REFERENCES users(user_id),
    FOREIGN KEY (user2_id) REFERENCES users(user_id),
    UNIQUE(user1_id, user2_id)
);

-- Reports
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL,
    reported_id INTEGER NOT NULL,
    session_id INTEGER,
    reason TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    reviewed_by INTEGER,
    FOREIGN KEY (reporter_id) REFERENCES users(user_id),
    FOREIGN KEY (reported_id) REFERENCES users(user_id)
);

-- Blocks
CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blocker_id INTEGER NOT NULL,
    blocked_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (blocker_id) REFERENCES users(user_id),
    FOREIGN KEY (blocked_id) REFERENCES users(user_id),
    UNIQUE(blocker_id, blocked_id)
);

-- XP and levels
CREATE TABLE IF NOT EXISTS xp (
    user_id INTEGER PRIMARY KEY,
    total_xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Coins
CREATE TABLE IF NOT EXISTS coins (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    total_earned INTEGER DEFAULT 0,
    total_spent INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Streaks
CREATE TABLE IF NOT EXISTS streaks (
    user_id INTEGER PRIMARY KEY,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_claim_date DATE,
    total_days INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Ratings
CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rater_id INTEGER NOT NULL,
    rated_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    rating TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rater_id) REFERENCES users(user_id),
    FOREIGN KEY (rated_id) REFERENCES users(user_id)
);

-- Daily stats
CREATE TABLE IF NOT EXISTS daily_stats (
    date DATE PRIMARY KEY,
    total_users INTEGER DEFAULT 0,
    new_users INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    chats_created INTEGER DEFAULT 0,
    messages_sent INTEGER DEFAULT 0,
    friend_requests INTEGER DEFAULT 0
);

-- Coin transactions
CREATE TABLE IF NOT EXISTS coin_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    type TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Rate limiting
CREATE TABLE IF NOT EXISTS rate_limits (
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    count INTEGER DEFAULT 1,
    window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, action),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen);
CREATE INDEX IF NOT EXISTS idx_users_is_banned ON users(is_banned);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_users ON chat_sessions(user1_id, user2_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_started ON chat_sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_friend_requests_to ON friend_requests(to_user_id, status);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_interests_user ON interests(user_id);
CREATE INDEX IF NOT EXISTS idx_ratings_rated ON ratings(rated_id);
"""


class Database:
    """Async SQLite database manager."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize database connection and schema."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    # ─── User Methods ──────────────────────────────────────────────

    async def get_or_create_user(self, user_id: int, first_name: str,
                                  username: Optional[str] = None,
                                  language_code: str = "en",
                                  referred_by: Optional[int] = None) -> Dict:
        """Get existing user or create new one."""
        async with self._conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                # Update last_seen and name
                await self._conn.execute(
                    "UPDATE users SET last_seen = CURRENT_TIMESTAMP, first_name = ?, username = ? WHERE user_id = ?",
                    (first_name, username, user_id)
                )
                await self._conn.commit()
                return dict(row)

        # Create new user
        import secrets
        import string
        ref_code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))

        await self._conn.execute(
            """INSERT INTO users (user_id, username, first_name, language_code, referral_code, referred_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, username, first_name, language_code, f"FC-{ref_code}", referred_by)
        )
        # Initialize XP, coins, streaks
        await self._conn.execute("INSERT OR IGNORE INTO xp (user_id) VALUES (?)", (user_id,))
        await self._conn.execute("INSERT OR IGNORE INTO coins (user_id) VALUES (?)", (user_id,))
        await self._conn.execute("INSERT OR IGNORE INTO streaks (user_id) VALUES (?)", (user_id,))
        await self._conn.commit()

        async with self._conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return dict(await cursor.fetchone())

    async def get_user(self, user_id: int) -> Optional[Dict]:
        async with self._conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_last_seen(self, user_id: int) -> None:
        await self._conn.execute(
            "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,)
        )
        await self._conn.commit()

    async def get_online_count(self) -> int:
        cutoff = datetime.utcnow() - timedelta(minutes=5)
        async with self._conn.execute(
            "SELECT COUNT(*) FROM users WHERE last_seen > ? AND is_banned = 0",
            (cutoff.isoformat(),)
        ) as cursor:
            return (await cursor.fetchone())[0]

    async def get_total_users(self) -> int:
        async with self._conn.execute("SELECT COUNT(*) FROM users") as cursor:
            return (await cursor.fetchone())[0]

    async def is_banned(self, user_id: int) -> bool:
        async with self._conn.execute(
            "SELECT is_banned FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0])

    async def ban_user(self, user_id: int, reason: str) -> None:
        await self._conn.execute(
            "UPDATE users SET is_banned = 1, ban_reason = ? WHERE user_id = ?",
            (reason, user_id)
        )
        await self._conn.commit()

    async def unban_user(self, user_id: int) -> None:
        await self._conn.execute(
            "UPDATE users SET is_banned = 0, ban_reason = NULL WHERE user_id = ?",
            (user_id,)
        )
        await self._conn.commit()

    async def get_user_by_referral(self, code: str) -> Optional[Dict]:
        async with self._conn.execute(
            "SELECT * FROM users WHERE referral_code = ?", (code,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    # ─── Interest Methods ──────────────────────────────────────────

    async def set_user_interests(self, user_id: int, interests: List[str]) -> None:
        await self._conn.execute("DELETE FROM interests WHERE user_id = ?", (user_id,))
        for interest in interests:
            await self._conn.execute(
                "INSERT OR IGNORE INTO interests (user_id, interest) VALUES (?, ?)",
                (user_id, interest)
            )
        await self._conn.commit()

    async def get_user_interests(self, user_id: int) -> List[str]:
        async with self._conn.execute(
            "SELECT interest FROM interests WHERE user_id = ?", (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    # ─── Chat Session Methods ──────────────────────────────────────

    async def create_chat_session(self, user1_id: int, user2_id: int,
                                   user1_identity: str, user2_identity: str,
                                   matched_interests: Optional[List[str]] = None) -> int:
        interests_str = ",".join(matched_interests) if matched_interests else ""
        async with self._conn.execute(
            """INSERT INTO chat_sessions (user1_id, user2_id, user1_identity, user2_identity, matched_interests)
               VALUES (?, ?, ?, ?, ?)""",
            (user1_id, user2_id, user1_identity, user2_identity, interests_str)
        ) as cursor:
            session_id = cursor.lastrowid
        await self._conn.commit()
        return session_id

    async def end_chat_session(self, session_id: int, ended_by: int, messages_count: int) -> None:
        await self._conn.execute(
            """UPDATE chat_sessions
               SET ended_at = CURRENT_TIMESTAMP,
                   ended_by = ?,
                   messages_count = ?,
                   duration_seconds = CAST((julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 86400 AS INTEGER)
               WHERE id = ?""",
            (ended_by, messages_count, session_id)
        )
        await self._conn.commit()

    async def get_active_chats_count(self) -> int:
        async with self._conn.execute(
            "SELECT COUNT(*) FROM chat_sessions WHERE ended_at IS NULL"
        ) as cursor:
            return (await cursor.fetchone())[0]

    async def get_chats_today(self) -> int:
        async with self._conn.execute(
            "SELECT COUNT(*) FROM chat_sessions WHERE DATE(started_at) = DATE('now')"
        ) as cursor:
            return (await cursor.fetchone())[0]

    async def increment_session_messages(self, session_id: int) -> None:
        await self._conn.execute(
            "UPDATE chat_sessions SET messages_count = messages_count + 1 WHERE id = ?",
            (session_id,)
        )
        await self._conn.commit()

    # ─── Friend Methods ───────────────────────────────────────────

    async def send_friend_request(self, from_user: int, to_user: int, session_id: int) -> Optional[int]:
        # Check no existing pending request
        async with self._conn.execute(
            "SELECT id FROM friend_requests WHERE from_user_id = ? AND to_user_id = ? AND status = 'pending'",
            (from_user, to_user)
        ) as cursor:
            if await cursor.fetchone():
                return None

        async with self._conn.execute(
            "INSERT INTO friend_requests (from_user_id, to_user_id, session_id) VALUES (?, ?, ?)",
            (from_user, to_user, session_id)
        ) as cursor:
            req_id = cursor.lastrowid
        await self._conn.commit()
        return req_id

    async def get_friend_request(self, req_id: int) -> Optional[Dict]:
        async with self._conn.execute(
            "SELECT * FROM friend_requests WHERE id = ?", (req_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_friend_request(self, req_id: int, status: str) -> None:
        await self._conn.execute(
            "UPDATE friend_requests SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, req_id)
        )
        await self._conn.commit()

    async def create_friendship(self, user1_id: int, user2_id: int) -> str:
        import secrets, string
        code = "FC-" + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        await self._conn.execute(
            "INSERT OR IGNORE INTO friendships (user1_id, user2_id, friend_code) VALUES (?, ?, ?)",
            (min(user1_id, user2_id), max(user1_id, user2_id), code)
        )
        await self._conn.commit()
        return code

    async def are_friends(self, user1_id: int, user2_id: int) -> bool:
        async with self._conn.execute(
            """SELECT id FROM friendships
               WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)""",
            (user1_id, user2_id, user2_id, user1_id)
        ) as cursor:
            return bool(await cursor.fetchone())

    async def get_friends(self, user_id: int) -> List[Dict]:
        async with self._conn.execute(
            """SELECT u.user_id, u.first_name, f.friend_code, f.created_at
               FROM friendships f
               JOIN users u ON (
                   CASE WHEN f.user1_id = ? THEN f.user2_id ELSE f.user1_id END = u.user_id
               )
               WHERE f.user1_id = ? OR f.user2_id = ?""",
            (user_id, user_id, user_id)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_pending_requests(self, user_id: int) -> List[Dict]:
        async with self._conn.execute(
            "SELECT * FROM friend_requests WHERE to_user_id = ? AND status = 'pending'",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ─── XP & Coins ───────────────────────────────────────────────

    async def add_xp(self, user_id: int, amount: int) -> Tuple[int, int, int]:
        """Add XP and calculate new level. Returns (new_xp, old_level, new_level)."""
        async with self._conn.execute(
            "SELECT total_xp, level FROM xp WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            current_xp = row[0] if row else 0
            old_level = row[1] if row else 1

        new_xp = current_xp + amount
        new_level = self._calculate_level(new_xp)

        await self._conn.execute(
            """INSERT INTO xp (user_id, total_xp, level) VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET total_xp = ?, level = ?, updated_at = CURRENT_TIMESTAMP""",
            (user_id, new_xp, new_level, new_xp, new_level)
        )
        await self._conn.commit()
        return new_xp, old_level, new_level

    def _calculate_level(self, xp: int) -> int:
        """Level formula: each level requires level * 100 XP."""
        level = 1
        required = 100
        while xp >= required:
            xp -= required
            level += 1
            required = level * 100
        return level

    async def get_xp(self, user_id: int) -> Dict:
        async with self._conn.execute(
            "SELECT total_xp, level FROM xp WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"total_xp": row[0], "level": row[1]}
            return {"total_xp": 0, "level": 1}

    async def add_coins(self, user_id: int, amount: int, tx_type: str, description: str = "") -> int:
        await self._conn.execute(
            """INSERT INTO coins (user_id, balance, total_earned) VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   balance = balance + ?,
                   total_earned = total_earned + ?,
                   updated_at = CURRENT_TIMESTAMP""",
            (user_id, amount, amount, amount, amount)
        )
        await self._conn.execute(
            "INSERT INTO coin_transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
            (user_id, amount, tx_type, description)
        )
        await self._conn.commit()
        async with self._conn.execute("SELECT balance FROM coins WHERE user_id = ?", (user_id,)) as c:
            row = await c.fetchone()
            return row[0] if row else 0

    async def spend_coins(self, user_id: int, amount: int, tx_type: str, description: str = "") -> bool:
        async with self._conn.execute("SELECT balance FROM coins WHERE user_id = ?", (user_id,)) as c:
            row = await c.fetchone()
            if not row or row[0] < amount:
                return False

        await self._conn.execute(
            """UPDATE coins SET balance = balance - ?, total_spent = total_spent + ?,
               updated_at = CURRENT_TIMESTAMP WHERE user_id = ?""",
            (amount, amount, user_id)
        )
        await self._conn.execute(
            "INSERT INTO coin_transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
            (user_id, -amount, tx_type, description)
        )
        await self._conn.commit()
        return True

    async def get_coins(self, user_id: int) -> int:
        async with self._conn.execute("SELECT balance FROM coins WHERE user_id = ?", (user_id,)) as c:
            row = await c.fetchone()
            return row[0] if row else 0

    # ─── Streaks ──────────────────────────────────────────────────

    async def claim_daily_streak(self, user_id: int) -> Tuple[bool, int, int]:
        """Returns (success, new_streak, coins_earned)."""
        today = datetime.utcnow().date()
        async with self._conn.execute(
            "SELECT current_streak, longest_streak, last_claim_date FROM streaks WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            await self._conn.execute(
                "INSERT INTO streaks (user_id, current_streak, longest_streak, last_claim_date, total_days) VALUES (?, 1, 1, ?, 1)",
                (user_id, today.isoformat())
            )
            await self._conn.commit()
            return True, 1, 10

        last_claim = datetime.strptime(row[2], "%Y-%m-%d").date() if row[2] else None

        if last_claim == today:
            return False, row[0], 0  # Already claimed today

        if last_claim == today - timedelta(days=1):
            new_streak = row[0] + 1
        else:
            new_streak = 1  # Streak broken

        longest = max(row[1], new_streak)
        coins = min(new_streak * 10, 100)  # Cap at 100

        await self._conn.execute(
            """UPDATE streaks SET current_streak = ?, longest_streak = ?,
               last_claim_date = ?, total_days = total_days + 1 WHERE user_id = ?""",
            (new_streak, longest, today.isoformat(), user_id)
        )
        await self._conn.commit()
        return True, new_streak, coins

    async def get_streak(self, user_id: int) -> Dict:
        async with self._conn.execute(
            "SELECT current_streak, longest_streak, last_claim_date, total_days FROM streaks WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "current_streak": row[0],
                    "longest_streak": row[1],
                    "last_claim_date": row[2],
                    "total_days": row[3],
                }
            return {"current_streak": 0, "longest_streak": 0, "last_claim_date": None, "total_days": 0}

    # ─── Ratings ──────────────────────────────────────────────────

    async def add_rating(self, rater_id: int, rated_id: int, session_id: int, rating: str) -> bool:
        try:
            await self._conn.execute(
                "INSERT INTO ratings (rater_id, rated_id, session_id, rating) VALUES (?, ?, ?, ?)",
                (rater_id, rated_id, session_id, rating)
            )
            await self._conn.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def get_reputation(self, user_id: int) -> Dict:
        async with self._conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN rating = 'good' THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN rating = 'bad' THEN 1 ELSE 0 END) as negative
               FROM ratings WHERE rated_id = ?""",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                pct = int((row[1] / row[0]) * 100)
                return {"total": row[0], "positive": row[1], "negative": row[2], "percentage": pct}
            return {"total": 0, "positive": 0, "negative": 0, "percentage": 100}

    # ─── Reports ──────────────────────────────────────────────────

    async def create_report(self, reporter_id: int, reported_id: int,
                             session_id: Optional[int], reason: str) -> int:
        async with self._conn.execute(
            "INSERT INTO reports (reporter_id, reported_id, session_id, reason) VALUES (?, ?, ?, ?)",
            (reporter_id, reported_id, session_id, reason)
        ) as cursor:
            report_id = cursor.lastrowid
        await self._conn.commit()
        return report_id

    async def get_report_count(self, user_id: int) -> int:
        async with self._conn.execute(
            "SELECT COUNT(*) FROM reports WHERE reported_id = ? AND status = 'pending'", (user_id,)
        ) as cursor:
            return (await cursor.fetchone())[0]

    async def get_pending_reports(self) -> List[Dict]:
        async with self._conn.execute(
            """SELECT r.*, u1.first_name as reporter_name, u2.first_name as reported_name
               FROM reports r
               JOIN users u1 ON r.reporter_id = u1.user_id
               JOIN users u2 ON r.reported_id = u2.user_id
               WHERE r.status = 'pending'
               ORDER BY r.created_at DESC LIMIT 20""",
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ─── Blocks ───────────────────────────────────────────────────

    async def block_user(self, blocker_id: int, blocked_id: int) -> None:
        await self._conn.execute(
            "INSERT OR IGNORE INTO blocks (blocker_id, blocked_id) VALUES (?, ?)",
            (blocker_id, blocked_id)
        )
        await self._conn.commit()

    async def is_blocked(self, user1_id: int, user2_id: int) -> bool:
        async with self._conn.execute(
            """SELECT id FROM blocks
               WHERE (blocker_id = ? AND blocked_id = ?) OR (blocker_id = ? AND blocked_id = ?)""",
            (user1_id, user2_id, user2_id, user1_id)
        ) as cursor:
            return bool(await cursor.fetchone())

    # ─── Leaderboard ──────────────────────────────────────────────

    async def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        async with self._conn.execute(
            """SELECT u.first_name, x.total_xp, x.level, c.balance
               FROM xp x
               JOIN users u ON x.user_id = u.user_id
               JOIN coins c ON x.user_id = c.user_id
               WHERE u.is_banned = 0
               ORDER BY x.total_xp DESC LIMIT ?""",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_user_rank(self, user_id: int) -> int:
        async with self._conn.execute(
            """SELECT COUNT(*) + 1 FROM xp
               WHERE total_xp > (SELECT total_xp FROM xp WHERE user_id = ?)""",
            (user_id,)
        ) as cursor:
            return (await cursor.fetchone())[0]

    # ─── Admin Stats ──────────────────────────────────────────────

    async def get_full_stats(self) -> Dict:
        total_users = await self.get_total_users()
        active_today = await self.get_online_count()
        chats_today = await self.get_chats_today()
        active_chats = await self.get_active_chats_count()

        async with self._conn.execute(
            "SELECT COUNT(*) FROM chat_sessions"
        ) as cursor:
            total_chats = (await cursor.fetchone())[0]

        async with self._conn.execute(
            "SELECT SUM(messages_count) FROM chat_sessions"
        ) as cursor:
            total_messages = (await cursor.fetchone())[0] or 0

        return {
            "total_users": total_users,
            "active_today": active_today,
            "chats_today": chats_today,
            "active_chats": active_chats,
            "total_chats": total_chats,
            "total_messages": total_messages,
        }

    # ─── Rate Limiting ────────────────────────────────────────────

    async def check_rate_limit(self, user_id: int, action: str,
                                max_count: int, window_seconds: int) -> bool:
        """Returns True if within limit, False if exceeded."""
        now = datetime.utcnow()
        window_start = (now - timedelta(seconds=window_seconds)).isoformat()

        async with self._conn.execute(
            """SELECT count, window_start FROM rate_limits
               WHERE user_id = ? AND action = ?""",
            (user_id, action)
        ) as cursor:
            row = await cursor.fetchone()

        if not row or row[1] < window_start:
            await self._conn.execute(
                """INSERT INTO rate_limits (user_id, action, count, window_start) VALUES (?, ?, 1, ?)
                   ON CONFLICT(user_id, action) DO UPDATE SET count = 1, window_start = ?""",
                (user_id, action, now.isoformat(), now.isoformat())
            )
            await self._conn.commit()
            return True

        if row[0] >= max_count:
            return False

        await self._conn.execute(
            "UPDATE rate_limits SET count = count + 1 WHERE user_id = ? AND action = ?",
            (user_id, action)
        )
        await self._conn.commit()
        return True
