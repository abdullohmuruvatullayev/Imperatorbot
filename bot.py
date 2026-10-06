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
import prices as P

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
    width = State()
    height = State()
    count = State()
    glass = State()
    color = State()
    fitting = State()
    fitting_count = State()
    handle = State()
    side = State()
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


STEPS = 10  # eni, balandlik, soni, oyna, rang, furnitura, furnitura soni, ruchka, yetkazish, kontakt


def step(n):
    return f"<i>Qadam {n}/{STEPS}</i>\n"


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


def pname(key):
    """Mahsulot nomi; o'chirilgan bo'lsa ham eski buyurtmalarda chiqadi."""
    return db.products.get(key, {}).get("name", key)


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
    new_price = State()
    setting = State()    # umumiy narx
    broadcast = State()


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
            f"<b>Hisobot</b> — statistika va Excel fayl\n"
            f"<b>Xabar</b> — barcha mijozlarga e'lon\n\n"
            f"Bo'limni tanlang {pe('👇')}")
    markup = rows([(f"🪟 Oyna turlari · {n['glass']} ta", "adm:k:glass", "primary")],
                  [(f"🎨 Profil ranglari · {n['color']} ta", "adm:k:color", "primary")],
                  [(f"🔩 Furnitura · {n['fitting']} ta", "adm:k:fitting", "primary")],
                  [("⚙️ Umumiy narxlar", "adm:set", "primary")],
                  [("📊 Statistika", "adm:stat"), ("📥 Excel hisobot", "adm:export")],
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


@dp.callback_query(F.data == "adm:stat", is_admin)
async def adm_stat(cb: CallbackQuery):
    s = await db.stats()
    await cb.answer()
    await screen(cb.message,
                 head(["Statistika"], f"{pe('📊')} <b>STATISTIKA</b>") +
                 f"📅 <b>BUGUN</b>\n"
                 f"• Yangi mijozlar: <b>{s['new_today']} ta</b>\n"
                 f"• Narx hisoblandi: <b>{s['calc_today']} marta</b>\n"
                 f"• Buyurtma berildi: <b>{s['ord_today']} ta</b>\n\n"
                 f"🗓 <b>OXIRGI 7 KUN</b>\n"
                 f"• Yangi mijozlar: <b>{s['new_week']} ta</b>\n"
                 f"• Narx hisoblandi: <b>{s['calc_week']} marta</b>\n"
                 f"• Buyurtma berildi: <b>{s['ord_week']} ta</b>\n\n"
                 f"{pe('📈')} <b>BOT ISHGA TUSHGANDAN BERI</b>\n"
                 f"• Jami mijozlar: <b>{s['users']} ta</b>\n"
                 f"• Narx hisoblandi: <b>{s['calc_all']} marta</b>\n"
                 f"• Buyurtma berildi: <b>{s['ord_all']} ta</b>\n\n"
                 f"{pe('🛒')} <b>BUYURTMALAR HOLATI</b>\n"
                 f"{pe('⏳')} Javob kutmoqda: <b>{s['st_new']} ta</b>\n"
                 f"{pe('✅')} Tasdiqlangan: <b>{s['st_confirmed']} ta</b>\n"
                 f"{pe('❌')} Bekor qilingan: <b>{s['st_cancelled']} ta</b>\n\n"
                 f"{pe('💰')} <b>Tasdiqlangan buyurtmalar summasi: {money(float(s['confirmed_usd']))} $</b>",
                 rows([("🔄 Yangilash", "adm:stat", "primary")], [HOME]))


@dp.callback_query(F.data == "adm:export", is_admin)
async def adm_export(cb: CallbackQuery):
    await cb.answer("Tayyorlanmoqda...")
    rows_ = await db.export_rows()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["ID", "Sana", "User ID", "Username", "Telegram ismi", "Buyurtmachi", "Telefon", "Eni mm",
                "Balandligi mm", "Soni", "Oyna", "Rang", "Furnitura", "Furnitura/fasad", "Ruchka", "Yetkazish",
                "USD", "Kurs", "So'm", "Buyurtma vaqti", "Holat", "Kim o'zgartirdi"])
    for r in rows_:
        w.writerow([r["id"], r["created_at"], r["user_id"], r["username"] or "", r["full_name"] or "",
                    r["customer_name"] or "", r["phone"] or "", r["width"], r["height"], r["count"],
                    pname(r["glass"]), pname(r["color"]), pname(r["fitting"]), r["fitting_count"],
                    r["handle"] or "yo'q", "ha" if r["delivery"] else "yo'q", r["usd"], r["rate"], r["total_sum"],
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
    lines = []
    if k["unit"]:
        lines.append(f"💵 Narxi: <b>{price_str(p)}</b>")
    if k["image"]:
        lines.append(f"🖼 Rasmi: <b>{image_status(p)}</b>")
    lines.append("🙈 Holati: <b>yashirin</b> — mijozlar ko'rmaydi" if p["hidden"]
                 else "👁 Holati: <b>mijozlarga ko'rinadi</b>")
    text = (notice_line(notice) + head([k["title"], p["name"]], f"{k['icon']} <b>{html.escape(p['name'])}</b>")
            + "\n".join(lines) + f"\n\nNimani o'zgartiramiz? {pe('👇')}")
    markup = rows([("✏️ Nomini o'zgartirish", f"adm:e:name:{key}", "primary")],
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
    if not p or field not in ("name", "price"):
        return await cb.answer()
    await cb.answer()
    k = KINDS[p["kind"]]
    if field == "name":
        body = f"✏️ <b>Yangi nomni yozing</b>\nHozirgi: <b>{html.escape(p['name'])}</b>"
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
    if d["field"] == "name":
        value = valid_name(msg.text)
        if value is None:
            return await msg.answer("❌ Nom 1 dan 40 belgigacha bo'lsin.")
        notice = f"✅ <b>Saqlandi:</b> nomi «{html.escape(p['name'])}» → «{html.escape(value)}»"
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
    steps = "nomi → " + ("narxi → " if k["unit"] else "") + ("rasmi" if k["image"] else "tayyor")
    await ask(cb.message, state, AdminForm.new_name, head([k["title"], "Yangi"], f"➕ <b>YANGI {k['one'].upper()}</b>")
              + f"<i>Qadamlar: {steps}</i>\n\n✏️ <b>Nomini yozing:</b>", f"adm:k:{kind}", kind=kind)


@dp.message(AdminForm.new_name, is_admin, NOT_CMD)
async def adm_new_name(msg: Message, state: FSMContext):
    name = valid_name(msg.text)
    if not name:
        return await msg.answer("❌ Nom 1 dan 40 belgigacha bo'lsin.")
    kind = (await state.get_data())["kind"]
    k = KINDS[kind]
    if k["unit"]:
        await clean_input(msg, state)
        return await ask(msg, state, AdminForm.new_price, head([k["title"], "Yangi"], f"➕ <b>{html.escape(name)}</b>")
                         + f"💵 <b>Narxini yozing</b> ({k['unit']})\n<i>Masalan: 22 yoki 5.5</i>",
                         f"adm:k:{kind}", edit=False, kind=kind, name=name)
    await finish_new(msg, state, kind, name, None)


@dp.message(AdminForm.new_price, is_admin, NOT_CMD)
async def adm_new_price(msg: Message, state: FSMContext):
    price = parse_price(msg.text)
    if price is None:
        return await msg.answer("❌ Faqat son yozing. Masalan: 22 yoki 5.5")
    d = await state.get_data()
    await finish_new(msg, state, d["kind"], d["name"], price)


async def finish_new(msg: Message, state: FSMContext, kind, name, price):
    key = await db.add_product(kind, name, price)
    await clean_input(msg, state)
    if KINDS[kind]["image"]:
        return await ask_photo(msg, state, key, edit=False, new=True)
    await show_product(msg, key, edit=False, notice="✅ <b>Yangi mahsulot qo'shildi.</b>")


# --- Umumiy narxlar ---

def setting_str(key):
    _, unit, _ = P.SETTINGS[key]
    return f"{num(db.settings[key])} {unit}"


async def show_settings(msg: Message, edit=True, notice=None):
    text = (notice_line(notice) + head(["Umumiy narxlar"], f"{pe('⚙')} <b>UMUMIY NARXLAR</b>")
            + "Bu narxlar har bir hisob-kitobda ishlatiladi.\n\n"
            f"✏️ O'zgartirish uchun <b>kerakli narx ustiga</b> bosing {pe('👇')}")
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
    await ask(cb.message, state, AdminForm.setting, head(["Umumiy narxlar", name], f"⚙️ <b>{name}</b>")
              + f"💵 <b>Yangi qiymatni yozing</b> ({unit})\nHozirgi: <b>{setting_str(key)}</b>", "adm:set", key=key)


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


# ================= Guruhdagi buyurtma: admin qarori =================

STATUS = {  # holat: (emoji, sarlavha, hashtag)
    "new": ("🛒", "YANGI BUYURTMA", "#yangi_buyurtma"),
    "confirmed": ("✅", "TASDIQLANGAN BUYURTMA", "#tasdiqlangan"),
    "cancelled": ("❌", "BEKOR QILINGAN BUYURTMA", "#bekor_qilingan"),
}


def order_body(o):
    """Buyurtma tafsilotlari (o — db.get_order qatori). Mijozga ham, guruhga ham bir xil."""
    handle = {"chap": "Chap tomonda", "ong": "O'ng tomonda"}.get(o["handle"], "Ruchkasiz")
    delivery = "Shahar bo'ylab yetkazib berish" if o["delivery"] else "O'zi olib ketadi"
    return (
        f"{pe('👤')} <b>Mijoz:</b> {html.escape(o['customer_name'] or '-')}\n"
        f"{pe('📞')} <b>Telefon:</b> {o['phone'] or '-'}\n\n"
        f"<blockquote>"
        f"📐 <b>O'lcham:</b> {o['width']} × {o['height']} mm\n"
        f"🔢 <b>Soni:</b> {o['count']} dona\n"
        f"🪟 <b>Oyna:</b> {html.escape(pname(o['glass']))}\n"
        f"{pe('🎨')} <b>Profil rangi:</b> {html.escape(pname(o['color']))}\n"
        f"🔩 <b>Furnitura:</b> {html.escape(pname(o['fitting']))} — {o['fitting_count']} dona/fasad\n"
        f"{pe('✋')} <b>Ruchka:</b> {handle}\n"
        f"🚚 <b>Yetkazish:</b> {delivery}"
        f"</blockquote>\n\n"
        f"{pe('💰')} <b>JAMI: {money(float(o['usd']))} USD</b>\n"
        f"{pe('💸')} <b>So'mda: {money(o['total_sum'])} so'm</b>"
        + (" <i>(yetkazish bilan)</i>" if o["delivery"] else "") + "\n"
        f"{pe('📈')} Dollar kursi: 1 USD = {num(float(o['rate']))} so'm"
    )


def group_card(o):
    icon, title, tag = STATUS[o["status"]]
    tg = (f"@{o['username']}" if o["username"]
          else f'<a href="tg://user?id={o["user_id"]}">{html.escape(o["full_name"] or "profil")}</a>')
    text = (f"{pe(icon)} <b>{title} #{o['id']}</b>\n{LINE}\n"
            f"{order_body(o)}\n{LINE}\n"
            f"{pe('💬')} <b>Telegram:</b> {tg}\n"
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
    try:
        await cb.message.edit_text(group_card(o), reply_markup=group_buttons(o))
    except TelegramBadRequest:
        pass
    if not changed:
        return await cb.answer(f"Bu buyurtma allaqachon: {STATUS_NAME.get(o['status'], '-')}", show_alert=True)
    await cb.answer("✅ Tasdiqlandi" if status == "confirmed" else "❌ Bekor qilindi")
    text = (f"{pe('🎉')} <b>Buyurtmangiz #{o['id']} tasdiqlandi!</b>\nRahmat, siz bilan ishlashdan xursandmiz {pe('🤝')}"
            if status == "confirmed" else
            f"{pe('❌')} <b>Buyurtmangiz #{o['id']} bekor qilindi.</b>\nSavollar bo'lsa, menejerimizga yozing: {pe('💬')} {CONTACT}")
    try:
        await cb.bot.send_message(o["user_id"], text)
    except Exception:
        logging.exception("Mijozga holatni yuborib bo'lmadi: %s", o["user_id"])


# ================= KARUSEL =================

CAROUSEL_TITLE = {"glass": f"{step(4)}{pe('✨')} <b>Oyna turini</b> tanlang",
                  "color": f"{step(5)}{pe('🎨')} <b>Profil rangini</b> tanlang"}


def carousel(kind, i):
    """Bitta xabar: rasm, tagida nomi, ◀️ Tanlash ▶️. Tanlash callback'i 'glass:key' / 'color:key'."""
    lst = items(kind)
    i %= len(lst)
    p = lst[i]
    markup = grid([("◀️", f"car:{kind}:{i - 1}"), ("Tanlash", f"{kind}:{p['key']}", "success", "✅"),
                   ("▶️", f"car:{kind}:{i + 1}")], 3)
    caption = (f"{CAROUSEL_TITLE[kind]}:\n\n<b>{html.escape(p['name'])}</b>  ·  {i + 1}/{len(lst)}\n\n"
               f"<i>◀️ ▶️ — boshqa variantlarni ko'rish,  ✅ — shuni tanlash</i>")
    return *photo_for(p), caption, markup


async def send_carousel(msg: Message, kind):
    if not items(kind):
        return await msg.answer(f"Kechirasiz, hozircha variantlar yo'q. Bog'lanish: {CONTACT}")
    photo, path, caption, markup = carousel(kind, 0)
    remember(path, await msg.answer_photo(photo, caption=caption, reply_markup=markup))


@dp.callback_query(F.data.startswith("car:"))
async def carousel_nav(cb: CallbackQuery):
    _, kind, i = cb.data.split(":")
    if not items(kind):
        return await cb.answer()
    photo, path, caption, markup = carousel(kind, int(i))
    try:
        remember(path, await cb.message.edit_media(InputMediaPhoto(media=photo, caption=caption), reply_markup=markup))
    except TelegramBadRequest:  # tez bosilganda "message is not modified"
        pass
    await cb.answer()


def visible(kind, key):
    p = db.products.get(key)
    return p if p and p["kind"] == kind and not p["hidden"] and not p["deleted"] else None


# ================= 1-2. O'lchamlar va soni =================

@dp.message(CommandStart())
async def start(msg: Message, state: FSMContext, user=None):
    await db.upsert_user(user or msg.from_user)
    await state.clear()
    await msg.answer(
        f"{pe('👋')} <b>Assalomu alaykum!</b>\n"
        f"Bu bot <b>alyumin fasad</b> narxini bir necha soniyada hisoblab beradi {pe('✨')}\n{LINE}\n"
        f"⚠️ O'lchamlarni faqat <b>millimetrda (mm)</b> kiriting. Masalan: <code>2400</code>\n"
        f"Maksimal o'lcham: <b>{P.MAX_MM} mm</b>\n\n"
        f"{step(1)}📏 Fasad <b>enini</b> kiriting (mm):",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(Form.width)


@dp.message(Form.width)
async def width(msg: Message, state: FSMContext):
    v = parse_int(msg.text, 1, P.MAX_MM)
    if not v:
        return await msg.answer(f"❌ Noto'g'ri. Enini millimetrda, faqat son bilan yozing (eng ko'pi {P.MAX_MM}).\n"
                                f"Masalan: <code>2400</code>")
    await state.update_data(width=v)
    await msg.answer(f"{step(2)}📏 Fasad <b>balandligini</b> kiriting (mm):\n<i>Masalan: 720</i>")
    await state.set_state(Form.height)


@dp.message(Form.height)
async def height(msg: Message, state: FSMContext):
    v = parse_int(msg.text, 1, P.MAX_MM)
    if not v:
        return await msg.answer(f"❌ Noto'g'ri. Balandlikni millimetrda, faqat son bilan yozing (eng ko'pi {P.MAX_MM}).\n"
                                f"Masalan: <code>720</code>")
    await state.update_data(height=v)
    await msg.answer(f"{step(3)}🔢 Shu o'lchamdagi fasaddan <b>nechta</b> kerak?\n<i>Masalan: 4</i>")
    await state.set_state(Form.count)


@dp.message(Form.count)
async def count(msg: Message, state: FSMContext):
    v = parse_int(msg.text, 1, 1000)
    if not v:
        return await msg.answer("❌ Fasad sonini faqat son bilan yozing (1 dan 1000 gacha). Masalan: <code>4</code>")
    await state.update_data(count=v)
    await send_carousel(msg, "glass")
    await state.set_state(Form.glass)


# ================= 3-4. Oyna va rang =================

@dp.callback_query(Form.glass, F.data.startswith("glass:"))
async def glass(cb: CallbackQuery, state: FSMContext):
    p = visible("glass", cb.data.split(":")[1])
    if not p:
        return await cb.answer("Bu variant hozir mavjud emas", show_alert=True)
    await state.update_data(glass=p["key"])
    await cb.answer(p["name"])
    await cb.message.edit_caption(caption=f"{pe('✅')} Oyna: <b>{html.escape(p['name'])}</b>", reply_markup=None)
    await send_carousel(cb.message, "color")
    await state.set_state(Form.color)


@dp.callback_query(Form.color, F.data.startswith("color:"))
async def color(cb: CallbackQuery, state: FSMContext):
    p = visible("color", cb.data.split(":")[1])
    if not p:
        return await cb.answer("Bu variant hozir mavjud emas", show_alert=True)
    await state.update_data(color=p["key"])
    await cb.answer(p["name"])
    await cb.message.edit_caption(caption=f"{pe('✅')} Profil rangi: <b>{html.escape(p['name'])}</b>", reply_markup=None)
    await cb.message.answer(f"{step(6)}🔩 <b>Furnitura</b> (petlya) turini tanlang:",
                            reply_markup=grid([(f["name"], f"fit:{f['key']}", "primary") for f in items("fitting")], 2))
    await state.set_state(Form.fitting)


# ================= 5-6. Furnitura =================

@dp.callback_query(Form.fitting, F.data.startswith("fit:"))
async def fitting(cb: CallbackQuery, state: FSMContext):
    p = visible("fitting", cb.data.split(":")[1])
    if not p:
        return await cb.answer("Bu variant hozir mavjud emas", show_alert=True)
    await state.update_data(fitting=p["key"])
    await cb.answer()
    await cb.message.edit_text(f"{pe('✅')} Furnitura: <b>{html.escape(p['name'])}</b>")
    await cb.message.answer(f"{step(7)}🔢 <b>Bitta fasadga nechta</b> furnitura kerak?\n"
                            f"<i>Masalan: 2. Kerak bo'lmasa 0 yozing.</i>")
    await state.set_state(Form.fitting_count)


@dp.message(Form.fitting_count)
async def fitting_count(msg: Message, state: FSMContext):
    v = parse_int(msg.text, 0, 20)
    if v is None:
        return await msg.answer("❌ Faqat son yozing (0 dan 20 gacha). Masalan: <code>2</code>")
    await state.update_data(fitting_count=v)
    await msg.answer(f"{step(8)}{pe('✋')} Fasad <b>ruchkalimi</b> yoki <b>ruchkasiz</b>?\n"
                     f"<i>Ruchka profilning o'zidan chiqariladi.</i>",
                     reply_markup=grid([("Ruchkali", "handle:yes", "primary"), ("Ruchkasiz", "handle:no", "primary")], 2))
    await state.set_state(Form.handle)


# ================= 7-8. Ruchka =================

async def ask_delivery(msg: Message, state: FSMContext):
    await msg.answer(f"{step(9)}🚚 <b>Yetkazib berish</b> kerakmi?",
                     reply_markup=grid([(f"Shahar bo'ylab — {money(round(db.settings['delivery']))} so'm", "dlv:yes",
                                         "primary", "🚚"),
                                        ("O'zim olib ketaman", "dlv:no", "primary", "🏠")]))
    await state.set_state(Form.delivery)


@dp.callback_query(Form.handle, F.data.startswith("handle:"))
async def handle(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    if cb.data == "handle:yes":
        await cb.message.edit_text(f"{pe('✋')} Ruchka qaysi tomonda?",
                                   reply_markup=grid([("⬅️ Chap", "side:chap", "primary"), ("O'ng ➡️", "side:ong", "primary")], 2))
        await state.set_state(Form.side)
    else:
        await state.update_data(side=None)
        await cb.message.edit_text(f"{pe('✅')} Ruchka: <b>Ruchkasiz</b>")
        await ask_delivery(cb.message, state)


@dp.callback_query(Form.side, F.data.in_({"side:chap", "side:ong"}))
async def side(cb: CallbackQuery, state: FSMContext):
    s = cb.data.split(":")[1]
    await state.update_data(side=s)
    await cb.answer()
    await cb.message.edit_text(f"{pe('✅')} Ruchka: <b>{'Chap' if s == 'chap' else 'O‘ng'} tomonda</b>")
    await ask_delivery(cb.message, state)


# ================= 9. Yetkazish -> hisob, ism, telefon =================

PHONE_KB = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Raqamni yuborish", request_contact=True, style="success",
                                                         icon_custom_emoji_id=EMOJI.get("📱"))]],
                               resize_keyboard=True, one_time_keyboard=True)


@dp.callback_query(Form.delivery, F.data.in_({"dlv:yes", "dlv:no"}))
async def delivery(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    dlv = cb.data == "dlv:yes"
    await cb.message.edit_text(f"{pe('✅')} Yetkazish: <b>{'Shahar bo‘ylab' if dlv else 'O‘zim olib ketaman'}</b>")

    d = await state.get_data()
    rate = await asyncio.to_thread(get_rate)
    s = db.settings
    # mahsulot hisob o'rtasida o'chirilgan bo'lsa ham oxirgi ma'lum narx bilan hisoblanadi
    glass_price = db.products[d["glass"]]["price"] or 0
    fitting_price = db.products[d["fitting"]]["price"] or 0
    usd = P.calc_usd(s, d["width"], d["height"], d["count"], glass_price, fitting_price, d["fitting_count"], d["side"])
    total_sum = P.calc_sum(s, usd, rate, dlv)
    d.update(delivery=dlv)
    await db.upsert_user(cb.from_user)
    d["calc_id"] = await db.add_calc(cb.from_user.id, d, usd, rate, total_sum)
    await state.set_data(d)

    saved = await db.get_user_contact(cb.from_user.id)
    if not saved:
        return await ask_name(cb.message, state)
    await cb.message.answer(
        f"{step(10)}{pe('📋')} <b>SIZNING MA'LUMOTLARINGIZ</b>\n{LINE}\n"
        f"{pe('👤')} <b>Ism va familiya:</b> {html.escape(saved[0])}\n"
        f"{pe('📞')} <b>Telefon:</b> {saved[1]}\n{LINE}\n"
        f"Shu ma'lumotlar bilan davom etasizmi? {pe('👇')}",
        reply_markup=grid([("Tasdiqlash", "contact:ok", "success", "✅"), ("Tahrirlash", "contact:edit", "primary", "✏")], 2))
    await state.set_state(Form.contact)


async def ask_name(msg: Message, state: FSMContext):
    await msg.answer(f"{step(10)}{pe('👤')} <b>Ism va familiyangizni</b> kiriting:\n<i>Masalan: Aliyev Vali</i>")
    await state.set_state(Form.name)


@dp.callback_query(Form.contact, F.data.in_({"contact:ok", "contact:edit"}))
async def contact_choice(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    saved = await db.get_user_contact(cb.from_user.id)
    if cb.data == "contact:edit" or not saved:
        await cb.message.edit_text(f"{pe('✏')} Ma'lumotlarni qaytadan kiritamiz.")
        return await ask_name(cb.message, state)
    await cb.message.edit_text(f"{pe('✅')} {html.escape(saved[0])} · {saved[1]}")
    await show_order(cb.message, state, *saved)


@dp.message(Form.name)
async def name(msg: Message, state: FSMContext):
    text = " ".join((msg.text or "").split())
    if not 2 <= len(text) <= 100 or any(c.isdigit() for c in text):
        return await msg.answer("❌ Ism va familiyani to'g'ri kiriting. Masalan: Aliyev Vali")
    await state.update_data(customer_name=text)
    await msg.answer(f"{pe('📞')} <b>Telefon raqamingizni</b> yuboring — pastdagi tugmani bosing yoki yozing.\n"
                     "<i>Masalan: +998901234567</i>\n\n"
                     "⚠️ Mutaxassislarimiz aynan <b>shu raqamga</b> aloqaga chiqishadi, iltimos raqamni to'g'ri kiriting.",
                     reply_markup=PHONE_KB)
    await state.set_state(Form.phone)


def user_card(o):
    return f"{pe('🛒')} <b>BUYURTMANGIZ #{o['id']}</b>\n{LINE}\n{order_body(o)}\n{LINE}\n"


@dp.message(Form.phone)
async def phone(msg: Message, state: FSMContext):
    raw = msg.contact.phone_number if msg.contact else re.sub(r"[\s\-()]", "", msg.text or "")
    if not re.fullmatch(r"\+?\d{9,15}", raw):
        return await msg.answer("❌ Raqam noto'g'ri. Masalan: +998901234567\n"
                                "⚠️ Shu raqamga aloqaga chiqamiz, to'g'ri kiriting.", reply_markup=PHONE_KB)
    digits = raw.lstrip("+")
    number = "+" + ("998" + digits if len(digits) == 9 else digits)  # 901234567 -> +998901234567
    name = (await state.get_data())["customer_name"]
    await db.save_user_contact(msg.from_user.id, name, number)  # keyingi buyurtmada qayta so'ralmaydi
    await msg.answer(f"{pe('✅')} Raqam qabul qilindi.", reply_markup=ReplyKeyboardRemove())
    await show_order(msg, state, name, number)


async def show_order(msg: Message, state: FSMContext, name, number):
    """Kontaktni hisobga yozib, mijozga tasdiqlash kartasini ko'rsatadi."""
    calc_id = (await state.get_data())["calc_id"]
    await db.set_contact(calc_id, name, number)
    await state.set_state(None)
    o = await db.get_order(calc_id)
    await msg.answer(user_card(o) + f"{pe('👇')} Ma'lumotlarni tekshirib, buyurtmani <b>tasdiqlang</b>:",
                     reply_markup=grid([("Tasdiqlash", f"ord:ok:{o['id']}", "success", "✅"),
                                        ("Bekor qilish", f"ord:no:{o['id']}", "danger", "❌")], 2))


# ================= 10. Mijoz tasdig'i =================

AFTER_ORDER = grid([("Savol yoki izoh qoldirish", "comment", "primary", "✍"),
                    ("Yangi hisob", "restart", None, "🔄"),
                    ("Biz bilan bog'lanish", PROFILE_LINK, None, "💬")])


@dp.callback_query(F.data.startswith("ord:"))
async def order_decision(cb: CallbackQuery):
    _, action, calc_id = cb.data.split(":")
    o = await db.get_order(int(calc_id))
    if not o or o["user_id"] != cb.from_user.id:
        return await cb.answer()
    if action == "no":
        await cb.answer("Bekor qilindi")
        if o["ordered_at"] is None:  # yuborilganini qaytarib bo'lmaydi
            await cb.message.edit_text(user_card(o) + f"{pe('❌')} <b>Buyurtma bekor qilindi.</b> Ma'lumotlar yuborilmadi.",
                                       reply_markup=grid([("Qayta hisoblash", "restart", "primary", "🔄")]))
        return
    if not await db.submit_order(o["id"]):
        return await cb.answer("Bu buyurtma allaqachon yuborilgan.", show_alert=True)
    await cb.answer("✅ Yuborildi")
    o = await db.get_order(o["id"])
    await cb.message.edit_text(
        user_card(o) + f"{pe('🎉')} <b>Buyurtmangiz adminlarga yuborildi!</b>\n"
        f"Tez orada mutaxassislarimiz siz bilan <b>{o['phone']}</b> raqami orqali bog'lanishadi {pe('🤝')}",
        reply_markup=AFTER_ORDER)
    await notify(cb.bot, group_card(o), group_buttons(o))


@dp.callback_query(F.data == "restart")
async def restart(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await start(cb.message, state, user=cb.from_user)


# ================= Izoh =================

@dp.callback_query(F.data == "comment")
async def ask_comment(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await cb.message.answer(f"{pe('✍')} Savol yoki izohingizni yozing:")
    await state.set_state(Form.comment)


@dp.message(Form.comment, F.text)
async def comment(msg: Message, state: FSMContext):
    await db.upsert_user(msg.from_user)
    await db.add_comment(msg.from_user.id, msg.text)
    await state.set_state(None)
    await msg.answer(f"{pe('🙏')} Rahmat! Izohingiz qabul qilindi.\n\nQayta hisoblash: /start",
                     reply_markup=grid([("Biz bilan bog'lanish", PROFILE_LINK, None, "💬")]))
    await notify(msg.bot, f"{pe('💬')} <b>MIJOZ IZOHI</b>\n{LINE}\n{user_line(msg.from_user)}\n\n"
                          f"<blockquote>{html.escape(msg.text)}</blockquote>\n\n#izoh")


@dp.message(F.chat.type == "private")
async def fallback(msg: Message):
    await msg.answer("🤔 Tushunmadim.\n\n"
                     "• Savolga javob berayotgan bo'lsangiz — yuqoridagi <b>tugmalardan birini</b> bosing.\n"
                     "• Yangi narx hisoblash uchun — /start bosing.")


@dp.callback_query()
async def stale_button(cb: CallbackQuery):
    await cb.answer("Bu tugma endi ishlamaydi. Yangi hisob boshlash uchun /start bosing.", show_alert=True)


async def main():
    if not BOT_TOKEN or not DATABASE_URL:
        raise SystemExit("BOT_TOKEN va DATABASE_URL muhit o'zgaruvchilarini o'rnating")
    await db.init(DATABASE_URL)
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML", link_preview_is_disabled=True))
    await bot.set_my_commands([BotCommand(command="start", description="Narx hisoblash")])
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main())
