import asyncio
import csv
import html
import io
import json
import logging
import os
import re
import urllib.request
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (BotCommand, BufferedInputFile, CallbackQuery, FSInputFile, InlineKeyboardButton,
                           InlineKeyboardMarkup, InputMediaPhoto, KeyboardButton, Message, ReplyKeyboardMarkup,
                           ReplyKeyboardRemove)

import db
import diagram
import prices as P
from texts import TEXTS

ROOT = Path(__file__).parent

# .env (lokal) — Railway Variables'dagi qiymatlar ustun turadi
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        k, sep, v = line.partition("=")
        if sep and not k.strip().startswith("#") and v.strip():
            os.environ.setdefault(k.strip(), v.strip().strip('"\''))

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}
GROUP_ID = int(os.getenv("GROUP_ID", "-1004405057037"))  # buyurtma va izohlar shu guruhga
PROFILE_LINK = "https://t.me/abdulloh_3344"
CONTACT = f'<a href="{PROFILE_LINK}">@{PROFILE_LINK.rsplit("/", 1)[-1]}</a>'  # matnda: @abdulloh_3344
IMAGES = ROOT / "images"
# Telegram'ning rasmiy premium (animatsiyali) emojilari: emoji -> custom_emoji_id.
# Bot egasida Telegram Premium bo'lgani uchun ishlaydi; bo'lmasa oddiy emoji ko'rinadi.
EMOJI = json.loads((ROOT / "premium_emoji.json").read_text(encoding="utf-8"))
LINE = "━━━━━━━━━━━━━━━━━━"

# Katalog turlari: sarlavha, emoji, narx birligi (None = narxsiz), rasmi bormi
KINDS = {
    "glass": {"title": "Oyna turlari", "one": "oyna turi", "icon": "🪟", "unit": "$/m²", "image": True},
    "color": {"title": "Profil ranglari", "one": "profil rangi", "icon": "🎨", "unit": None, "image": True},
    "fitting": {"title": "Furnitura", "one": "furnitura", "icon": "🔩", "unit": "$/dona", "image": False},
}

dp = Dispatcher()
is_admin = F.from_user.id.in_(ADMIN_IDS)


class Form(StatesGroup):
    count = State()        # nechta fasad
    dims = State()         # har bir fasad: BO'YI (mm)
    width = State()        # har bir fasad: ENI (mm)
    glass = State()
    color = State()
    fitting = State()
    fit_list = State()     # furnitura soni: fasadlar ro'yxati
    fit = State()          # furnitura soni: tanlangan fasadga son kiritish
    handle = State()
    side = State()         # ruchka: qaysi fasad -> qaysi tomon
    delivery = State()
    contact = State()
    name = State()
    phone = State()
    comment = State()


# ================= Dizayn yordamchilari =================

def pe(ch):
    """Premium emoji (matn uchun); ro'yxatda bo'lmasa oddiy emoji."""
    i = EMOJI.get(ch.replace("️", ""))
    return f'<tg-emoji emoji-id="{i}">{ch}</tg-emoji>' if i else ch


STEPS = 9  # soni, o'lchamlar, ruchka, oyna, rang, furnitura, furnitura soni, yetkazish, kontakt

# Matndagi oddiy emojilarni premium emojiga aylantirish (uzunlari birinchi: ko'p belgili emoji bo'linmasin)
_EMOJI_RE = re.compile("|".join(re.escape(k) + "\ufe0f?" for k in sorted(EMOJI, key=len, reverse=True)
                                if k and not k.isascii()))


def rich(text):
    return _EMOJI_RE.sub(lambda m: f'<tg-emoji emoji-id="{EMOJI[m.group(0).replace(chr(0xFE0F), "")]}">'
                                   f'{m.group(0)}</tg-emoji>', text)


def t(lang, key, **kw):
    """Mijoz tilidagi matn (texts.py). 'b_'/'a_' kalitlari — tugma/ogohlantirish: oddiy matn."""
    text = TEXTS[key][lang == "ru"].format(line=LINE, max=P.MAX_MM, fmax=P.MAX_FACADES, contact=CONTACT,
                                           total=STEPS, **kw)
    return text if key.startswith(("b_", "a_")) else rich(text)


def facades_of(o):
    """Buyurtma fasadlari: [{'w':.., 'h':.., 'handle':.., 'fit':..}, ...].
    Eski buyurtmalarda facades yo'q — bitta o'lcham count marta takrorlanadi,
    furnitura soni esa fitting_count ustunidan olinadi."""
    if o.get("facades"):
        return json.loads(o["facades"])
    return [{"w": o["width"], "h": o["height"], "handle": o["handle"],
             "fit": o["fitting_count"]}] * (o["count"] or 1)


def dims_block(o, lang):
    """Buyurtma kartasidagi o'lchamlar bloki: har bir fasad alohida qatorda (bo'yi × eni)."""
    lines = [t(lang, "dims_line", n=i, h=f["h"], w=f["w"]) for i, f in enumerate(facades_of(o), 1)]
    return t(lang, "dims_title") + "\n".join(lines) + "\n"


def step(lang, n):
    return t(lang, "step", n=n)


def btn(text, data, style=None, icon=None):
    """style: 'success' (yashil), 'danger' (qizil), 'primary' (ko'k). icon: emoji — premium bo'lsa tugma ikonkasi.
    data 'http' bilan boshlansa — havola tugmasi."""
    i = EMOJI.get(icon.replace("️", "")) if icon else None
    text = text if i or not icon else f"{icon} {text}"
    link = {"url": data} if data.startswith("http") else {"callback_data": data}
    return InlineKeyboardButton(text=text, style=style, icon_custom_emoji_id=i, **link)


def grid(buttons, per_row=1):
    """buttons: [(text, data[, style[, icon]]), ...]"""
    rows = [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]
    return InlineKeyboardMarkup(inline_keyboard=[[btn(*b) for b in r] for r in rows])


def find_image(name):
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = IMAGES / f"{name}.{ext}"
        if p.exists():
            return p


def parse_int(text, lo, hi):
    text = (text or "").strip().replace(" ", "")
    if text.isdigit() and lo <= int(text) <= hi:
        return int(text)


def parse_price(text):
    try:
        v = float((text or "").strip().replace(",", ".").replace(" ", ""))
    except ValueError:
        return None
    return v if 0 <= v < 10_000_000 else None


def get_rate():
    try:
        with urllib.request.urlopen("https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/", timeout=10) as r:
            return float(json.load(r)[0]["Rate"])
    except Exception:
        logging.exception("Kursni olib bo'lmadi")
        return db.settings["fallback_rate"]


def money(x):
    return f"{x:,.2f}".replace(",", " ") if isinstance(x, float) else f"{x:,}".replace(",", " ")


def user_line(u):
    return f"@{u.username or '-'} ({html.escape(u.full_name)}, id {u.id})"


def pname(key, lang="uz"):
    """Mahsulot nomi mijoz tilida; o'chirilgan bo'lsa ham eski buyurtmalarda chiqadi."""
    p = db.products.get(key, {})
    return (lang == "ru" and p.get("name_ru")) or p.get("name", key)


def items(kind, admin=False):
    """Katalogdagi mahsulotlar. Mijozga yashirinlari ko'rinmaydi, o'chirilganlar hech kimga."""
    return [p for p in db.products.values() if p["kind"] == kind and not p["deleted"] and (admin or not p["hidden"])]


# --- Rasmlar ---
_file_ids = {}  # papkadagi rasmlar qayta yuklanmasin: path -> Telegram file_id


def photo_for(p):
    """(rasm, path): admin yuklagan -> papkadagi -> umumiy glass_ref -> no_photo."""
    if p.get("file_id"):
        return p["file_id"], None
    image = p.get("image") or ""
    path = (image and find_image(image)) or (image.startswith("glass_ref_") and find_image("glass_ref")) \
        or find_image("no_photo")
    return _file_ids.get(path) or FSInputFile(path), path


def remember(path, m):
    if path and isinstance(m, Message) and m.photo:
        _file_ids[path] = m.photo[-1].file_id


# --- O'lcham chizmasi (rasm) ---
_diagram_ids = {}  # kalit -> Telegram file_id (bir xil chizma qayta yuklanmaydi)


def dg_texts(lang):
    """diagram.py uchun tilga bog'liq yozuvlar."""
    keys = ("dg_title", "dg_mm", "dg_height", "dg_width", "dg_no_height", "dg_no_width", "dg_handle")
    return {k: TEXTS[k][lang == "ru"] for k in keys}


async def send_diagram(msg: Message, lang, *, n, n_all, height=None, width=None, handle=None, ask=None,
                       caption=None, reply_markup=None):
    """Fasad chizmasini yuboradi. Chizma yasalmasa — faqat matn (oqim uzulmaydi).

    Bir xil chizma Telegram'ga qayta yuklanmaydi: file_id keshda saqlanadi.
    """
    texts = dg_texts(lang)
    png = await asyncio.to_thread(diagram.diagram, n, n_all, height, width, handle, texts, ask)
    if png is None:                      # chizma bo'lmasa — matn bilan davom etamiz
        return await msg.answer(caption or "", reply_markup=reply_markup)
    key = (lang, n, n_all, height, width, handle, ask)
    fid = _diagram_ids.get(key)
    try:
        m = await msg.answer_photo(BufferedInputFile(png, f"fasad_{n}.png") if not fid else fid,
                                   caption=caption, reply_markup=reply_markup)
    except TelegramBadRequest:           # eskigan file_id — qaytadan yuklaymiz
        m = await msg.answer_photo(BufferedInputFile(png, f"fasad_{n}.png"),
                                   caption=caption, reply_markup=reply_markup)
    if m.photo:
        _diagram_ids[key] = m.photo[-1].file_id
    return m


async def screen(msg: Message, text, markup=None, photo=None, path=None, edit=True):
    """Bitta xabar ichida navigatsiya: imkon bo'lsa shu xabarni tahrirlaydi (matn<->matn, rasm<->rasm),
    bo'lmasa eskisini o'chirib yangisini yuboradi. Chat toza qoladi."""
    if edit:
        try:
            if photo is not None and msg.photo:
                m = await msg.edit_media(InputMediaPhoto(media=photo, caption=text), reply_markup=markup)
                remember(path, m)
                return m
            if photo is None and msg.text:
                return await msg.edit_text(text, reply_markup=markup)
        except TelegramBadRequest as e:
            if "not modified" in str(e):
                return msg
        try:
            await msg.delete()
        except TelegramBadRequest:
            pass
    if photo is not None:
        m = await msg.answer_photo(photo, caption=text, reply_markup=markup)
        remember(path, m)
        return m
    return await msg.answer(text, reply_markup=markup)


