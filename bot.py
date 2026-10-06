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
IMAGES = ROOT / "images"
# Telegram'ning rasmiy premium (animatsiyali) emojilari: emoji -> custom_emoji_id.
# Bot egasida Telegram Premium bo'lgani uchun ishlaydi; bo'lmasa oddiy emoji ko'rinadi.
EMOJI = json.loads((ROOT / "premium_emoji.json").read_text(encoding="utf-8"))
LINE = "━━━━━━━━━━━━━━━━━━"

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
    name = State()
    phone = State()
    comment = State()


# ================= Dizayn yordamchilari =================

def pe(ch):
    """Premium emoji (matn uchun); ro'yxatda bo'lmasa oddiy emoji."""
    i = EMOJI.get(ch.replace("️", ""))
    return f'<tg-emoji emoji-id="{i}">{ch}</tg-emoji>' if i else ch


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


def get_rate():
    try:
        with urllib.request.urlopen("https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/", timeout=10) as r:
            return float(json.load(r)[0]["Rate"])
    except Exception:
        logging.exception("Kursni olib bo'lmadi")
        return db.prices["fallback_rate"]


def money(x):
    return f"{x:,.2f}".replace(",", " ") if isinstance(x, float) else f"{x:,}".replace(",", " ")


def user_line(u):
    return f"@{u.username or '-'} ({html.escape(u.full_name)}, id {u.id})"


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

class AdminForm(StatesGroup):
    price = State()
    image = State()
    broadcast = State()


NOT_CMD = ~F.text.startswith("/")  # admin kutish holatida /start yozsa, u buyruq sifatida ishlasin
BACK = ("Orqaga", "adm:menu", None, "⬅")
ADMIN_TITLE = f"{pe('🛠')} <b>ADMIN PANEL</b>\n{LINE}\nBo'limni tanlang {pe('👇')}"
ADMIN_MENU = grid([("Statistika", "adm:stat", "primary", "📊"), ("Eksport (Excel)", "adm:export", "primary", "📥"),
                   ("Narxlar", "adm:prices", "primary", "💰"), ("Rasmlar", "adm:images", "primary", "🖼"),
                   ("Xabar yuborish", "adm:bc", "success", "📢")], 2)


async def show(cb: CallbackQuery, text, markup):
    """Tugma bosilgan xabarni tahrirlaydi; bo'lmasa (rasm xabari va h.k.) yangisini yuboradi."""
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await cb.message.answer(text, reply_markup=markup)


