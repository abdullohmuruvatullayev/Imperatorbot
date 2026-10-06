import asyncpg

import prices as P

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id         BIGINT PRIMARY KEY,
    username   TEXT,
    full_name  TEXT,
    phone      TEXT,
    blocked    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS calculations (
    id            SERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL REFERENCES users(id),
    width         INT NOT NULL,
    height        INT NOT NULL,
    count         INT NOT NULL,
    glass         TEXT NOT NULL,
    color         TEXT NOT NULL,
    fitting       TEXT NOT NULL,
    fitting_count INT NOT NULL,
    handle        TEXT,
    delivery      BOOLEAN NOT NULL,
    usd           NUMERIC(12,2) NOT NULL,
    rate          NUMERIC(12,2) NOT NULL,
    total_sum     BIGINT NOT NULL,
    ordered_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS comments (
    id         SERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id),
    text       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS prices (
    key   TEXT PRIMARY KEY,
    value DOUBLE PRECISION
);
CREATE TABLE IF NOT EXISTS images (
    key     TEXT PRIMARY KEY,   -- glass_peppil, color_qora, ...
    file_id TEXT NOT NULL       -- Telegram file_id (rasm Telegram serverida turadi)
);
-- mavjud bazaga ham qo'shiladi
ALTER TABLE users ADD COLUMN IF NOT EXISTS customer_name TEXT;   -- buyurtmada kiritilgan ism-familiya
ALTER TABLE calculations ADD COLUMN IF NOT EXISTS customer_name TEXT;
ALTER TABLE calculations ADD COLUMN IF NOT EXISTS phone TEXT;
ALTER TABLE calculations ADD COLUMN IF NOT EXISTS status TEXT;        -- NULL | new | confirmed | cancelled
ALTER TABLE calculations ADD COLUMN IF NOT EXISTS status_by TEXT;     -- qaysi admin
ALTER TABLE calculations ADD COLUMN IF NOT EXISTS status_at TIMESTAMPTZ;
UPDATE calculations SET status = 'new' WHERE ordered_at IS NOT NULL AND status IS NULL;
CREATE INDEX IF NOT EXISTS calculations_created_at ON calculations(created_at);
"""

pool: asyncpg.Pool = None
prices: dict = {}  # xotiradagi nusxa; bitta jarayon uchun yetarli
images: dict = {}  # key -> file_id


async def init(dsn):
    global pool
    # Toshkent vaqti (UTC+5, yozgi vaqt yo'q): sana/vaqt chiqishi va "bugun" statistikasi uchun.
    # server_settings orqali — pool ulanishni qaytarganda qiladigan RESET ALL buni o'chirmaydi.
    # '<+05>-05' POSIX yozuvi: tzdata kerak emas, ishorasi teskari bo'lishi POSIX qoidasi.
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5, server_settings={"timezone": "<+05>-05"})
    async with pool.acquire() as c:
        await c.execute(SCHEMA)
        await c.executemany("INSERT INTO prices(key, value) VALUES($1, $2) ON CONFLICT DO NOTHING",
                            [(k, v) for k, (_, v) in P.DEFAULTS.items()])
        prices.update({r["key"]: r["value"] for r in await c.fetch("SELECT key, value FROM prices")})
        images.update({r["key"]: r["file_id"] for r in await c.fetch("SELECT key, file_id FROM images")})


async def set_price(key, value):
    await pool.execute("UPDATE prices SET value = $2 WHERE key = $1", key, value)
    prices[key] = value


async def set_image(key, file_id):
    await pool.execute("INSERT INTO images(key, file_id) VALUES($1, $2) ON CONFLICT (key) DO UPDATE SET file_id = $2",
                       key, file_id)
    images[key] = file_id


async def delete_image(key):
    await pool.execute("DELETE FROM images WHERE key = $1", key)
    images.pop(key, None)


async def upsert_user(u):
    await pool.execute(
        """INSERT INTO users(id, username, full_name) VALUES($1, $2, $3)
           ON CONFLICT (id) DO UPDATE SET username = $2, full_name = $3, blocked = FALSE""",
        u.id, u.username, u.full_name)


async def save_user_contact(user_id, customer_name, phone):
    await pool.execute("UPDATE users SET customer_name = $2, phone = $3 WHERE id = $1", user_id, customer_name, phone)


async def get_user_contact(user_id):
    """Oldin kiritilgan (ism, telefon) yoki None."""
    r = await pool.fetchrow("SELECT customer_name, phone FROM users WHERE id = $1", user_id)
    return (r["customer_name"], r["phone"]) if r and r["customer_name"] and r["phone"] else None


async def add_calc(user_id, d, usd, rate, total_sum):
    return await pool.fetchval(
        """INSERT INTO calculations(user_id, width, height, count, glass, color, fitting, fitting_count,
                                    handle, delivery, usd, rate, total_sum)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) RETURNING id""",
        user_id, d["width"], d["height"], d["count"], d["glass"], d["color"], d["fitting"], d["fitting_count"],
        d["side"], d["delivery"], usd, rate, total_sum)


async def set_contact(calc_id, customer_name, phone):
    await pool.execute("UPDATE calculations SET customer_name = $2, phone = $3 WHERE id = $1", calc_id, customer_name, phone)


async def submit_order(calc_id):
    """Mijoz tasdiqladi. Ikki marta bosilsa ikkinchisi None qaytaradi."""
    return await pool.fetchval("UPDATE calculations SET ordered_at = now(), status = 'new' "
                               "WHERE id = $1 AND ordered_at IS NULL RETURNING id", calc_id)


async def set_status(calc_id, status, by):
    """Admin qarori. Faqat 'new' holatdagisi o'zgaradi — ikki admin bir vaqtda bossa ham bittasi o'tadi."""
    return await pool.fetchval("UPDATE calculations SET status = $2, status_by = $3, status_at = now() "
                               "WHERE id = $1 AND status = 'new' RETURNING id", calc_id, status, by)


async def get_order(calc_id):
    return await pool.fetchrow("""
        SELECT c.*, u.username, u.full_name,
               to_char(c.created_at, 'DD.MM.YYYY HH24:MI') AS created_str,
               to_char(c.status_at, 'DD.MM.YYYY HH24:MI') AS status_str
        FROM calculations c JOIN users u ON u.id = c.user_id WHERE c.id = $1""", calc_id)


async def add_comment(user_id, text):
    await pool.execute("INSERT INTO comments(user_id, text) VALUES($1, $2)", user_id, text)


async def stats():
    return await pool.fetchrow("""
        SELECT
          (SELECT count(*) FROM users)                                   AS users,
          (SELECT count(*) FROM users WHERE NOT blocked)                 AS active_users,
          (SELECT count(*) FROM users WHERE created_at >= current_date)  AS new_today,
          count(*) FILTER (WHERE created_at >= current_date)             AS calc_today,
          count(*) FILTER (WHERE created_at >= now() - interval '7 days') AS calc_week,
          count(*)                                                        AS calc_all,
          count(ordered_at) FILTER (WHERE created_at >= current_date)    AS ord_today,
          count(ordered_at) FILTER (WHERE created_at >= now() - interval '7 days') AS ord_week,
          count(ordered_at)                                               AS ord_all,
          count(*) FILTER (WHERE status = 'new')                          AS st_new,
          count(*) FILTER (WHERE status = 'confirmed')                    AS st_confirmed,
          count(*) FILTER (WHERE status = 'cancelled')                    AS st_cancelled,
          coalesce(sum(usd) FILTER (WHERE status = 'confirmed'), 0)       AS confirmed_usd
        FROM calculations""")


async def export_rows():
    return await pool.fetch("""
        SELECT c.id, to_char(c.created_at, 'YYYY-MM-DD HH24:MI') AS created_at, u.id AS user_id, u.username, u.full_name, c.customer_name, coalesce(c.phone, u.phone) AS phone,
               c.width, c.height, c.count, c.glass, c.color, c.fitting, c.fitting_count, c.handle,
               c.delivery, c.usd, c.rate, c.total_sum,
               to_char(c.ordered_at, 'YYYY-MM-DD HH24:MI') AS ordered_at, c.status, c.status_by
        FROM calculations c JOIN users u ON u.id = c.user_id ORDER BY c.id""")


async def active_user_ids():
    return [r["id"] for r in await pool.fetch("SELECT id FROM users WHERE NOT blocked")]


async def mark_blocked(user_id):
    await pool.execute("UPDATE users SET blocked = TRUE WHERE id = $1", user_id)