async def notify(bot: Bot, text, reply_markup=None):
    """Guruhga yuboradi; guruh ishlamasa buyurtma yo'qolmasin deb adminlarga."""
    try:
        return await bot.send_message(GROUP_ID, text, reply_markup=reply_markup)
    except Exception:
        logging.exception("Guruhga yuborib bo'lmadi: %s", GROUP_ID)
    for admin in ADMIN_IDS:
        try:
            await bot.send_message(admin, text, reply_markup=reply_markup)
        except Exception:
            logging.exception("Adminga yuborib bo'lmadi: %s", admin)


# ================= ADMIN PANEL =================
# Admin handlerlari birinchi ro'yxatdan o'tadi, shunda admin hisoblash o'rtasida ham /admin ocha oladi.
# Har bir ekran: yo'l (Admin › Bo'lim › Mahsulot), sarlavha, qisqa izoh, bir ustunli tugmalar.

class AdminForm(StatesGroup):
    edit = State()       # mahsulot nomi / narxi
    photo = State()      # mahsulot rasmi
    new_name = State()   # yangi mahsulot
    new_name_ru = State()
    new_price = State()
    setting = State()    # umumiy narx
    broadcast = State()
    find = State()       # buyurtma qidiruv


NOT_CMD = ~F.text.startswith("/")  # admin kutish holatida /start yozsa, u buyruq sifatida ishlasin
HOME = ("🏠 Bosh menyu", "adm:menu")


def rows(*rs):
    """Har bir argument — bitta qator: [(text, data[, style]), ...]"""
    return InlineKeyboardMarkup(inline_keyboard=[[btn(*b) for b in r] for r in rs if r])


def num(v):
    """6 -> '6', 8.5 -> '8.5', 100000 -> '100 000'"""
    return f"{v:,.2f}".replace(",", " ").rstrip("0").rstrip(".")


def head(path, title):
    """Yuqorida qayerdaligi: Admin › Oyna turlari › Peppil"""
    return f"<i>🛠 Admin{''.join(' › ' + html.escape(p) for p in path)}</i>\n\n{title}\n{LINE}\n"


def notice_line(notice):
    return f"{notice}\n\n" if notice else ""


async def ask(msg: Message, state: FSMContext, new_state, text, cancel, edit=True, **data):
    """Admin'dan qiymat so'raydi. So'rov xabari id'si saqlanadi — javobdan keyin ikkalasi o'chiriladi."""
    m = await screen(msg, text, rows([("❌ Bekor qilish", cancel, "danger")]), edit=edit)
    await state.set_state(new_state)
    await state.update_data(prompt_id=m.message_id, **data)


async def clean_input(msg: Message, state: FSMContext):
    """Admin javobini va so'rov xabarini o'chiradi — chatda faqat yangilangan karta qoladi."""
    d = await state.get_data()
    for mid in (msg.message_id, d.get("prompt_id")):
        try:
            await msg.bot.delete_message(msg.chat.id, mid)
        except Exception:
            pass
    await state.clear()


# --- Bosh menyu ---

def admin_home():
    n = {k: len(items(k, admin=True)) for k in KINDS}
    text = (f"{pe('🛠')} <b>ADMIN PANEL</b>\n{LINE}\n"
            f"<b>Katalog</b> — mahsulot qo'shish, narxi, rasmi, o'chirish\n"
            f"<b>Umumiy narxlar</b> — profil, yig'ish, yetkazish va boshqalar\n"
            f"<b>Buyurtmalar</b> — tarix, qidiruv, tasdiqlash/bekor qilish\n"
            f"<b>Hisobot</b> — statistika va Excel fayl\n"
            f"<b>Xabar</b> — barcha mijozlarga e'lon\n\n"
            f"Bo'limni tanlang {pe('👇')}")
    markup = rows([(f"🪟 Oyna turlari · {n['glass']} ta", "adm:k:glass", "primary")],
                  [(f"🎨 Profil ranglari · {n['color']} ta", "adm:k:color", "primary")],
                  [(f"🔩 Furnitura · {n['fitting']} ta", "adm:k:fitting", "primary")],
                  [("⚙️ Umumiy narxlar", "adm:set", "primary")],
                  [("📊 Statistika", "adm:stat"), ("📥 Excel hisobot", "adm:export")],
                  [("📋 Buyurtmalar tarixi", "adm:orders"), ("🚫 Bloklangan mijozlar", "adm:blocked")],
                  [("📢 Mijozlarga xabar yuborish", "adm:bc", "success")])
    return text, markup


@dp.message(Command("admin"), is_admin)
async def admin(msg: Message, state: FSMContext):
    await state.clear()
    text, markup = admin_home()
    await msg.answer(text, reply_markup=markup)


@dp.callback_query(F.data == "adm:menu", is_admin)
async def adm_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer()
    await screen(cb.message, *admin_home())


# --- Statistika va eksport ---

STATUS_NAME = {"new": "Kutilmoqda", "confirmed": "Tasdiqlangan", "cancelled": "Bekor qilingan"}
HANDLE_NAME = {"chap": "Chap", "ong": "O'ng"}  # CSV uchun (admin paneli o'zbekcha)


@dp.callback_query(F.data == "adm:stat", is_admin)
async def adm_stat(cb: CallbackQuery):
    s = await db.stats()
    days = await db.stats_days()
    avg = float(s['confirmed_usd']) / s['st_confirmed'] if s['st_confirmed'] else 0
    week = "\n".join(f"• {d['day']}: <b>{d['calc']}</b> hisob, <b>{d['ord']}</b> buyurtma"
                     for d in days)
    await cb.answer()
    await screen(cb.message,
                 head(["Statistika"], f"{pe('📊')} <b>STATISTIKA</b>") +
                 f"📅 <b>BUGUN</b>\n"
                 f"• Yangi mijozlar: <b>{s['new_today']} ta</b>\n"
                 f"• Narx hisoblandi: <b>{s['calc_today']} marta</b>\n"
                 f"• Buyurtma berildi: <b>{s['ord_today']} ta</b>\n\n"
                 f"🗓 <b>OXIRGI 7 KUN</b> (kunma-kun)\n{week}\n\n"
                 f"{pe('📈')} <b>BOT ISHGA TUSHGANDAN BERI</b>\n"
                 f"• Jami mijozlar: <b>{s['users']} ta</b>\n"
                 f"• Narx hisoblandi: <b>{s['calc_all']} marta</b>\n"
                 f"• Buyurtma berildi: <b>{s['ord_all']} ta</b>\n\n"
                 f"{pe('🛒')} <b>BUYURTMALAR HOLATI</b>\n"
                 f"{pe('⏳')} Javob kutmoqda: <b>{s['st_new']} ta</b>\n"
                 f"{pe('✅')} Tasdiqlangan: <b>{s['st_confirmed']} ta</b> — "
                 f"<b>{money(float(s['confirmed_usd']))} $</b>\n"
                 f"{pe('❌')} Bekor qilingan: <b>{s['st_cancelled']} ta</b> — "
                 f"<b>{money(float(s['cancelled_usd']))} $</b>\n\n"
                 f"{pe('💳')} <b>O'rtacha chek: {money(avg)} $</b>",
                 rows([("🔄 Yangilash", "adm:stat", "primary")], [HOME]))


@dp.callback_query(F.data == "adm:export", is_admin)
async def adm_export(cb: CallbackQuery):
    await cb.answer("Tayyorlanmoqda...")
    rows_ = await db.export_rows()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["ID", "Sana", "User ID", "Username", "Telegram ismi", "Buyurtmachi", "Telefon",
                "Fasadlar (bo'yi x eni mm)", "Soni", "Oyna", "Rang", "Furnitura", "Furnitura/fasad",
                "Ruchka", "Yetkazish", "USD", "Kurs", "So'm", "Buyurtma vaqti", "Holat", "Kim o'zgartirdi"])
    for r in rows_:
        dims = " | ".join(f"{f['h']}x{f['w']}" for f in facades_of(r))
        hs = "; ".join(f"{i}:{HANDLE_NAME[f['handle']]}" for i, f in enumerate(facades_of(r), 1)
                       if f.get("handle")) or "yo'q"
        fs = "; ".join(f"{i}:{f.get('fit', 0)}" for i, f in enumerate(facades_of(r), 1)) or "yo'q"
        w.writerow([r["id"], r["created_at"], r["user_id"], r["username"] or "", r["full_name"] or "",
                    r["customer_name"] or "", r["phone"] or "", dims, len(facades_of(r)),
                    pname(r["glass"]), pname(r["color"]), pname(r["fitting"]), fs,
                    hs, "ha" if r["delivery"] else "yo'q", r["usd"], r["rate"], r["total_sum"],
                    r["ordered_at"] or "", STATUS_NAME.get(r["status"], "Faqat hisob"), r["status_by"] or ""])
    data = buf.getvalue().encode("utf-8-sig")  # BOM — Excel o'zbekcha harflarni to'g'ri ochadi
    await cb.message.answer_document(BufferedInputFile(data, "hisoblar.csv"),
                                     caption=f"📥 <b>Excel hisobot</b>\nJami: {len(rows_)} ta hisob-kitob.\n"
                                             f"<i>Faylni Excel yoki Google Sheets'da oching.</i>")


# --- Katalog: ro'yxat ---

def price_str(p):
    unit = KINDS[p["kind"]]["unit"]
    return f"{num(p['price'])} {unit}" if unit and p["price"] is not None else ""


