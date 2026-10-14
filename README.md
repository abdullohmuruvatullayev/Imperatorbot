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

- 📊 Statistika — bugun / oxirgi 7 kun (**kunma-kun**) / jami, buyurtmalar holati,
  tasdiqlangan va bekor qilingan summalari, **o'rtacha chek**
- 📥 Eksport (CSV, Excel'da ochiladi)
- 📋 **Buyurtmalar tarixi** — sahifalangan ro'yxat (ko'pi 10 ta/sahifa),
  🔍 **qidiruv** (buyurtma ID, mijoz ismi, telefon yoki username),
  buyurtma kartasi (fasadlar, narx, kurs) va **admin panelidan Tasdiqlandi / Bekor qilindi**
  (mijozga xabar ketadi; guruhdagi qaror bilan bir xil ishlaydi)
- 🚫 **Bloklangan mijozlar** — ro'yxat va blokdan olish (mijoz /start qilsa ham blok o'zi ochiladi)
- 🪟 Oyna turlari, 🎨 Profil ranglari, 🔩 Furnitura — ro'yxatdagi mahsulot ustiga bosing: nomi, narxi, rasmi,
  yashirish/ko'rsatish, o'chirish. "➕ Yangi qo'shish" bilan yangi mahsulot (nom -> narx -> rasm).
  O'chirilgan mahsulot eski buyurtmalarda nomi bilan qoladi. Mijozga kamida bitta variant ko'rinib turadi.
- ⚙️ Narx sozlamalari — har birining **qayerda ishlatilishi** yozilgan
  (profil, yig'ish, ugolnik, rezinka, yetkazish, zaxira kurs)
- 📢 Xabar yuborish (tasdiqlash bilan)

Buyurtmalar guruhga keladi (Tasdiqlandi / Bekor qilindi tugmalari, #tasdiqlangan / #bekor_qilingan hashtaglari).
Tarixda "Tasdiqlanmagan" deb yozilganlari — mijoz hisobni yasagan, lekin tasdiqlash tugmasini basmagan
(admin o'zi tasdiqlasa, u to'liq buyurtmaga aylanadi).

## Tillar

Mijoz birinchi /start da tilni tanlaydi (o'zbekcha / ruscha), keyin /lang bilan o'zgartiradi.
Mijoz matnlari: `texts.py` (kalit -> o'zbekcha, ruscha). Mahsulotning ruscha nomi admin panelda tahrirlanadi.
Admin panel va guruh kartalari o'zbekcha (guruhda mijoz tili ko'rsatiladi).

## Mijoz oqimi (10 qadam)

1. **Nechta fasad** (1–100)
2. **Har bir fasad o'lchami** — navbatma-navbat, **har birida chizma (rasm) chiqadi**.
   ⚠️ Har doim **avval BO'YI, keyin ENI**. Rasmda aynan so'ralayotgan o'q **yashil**:
   - `Bo'yi?` → rasmda **chapdagi** vertikal o'q yashil → `1800`
   - `Eni?` → rasmda **pastdagi** gorizontal o'q yashil, bo'yi yashil saqlanadi → `900`
   - Kiritilgach → rasmda **ikkala o'q ham yashil**, o'lcham haqiqiy nisbatda
   - Ikkalasini birdan yozish ham mumkin: `1800 900`
3. **Ruchkali yoki ruchkasiz**. Ruchkali bo'lsa — **barcha fasadlar ro'yxati** chiqadi.
   Har biriga bosing va **Chap / O'ng** ni tanlang.
   Belgilanganlar ✅ va tomoni bilan ko'rinadi. Hammasi belgilangach **✅ Tayyor** tugmasi chiqadi.
   Ruchkasiz deb belgilansa — bu qadam o'tkazib yuboriladi.
4–5. Oyna turi va profil rangi (karusel, rasm + nom)
6. Furnitura turi
7. Har bir fasadga furnitura soni (fachadlar ro'yxati — ruchka qismiga o'xshash)
8. Yetkazib berish
9–10. Ism va telefon → tasdiqlash

Har bir fasad o'lchami bazada alohida saqlanadi (`calculations.facades` JSONB), narx ham har biriga alohida
hisoblanadi. Eski buyurtmalarda bu ustun bo'sh — ular uchun bitta o'lcham `count` marta takrorlanadi.

## Fayllar

- `bot.py` — bot; `db.py` — PostgreSQL; `prices.py` — nomlar, boshlang'ich narxlar, hisoblash formulasi (`python prices.py` → `ok`)
- Hisoblash: `calc_facade()` (bitta fasad) → `calc_total()` (har xil o'lchamli fasadlar yig'indisi).
  `calc_usd()` — bir xil o'lchamli `count` ta fasad (eski API).
- `diagram.py` — o'lcham kiritishda chizma (PNG) chizadi (`python diagram.py` → `ok`).
  **Nega Pillow, SVG emas:** Telegram Bot API SVG qabul qilmaydi; CairoSVG SVG→PNG uchun tizim
  darajasidagi `libcairo` kutadi (Railway'da `OSError: no library called "libcairo-2" was found`)
  va shriftlarni tizimdan izlaydi. Pillow bilan bu muammolar yo'q.
- `fonts/DejaVuSans.ttf` — chizma shrifti (ochiq kodli). **PIL default shriftida KIRILL YO'Q**,
  shuning uchun bu fayl majburiy. Shrift topilmasa chizma matnsiz chiziladi, bot ishlashda davom etadi.
- Har bir chizma Telegram'da `file_id` bilan keshlanadi — bir xil chizma qayta yuklanmaydi.
- Mahsulotlar bazada (`products`); `prices.py` dagi ro'yxat faqat birinchi ishga tushishda yoziladi.

Rasm tartibi: admin paneldan yuklangan -> `images/` papkadagi -> `no_photo.png`. Papkadagi nomlar:

- Oyna: glass_peppil, glass_yodiviy, glass_prazrachniy, glass_tosh, glass_tosh_tillali, glass_tosh_peppili,
  glass_ref_prazrachniy, glass_ref_yodiviy, glass_ref_peppil, glass_ref_matoviy, glass_lakabel
  (glass_ref_* bo'lmasa umumiy `glass_ref` ishlatiladi)
- Rang: color_qora, color_tilla_mat, color_tilla_glyans, color_shanpan