@dp.message(Command("admin"), is_admin)
async def admin(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(ADMIN_TITLE, reply_markup=ADMIN_MENU)


@dp.callback_query(F.data == "adm:menu", is_admin)
async def adm_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer()
    await show(cb, ADMIN_TITLE, ADMIN_MENU)


# --- Statistika va eksport ---

@dp.callback_query(F.data == "adm:stat", is_admin)
async def adm_stat(cb: CallbackQuery):
    await cb.answer()
    s = await db.stats()
    await show(cb,
               f"{pe('📊')} <b>STATISTIKA</b>\n{LINE}\n"
               f"{pe('👤')} <b>Foydalanuvchilar:</b> {s['users']}\n"
               f"      faol: {s['active_users']} · bugun yangi: {s['new_today']}\n\n"
               f"{pe('🧮')} <b>Hisoblar:</b> bugun {s['calc_today']} · 7 kun {s['calc_week']} · jami {s['calc_all']}\n"
               f"{pe('🛒')} <b>Buyurtmalar:</b> bugun {s['ord_today']} · 7 kun {s['ord_week']} · jami {s['ord_all']}\n\n"
               f"{pe('⏳')} Kutilmoqda: <b>{s['st_new']}</b>\n"
               f"{pe('✅')} Tasdiqlangan: <b>{s['st_confirmed']}</b>\n"
               f"{pe('❌')} Bekor qilingan: <b>{s['st_cancelled']}</b>\n\n"
               f"{pe('💰')} <b>Tasdiqlangan summa: {money(float(s['confirmed_usd']))} USD</b>",
               grid([("Yangilash", "adm:stat", "primary", "🔄"), BACK], 2))


STATUS_NAME = {"new": "Kutilmoqda", "confirmed": "Tasdiqlangan", "cancelled": "Bekor qilingan"}


@dp.callback_query(F.data == "adm:export", is_admin)
async def adm_export(cb: CallbackQuery):
    await cb.answer("Tayyorlanmoqda...")
    rows = await db.export_rows()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["ID", "Sana", "User ID", "Username", "Telegram ismi", "Buyurtmachi", "Telefon", "Eni mm",
                "Balandligi mm", "Soni", "Oyna", "Rang", "Furnitura", "Furnitura/fasad", "Ruchka", "Yetkazish",
                "USD", "Kurs", "So'm", "Buyurtma vaqti", "Holat", "Kim o'zgartirdi"])
    for r in rows:
        w.writerow([r["id"], r["created_at"], r["user_id"], r["username"] or "", r["full_name"] or "",
                    r["customer_name"] or "", r["phone"] or "", r["width"], r["height"], r["count"],
                    P.GLASS.get(r["glass"], r["glass"]), P.COLORS.get(r["color"], r["color"]),
                    P.FITTINGS.get(r["fitting"], r["fitting"]), r["fitting_count"], r["handle"] or "yo'q",
                    "ha" if r["delivery"] else "yo'q", r["usd"], r["rate"], r["total_sum"], r["ordered_at"] or "",
                    STATUS_NAME.get(r["status"], "Faqat hisob"), r["status_by"] or ""])
    data = buf.getvalue().encode("utf-8-sig")  # BOM — Excel o'zbekcha harflarni to'g'ri ochadi
    await cb.message.answer_document(BufferedInputFile(data, "hisoblar.csv"), caption=f"Jami: {len(rows)} ta hisob")


# --- Narxlar ---

def price_value(key):
    v = db.prices.get(key)
    return "yashirin" if v is None else f"{v:g}"


def price_name(key):
    if key.startswith("glass."):
        return "🪟 " + P.GLASS[key[6:]]
    if key.startswith("fit."):
        return "🔩 " + P.FITTINGS[key[4:]]
    return "⚙️ " + P.DEFAULTS[key][0].split(",")[0]


def prices_menu():
    return grid([(f"{price_name(k)}: {price_value(k)}", f"adm:p:{k}") for k in P.DEFAULTS] + [BACK])


PRICES_TEXT = f"{pe('💰')} <b>NARXLAR</b>\n{LINE}\nOyna — USD/m², furnitura — USD/dona.\nO'zgartirish uchun tanlang {pe('👇')}"
CANCEL_PRICE = grid([("Bekor qilish", "adm:prices", "danger", "❌")])