async def show_kind(msg: Message, kind, edit=True, notice=None):
    k = KINDS[kind]
    lst = items(kind, admin=True)
    hidden = sum(p["hidden"] for p in lst)
    text = (notice_line(notice) + head([k["title"]], f"{k['icon']} <b>{k['title'].upper()}</b>")
            + f"Jami: <b>{len(lst)} ta</b>" + (f"  ·  🙈 yashirin: <b>{hidden} ta</b>" if hidden else "")
            + (f"\nNarxlar {k['unit']} hisobida." if k["unit"] else "") + "\n\n"
            f"✏️ O'zgartirish yoki o'chirish uchun <b>mahsulot ustiga</b> bosing.\n"
            f"➕ Yangisini qo'shish — <b>yashil tugma</b>.")
    buttons = [[(f"{i}. {'🙈 ' if p['hidden'] else ''}{p['name']}" + (f" — {price_str(p)}" if k["unit"] else ""),
                 f"adm:pr:{p['key']}")] for i, p in enumerate(lst, 1)]
    await screen(msg, text, rows(*buttons, [(f"➕ Yangi {k['one']} qo'shish", f"adm:new:{kind}", "success")], [HOME]),
                 edit=edit)


@dp.callback_query(F.data.startswith("adm:k:"), is_admin)
async def adm_kind(cb: CallbackQuery, state: FSMContext):
    kind = cb.data[6:]
    if kind not in KINDS:
        return await cb.answer()
    await state.clear()
    await cb.answer()
    await show_kind(cb.message, kind)


# --- Katalog: bitta mahsulot ---

def image_status(p):
    if p["file_id"]:
        return "bor ✅"
    if p["image"] and find_image(p["image"]):
        return "bor (dastlabki rasm)"
    return "yo'q ➖"


async def show_product(msg: Message, key, edit=True, notice=None):
    p = db.products[key]
    k = KINDS[p["kind"]]
    lines = [f"🇺🇿 Nomi (o'zbekcha): <b>{html.escape(p['name'])}</b>",
             f"🇷🇺 Nomi (ruscha): <b>{html.escape(p['name_ru'] or '— yozilmagan')}</b>"]
    if k["unit"]:
        lines.append(f"💵 Narxi: <b>{price_str(p)}</b>")
    if k["image"]:
        lines.append(f"🖼 Rasmi: <b>{image_status(p)}</b>")
    lines.append("🙈 Holati: <b>yashirin</b> — mijozlar ko'rmaydi" if p["hidden"]
                 else "👁 Holati: <b>mijozlarga ko'rinadi</b>")
    text = (notice_line(notice) + head([k["title"], p["name"]], f"{k['icon']} <b>{html.escape(p['name'])}</b>")
            + "\n".join(lines) + f"\n\nNimani o'zgartiramiz? {pe('👇')}")
    markup = rows([("✏️ O'zbekcha nomini o'zgartirish", f"adm:e:name:{key}", "primary")],
                  [("✏️ Ruscha nomini o'zgartirish", f"adm:e:name_ru:{key}", "primary")],
                  [("💵 Narxini o'zgartirish", f"adm:e:price:{key}", "primary")] if k["unit"] else None,
                  [("🖼 Rasmini almashtirish", f"adm:ph:{key}", "primary")] if k["image"] else None,
                  [("👁 Mijozlarga ko'rsatish" if p["hidden"] else "🙈 Mijozlardan yashirish", f"adm:hide:{key}")],
                  [("🗑 O'chirish", f"adm:del:{key}", "danger")],
                  [("⬅️ Ro'yxatga", f"adm:k:{p['kind']}"), HOME])
    photo, path = photo_for(p) if k["image"] else (None, None)
    await screen(msg, text, markup, photo, path, edit=edit)


@dp.callback_query(F.data.startswith("adm:pr:"), is_admin)
async def adm_product(cb: CallbackQuery, state: FSMContext):
    key = cb.data[7:]
    if key not in db.products:
        return await cb.answer()
    await state.clear()
    await cb.answer()
    await show_product(cb.message, key)


def last_visible(key):
    """Mijozga ko'rinadigan oxirgi mahsulotmi (uni yashirish/o'chirish mumkin emas)."""
    p = db.products[key]
    return not p["hidden"] and len(items(p["kind"])) <= 1


LAST_ONE = "Mijozlar uchun kamida bitta variant ko'rinib turishi kerak. Avval boshqasini qo'shing yoki ko'rsating."


@dp.callback_query(F.data.startswith("adm:hide:"), is_admin)
async def adm_hide(cb: CallbackQuery):
    key = cb.data[9:]
    p = db.products.get(key)
    if not p:
        return await cb.answer()
    if last_visible(key):
        return await cb.answer(LAST_ONE, show_alert=True)
    await db.update_product(key, "hidden", not p["hidden"])
    await cb.answer()
    await show_product(cb.message, key, notice="🙈 <b>Yashirildi</b> — mijozlar endi ko'rmaydi." if p["hidden"]
                       else "👁 <b>Mijozlarga ko'rsatildi.</b>")


@dp.callback_query(F.data.startswith("adm:del:"), is_admin)
async def adm_delete(cb: CallbackQuery):
    key = cb.data[8:]
    p = db.products.get(key)
    if not p:
        return await cb.answer()
    if last_visible(key):
        return await cb.answer(LAST_ONE, show_alert=True)
    await cb.answer()
    k = KINDS[p["kind"]]
    await screen(cb.message, head([k["title"], p["name"]], f"🗑 <b>{html.escape(p['name'])}</b> o'chirilsinmi?")
                 + "Mijozlar uni boshqa ko'rmaydi.\n<i>Eski buyurtmalarda nomi saqlanib qoladi.</i>",
                 rows([("🗑 Ha, o'chirish", f"adm:delok:{key}", "danger")], [("⬅️ Yo'q, qaytish", f"adm:pr:{key}")]))


@dp.callback_query(F.data.startswith("adm:delok:"), is_admin)
async def adm_delete_ok(cb: CallbackQuery):
    key = cb.data[10:]
    p = db.products.get(key)
    if not p or p["deleted"]:
        return await cb.answer()
    if last_visible(key):
        return await cb.answer(LAST_ONE, show_alert=True)
    await db.update_product(key, "deleted", True)
    await cb.answer()
    await show_kind(cb.message, p["kind"], notice=f"🗑 <b>{html.escape(p['name'])}</b> o'chirildi.")


# nomi / narxi
@dp.callback_query(F.data.startswith("adm:e:"), is_admin)
async def adm_edit(cb: CallbackQuery, state: FSMContext):
    _, _, field, key = cb.data.split(":")
    p = db.products.get(key)
    if not p or field not in ("name", "name_ru", "price"):
        return await cb.answer()
    await cb.answer()
    k = KINDS[p["kind"]]
    if field == "name":
        body = f"🇺🇿 <b>Yangi o'zbekcha nomni yozing</b>\nHozirgi: <b>{html.escape(p['name'])}</b>"
    elif field == "name_ru":
        body = (f"🇷🇺 <b>Yangi ruscha nomni yozing</b>\nHozirgi: <b>{html.escape(p['name_ru'] or '—')}</b>\n"
                f"<i>Rus tilini tanlagan mijozlar shu nomni ko'radi.</i>")
    else:
        body = f"💵 <b>Yangi narxni yozing</b> ({k['unit']})\nHozirgi: <b>{price_str(p)}</b>\n<i>Masalan: 22 yoki 5.5</i>"
    await ask(cb.message, state, AdminForm.edit, head([k["title"], p["name"]], f"{k['icon']} <b>{html.escape(p['name'])}</b>")
              + body, f"adm:pr:{key}", key=key, field=field)


def valid_name(text):
    text = " ".join((text or "").split())
    return text if 1 <= len(text) <= 40 else None


@dp.message(AdminForm.edit, is_admin, NOT_CMD)
async def adm_edit_set(msg: Message, state: FSMContext):
    d = await state.get_data()
    p = db.products[d["key"]]
    if d["field"] in ("name", "name_ru"):
        value = valid_name(msg.text)
        if value is None:
            return await msg.answer("❌ Nom 1 dan 40 belgigacha bo'lsin.")
        which = "o'zbekcha nomi" if d["field"] == "name" else "ruscha nomi"
        notice = f"✅ <b>Saqlandi:</b> {which} «{html.escape(p[d['field']] or '—')}» → «{html.escape(value)}»"
    else:
        value = parse_price(msg.text)
        if value is None:
            return await msg.answer("❌ Faqat son yozing. Masalan: 22 yoki 5.5")
        notice = f"✅ <b>Saqlandi:</b> narxi {price_str(p)} → {num(value)} {KINDS[p['kind']]['unit']}"
    await db.update_product(d["key"], d["field"], value)
    await clean_input(msg, state)
    await show_product(msg, d["key"], edit=False, notice=notice)


# rasmi
@dp.callback_query(F.data.startswith("adm:ph:"), is_admin)
async def adm_photo(cb: CallbackQuery, state: FSMContext):
    key = cb.data[7:]
    if key not in db.products:
        return await cb.answer()
    await cb.answer()
    await ask_photo(cb.message, state, key)


async def ask_photo(msg: Message, state: FSMContext, key, edit=True, new=False):
    p = db.products[key]
    k = KINDS[p["kind"]]
    text = (head([k["title"], p["name"]], f"{k['icon']} <b>{html.escape(p['name'])}</b>")
            + f"🖼 <b>Rasmini yuboring</b>\n<i>Galereyadan oddiy rasm sifatida (fayl emas).</i>")
    if new:
        markup = rows([("➡️ Rasmsiz saqlash", f"adm:pr:{key}")])
    else:
        markup = rows([("🗑 Yuklangan rasmni o'chirish", f"adm:phdel:{key}", "danger")] if p["file_id"] else None,
                      [("❌ Bekor qilish", f"adm:pr:{key}", "danger")])
    m = await screen(msg, text, markup, edit=edit)
    await state.set_state(AdminForm.photo)
    await state.update_data(prompt_id=m.message_id, key=key, new=new)


@dp.message(AdminForm.photo, F.photo, is_admin)
async def adm_photo_set(msg: Message, state: FSMContext):
    d = await state.get_data()
    await db.update_product(d["key"], "file_id", msg.photo[-1].file_id)
    await clean_input(msg, state)
    await show_product(msg, d["key"], edit=False,
                       notice="✅ <b>Yangi mahsulot qo'shildi.</b>" if d.get("new") else "✅ <b>Rasm saqlandi.</b>")


@dp.message(AdminForm.photo, is_admin, NOT_CMD)
async def adm_photo_wrong(msg: Message):
    await msg.answer("❌ Rasm yuboring — galereyadan, oddiy rasm sifatida.")


