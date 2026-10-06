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

- 📊 Statistika, 📥 Eksport (CSV, Excel'da ochiladi)
- 🪟 Oyna turlari, 🎨 Profil ranglari, 🔩 Furnitura — ro'yxatdagi mahsulot ustiga bosing: nomi, narxi, rasmi,
  yashirish/ko'rsatish, o'chirish. "➕ Yangi qo'shish" bilan yangi mahsulot (nom -> narx -> rasm).
  O'chirilgan mahsulot eski buyurtmalarda nomi bilan qoladi. Mijozga kamida bitta variant ko'rinib turadi.
- ⚙️ Narx sozlamalari — profil, yig'ish, ugolnik, rezinka, yetkazish, zaxira kurs
- 📢 Xabar yuborish (tasdiqlash bilan)

Buyurtmalar guruhga keladi (Tasdiqlandi / Bekor qilindi tugmalari, #tasdiqlangan / #bekor_qilingan hashtaglari).

## Tillar

Mijoz birinchi /start da tilni tanlaydi (o'zbekcha / ruscha), keyin /lang bilan o'zgartiradi.
Mijoz matnlari: `texts.py` (kalit -> o'zbekcha, ruscha). Mahsulotning ruscha nomi admin panelda tahrirlanadi.
Admin panel va guruh kartalari o'zbekcha (guruhda mijoz tili ko'rsatiladi).

## Fayllar

- `bot.py` — bot; `db.py` — PostgreSQL; `prices.py` — nomlar, boshlang'ich narxlar, hisoblash formulasi (`python prices.py` → `ok`)
- Mahsulotlar bazada (`products`); `prices.py` dagi ro'yxat faqat birinchi ishga tushishda yoziladi.

Rasm tartibi: admin paneldan yuklangan -> `images/` papkadagi -> `no_photo.png`. Papkadagi nomlar:

- Oyna: glass_peppil, glass_yodiviy, glass_prazrachniy, glass_tosh, glass_tosh_tillali, glass_tosh_peppili,
  glass_ref_prazrachniy, glass_ref_yodiviy, glass_ref_peppil, glass_ref_matoviy, glass_lakabel
  (glass_ref_* bo'lmasa umumiy `glass_ref` ishlatiladi)
- Rang: color_qora, color_tilla_mat, color_tilla_glyans, color_shanpan