@dp.callback_query(F.data == "adm:prices", is_admin)
async def adm_prices(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer()
    await show(cb, PRICES_TEXT, prices_menu())


@dp.callback_query(F.data.startswith("adm:p:"), is_admin)
async def adm_price_pick(cb: CallbackQuery, state: FSMContext):
    key = cb.data[6:]
    if key not in P.DEFAULTS:
        return await cb.answer()
    await cb.answer()
    await state.set_state(AdminForm.price)
    await state.update_data(price_key=key)
    await show(cb, f"{pe('✍')} <b>{P.DEFAULTS[key][0]}</b>\nHozirgi qiymat: <b>{price_value(key)}</b>\n\nYangi qiymatni yozing:"
               + ("\n<i>(Mijozlardan yashirish uchun: <code>yoq</code>)</i>" if key.startswith("glass.") else ""),
               CANCEL_PRICE)


@dp.message(AdminForm.price, is_admin, NOT_CMD)
async def adm_price_set(msg: Message, state: FSMContext):
    key = (await state.get_data())["price_key"]
    raw = (msg.text or "").strip().replace(",", ".").replace(" ", "").lower()
    if raw == "yoq" and key.startswith("glass."):
        value = None
    else:
        try:
            value = float(raw)
        except ValueError:
            return await msg.answer("❌ Son yozing, masalan 22 yoki 5.5", reply_markup=CANCEL_PRICE)
        if not 0 <= value < 10_000_000:
            return await msg.answer("❌ Qiymat 0 dan kichik bo'lmasin.", reply_markup=CANCEL_PRICE)
    old = price_value(key)
    await db.set_price(key, value)
    await state.clear()
    await msg.answer(f"{pe('✅')} {P.DEFAULTS[key][0]}: {old} → <b>{price_value(key)}</b>\n\n" + PRICES_TEXT,
                     reply_markup=prices_menu())


# --- Rasmlar ---

IMAGE_KEYS = {**{f"glass_{k}": "🪟 " + n for k, n in P.GLASS.items()},
              **{f"color_{k}": "🎨 " + n for k, n in P.COLORS.items()}}
IMAGES_TEXT = (f"{pe('🖼')} <b>RASMLAR</b>\n{LINE}\n✅ — botdan yuklangan · 📁 — papkadagi · ➖ — rasm yo'q\n"
               f"Almashtirish uchun tanlang {pe('👇')}")
CANCEL_IMAGE = ("Bekor qilish", "adm:images", "danger", "❌")


def images_menu():
    def mark(k):
        return "✅" if k in db.images else "📁" if find_image(k) else "➖"
    return grid([(f"{mark(k)} {n}", f"adm:i:{k}") for k, n in IMAGE_KEYS.items()] + [BACK], 2)


@dp.callback_query(F.data == "adm:images", is_admin)
async def adm_images(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer()
    await show(cb, IMAGES_TEXT, images_menu())


@dp.callback_query(F.data.startswith("adm:i:"), is_admin)
async def adm_image_pick(cb: CallbackQuery, state: FSMContext):
    key = cb.data[6:]
    if key not in IMAGE_KEYS:
        return await cb.answer()
    await cb.answer()
    await state.set_state(AdminForm.image)
    await state.update_data(image_key=key)
    buttons = [("Yuklangan rasmni o'chirish", f"adm:idel:{key}", "danger", "🗑")] if key in db.images else []
    photo, path = photo_for(key)
    m = await cb.message.answer_photo(photo, caption=f"Hozirgi rasm: <b>{IMAGE_KEYS[key]}</b>\n\n"
                                      "Yangi rasmni yuboring (fayl emas, <b>rasm</b> sifatida):",
                                      reply_markup=grid(buttons + [CANCEL_IMAGE]))
    remember(path, m)


@dp.message(AdminForm.image, F.photo, is_admin)
async def adm_image_set(msg: Message, state: FSMContext):
    key = (await state.get_data())["image_key"]
    await db.set_image(key, msg.photo[-1].file_id)
    await state.clear()
    await msg.answer(f"{pe('✅')} {IMAGE_KEYS[key]} rasmi saqlandi.\n\n" + IMAGES_TEXT, reply_markup=images_menu())


@dp.message(AdminForm.image, is_admin, NOT_CMD)
async def adm_image_wrong(msg: Message):
    await msg.answer("❌ Rasm yuboring (galereyadan, oddiy rasm sifatida).", reply_markup=grid([CANCEL_IMAGE]))


@dp.callback_query(F.data.startswith("adm:idel:"), is_admin)
async def adm_image_delete(cb: CallbackQuery, state: FSMContext):
    key = cb.data[9:]
    await db.delete_image(key)
    await state.clear()
    await cb.answer("O'chirildi")
    await cb.message.answer(f"🗑 {IMAGE_KEYS.get(key, key)}: endi papkadagi rasm ishlatiladi.\n\n" + IMAGES_TEXT,
                            reply_markup=images_menu())


# --- Ommaviy xabar ---

@dp.callback_query(F.data == "adm:bc", is_admin)
async def adm_bc(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(AdminForm.broadcast)
    await show(cb, f"{pe('📢')} Barcha foydalanuvchilarga yuboriladigan xabarni yuboring (matn, rasm, video — har qanday):",
               grid([("Bekor qilish", "adm:menu", "danger", "❌")]))


@dp.message(AdminForm.broadcast, is_admin, NOT_CMD)
async def adm_bc_preview(msg: Message, state: FSMContext):
    ids = await db.active_user_ids()
    await state.update_data(bc_chat=msg.chat.id, bc_msg=msg.message_id)
    await msg.reply(f"Shu xabar <b>{len(ids)}</b> ta foydalanuvchiga yuborilsinmi?",
                    reply_markup=grid([("Yuborish", "adm:bcgo", "success", "✅"),
                                       ("Bekor qilish", "adm:menu", "danger", "❌")], 2))


@dp.callback_query(F.data == "adm:bcgo", is_admin)
async def adm_bc_go(cb: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    await state.clear()
    if "bc_msg" not in d:
        return await cb.answer("Xabar topilmadi, qaytadan boshlang.", show_alert=True)
    await cb.answer()
    ids = await db.active_user_ids()
    await cb.message.edit_text(f"{pe('📢')} {len(ids)} ta foydalanuvchiga yuborilmoqda... Tugagach xabar beraman.")
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
    await bot.send_message(admin_chat, f"{pe('✅')} Xabar yuborildi: {ok} ta. Yetmadi (botni bloklagan): {failed} ta.")


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
        f"🪟 <b>Oyna:</b> {P.GLASS.get(o['glass'], o['glass'])}\n"
        f"{pe('🎨')} <b>Profil rangi:</b> {P.COLORS.get(o['color'], o['color'])}\n"
        f"🔩 <b>Furnitura:</b> {P.FITTINGS.get(o['fitting'], o['fitting'])} — {o['fitting_count']} dona/fasad\n"
        f"{pe('✋')} <b>Ruchka:</b> {handle}\n"
        f"🚚 <b>Yetkazish:</b> {delivery}"
        f"</blockquote>\n\n"
        f"{pe('💰')} <b>JAMI: {money(float(o['usd']))} USD</b>\n"
        f"{pe('💸')} <b>So'mda: {money(o['total_sum'])} so'm</b>"
        + (" <i>(yetkazish bilan)</i>" if o["delivery"] else "") + "\n"
        f"{pe('📈')} Kurs: 1 USD = {money(float(o['rate']))} so'm"
    )


def group_card(o):
    icon, title, tag = STATUS[o["status"]]
    tg = (f"@{o['username']}" if o["username"]
          else f'<a href="tg://user?id={o["user_id"]}">{html.escape(o["full_name"] or "profil")}</a>')
    text = (f"{pe(icon)}{pe(icon)} <b>{title} #{o['id']}</b> {pe(icon)}{pe(icon)}\n{LINE}\n"
            f"{order_body(o)}\n{LINE}\n"
            f"{pe('💬')} <b>Telegram:</b> {tg}\n"
            f"{pe('⏰')} <b>Vaqt:</b> {o['created_str']}")
    if o["status"] != "new":
        who = "Tasdiqladi" if o["status"] == "confirmed" else "Bekor qildi"
        text += f"\n{pe(icon)} <b>{who}:</b> {html.escape(o['status_by'])} · {o['status_str']}"
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
            f"{pe('❌')} <b>Buyurtmangiz #{o['id']} bekor qilindi.</b>\nSavollar bo'lsa: {PROFILE_LINK}")
    try:
        await cb.bot.send_message(o["user_id"], text)
    except Exception:
        logging.exception("Mijozga holatni yuborib bo'lmadi: %s", o["user_id"])


# ================= KARUSEL =================

CAROUSEL_TITLE = {"glass": f"{pe('✨')} <b>Oyna turini</b> tanlang", "color": f"{pe('🎨')} <b>Profil rangini</b> tanlang"}
_file_ids = {}  # papkadagi rasmlar qayta yuklanmasin: path -> Telegram file_id


def photo_for(image):
    """(rasm, path): bazadagi (admin yuklagan) -> papkadagi -> umumiy glass_ref -> no_photo."""
    if image in db.images:
        return db.images[image], None
    path = find_image(image) or (image.startswith("glass_ref_") and find_image("glass_ref")) or find_image("no_photo")
    return _file_ids.get(path) or FSInputFile(path), path


def remember(path, m):
    if path and isinstance(m, Message) and m.photo:
        _file_ids[path] = m.photo[-1].file_id


def carousel_items(kind):
    if kind == "glass":
        return [(k, n, f"glass_{k}") for k, n in P.GLASS.items() if db.prices.get(f"glass.{k}") is not None]
    return [(k, n, f"color_{k}") for k, n in P.COLORS.items()]


def carousel(kind, i):
    """Bitta xabar: rasm, tagida nomi, ◀️ Tanlash ▶️. Tanlash callback'i 'glass:key' / 'color:key'."""
    items = carousel_items(kind)
    i %= len(items)
    key, name, image = items[i]
    markup = grid([("◀️", f"car:{kind}:{i - 1}"), ("Tanlash", f"{kind}:{key}", "success", "✅"),
                   ("▶️", f"car:{kind}:{i + 1}")], 3)
    caption = f"{CAROUSEL_TITLE[kind]}:\n\n<b>{name}</b>  ·  {i + 1}/{len(items)}"
    return *photo_for(image), caption, markup


async def send_carousel(msg: Message, kind):
    photo, path, caption, markup = carousel(kind, 0)
    remember(path, await msg.answer_photo(photo, caption=caption, reply_markup=markup))


@dp.callback_query(F.data.startswith("car:"))
async def carousel_nav(cb: CallbackQuery):
    _, kind, i = cb.data.split(":")
    photo, path, caption, markup = carousel(kind, int(i))
    try:
        remember(path, await cb.message.edit_media(InputMediaPhoto(media=photo, caption=caption), reply_markup=markup))
    except TelegramBadRequest:  # tez bosilganda "message is not modified"
        pass
    await cb.answer()


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
        f"📏 Fasad <b>enini</b> kiriting (mm):",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(Form.width)


@dp.message(Form.width)
async def width(msg: Message, state: FSMContext):
    v = parse_int(msg.text, 1, P.MAX_MM)
    if not v:
        return await msg.answer(f"❌ Noto'g'ri qiymat. Enini mmda, 1 dan {P.MAX_MM} gacha butun son bilan kiriting. Masalan: 2400")
    await state.update_data(width=v)
    await msg.answer("📏 Fasad <b>balandligini</b> kiriting (mm):")
    await state.set_state(Form.height)


@dp.message(Form.height)
async def height(msg: Message, state: FSMContext):
    v = parse_int(msg.text, 1, P.MAX_MM)
    if not v:
        return await msg.answer(f"❌ Noto'g'ri qiymat. Balandlikni mmda, 1 dan {P.MAX_MM} gacha butun son bilan kiriting. Masalan: 2400")
    await state.update_data(height=v)
    await msg.answer("🔢 <b>Fasad sonini</b> kiriting:")
    await state.set_state(Form.count)


@dp.message(Form.count)
async def count(msg: Message, state: FSMContext):
    v = parse_int(msg.text, 1, 1000)
    if not v:
        return await msg.answer("❌ Fasad sonini 1 dan 1000 gacha butun son bilan kiriting.")
    await state.update_data(count=v)
    await send_carousel(msg, "glass")
    await state.set_state(Form.glass)


# ================= 3-4. Oyna va rang =================

@dp.callback_query(Form.glass, F.data.startswith("glass:"))
async def glass(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":")[1]
    if key not in P.GLASS or db.prices.get(f"glass.{key}") is None:
        return await cb.answer("Bu variant hozir mavjud emas", show_alert=True)
    await state.update_data(glass=key)
    await cb.answer(P.GLASS[key])
    await cb.message.edit_caption(caption=f"{pe('✅')} Oyna: <b>{P.GLASS[key]}</b>", reply_markup=None)
    await send_carousel(cb.message, "color")
    await state.set_state(Form.color)


@dp.callback_query(Form.color, F.data.startswith("color:"))
async def color(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":")[1]
    if key not in P.COLORS:
        return await cb.answer()
    await state.update_data(color=key)
    await cb.answer(P.COLORS[key])
    await cb.message.edit_caption(caption=f"{pe('✅')} Profil rangi: <b>{P.COLORS[key]}</b>", reply_markup=None)
    await cb.message.answer("🔩 <b>Furnitura turini</b> tanlang:",
                            reply_markup=grid([(name, f"fit:{k}", "primary") for k, name in P.FITTINGS.items()], 2))
    await state.set_state(Form.fitting)


# ================= 5-6. Furnitura =================

@dp.callback_query(Form.fitting, F.data.startswith("fit:"))
async def fitting(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":")[1]
    if key not in P.FITTINGS:
        return await cb.answer()
    await state.update_data(fitting=key)
    await cb.answer()
    await cb.message.edit_text(f"{pe('✅')} Furnitura: <b>{P.FITTINGS[key]}</b>")
    await cb.message.answer("🔢 <b>Har bir fasadda nechta</b> furnitura kerak? <i>(0–20)</i>")
    await state.set_state(Form.fitting_count)


@dp.message(Form.fitting_count)
async def fitting_count(msg: Message, state: FSMContext):
    v = parse_int(msg.text, 0, 20)
    if v is None:
        return await msg.answer("❌ Furnitura sonini 0 dan 20 gacha butun son bilan kiriting.")
    await state.update_data(fitting_count=v)
    await msg.answer(f"{pe('✋')} Fasad <b>ruchkalimi</b> yoki <b>ruchkasiz</b>?",
                     reply_markup=grid([("Ruchkali", "handle:yes", "primary"), ("Ruchkasiz", "handle:no", "primary")], 2))
    await state.set_state(Form.handle)


# ================= 7-8. Ruchka =================

async def ask_delivery(msg: Message, state: FSMContext):
    await msg.answer(f"🚚 <b>Yetkazib berish</b> kerakmi?",
                     reply_markup=grid([(f"Shahar bo'ylab — {money(round(db.prices['delivery']))} so'm", "dlv:yes",
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
    p = db.prices
    usd = P.calc_usd(p, d["width"], d["height"], d["count"], d["glass"], d["fitting"], d["fitting_count"], d["side"])
    total_sum = P.calc_sum(p, usd, rate, dlv)
    d.update(delivery=dlv)
    await db.upsert_user(cb.from_user)
    d["calc_id"] = await db.add_calc(cb.from_user.id, d, usd, rate, total_sum)
    await state.set_data(d)
    await cb.message.answer(f"{pe('👤')} <b>Ism va familiyangizni</b> kiriting:\n<i>Masalan: Aliyev Vali</i>")
    await state.set_state(Form.name)


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
    d = await state.get_data()
    await db.set_phone(msg.from_user.id, number)
    await db.set_contact(d["calc_id"], d["customer_name"], number)
    await state.set_state(None)
    await msg.answer(f"{pe('✅')} Raqam qabul qilindi.", reply_markup=ReplyKeyboardRemove())
    o = await db.get_order(d["calc_id"])
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
    await msg.answer("Iltimos, yuqoridagi tugmalardan birini tanlang yoki /start bosing.")


@dp.callback_query()
async def stale_button(cb: CallbackQuery):
    await cb.answer("Bu tugma eskirgan. /start bosing.", show_alert=True)


async def main():
    if not BOT_TOKEN or not DATABASE_URL:
        raise SystemExit("BOT_TOKEN va DATABASE_URL muhit o'zgaruvchilarini o'rnating")
    await db.init(DATABASE_URL)
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    await bot.set_my_commands([BotCommand(command="start", description="Narx hisoblash")])
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main())