@dp.callback_query(F.data.startswith("adm:phdel:"), is_admin)
async def adm_photo_delete(cb: CallbackQuery, state: FSMContext):
    key = cb.data[10:]
    if key not in db.products:
        return await cb.answer()
    await db.update_product(key, "file_id", None)
    await state.clear()
    await cb.answer()
    await show_product(cb.message, key, notice="🗑 <b>Yuklangan rasm o'chirildi.</b>")


# yangi mahsulot: nom -> narx (bo'lsa) -> rasm (bo'lsa)
@dp.callback_query(F.data.startswith("adm:new:"), is_admin)
async def adm_new(cb: CallbackQuery, state: FSMContext):
    kind = cb.data[8:]
    if kind not in KINDS:
        return await cb.answer()
    await cb.answer()
    await state.clear()
    k = KINDS[kind]
    steps = "o'zbekcha nomi → ruscha nomi → " + ("narxi → " if k["unit"] else "") + ("rasmi" if k["image"] else "tayyor")
    await ask(cb.message, state, AdminForm.new_name, head([k["title"], "Yangi"], f"➕ <b>YANGI {k['one'].upper()}</b>")
              + f"<i>Qadamlar: {steps}</i>\n\n🇺🇿 <b>O'zbekcha nomini yozing:</b>", f"adm:k:{kind}", kind=kind)


@dp.message(AdminForm.new_name, is_admin, NOT_CMD)
async def adm_new_name(msg: Message, state: FSMContext):
    name = valid_name(msg.text)
    if not name:
        return await msg.answer("❌ Nom 1 dan 40 belgigacha bo'lsin.")
    kind = (await state.get_data())["kind"]
    k = KINDS[kind]
    await clean_input(msg, state)
    await ask(msg, state, AdminForm.new_name_ru, head([k["title"], "Yangi"], f"➕ <b>{html.escape(name)}</b>")
              + "🇷🇺 <b>Ruscha nomini yozing:</b>\n<i>Rus tilini tanlagan mijozlar shu nomni ko'radi.</i>",
              f"adm:k:{kind}", edit=False, kind=kind, name=name)


@dp.message(AdminForm.new_name_ru, is_admin, NOT_CMD)
async def adm_new_name_ru(msg: Message, state: FSMContext):
    name_ru = valid_name(msg.text)
    if not name_ru:
        return await msg.answer("❌ Nom 1 dan 40 belgigacha bo'lsin.")
    d = await state.get_data()
    kind, name = d["kind"], d["name"]
    k = KINDS[kind]
    if k["unit"]:
        await clean_input(msg, state)
        return await ask(msg, state, AdminForm.new_price, head([k["title"], "Yangi"], f"➕ <b>{html.escape(name)}</b>")
                         + f"💵 <b>Narxini yozing</b> ({k['unit']})\n<i>Masalan: 22 yoki 5.5</i>",
                         f"adm:k:{kind}", edit=False, kind=kind, name=name, name_ru=name_ru)
    await finish_new(msg, state, kind, name, name_ru, None)


@dp.message(AdminForm.new_price, is_admin, NOT_CMD)
async def adm_new_price(msg: Message, state: FSMContext):
    price = parse_price(msg.text)
    if price is None:
        return await msg.answer("❌ Faqat son yozing. Masalan: 22 yoki 5.5")
    d = await state.get_data()
    await finish_new(msg, state, d["kind"], d["name"], d["name_ru"], price)


async def finish_new(msg: Message, state: FSMContext, kind, name, name_ru, price):
    key = await db.add_product(kind, name, name_ru, price)
    await clean_input(msg, state)
    if KINDS[kind]["image"]:
        return await ask_photo(msg, state, key, edit=False, new=True)
    await show_product(msg, key, edit=False, notice="✅ <b>Yangi mahsulot qo'shildi.</b>")


# --- Umumiy narxlar ---

def setting_str(key):
    _, unit, _ = P.SETTINGS[key]
    return f"{num(db.settings[key])} {unit}"


# Har bir umumiy narx qayerda ishlatilishini tushuntirish
SETTING_HELP = {
    "profile": "Fasad perimetri bo'yicha — profilning har bir metri uchun",
    "handle_profile": "Ruchkali tomon (balandlik) — uning har bir metri uchun",
    "assembly_low": "Balandligi 1000 mm gacha bo'lgan har bir fasad uchun",
    "assembly_high": "Balandligi 1000 mm dan baland bo'lgan har bir fasad uchun",
    "corner": "Har bir fasadga 4 dona ugolnik",
    "rubber": "Profilning har bir metri uchun rezinka",
    "delivery": "Shahar bo'ylab yetkazib berish (so'mda, jami summaga qo'shiladi)",
    "fallback_rate": "CBU kursi olinmasa ishlatiladigan zaxira kurs (so'm)",
}


async def show_settings(msg: Message, edit=True, notice=None):
    lst = "\n".join(f"• <b>{name}</b> — {setting_str(k)}\n"
                      f"  <i>{SETTING_HELP[k]}</i>"
                      for k, (name, _, _) in P.SETTINGS.items())
    text = (notice_line(notice) + head(["Umumiy narxlar"], f"{pe('⚙')} <b>UMUMIY NARXLAR</b>")
            + "Bu narxlar har bir hisob-kitobda ishlatiladi.\n\n"
            + lst
            + f"\n\n✏️ O'zgartirish uchun <b>kerakli narx ustiga</b> bosing {pe('👇')}")
    buttons = [[(f"{name} — {setting_str(k)}", f"adm:s:{k}")] for k, (name, _, _) in P.SETTINGS.items()]
    await screen(msg, text, rows(*buttons, [HOME]), edit=edit)


