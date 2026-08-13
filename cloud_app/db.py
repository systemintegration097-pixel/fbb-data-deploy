import os

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")

CLIENT_FIELDS = (
    "partner", "shop_code", "customer_name", "phone",
    "deployment_type", "pending_days", "ft_code", "connector_code",
)


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL no está configurado (ver cloud_app/.env.example).")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


def init_db():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS branch_users (
                    id SERIAL PRIMARY KEY,
                    branch_code TEXT UNIQUE NOT NULL,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS pending_clients (
                    id SERIAL PRIMARY KEY,
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
                    comment_updated_at TIMESTAMPTZ,
                    first_synced_at TIMESTAMPTZ DEFAULT NOW(),
                    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT TRUE
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
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM branch_users WHERE username = %s", (username,))
            return cur.fetchone()
    finally:
        conn.close()


def upsert_branch_user(branch_code, username, password_hash):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO branch_users (branch_code, username, password_hash)
                VALUES (%s, %s, %s)
                ON CONFLICT (branch_code) DO UPDATE SET
                    username = EXCLUDED.username,
                    password_hash = EXCLUDED.password_hash,
                    updated_at = NOW()
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
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM pending_clients
                WHERE branch = %s AND is_active = TRUE
                ORDER BY deployment_type DESC, pending_days DESC
                """,
                (branch,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def get_client_by_account(account):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM pending_clients WHERE account = %s", (account,))
            return cur.fetchone()
    finally:
        conn.close()


def update_client_comment(account, comment, status, updated_by):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pending_clients
                SET comment = %s, status = %s, comment_updated_by = %s, comment_updated_at = NOW()
                WHERE account = %s
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
        with conn.cursor() as cur:
            seen_accounts = []
            for c in clients:
                account = (c.get("account") or "").strip()
                if not account:
                    continue
                seen_accounts.append(account)
                values = [c.get(field, "") or "" for field in CLIENT_FIELDS]
                cur.execute(
                    f"""
                    INSERT INTO pending_clients (account, branch, {", ".join(CLIENT_FIELDS)}, last_synced_at, is_active)
                    VALUES (%s, %s, {", ".join(["%s"] * len(CLIENT_FIELDS))}, NOW(), TRUE)
                    ON CONFLICT (account) DO UPDATE SET
                        branch = EXCLUDED.branch,
                        {", ".join(f"{f} = EXCLUDED.{f}" for f in CLIENT_FIELDS)},
                        last_synced_at = NOW(),
                        is_active = TRUE
                    """,
                    [account, c.get("branch", "") or ""] + values,
                )
                upserted += 1

            if seen_accounts:
                cur.execute(
                    """
                    UPDATE pending_clients SET is_active = FALSE
                    WHERE is_active = TRUE AND account != ALL(%s)
                    """,
                    (seen_accounts,),
                )
                deactivated = cur.rowcount

        conn.commit()
        return upserted, deactivated
    finally:
        conn.close()


def get_comments_since(since_iso=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if since_iso:
                cur.execute(
                    """
                    SELECT account, branch, comment, status, comment_updated_by, comment_updated_at
                    FROM pending_clients
                    WHERE comment_updated_at IS NOT NULL AND comment_updated_at > %s
                    """,
                    (since_iso,),
                )
            else:
                cur.execute(
                    """
                    SELECT account, branch, comment, status, comment_updated_by, comment_updated_at
                    FROM pending_clients
                    WHERE comment_updated_at IS NOT NULL
                    """
                )
            rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("comment_updated_at") is not None:
                d["comment_updated_at"] = d["comment_updated_at"].isoformat(sep=" ", timespec="seconds")
            result.append(d)
        return result
    finally:
        conn.close()
