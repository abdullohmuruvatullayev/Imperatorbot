# Alyumin fasad narx boti

## Railway'ga joylash

1. Papkani GitHub'ga yuklang (`.gitignore` tayyor) va Railway'da **New Project → Deploy from GitHub repo**.
2. Shu projectga **+ New → Database → PostgreSQL** qo'shing.
3. Bot servisining **Variables** bo'limiga:
   - `BOT_TOKEN` — @BotFather bergan token
   - `DATABASE_URL` — `${{Postgres.DATABASE_URL}}` (Railway o'zi ulaydi)
   - `ADMIN_IDS` — adminlar Telegram id'lari, vergul bilan: `123456789,987654321` (id'ni @userinfobot dan bilish mumkin)
4. Deploy. Start buyrug'i `railway.json` da: `python bot.py`. Jadvallar birinchi ishga tushishda o'zi yaratiladi.

⚠️ Botni bir vaqtda faqat **bitta** joyda ishga tushiring (Railway'da ishlayotganda kompyuterda `python bot.py` qilmang — Telegram ikkalasiga ham ruxsat bermaydi).

## Lokal ishga tushirish (PowerShell)

    $env:BOT_TOKEN="..."; $env:DATABASE_URL="postgresql://..."; $env:ADMIN_IDS="123456789"
    python bot.py

## Admin panel (`/admin`)

Tugmalar: 📊 Statistika, 📥 Eksport (CSV, Excel'da ochiladi), 💲 Narxlar (tanlang -> yangi qiymat yozing; oyna uchun `yoq` = yashirish),
🖼 Rasmlar (tanlang -> yangi rasm yuboring; bazada saqlanadi, deploy kerak emas), 📢 Xabar yuborish (tasdiqlash bilan).

Buyurtma (telefon raqam bilan) va mijoz izohlari adminlarga darhol keladi.

## Fayllar

- `bot.py` — bot; `db.py` — PostgreSQL; `prices.py` — nomlar, boshlang'ich narxlar, hisoblash formulasi (`python prices.py` → `ok`)
- Yangi oyna/furnitura turi qo'shish: `prices.py` dagi ro'yxatga qo'shing — narxi bazaga avtomatik yoziladi.

Rasm tartibi: admin paneldan yuklangan -> `images/` papkadagi -> `no_photo.png`. Papkadagi nomlar:

- Oyna: glass_peppil, glass_yodiviy, glass_prazrachniy, glass_tosh, glass_tosh_tillali, glass_tosh_peppili,
  glass_ref_prazrachniy, glass_ref_yodiviy, glass_ref_peppil, glass_ref_matoviy, glass_lakabel
  (glass_ref_* bo'lmasa umumiy `glass_ref` ishlatiladi)
- Rang: color_qora, color_tilla_mat, color_tilla_glyans, color_shanpan