@dp.callback_query(F.data == "adm:set", is_admin)
async def adm_settings(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer()
    await show_settings(cb.message)


@dp.callback_query(F.data.startswith("adm:s:"), is_admin)
async def adm_setting_pick(cb: CallbackQuery, state: FSMContext):
    key = cb.data[6:]
    if key not in P.SETTINGS:
        return await cb.answer()
    await cb.answer()
    name, unit, _ = P.SETTINGS[key]
    await ask(cb.message, state, AdminForm.setting,
              head(["Umumiy narxlar", name], f"⚙️ <b>{name}</b>")
              + f"<i>{SETTING_HELP[key]}</i>\n\n"
              + f"💵 <b>Yangi qiymatni yozing</b> ({unit})\nHozirgi: <b>{setting_str(key)}</b>",
              "adm:set", key=key)


@dp.message(AdminForm.setting, is_admin, NOT_CMD)
async def adm_setting_set(msg: Message, state: FSMContext):
    value = parse_price(msg.text)
    if value is None:
        return await msg.answer("❌ Faqat son yozing. Masalan: 6 yoki 0.8")
    key = (await state.get_data())["key"]
    old = setting_str(key)
    await db.set_setting(key, value)
    await clean_input(msg, state)
    await show_settings(msg, edit=False, notice=f"✅ <b>Saqlandi:</b> {P.SETTINGS[key][0]} {old} → {setting_str(key)}")


# --- Mijozlarga xabar ---

@dp.callback_query(F.data == "adm:bc", is_admin)
async def adm_bc(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    n = len(await db.active_user_ids())
    await ask(cb.message, state, AdminForm.broadcast, head(["Mijozlarga xabar"], f"{pe('📢')} <b>MIJOZLARGA XABAR</b>")
              + f"Xabar <b>{n}</b> ta mijozga boradi.\n\n"
              f"✏️ <b>Xabarni yuboring</b> — matn, rasm yoki video.\n<i>Yuborishdan oldin yana bir bor so'rayman.</i>",
              "adm:menu")


@dp.message(AdminForm.broadcast, is_admin, NOT_CMD)
async def adm_bc_preview(msg: Message, state: FSMContext):
    ids = await db.active_user_ids()
    await state.update_data(bc_chat=msg.chat.id, bc_msg=msg.message_id)
    await msg.reply(f"👆 Shu xabar <b>{len(ids)}</b> ta mijozga yuborilsinmi?",
                    reply_markup=rows([("✅ Ha, yuborish", "adm:bcgo", "success")], [("❌ Bekor qilish", "adm:menu", "danger")]))


@dp.callback_query(F.data == "adm:bcgo", is_admin)
async def adm_bc_go(cb: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    await state.clear()
    if "bc_msg" not in d:
        return await cb.answer("Xabar topilmadi, qaytadan boshlang.", show_alert=True)
    await cb.answer()
    ids = await db.active_user_ids()
    await cb.message.edit_text(f"{pe('📢')} {len(ids)} ta mijozga yuborilmoqda... Tugagach xabar beraman.")
    asyncio.create_task(broadcast(cb.bot, cb.message.chat.id, d["bc_chat"], d["bc_msg"], ids))


async def broadcast(bot: Bot, admin_chat, from_chat, message_id, ids):
    ok = failed = 0
    for uid in ids:
        for _ in range(2):  # RetryAfter bo'lsa bir marta qayta urinadi
            try:
                await bot.copy_message(uid, from_chat, message_id)
                ok += 1
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
                continue
            except TelegramForbiddenError:
                await db.mark_blocked(uid)
                failed += 1
            except Exception:
                logging.exception("Broadcast: %s", uid)
                failed += 1
            break
        await asyncio.sleep(0.05)  # Telegram limiti ~30 xabar/soniya
    await bot.send_message(admin_chat, f"{pe('✅')} <b>Xabar yuborildi:</b> {ok} ta mijozga.\n"
                                       f"Yetib bormadi (botni bloklagan): {failed} ta.",
                           reply_markup=rows([HOME]))


# --- Buyurtmalar tarixi ---

ORD_PER_PAGE = 10


def order_line(o):
    """Tarixdagi bitta buyurtma qatori."""
    who = o["customer_name"] or o["full_name"] or "-"
    st = STATUS_NAME.get(o["status"]) or "Tasdiqlanmagan"
    return (f"#{o['id']} · {o['created_str']} · {html.escape(who)}"
            f" · <b>{money(float(o['usd']))} $</b> · {st}")


async def show_orders(msg: Message, page=0, edit=True, notice=None):
    """Buyurtmalar tarixi (sahifalangan)."""
    lst = await db.orders(page, ORD_PER_PAGE)
    total = await db.order_count()
    pages = max(1, -(-total // ORD_PER_PAGE))
    body = "\n".join(order_line(o) for o in lst) or "Hozircha buyurtma yo'q."
    text = (notice_line(notice) + head(["Buyurtmalar"], f"📋 <b>BUYURTMALAR TARIXI</b>")
            + f"Jami: <b>{total} ta</b> · sahifa <b>{page + 1}/{pages}</b>\n\n"
            + body
            + "\n\nBuyurtma ustiga bosing — tafsilotlari va holati.")
    buttons = [[(f"#{o['id']} · {STATUS_NAME.get(o['status'], '-')}", f"adm:ord:{o['id']}")]
               for o in lst]
    nav = []
    if page > 0:
        nav.append(("⬅️ Orqaga", f"adm:ords:{page - 1}", "primary"))
    if (page + 1) * ORD_PER_PAGE < total:
        nav.append(("Oldinga ➡️", f"adm:ords:{page + 1}", "primary"))
    if nav:
        buttons.append(nav)
    buttons.append([("🔍 Qidiruv", "adm:find", "primary")])
    buttons.append([HOME])
    await screen(msg, text, rows(*buttons), edit=edit)


async def show_order_list(msg: Message, lst, title, edit=True, notice=None):
    """Qidiruv natijalari ro'yxati."""
    text = (notice_line(notice) + head(["Buyurtmalar"], title)
            + ("\n".join(order_line(o) for o in lst) or "Hech narsa topilmadi."))
    buttons = [[(f"#{o['id']} · {STATUS_NAME.get(o['status'], '-')}", f"adm:ord:{o['id']}")]
               for o in lst]
    buttons.append([("⬅️ Tarixga qaytish", "adm:ords:0"), HOME])
    await screen(msg, text, rows(*buttons), edit=edit)


async def show_order_detail(msg: Message, calc_id, edit=True, notice=None):
    """Bitta buyurtmaning to'liq kartasi (admin ko'rishi)."""
    o = await db.get_order(calc_id)
    if not o:
        return await msg.answer("❌ Buyurtma topilmadi.")
    lang = await db.get_lang(o["user_id"]) or "uz"
    tg = (f"@{o['username']}" if o["username"]
          else f'<a href="tg://user?id={o["user_id"]}">{html.escape(o["full_name"] or "profil")}</a>')
    status = o["status"]            # None — mijoz hali tasdiqlamagan hisob-kitob
    label = STATUS_NAME.get(status) or "Tasdiqlanmagan"
    text = (notice_line(notice) + user_card(o, lang)
            + f"\n{pe('💬')} <b>Telegram:</b> {tg}"
            + f"\n{pe('🌐')} <b>Mijoz tili:</b> {LANG_NAME[lang]}"
            + f"\n{pe('🛠')} <b>Holat: {label}</b>")
    if status:
        text += f"\n👤 <b>{html.escape(o['status_by'] or '-')}</b> · {o['status_str']}"
    if status in (None, "new"):
        markup = rows([("✅ Tasdiqlandi", f"aord:ok:{calc_id}", "success", "✅"),
                       ("❌ Bekor qilindi", f"aord:no:{calc_id}", "danger", "❌")],
                      [("⬅️ Tarixga qaytish", "adm:ords:0"), HOME])
    else:
        markup = rows([("⬅️ Tarixga qaytish", "adm:ords:0"), HOME])
    await screen(msg, text, markup, edit=edit)


@dp.callback_query(F.data == "adm:orders", is_admin)
async def adm_orders(cb: CallbackQuery):
    await cb.answer()
    await show_orders(cb.message, 0, edit=True)


@dp.callback_query(F.data.startswith("adm:ords:"), is_admin)
async def adm_orders_page(cb: CallbackQuery):
    await cb.answer()
    await show_orders(cb.message, int(cb.data[9:]), edit=True)


@dp.callback_query(F.data.startswith("adm:ord:"), is_admin)
async def adm_order_detail(cb: CallbackQuery):
    await cb.answer()
    await show_order_detail(cb.message, int(cb.data[8:]), edit=True)


@dp.callback_query(F.data == "adm:find", is_admin)
async def adm_find(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await ask(cb.message, state, AdminForm.find,
              head(["Buyurtmalar"], "🔍 <b>BUYURTMA QIDIRUV</b>")
              + "Buyurtma <b>ID</b>si, mijoz <b>ismi</b>, <b>telefoni</b> yoki "
              "<b>username</b>ini yozing:\n<i>Masalan: 12 yoki Aliyev yoki 99890</i>",
              "adm:orders")


@dp.message(AdminForm.find, is_admin, NOT_CMD)
async def adm_find_set(msg: Message, state: FSMContext):
    q = " ".join((msg.text or "").split())
    await clean_input(msg, state)
    if not q:
        return await msg.answer("❌ Qidiruv so'zini yozing.")
    results = await db.search_orders(q)
    await show_order_list(msg, results, f"🔍 <b>«{html.escape(q)}» BO'YICHA QIDIRUV</b>",
                            edit=False, notice=f"Topildi: <b>{len(results)} ta</b> (ko'pi 50 ta)")


@dp.callback_query(F.data.startswith("aord:"), is_admin)
async def admin_order_decision(cb: CallbackQuery):
    """Admin panelidan buyurtma holatini o'zgartirish."""
    _, action, calc_id = cb.data.split(":")
    calc_id = int(calc_id)
    status = "confirmed" if action == "ok" else "cancelled"
    who = cb.from_user.full_name + (f" (@{cb.from_user.username})" if cb.from_user.username else "")
    changed = await db.set_status(calc_id, status, who, order=(status == "confirmed"))
    o = await db.get_order(calc_id)
    if not o:
        return await cb.answer("Buyurtma topilmadi.", show_alert=True)
    lang = await db.get_lang(o["user_id"]) or "uz"
    if not changed:
        return await cb.answer(f"Bu buyurtma allaqachon: {STATUS_NAME.get(o['status'], '-')}",
                               show_alert=True)
    await cb.answer("✅ Tasdiqlandi" if status == "confirmed" else "❌ Bekor qilindi")
    await show_order_detail(cb.message, calc_id, edit=True,
                            notice=f"✅ Holat: <b>{STATUS_NAME[status]}</b> ({html.escape(who)})")
    try:
        await cb.bot.send_message(
            o["user_id"],
            t(lang, "notify_confirmed" if status == "confirmed" else "notify_cancelled", id=o["id"]))
    except Exception:
        logging.exception("Mijozga holatni yuborib bo'lmadi: %s", o["user_id"])


# --- Bloklangan mijozlar ---


async def show_blocked(msg: Message, edit=True, notice=None):
    users = await db.blocked_users()
    text = (notice_line(notice) + head(["Mijozlar"], f"🚫 <b>BLOKLANGAN MIJOZLAR</b>")
            + (f"Jami: <b>{len(users)} ta</b> — ularga xabar yetib bormagan.\n\n"
               if users else "Hech kim bloklanmagan.\n\n")
            + "\n".join(f"• {user_line(u)}" for u in users)
            + ("\n\nMijoz /start qilsa — blok o'zi ochiladi." if users else ""))
    buttons = [[(f"Blokdan olish — {u.id}", f"adm:unblock:{u.id}", "success")] for u in users]
    buttons.append([HOME])
    await screen(msg, text, rows(*buttons), edit=edit)


@dp.callback_query(F.data == "adm:blocked", is_admin)
async def adm_blocked(cb: CallbackQuery):
    await cb.answer()
    await show_blocked(cb.message, edit=True)


@dp.callback_query(F.data.startswith("adm:unblock:"), is_admin)
async def adm_unblock(cb: CallbackQuery):
    uid = int(cb.data.split(":")[2])
    await db.unblock_user(uid)
    await cb.answer("✅ Blok olishildi")
    await show_blocked(cb.message, edit=True,
                       notice="✅ Mijoz blokdan olindi — keyingi xabar yetib boradi.")


# ================= Guruhdagi buyurtma: admin qarori =================

STATUS = {  # holat: (emoji, sarlavha, hashtag)
    "new": ("🛒", "YANGI BUYURTMA", "#yangi_buyurtma"),
    "confirmed": ("✅", "TASDIQLANGAN BUYURTMA", "#tasdiqlangan"),
    "cancelled": ("❌", "BEKOR QILINGAN BUYURTMA", "#bekor_qilingan"),
}
LANG_NAME = {"uz": "O'zbekcha", "ru": "Ruscha"}


def handle_summary(o, lang):
    """Ruchka holati: faqat ruchkali fasadlar sanab o'tiladi (1-fasad: O'ng tomonda; ...)."""
    hs = [(i, f["handle"]) for i, f in enumerate(facades_of(o), 1) if f.get("handle")]
    if not hs:
        return t(lang, "handle_none")
    return "; ".join(f"{i} — {t(lang, f'handle_{h}')}" for i, h in hs)


def fit_summary(o):
    """Furnitura soni xulosi: hammasi bir xil bo'lsa — 'X dona/fasad',
    turli bo'lsa — har bir fasad alohida."""
    fs = [f.get("fit", 0) for f in facades_of(o)]
    if not fs:
        return "0 dona/fasad"
    if len(set(fs)) == 1:
        return f"{fs[0]} dona/fasad"
    return ", ".join(f"{i}-fasad {v} dona" for i, v in enumerate(fs, 1))


def order_body(o, lang="uz"):
    """Buyurtma tafsilotlari (o — db.get_order qatori). Mijozga uning tilida, guruhga o'zbekcha."""
    return t(lang, "order_body",
             name=html.escape(o["customer_name"] or "-"), phone=o["phone"] or "-",
             dims=dims_block(o, lang), count=len(facades_of(o)),
             glass=html.escape(pname(o["glass"], lang)), color=html.escape(pname(o["color"], lang)),
             fitting=html.escape(pname(o["fitting"], lang)), fit=fit_summary(o),
             handle=handle_summary(o, lang),
             delivery=t(lang, "delivery_yes" if o["delivery"] else "delivery_no"),
             usd=money(float(o["usd"])), sum=money(o["total_sum"]), rate=num(float(o["rate"])),
             with_dlv=t(lang, "with_delivery") if o["delivery"] else "")


def group_card(o, lang=None):
    icon, title, tag = STATUS[o["status"]]
    tg = (f"@{o['username']}" if o["username"]
          else f'<a href="tg://user?id={o["user_id"]}">{html.escape(o["full_name"] or "profil")}</a>')
    text = (f"{pe(icon)} <b>{title} #{o['id']}</b>\n{LINE}\n"
            f"{order_body(o)}\n{LINE}\n"
            f"{pe('💬')} <b>Telegram:</b> {tg}\n"
            + (f"🌐 <b>Mijoz tili:</b> {LANG_NAME[lang]}\n" if lang else "") +
            f"{pe('⏰')} <b>Vaqt:</b> {o['created_str']}")
    if o["status"] != "new":
        who = "Tasdiqladi" if o["status"] == "confirmed" else "Bekor qildi"
        text += f"\n{pe('👤')} <b>{who}:</b> {html.escape(o['status_by'])} · {o['status_str']}"
    return text + f"\n\n{tag} #buyurtma{o['id']}"


def group_buttons(o):
    if o["status"] != "new":
        return None
    return grid([("Tasdiqlandi", f"gord:ok:{o['id']}", "success", "✅"),
                 ("Bekor qilindi", f"gord:no:{o['id']}", "danger", "❌")], 2)


async def can_manage(bot: Bot, chat_id, user_id):
    if user_id in ADMIN_IDS:
        return True
    try:
        return (await bot.get_chat_member(chat_id, user_id)).status in ("administrator", "creator")
    except Exception:
        return False


@dp.callback_query(F.data.startswith("gord:"))
async def group_decision(cb: CallbackQuery):
    _, action, calc_id = cb.data.split(":")
    if not await can_manage(cb.bot, cb.message.chat.id, cb.from_user.id):
        return await cb.answer("Faqat adminlar tasdiqlay oladi.", show_alert=True)
    status = "confirmed" if action == "ok" else "cancelled"
    who = cb.from_user.full_name + (f" (@{cb.from_user.username})" if cb.from_user.username else "")
    changed = await db.set_status(int(calc_id), status, who)
    o = await db.get_order(int(calc_id))
    lang = await db.get_lang(o["user_id"]) or "uz"
    try:
        await cb.message.edit_text(group_card(o, lang), reply_markup=group_buttons(o))
    except TelegramBadRequest:
        pass
    if not changed:
        return await cb.answer(f"Bu buyurtma allaqachon: {STATUS_NAME.get(o['status'], '-')}", show_alert=True)
    await cb.answer("✅ Tasdiqlandi" if status == "confirmed" else "❌ Bekor qilindi")
    try:
        await cb.bot.send_message(o["user_id"], t(lang, "notify_confirmed" if status == "confirmed" else "notify_cancelled",
                                                  id=o["id"]))
    except Exception:
        logging.exception("Mijozga holatni yuborib bo'lmadi: %s", o["user_id"])


# ================= Til =================

LANG_KB = grid([("🇺🇿 O'zbekcha", "lang:uz", "primary"), ("🇷🇺 Русский", "lang:ru", "primary")], 2)


async def lang_of(user_id):
    return await db.get_lang(user_id) or "uz"


@dp.message(Command("lang"))
async def choose_lang(msg: Message, state: FSMContext):
    await db.upsert_user(msg.from_user)
    await state.clear()
    await msg.answer("🌐 <b>Tilni tanlang</b>\n🌐 <b>Выберите язык</b>", reply_markup=LANG_KB)


@dp.callback_query(F.data.in_({"lang:uz", "lang:ru"}))
async def set_lang(cb: CallbackQuery, state: FSMContext):
    lang = cb.data[5:]
    await db.upsert_user(cb.from_user)
    await db.set_lang(cb.from_user.id, lang)
    await cb.answer()
    await cb.message.edit_text(t(lang, "lang_set"))
    await begin(cb.message, state, lang)


# ================= KARUSEL =================

def carousel(kind, i, lang):
    """Bitta xabar: rasm, tagida nomi, ◀️ Tanlash ▶️. Tanlash callback'i 'glass:key' / 'color:key'."""
    lst = items(kind)
    i %= len(lst)
    p = lst[i]
    markup = grid([("◀️", f"car:{kind}:{i - 1}"), (t(lang, "b_choose"), f"{kind}:{p['key']}", "success", "✅"),
                   ("▶️", f"car:{kind}:{i + 1}")], 3)
    title = step(lang, 4 if kind == "glass" else 5) + t(lang, f"title_{kind}")
    caption = (f"{title}:\n\n<b>{html.escape(pname(p['key'], lang))}</b>  ·  {i + 1}/{len(lst)}\n\n"
               + t(lang, "carousel_hint"))
    return *photo_for(p), caption, markup


async def send_carousel(msg: Message, kind, lang):
    if not items(kind):
        return await msg.answer(t(lang, "no_variants"))
    photo, path, caption, markup = carousel(kind, 0, lang)
    remember(path, await msg.answer_photo(photo, caption=caption, reply_markup=markup))


@dp.callback_query(F.data.startswith("car:"))
async def carousel_nav(cb: CallbackQuery):
    _, kind, i = cb.data.split(":")
    if not items(kind):
        return await cb.answer()
    photo, path, caption, markup = carousel(kind, int(i), await lang_of(cb.from_user.id))
    try:
        remember(path, await cb.message.edit_media(InputMediaPhoto(media=photo, caption=caption), reply_markup=markup))
    except TelegramBadRequest:  # tez bosilganda "message is not modified"
        pass
    await cb.answer()


def visible(kind, key):
    p = db.products.get(key)
    return p if p and p["kind"] == kind and not p["hidden"] and not p["deleted"] else None


# ================= 1-2. Fasad soni va har bir fasad o'lchami =================
# Tartib: avval nechta fasad, keyin har bir fasaddi alohida so'raladi.
# Har bir fasadda AVVAL BO'YI, keyin ENI kiritiladi ("1800 900").

@dp.message(CommandStart())
async def start(msg: Message, state: FSMContext, user=None):
    user = user or msg.from_user
    await db.upsert_user(user)
    await state.clear()
    lang = await db.get_lang(user.id)
    if not lang:  # birinchi marta — avval til
        return await msg.answer("🌐 <b>Tilni tanlang</b>\n🌐 <b>Выберите язык</b>\n", reply_markup=LANG_KB)
    await begin(msg, state, lang)


async def begin(msg: Message, state: FSMContext, lang):
    await state.clear()
    await msg.answer(t(lang, "welcome") + step(lang, 1) + t(lang, "ask_count"), reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.count)


@dp.message(Form.count)
async def count(msg: Message, state: FSMContext):
    lang = await lang_of(msg.from_user.id)
    v = parse_int(msg.text, 1, P.MAX_FACADES)
    if not v:
        return await msg.answer(t(lang, "err_count"))
    await state.update_data(facades=[], n=v)
    await ask_dims(msg, state, lang)


async def ask_dims(msg: Message, state: FSMContext, lang):
    """Navbatdagi fasad BO'YINI so'raydi — chizma bilan (bo'yi o'qi yashil)."""
    d = await state.get_data()
    n = len(d["facades"]) + 1
    await send_diagram(msg, lang, n=n, n_all=d["n"], ask="h",
                       caption=step(lang, 2) + t(lang, "ask_facade_dims", n=n, i=n, n_all=d["n"]))
    await state.set_state(Form.dims)


async def ask_width(msg: Message, state: FSMContext, lang, height):
    """Bo'yi kiritilgach ENINI so'raydi — chizma endi bo'yini yashil ko'rsatadi."""
    d = await state.get_data()
    n = len(d["facades"]) + 1
    await send_diagram(msg, lang, n=n, n_all=d["n"], height=height, ask="w",
                       caption=step(lang, 2) + t(lang, "ask_width", n=n, i=n, n_all=d["n"], h=height))
    await state.set_state(Form.width)


def parse_dims(text, hi=P.MAX_MM):
    """"1800 900" -> (bo'yi 1800, eni 900) yoki None. Avval bo'yi, keyin eni.
    Ikkalasi bir xabarda yuborilsa ham ishlaydi (eski qulaylik saqlanadi)."""
    parts = (text or "").replace(",", " ").replace("x", " ").replace("×", " ").split()
    vals = [parse_int(p, 1, hi) for p in parts]
    return tuple(vals) if len(vals) == 2 and all(vals) else None


@dp.message(Form.dims)
async def dims(msg: Message, state: FSMContext):
    lang = await lang_of(msg.from_user.id)
    both = parse_dims(msg.text)
    if both:                       # mijoz "1800 900" deb ikkisini birdan yozsa
        return await save_facade(msg, state, lang, both[0], both[1])
    height = parse_int(msg.text, 1, P.MAX_MM)
    if not height:
        return await msg.answer(t(lang, "err_facade_dims"))
    await state.update_data(h=height)
    await ask_width(msg, state, lang, height)


@dp.message(Form.width)
async def width(msg: Message, state: FSMContext):
    lang = await lang_of(msg.from_user.id)
    w = parse_int(msg.text, 1, P.MAX_MM)
    if not w:
        return await msg.answer(t(lang, "err_width"))
    await save_facade(msg, state, lang, (await state.get_data())["h"], w)


async def save_facade(msg: Message, state: FSMContext, lang, height, width):
    """Fasadni saqlaydi va kiritilgan o'lchamni chizma bilan ko'rsatadi."""
    d = await state.get_data()
    facades = d["facades"] + [{"w": width, "h": height, "handle": None, "fit": None}]
    await state.update_data(facades=facades, h=None)
    # chizma: ikkala o'q ham yashil — mijoz kiritganini ko'radi
    await send_diagram(msg, lang, n=len(facades), n_all=d["n"], height=height, width=width,
                       caption=t(lang, "facade_saved", n=len(facades), h=height, w=width))
    if len(facades) < d["n"]:
        return await ask_dims(msg, state, lang)
    await msg.answer(t(lang, "all_dims_done", n=len(facades)))
    await ask_handle(msg, state, lang)


async def ask_handle(msg: Message, state: FSMContext, lang):
    """3-qadam: ruchkali yoki ruchkasiz."""
    await msg.answer(step(lang, 3) + t(lang, "ask_handle"),
                     reply_markup=grid([(t(lang, "b_handle_yes"), "handle:yes", "primary"),
                                        (t(lang, "b_handle_no"), "handle:no", "primary")], 2))
    await state.set_state(Form.handle)


# ================= 4-5. Oyna va rang =================

@dp.callback_query(Form.glass, F.data.startswith("glass:"))
async def glass(cb: CallbackQuery, state: FSMContext):
    lang = await lang_of(cb.from_user.id)
    p = visible("glass", cb.data.split(":")[1])
    if not p:
        return await cb.answer(t(lang, "a_not_available"), show_alert=True)
    await state.update_data(glass=p["key"])
    await cb.answer()
    await cb.message.edit_caption(caption=t(lang, "chosen_glass", name=html.escape(pname(p["key"], lang))), reply_markup=None)
    await send_carousel(cb.message, "color", lang)
    await state.set_state(Form.color)


@dp.callback_query(Form.color, F.data.startswith("color:"))
async def color(cb: CallbackQuery, state: FSMContext):
    lang = await lang_of(cb.from_user.id)
    p = visible("color", cb.data.split(":")[1])
    if not p:
        return await cb.answer(t(lang, "a_not_available"), show_alert=True)
    await state.update_data(color=p["key"])
    await cb.answer()
    await cb.message.edit_caption(caption=t(lang, "chosen_color", name=html.escape(pname(p["key"], lang))), reply_markup=None)
    await cb.message.answer(step(lang, 6) + t(lang, "ask_fitting"),
                            reply_markup=grid([(pname(f["key"], lang), f"fit:{f['key']}", "primary")
                                               for f in items("fitting")], 2))
    await state.set_state(Form.fitting)


# ================= 6. Furnitura turi =================

@dp.callback_query(Form.fitting, F.data.startswith("fit:"))
async def fitting(cb: CallbackQuery, state: FSMContext):
    lang = await lang_of(cb.from_user.id)
    p = visible("fitting", cb.data.split(":")[1])
    if not p:
        return await cb.answer(t(lang, "a_not_available"), show_alert=True)
    await state.update_data(fitting=p["key"])
    await cb.answer()
    await cb.message.edit_text(t(lang, "chosen_fitting", name=html.escape(pname(p["key"], lang))))
    await show_fit_list(cb.message, state, lang, edit=False)


# ================= 7. Furnitura soni (har bir fasad alohida) =================
# Ruchka tanlash oqimiga o'xshash: fasadlar ro'yxati -> son kiritish -> Tasdiqlash.

def fit_btn(lang, i, f, prefix="ff"):
    """Furnitura ro'yxatidagi bitta fasad tugmasi: soni kiritilganmi ko'rinadi."""
    label = (t(lang, "b_fit_marked", n=i, h=f["h"], w=f["w"], v=f["fit"])
             if f.get("fit") is not None else t(lang, "b_fit", n=i, h=f["h"], w=f["w"]))
    return (label, f"{prefix}:{i}", "success" if f.get("fit") is not None else None)


async def show_fit_list(msg: Message, state: FSMContext, lang, edit=True, notice=None):
    """Har bir fasadga furnitura soni kiritiladi. Hammasi kiritilgach 'Tayyor' tugmasi chiqadi."""
    d = await state.get_data()
    facades = d["facades"]
    done = sum(1 for f in facades if f.get("fit") is not None)
    all_done = done == len(facades)
    rows_ = [[fit_btn(lang, i, f)] for i, f in enumerate(facades, 1)]
    if all_done:
        rows_.append([(t(lang, "b_fits_done"), "fdone", "success", "✅")])
    else:
        rows_.append([(t(lang, "fits_progress", done=done, n=len(facades)), "fnone")])
    text = (notice_line(notice) + step(lang, 7) + t(lang, "ask_fit_list",
                                                      n=len(facades),
                                                      fitting=pname(d["fitting"], lang))
            + "\n\n" + (t(lang, "a_all_fits_done") if all_done else ""))
    await screen(msg, text, rows(*rows_), edit=edit)
    await state.set_state(Form.fit_list)


@dp.callback_query(F.data == "fnone")
async def fit_none_btn(cb: CallbackQuery):
    await cb.answer()  # faqat ko'rsatma tugmasi — hech narsa qilmaydi


@dp.callback_query(F.data.startswith("ff:"), Form.fit_list)
async def fit_pick(cb: CallbackQuery, state: FSMContext):
    """Tanlangan fasad uchun furnitura sonini so'raydi."""
    lang = await lang_of(cb.from_user.id)
    i = int(cb.data.split(":")[1])
    d = await state.get_data()
    if not 1 <= i <= len(d["facades"]):
        return await cb.answer()
    f = d["facades"][i - 1]
    await state.update_data(ff=i)
    await cb.answer()
    cur = f"\n<i>Hozirgi: {f['fit']} dona</i>" if f.get("fit") is not None else ""
    m = await screen(cb.message, step(lang, 7) + t(lang, "ask_fit", n=i, h=f["h"], w=f["w"], cur=cur),
                 grid([(t(lang, "b_facade_list"), "flist")], 1), edit=True)
    await state.update_data(fit_prompt_id=m.message_id)
    await state.set_state(Form.fit)


@dp.callback_query(F.data == "flist", Form.fit_list)
async def fit_back(cb: CallbackQuery, state: FSMContext):
    lang = await lang_of(cb.from_user.id)
    await cb.answer()
    await show_fit_list(cb.message, state, lang, edit=True)


@dp.callback_query(F.data == "flist", Form.fit)
async def fit_back_from_entry(cb: CallbackQuery, state: FSMContext):
    lang = await lang_of(cb.from_user.id)
    await cb.answer()
    await show_fit_list(cb.message, state, lang, edit=True)


@dp.message(Form.fit)
async def fit_set(msg: Message, state: FSMContext):
    lang = await lang_of(msg.from_user.id)
    v = parse_int(msg.text, 0, 20)
    if v is None:
        return await msg.answer(t(lang, "err_fit_count"))
    d = await state.get_data()
    i = d["ff"]
    facades = [{**f} for f in d["facades"]]
    facades[i - 1]["fit"] = v
    await state.update_data(facades=facades, ff=None)
    # so'rov xabarini o'chiramiz (chat tozaligi uchun)
    try:
        await msg.bot.delete_message(msg.chat.id, d.get("fit_prompt_id"))
    except Exception:
        pass
    await show_fit_list(msg, state, lang, edit=False,
                        notice=t(lang, "fit_saved", n=i, v=v))


@dp.callback_query(F.data == "fdone", Form.fit_list)
async def fit_done(cb: CallbackQuery, state: FSMContext):
    """Barcha fasadlar kiritilgan — yetkazib berishga o'tamiz."""
    lang = await lang_of(cb.from_user.id)
    d = await state.get_data()
    left = [i for i, f in enumerate(d["facades"], 1) if f.get("fit") is None]
    if left:
        return await cb.answer(t(lang, "err_fits_left",
                                 left=", ".join(f"{i}-fasad" for i in left)), show_alert=True)
    await cb.answer(t(lang, "a_all_fits_done"))
    await ask_delivery(cb.message, state, lang)


# ================= 3. Ruchka (o'lchamlardan keyin) =================

async def ask_delivery(msg: Message, state: FSMContext, lang):
    await msg.answer(step(lang, 8) + t(lang, "ask_delivery"),
                     reply_markup=grid([(t(lang, "b_delivery_yes", sum=money(round(db.settings["delivery"]))),
                                         "dlv:yes", "primary", "🚚"),
                                        (t(lang, "b_delivery_no"), "dlv:no", "primary", "🏠")]))
    await state.set_state(Form.delivery)


async def go_glass(msg: Message, state: FSMContext, lang):
    """Ruchka belgilanib bo'lingach — oyna turiga o'tamiz (4-qadam)."""
    await send_carousel(msg, "glass", lang)
    await state.set_state(Form.glass)


@dp.callback_query(Form.handle, F.data.startswith("handle:"))
async def handle(cb: CallbackQuery, state: FSMContext):
    lang = await lang_of(cb.from_user.id)
    await cb.answer()
    if cb.data == "handle:yes":
        await show_handle_list(cb.message, state, lang, edit=True)
    else:
        d = await state.get_data()
        facades = [{**f, "handle": None} for f in d["facades"]]
        await state.update_data(facades=facades)
        await cb.message.edit_text(t(lang, "chosen_handle", v=t(lang, "handle_none")))
        await go_glass(cb.message, state, lang)


def facade_btn(lang, i, f, prefix="hf"):
    """Ruchka ro'yxatidagi bitta fasad tugmasi: belgilanganmi yo'qmi ko'rinadi."""
    label = (t(lang, "b_facade_marked", n=i, h=f["h"], w=f["w"], v=t(lang, f"handle_{f['handle']}"))
             if f["handle"] else t(lang, "b_facade", n=i, h=f["h"], w=f["w"]))
    return (label, f"{prefix}:{i}", "success" if f["handle"] else None)


async def show_handle_list(msg: Message, state: FSMContext, lang, edit=True, notice=None):
    """Ruchkali fasadlar ro'yxati. Hammasi belgilangach 'Tayyor' tugmasi chiqadi."""
    d = await state.get_data()
    facades = d["facades"]
    done = sum(1 for f in facades if f["handle"])
    all_done = done == len(facades)
    rows_ = [[facade_btn(lang, i, f)] for i, f in enumerate(facades, 1)]
    if all_done:
        rows_.append([(t(lang, "b_handles_done"), "hdone", "success", "✅")])
    else:
        rows_.append([(t(lang, "handles_progress", done=done, n=len(facades)), "hnone")])
    text = (notice_line(notice) + step(lang, 3) + t(lang, "ask_handle_list", n=len(facades))
            + "\n\n" + (t(lang, "a_all_handles_done") if all_done else ""))
    await screen(msg, text, rows(*rows_), edit=edit)
    await state.set_state(Form.side)


@dp.callback_query(F.data == "hnone")
async def handle_none_btn(cb: CallbackQuery):
    await cb.answer()  # faqat ko'rsatma tugmasi — hech narsa qilmaydi


@dp.callback_query(F.data.startswith("hf:"), Form.side)
async def handle_pick(cb: CallbackQuery, state: FSMContext):
    """Tanlangan fasad uchun ruchka tomonini so'raydi (Chap / O'ng)."""
    lang = await lang_of(cb.from_user.id)
    i = int(cb.data.split(":")[1])
    d = await state.get_data()
    if not 1 <= i <= len(d["facades"]):
        return await cb.answer()
    f = d["facades"][i - 1]
    await state.update_data(hf=i)
    await cb.answer()
    await screen(cb.message, step(lang, 3) + t(lang, "ask_side", n=i, h=f["h"], w=f["w"]),
                 grid([(t(lang, "b_left"), f"side:{i}:chap", "primary"),
                       (t(lang, "b_right"), f"side:{i}:ong", "primary"),
                       (t(lang, "b_facade_list"), "hlist")], 1), edit=True)


@dp.callback_query(F.data == "hlist", Form.side)
async def handle_back(cb: CallbackQuery, state: FSMContext):
    lang = await lang_of(cb.from_user.id)
    await cb.answer()
    await show_handle_list(cb.message, state, lang, edit=True)


@dp.callback_query(F.data.startswith("side:"), Form.side)
async def side(cb: CallbackQuery, state: FSMContext):
    lang = await lang_of(cb.from_user.id)
    _, i, s = cb.data.split(":")
    d = await state.get_data()
    i = int(i)
    if not 1 <= i <= len(d["facades"]):
        return await cb.answer()
    facades = [{**f} for f in d["facades"]]
    facades[i - 1]["handle"] = s
    await state.update_data(facades=facades, hf=None)
    await cb.answer()
    f = facades[i - 1]
    await show_handle_list(cb.message, state, lang, edit=True,
                           notice=t(lang, "chosen_handle", v=t(lang, f"handle_{s}"))
                           + f"  ·  {t(lang, 'facade_saved', n=i, h=f['h'], w=f['w'])}")


@dp.callback_query(F.data == "hdone", Form.side)
async def handle_done(cb: CallbackQuery, state: FSMContext):
    """Barcha fasadlar belgilangan — oyna turiga o'tamiz (4-qadam)."""
    lang = await lang_of(cb.from_user.id)
    d = await state.get_data()
    left = [i for i, f in enumerate(d["facades"], 1) if not f["handle"]]
    if left:
        return await cb.answer(t(lang, "err_handles_left",
                                 left=", ".join(f"{i}-fasad" for i in left)), show_alert=True)
    await cb.answer(t(lang, "a_all_handles_done"))
    await go_glass(cb.message, state, lang)


# ================= 8. Yetkazish -> hisob, ism, telefon =================

def phone_kb(lang):
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t(lang, "b_send_phone"), request_contact=True,
                                                         style="success", icon_custom_emoji_id=EMOJI.get("📱"))]],
                               resize_keyboard=True, one_time_keyboard=True)


@dp.callback_query(Form.delivery, F.data.in_({"dlv:yes", "dlv:no"}))
async def delivery(cb: CallbackQuery, state: FSMContext):
    lang = await lang_of(cb.from_user.id)
    await cb.answer()
    dlv = cb.data == "dlv:yes"
    await cb.message.edit_text(t(lang, "chosen_delivery", v=t(lang, "delivery_yes" if dlv else "delivery_no")))

    d = await state.get_data()
    rate = await asyncio.to_thread(get_rate)
    s = db.settings
    # mahsulot hisob o'rtasida o'chirilgan bo'lsa ham oxirgi ma'lum narx bilan hisoblanadi
    glass_price = db.products[d["glass"]]["price"] or 0
    fitting_price = db.products[d["fitting"]]["price"] or 0
    # har bir fasad o'lchami, ruchkasi va furnitura soni alohida
    usd = P.calc_total(s, [(f["w"], f["h"], f["handle"], f.get("fit") or 0)
                           for f in d["facades"]], glass_price, fitting_price)
    total_sum = P.calc_sum(s, usd, rate, dlv)
    d.update(delivery=dlv)
    await db.upsert_user(cb.from_user)
    d["calc_id"] = await db.add_calc(cb.from_user.id, d, usd, rate, total_sum)
    await state.set_data(d)

    saved = await db.get_user_contact(cb.from_user.id)
    if not saved:
        return await ask_name(cb.message, state, lang)
    await cb.message.answer(step(lang, 10) + t(lang, "saved_contact", name=html.escape(saved[0]), phone=saved[1]),
                            reply_markup=grid([(t(lang, "b_confirm"), "contact:ok", "success", "✅"),
                                               (t(lang, "b_edit"), "contact:edit", "primary", "✏")], 2))
    await state.set_state(Form.contact)


async def ask_name(msg: Message, state: FSMContext, lang):
    await msg.answer(step(lang, 10) + t(lang, "ask_name"))
    await state.set_state(Form.name)


@dp.callback_query(Form.contact, F.data.in_({"contact:ok", "contact:edit"}))
async def contact_choice(cb: CallbackQuery, state: FSMContext):
    lang = await lang_of(cb.from_user.id)
    await cb.answer()
    saved = await db.get_user_contact(cb.from_user.id)
    if cb.data == "contact:edit" or not saved:
        await cb.message.edit_text(t(lang, "contact_edit"))
        return await ask_name(cb.message, state, lang)
    await cb.message.edit_text(f"{pe('✅')} {html.escape(saved[0])} · {saved[1]}")
    await show_order(cb.message, state, lang, *saved)


@dp.message(Form.name)
async def name(msg: Message, state: FSMContext):
    lang = await lang_of(msg.from_user.id)
    text = " ".join((msg.text or "").split())
    if not 2 <= len(text) <= 100 or any(c.isdigit() for c in text):
        return await msg.answer(t(lang, "err_name"))
    await state.update_data(customer_name=text)
    await msg.answer(t(lang, "ask_phone"), reply_markup=phone_kb(lang))
    await state.set_state(Form.phone)


def user_card(o, lang):
    return f"{t(lang, 'order_title', id=o['id'])}\n{LINE}\n{order_body(o, lang)}\n{LINE}\n"


@dp.message(Form.phone)
async def phone(msg: Message, state: FSMContext):
    lang = await lang_of(msg.from_user.id)
    raw = msg.contact.phone_number if msg.contact else re.sub(r"[\s\-()]", "", msg.text or "")
    if not re.fullmatch(r"\+?\d{9,15}", raw):
        return await msg.answer(t(lang, "err_phone"), reply_markup=phone_kb(lang))
    digits = raw.lstrip("+")
    number = "+" + ("998" + digits if len(digits) == 9 else digits)  # 901234567 -> +998901234567
    name = (await state.get_data())["customer_name"]
    await db.save_user_contact(msg.from_user.id, name, number)  # keyingi buyurtmada qayta so'ralmaydi
    await msg.answer(t(lang, "phone_ok"), reply_markup=ReplyKeyboardRemove())
    await show_order(msg, state, lang, name, number)


async def show_order(msg: Message, state: FSMContext, lang, name, number):
    """Kontaktni hisobga yozib, mijozga tasdiqlash kartasini ko'rsatadi."""
    calc_id = (await state.get_data())["calc_id"]
    await db.set_contact(calc_id, name, number)
    await state.set_state(None)
    o = await db.get_order(calc_id)
    await msg.answer(user_card(o, lang) + t(lang, "confirm_prompt"),
                     reply_markup=grid([(t(lang, "b_confirm"), f"ord:ok:{o['id']}", "success", "✅"),
                                        (t(lang, "b_cancel"), f"ord:no:{o['id']}", "danger", "❌")], 2))


# ================= 10. Mijoz tasdig'i =================

def after_order_kb(lang):
    return grid([(t(lang, "b_comment"), "comment", "primary", "✍"),
                 (t(lang, "b_new"), "restart", None, "🔄"),
                 (t(lang, "b_contact"), PROFILE_LINK, None, "💬")])


@dp.callback_query(F.data.startswith("ord:"))
async def order_decision(cb: CallbackQuery):
    _, action, calc_id = cb.data.split(":")
    o = await db.get_order(int(calc_id))
    if not o or o["user_id"] != cb.from_user.id:
        return await cb.answer()
    lang = await lang_of(cb.from_user.id)
    if action == "no":
        await cb.answer(t(lang, "a_cancelled"))
        if o["ordered_at"] is None:  # yuborilganini qaytarib bo'lmaydi
            await cb.message.edit_text(user_card(o, lang) + t(lang, "order_cancelled"),
                                       reply_markup=grid([(t(lang, "b_restart"), "restart", "primary", "🔄")]))
        return
    if not await db.submit_order(o["id"]):
        return await cb.answer(t(lang, "a_already_sent"), show_alert=True)
    await cb.answer(t(lang, "a_sent"))
    o = await db.get_order(o["id"])
    await cb.message.edit_text(user_card(o, lang) + t(lang, "order_sent", phone=o["phone"]),
                               reply_markup=after_order_kb(lang))
    await notify(cb.bot, group_card(o, lang), group_buttons(o))


@dp.callback_query(F.data == "restart")
async def restart(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await start(cb.message, state, user=cb.from_user)


# ================= Izoh =================

@dp.callback_query(F.data == "comment")
async def ask_comment(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await cb.message.answer(t(await lang_of(cb.from_user.id), "ask_comment"))
    await state.set_state(Form.comment)


@dp.message(Form.comment, F.text)
async def comment(msg: Message, state: FSMContext):
    lang = await lang_of(msg.from_user.id)
    await db.upsert_user(msg.from_user)
    await db.add_comment(msg.from_user.id, msg.text)
    await state.set_state(None)
    await msg.answer(t(lang, "comment_thanks"), reply_markup=grid([(t(lang, "b_contact"), PROFILE_LINK, None, "💬")]))
    await notify(msg.bot, f"{pe('💬')} <b>MIJOZ IZOHI</b>\n{LINE}\n{user_line(msg.from_user)}\n"
                          f"🌐 Mijoz tili: {LANG_NAME[lang]}\n\n"
                          f"<blockquote>{html.escape(msg.text)}</blockquote>\n\n#izoh")


@dp.message(F.chat.type == "private")
async def fallback(msg: Message):
    await msg.answer(t(await lang_of(msg.from_user.id), "fallback"))


@dp.callback_query()
async def stale_button(cb: CallbackQuery):
    await cb.answer(t(await lang_of(cb.from_user.id), "a_stale"), show_alert=True)


async def main():
    if not BOT_TOKEN or not DATABASE_URL:
        raise SystemExit("BOT_TOKEN va DATABASE_URL muhit o'zgaruvchilarini o'rnating")
    await db.init(DATABASE_URL)
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML", link_preview_is_disabled=True))
    for lang, code in (("uz", None), ("ru", "ru")):  # menyu buyruqlari Telegram tiliga qarab
        await bot.set_my_commands([BotCommand(command="start", description=t(lang, "b_menu_start")),
                                   BotCommand(command="lang", description=t(lang, "b_menu_lang"))],
                                  language_code=code)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main())
