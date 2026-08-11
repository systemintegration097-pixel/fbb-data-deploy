import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "cloud.db"))

CLIENT_FIELDS = (
    "partner", "shop_code", "customer_name", "phone",
    "deployment_type", "pending_days", "ft_code", "connector_code",
)


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS branch_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_code TEXT UNIQUE NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS pending_clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account TEXT UNIQUE NOT NULL,
                branch TEXT NOT NULL,
                partner TEXT,
                shop_code TEXT,
                customer_name TEXT,
                phone TEXT,
                deployment_type TEXT,
                pending_days TEXT,
                ft_code TEXT,
                connector_code TEXT,
                comment TEXT DEFAULT '',
                status TEXT DEFAULT '',
                comment_updated_by TEXT,
                comment_updated_at TEXT,
                first_synced_at TEXT DEFAULT (datetime('now')),
                last_synced_at TEXT DEFAULT (datetime('now')),
                is_active INTEGER DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_pending_clients_branch ON pending_clients(branch);
            CREATE INDEX IF NOT EXISTS idx_pending_clients_active ON pending_clients(is_active);
            """
        )
        conn.commit()
    finally:
        conn.close()


# ---------------- branch_users ----------------

def get_branch_user_by_username(username):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM branch_users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()


def upsert_branch_user(branch_code, username, password_hash):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO branch_users (branch_code, username, password_hash)
            VALUES (?, ?, ?)
            ON CONFLICT(branch_code) DO UPDATE SET
                username = excluded.username,
                password_hash = excluded.password_hash,
                updated_at = datetime('now')
            """,
            (branch_code, username, password_hash),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------- pending_clients ----------------

def get_active_clients_by_branch(branch):
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT * FROM pending_clients
            WHERE branch = ? AND is_active = 1
            ORDER BY deployment_type DESC, pending_days DESC
            """,
            (branch,),
        ).fetchall()
    finally:
        conn.close()


def get_client_by_account(account):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM pending_clients WHERE account = ?", (account,)
        ).fetchone()
    finally:
        conn.close()


def update_client_comment(account, comment, status, updated_by):
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE pending_clients
            SET comment = ?, status = ?, comment_updated_by = ?, comment_updated_at = datetime('now')
            WHERE account = ?
            """,
            (comment, status, updated_by, account),
        )
        conn.commit()
    finally:
        conn.close()


def sync_push_clients(clients):
    """Full-refresh upsert: rows not present in `clients` are deactivated
    (never deleted), so an existing manager comment on a resolved client
    isn't lost if it briefly drops off one push."""
    conn = get_connection()
    upserted = 0
    deactivated = 0
    try:
        seen_accounts = []
        for c in clients:
            account = (c.get("account") or "").strip()
            if not account:
                continue
            seen_accounts.append(account)
            values = [c.get(field, "") or "" for field in CLIENT_FIELDS]
            conn.execute(
                f"""
                INSERT INTO pending_clients (account, branch, {", ".join(CLIENT_FIELDS)}, last_synced_at, is_active)
                VALUES (?, ?, {", ".join(["?"] * len(CLIENT_FIELDS))}, datetime('now'), 1)
                ON CONFLICT(account) DO UPDATE SET
                    branch = excluded.branch,
                    {", ".join(f"{f} = excluded.{f}" for f in CLIENT_FIELDS)},
                    last_synced_at = datetime('now'),
                    is_active = 1
                """,
                [account, c.get("branch", "") or ""] + values,
            )
            upserted += 1

        if seen_accounts:
            placeholders = ", ".join(["?"] * len(seen_accounts))
            cur = conn.execute(
                f"""
                UPDATE pending_clients SET is_active = 0
                WHERE is_active = 1 AND account NOT IN ({placeholders})
                """,
                seen_accounts,
            )
            deactivated = cur.rowcount

        conn.commit()
        return upserted, deactivated
    finally:
        conn.close()


def get_comments_since(since_iso=None):
    conn = get_connection()
    try:
        if since_iso:
            rows = conn.execute(
                """
                SELECT account, branch, comment, status, comment_updated_by, comment_updated_at
                FROM pending_clients
                WHERE comment_updated_at IS NOT NULL AND comment_updated_at > ?
                """,
                (since_iso,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT account, branch, comment, status, comment_updated_by, comment_updated_at
                FROM pending_clients
                WHERE comment_updated_at IS NOT NULL
                """
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
