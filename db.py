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
ALTER TABLE calculations ADD COLUMN IF NOT EXISTS customer_name TEXT;
ALTER TABLE calculations ADD COLUMN IF NOT EXISTS phone TEXT;
CREATE INDEX IF NOT EXISTS calculations_created_at ON calculations(created_at);
"""

pool: asyncpg.Pool = None
prices: dict = {}  # xotiradagi nusxa; bitta jarayon uchun yetarli
images: dict = {}  # key -> file_id


async def init(dsn):
    global pool
    # Toshkent vaqti (UTC+5, yozgi vaqt yo'q) — "bugun" statistikasi va eksport sanalari uchun
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5,
                                     init=lambda c: c.execute("SET TIME ZONE INTERVAL '+05:00' HOUR TO MINUTE"))
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


async def set_phone(user_id, phone):
    await pool.execute("UPDATE users SET phone = $2 WHERE id = $1", user_id, phone)


async def add_calc(user_id, d, usd, rate, total_sum):
    return await pool.fetchval(
        """INSERT INTO calculations(user_id, width, height, count, glass, color, fitting, fitting_count,
                                    handle, delivery, usd, rate, total_sum)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) RETURNING id""",
        user_id, d["width"], d["height"], d["count"], d["glass"], d["color"], d["fitting"], d["fitting_count"],
        d["side"], d["delivery"], usd, rate, total_sum)


async def mark_ordered(calc_id, customer_name, phone):
    await pool.execute("UPDATE calculations SET ordered_at = now(), customer_name = $2, phone = $3 WHERE id = $1",
                       calc_id, customer_name, phone)


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
          coalesce(sum(usd) FILTER (WHERE ordered_at IS NOT NULL), 0)     AS ord_usd
        FROM calculations""")


async def export_rows():
    return await pool.fetch("""
        SELECT c.id, to_char(c.created_at, 'YYYY-MM-DD HH24:MI') AS created_at, u.id AS user_id, u.username, u.full_name, c.customer_name, coalesce(c.phone, u.phone) AS phone,
               c.width, c.height, c.count, c.glass, c.color, c.fitting, c.fitting_count, c.handle,
               c.delivery, c.usd, c.rate, c.total_sum,
               to_char(c.ordered_at, 'YYYY-MM-DD HH24:MI') AS ordered_at
        FROM calculations c JOIN users u ON u.id = c.user_id ORDER BY c.id""")


async def active_user_ids():
    return [r["id"] for r in await pool.fetch("SELECT id FROM users WHERE NOT blocked")]


async def mark_blocked(user_id):
    await pool.execute("UPDATE users SET blocked = TRUE WHERE id = $1", user_id)
