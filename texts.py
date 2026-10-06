"""Mijozga ko'rinadigan barcha matnlar: kalit -> (o'zbekcha, ruscha).
Kalit 'b_' (tugma) yoki 'a_' (ogohlantirish oynasi) bilan boshlansa — oddiy matn, HTML va premium emojisiz.
{line}, {max}, {contact}, {total} har doim mavjud; qolganlari chaqirganda beriladi."""

TEXTS = {
    # --- til ---
    "lang_set": ("✅ O'zbek tili tanlandi.", "✅ Выбран русский язык."),
    "b_menu_start": ("Narx hisoblash", "Рассчитать цену"),
    "b_menu_lang": ("Tilni o'zgartirish", "Сменить язык"),

    # --- qadamlar ---
    "step": ("<i>Qadam {n}/{total}</i>\n", "<i>Шаг {n}/{total}</i>\n"),
    "welcome": (
        "👋 <b>Assalomu alaykum!</b>\n"
        "Bu bot <b>alyumin fasad</b> narxini bir necha soniyada hisoblab beradi ✨\n{line}\n"
        "⚠️ O'lchamlarni faqat <b>millimetrda (mm)</b> kiriting. Masalan: <code>2400</code>\n"
        "Maksimal o'lcham: <b>{max} mm</b>\n\n",
        "👋 <b>Здравствуйте!</b>\n"
        "Этот бот за несколько секунд рассчитает стоимость <b>алюминиевого фасада</b> ✨\n{line}\n"
        "⚠️ Размеры вводите только в <b>миллиметрах (мм)</b>. Например: <code>2400</code>\n"
        "Максимальный размер: <b>{max} мм</b>\n\n",
    ),
    "ask_width": ("📏 Fasad <b>enini</b> kiriting (mm):", "📏 Введите <b>ширину</b> фасада (мм):"),
    "err_width": ("❌ Noto'g'ri. Enini millimetrda, faqat son bilan yozing (eng ko'pi {max}).\nMasalan: <code>2400</code>",
                  "❌ Неверно. Введите ширину в миллиметрах, только числом (не больше {max}).\nНапример: <code>2400</code>"),
    "ask_height": ("📏 Fasad <b>balandligini</b> kiriting (mm):\n<i>Masalan: 720</i>",
                   "📏 Введите <b>высоту</b> фасада (мм):\n<i>Например: 720</i>"),
    "err_height": ("❌ Noto'g'ri. Balandlikni millimetrda, faqat son bilan yozing (eng ko'pi {max}).\nMasalan: <code>720</code>",
                   "❌ Неверно. Введите высоту в миллиметрах, только числом (не больше {max}).\nНапример: <code>720</code>"),
    "ask_count": ("🔢 Shu o'lchamdagi fasaddan <b>nechta</b> kerak?\n<i>Masalan: 4</i>",
                  "🔢 Сколько фасадов <b>такого размера</b> нужно?\n<i>Например: 4</i>"),
    "err_count": ("❌ Fasad sonini faqat son bilan yozing (1 dan 1000 gacha). Masalan: <code>4</code>",
                  "❌ Введите количество числом (от 1 до 1000). Например: <code>4</code>"),

    # --- karusel ---
    "title_glass": ("✨ <b>Oyna turini</b> tanlang", "✨ Выберите <b>тип стекла</b>"),
    "title_color": ("🎨 <b>Profil rangini</b> tanlang", "🎨 Выберите <b>цвет профиля</b>"),
    "carousel_hint": ("<i>◀️ ▶️ — boshqa variantlarni ko'rish,  ✅ — shuni tanlash</i>",
                      "<i>◀️ ▶️ — смотреть другие варианты,  ✅ — выбрать этот</i>"),
    "b_choose": ("Tanlash", "Выбрать"),
    "chosen_glass": ("✅ Oyna: <b>{name}</b>", "✅ Стекло: <b>{name}</b>"),
    "chosen_color": ("✅ Profil rangi: <b>{name}</b>", "✅ Цвет профиля: <b>{name}</b>"),
    "a_not_available": ("Bu variant hozir mavjud emas", "Этот вариант сейчас недоступен"),
    "no_variants": ("Kechirasiz, hozircha variantlar yo'q. Bog'lanish: {contact}",
                    "Извините, сейчас вариантов нет. Связь: {contact}"),

    # --- furnitura ---
    "ask_fitting": ("🔩 <b>Furnitura</b> (petlya) turini tanlang:", "🔩 Выберите тип <b>фурнитуры</b> (петли):"),
    "chosen_fitting": ("✅ Furnitura: <b>{name}</b>", "✅ Фурнитура: <b>{name}</b>"),
    "ask_fit_count": ("🔢 <b>Bitta fasadga nechta</b> furnitura kerak?\n<i>Masalan: 2. Kerak bo'lmasa 0 yozing.</i>",
                      "🔢 Сколько петель нужно <b>на один фасад</b>?\n<i>Например: 2. Если не нужно — напишите 0.</i>"),
    "err_fit_count": ("❌ Faqat son yozing (0 dan 20 gacha). Masalan: <code>2</code>",
                      "❌ Введите число (от 0 до 20). Например: <code>2</code>"),

    # --- ruchka ---
    "ask_handle": ("✋ Fasad <b>ruchkalimi</b> yoki <b>ruchkasiz</b>?\n<i>Ruchka profilning o'zidan chiqariladi.</i>",
                   "✋ Фасад <b>с ручкой</b> или <b>без ручки</b>?\n<i>Ручка делается из самого профиля.</i>"),
    "b_handle_yes": ("Ruchkali", "С ручкой"),
    "b_handle_no": ("Ruchkasiz", "Без ручки"),
    "ask_side": ("✋ Ruchka qaysi tomonda?", "✋ С какой стороны ручка?"),
    "b_left": ("⬅️ Chap", "⬅️ Слева"),
    "b_right": ("O'ng ➡️", "Справа ➡️"),
    "chosen_handle": ("✅ Ruchka: <b>{v}</b>", "✅ Ручка: <b>{v}</b>"),
    "handle_none": ("Ruchkasiz", "Без ручки"),
    "handle_chap": ("Chap tomonda", "Слева"),
    "handle_ong": ("O'ng tomonda", "Справа"),

    # --- yetkazish ---
    "ask_delivery": ("🚚 <b>Yetkazib berish</b> kerakmi?", "🚚 Нужна <b>доставка</b>?"),
    "b_delivery_yes": ("Shahar bo'ylab — {sum} so'm", "По городу — {sum} сум"),
    "b_delivery_no": ("O'zim olib ketaman", "Заберу сам"),
    "chosen_delivery": ("✅ Yetkazish: <b>{v}</b>", "✅ Доставка: <b>{v}</b>"),
    "delivery_yes": ("Shahar bo'ylab", "По городу"),
    "delivery_no": ("O'zi olib ketadi", "Самовывоз"),

    # --- ism va telefon ---
    "saved_contact": (
        "📋 <b>SIZNING MA'LUMOTLARINGIZ</b>\n{line}\n👤 <b>Ism va familiya:</b> {name}\n📞 <b>Telefon:</b> {phone}\n{line}\n"
        "Shu ma'lumotlar bilan davom etasizmi? 👇",
        "📋 <b>ВАШИ ДАННЫЕ</b>\n{line}\n👤 <b>Имя и фамилия:</b> {name}\n📞 <b>Телефон:</b> {phone}\n{line}\n"
        "Продолжить с этими данными? 👇",
    ),
    "b_confirm": ("Tasdiqlash", "Подтвердить"),
    "b_edit": ("Tahrirlash", "Изменить"),
    "contact_edit": ("✏ Ma'lumotlarni qaytadan kiritamiz.", "✏ Введём данные заново."),
    "ask_name": ("👤 <b>Ism va familiyangizni</b> kiriting:\n<i>Masalan: Aliyev Vali</i>",
                 "👤 Введите <b>имя и фамилию</b>:\n<i>Например: Алиев Вали</i>"),
    "err_name": ("❌ Ism va familiyani to'g'ri kiriting. Masalan: Aliyev Vali",
                 "❌ Введите имя и фамилию правильно. Например: Алиев Вали"),
    "ask_phone": (
        "📞 <b>Telefon raqamingizni</b> yuboring — pastdagi tugmani bosing yoki yozing.\n<i>Masalan: +998901234567</i>\n\n"
        "⚠️ Mutaxassislarimiz aynan <b>shu raqamga</b> aloqaga chiqishadi, iltimos raqamni to'g'ri kiriting.",
        "📞 Отправьте <b>номер телефона</b> — нажмите кнопку внизу или напишите.\n<i>Например: +998901234567</i>\n\n"
        "⚠️ Наши специалисты свяжутся именно <b>по этому номеру</b>, пожалуйста, введите его правильно.",
    ),
    "err_phone": ("❌ Raqam noto'g'ri. Masalan: +998901234567\n⚠️ Shu raqamga aloqaga chiqamiz, to'g'ri kiriting.",
                  "❌ Неверный номер. Например: +998901234567\n⚠️ Мы свяжемся по этому номеру, введите правильно."),
    "b_send_phone": ("Raqamni yuborish", "Отправить номер"),
    "phone_ok": ("✅ Raqam qabul qilindi.", "✅ Номер принят."),

    # --- buyurtma kartasi ---
    "order_title": ("🛒 <b>BUYURTMANGIZ #{id}</b>", "🛒 <b>ВАШ ЗАКАЗ №{id}</b>"),
    "order_body": (
        "👤 <b>Mijoz:</b> {name}\n📞 <b>Telefon:</b> {phone}\n\n<blockquote>"
        "📐 <b>O'lcham:</b> {w} × {h} mm\n🔢 <b>Soni:</b> {count} dona\n🪟 <b>Oyna:</b> {glass}\n"
        "🎨 <b>Profil rangi:</b> {color}\n🔩 <b>Furnitura:</b> {fitting} — {fc} dona/fasad\n"
        "✋ <b>Ruchka:</b> {handle}\n🚚 <b>Yetkazish:</b> {delivery}</blockquote>\n\n"
        "💰 <b>JAMI: {usd} USD</b>\n💸 <b>So'mda: {sum} so'm</b>{with_dlv}\n📈 Dollar kursi: 1 USD = {rate} so'm",
        "👤 <b>Клиент:</b> {name}\n📞 <b>Телефон:</b> {phone}\n\n<blockquote>"
        "📐 <b>Размер:</b> {w} × {h} мм\n🔢 <b>Количество:</b> {count} шт\n🪟 <b>Стекло:</b> {glass}\n"
        "🎨 <b>Цвет профиля:</b> {color}\n🔩 <b>Фурнитура:</b> {fitting} — {fc} шт/фасад\n"
        "✋ <b>Ручка:</b> {handle}\n🚚 <b>Доставка:</b> {delivery}</blockquote>\n\n"
        "💰 <b>ИТОГО: {usd} USD</b>\n💸 <b>В сумах: {sum} сум</b>{with_dlv}\n📈 Курс доллара: 1 USD = {rate} сум",
    ),
    "with_delivery": (" <i>(yetkazish bilan)</i>", " <i>(с доставкой)</i>"),
    "confirm_prompt": ("👇 Ma'lumotlarni tekshirib, buyurtmani <b>tasdiqlang</b>:",
                       "👇 Проверьте данные и <b>подтвердите</b> заказ:"),
    "b_cancel": ("Bekor qilish", "Отменить"),
    "order_sent": ("🎉 <b>Buyurtmangiz adminlarga yuborildi!</b>\n"
                   "Tez orada mutaxassislarimiz siz bilan <b>{phone}</b> raqami orqali bog'lanishadi 🤝",
                   "🎉 <b>Ваш заказ отправлен!</b>\n"
                   "Скоро наши специалисты свяжутся с вами по номеру <b>{phone}</b> 🤝"),
    "order_cancelled": ("❌ <b>Buyurtma bekor qilindi.</b> Ma'lumotlar yuborilmadi.",
                        "❌ <b>Заказ отменён.</b> Данные не отправлены."),
    "a_sent": ("✅ Yuborildi", "✅ Отправлено"),
    "a_cancelled": ("Bekor qilindi", "Отменено"),
    "a_already_sent": ("Bu buyurtma allaqachon yuborilgan.", "Этот заказ уже отправлен."),
    "b_restart": ("Qayta hisoblash", "Рассчитать заново"),
    "b_comment": ("Savol yoki izoh qoldirish", "Задать вопрос / оставить отзыв"),
    "b_new": ("Yangi hisob", "Новый расчёт"),
    "b_contact": ("Biz bilan bog'lanish", "Связаться с нами"),

    # --- admin qarori mijozga ---
    "notify_confirmed": ("🎉 <b>Buyurtmangiz #{id} tasdiqlandi!</b>\nRahmat, siz bilan ishlashdan xursandmiz 🤝",
                         "🎉 <b>Ваш заказ №{id} подтверждён!</b>\nСпасибо, рады работать с вами 🤝"),
    "notify_cancelled": ("❌ <b>Buyurtmangiz #{id} bekor qilindi.</b>\nSavollar bo'lsa, menejerimizga yozing: 💬 {contact}",
                         "❌ <b>Ваш заказ №{id} отменён.</b>\nЕсли есть вопросы, напишите менеджеру: 💬 {contact}"),

    # --- izoh va boshqalar ---
    "ask_comment": ("✍ Savol yoki izohingizni yozing:", "✍ Напишите ваш вопрос или отзыв:"),
    "comment_thanks": ("🙏 Rahmat! Izohingiz qabul qilindi.\n\nQayta hisoblash: /start",
                       "🙏 Спасибо! Ваше сообщение принято.\n\nНовый расчёт: /start"),
    "fallback": ("🤔 Tushunmadim.\n\n• Savolga javob berayotgan bo'lsangiz — yuqoridagi <b>tugmalardan birini</b> bosing.\n"
                 "• Yangi narx hisoblash uchun — /start bosing.",
                 "🤔 Не понял.\n\n• Если отвечаете на вопрос — нажмите одну из <b>кнопок</b> выше.\n"
                 "• Для нового расчёта — нажмите /start."),
    "a_stale": ("Bu tugma endi ishlamaydi. Yangi hisob boshlash uchun /start bosing.",
                "Эта кнопка больше не работает. Для нового расчёта нажмите /start."),
}

if __name__ == "__main__":
    import string
    for k, pair in TEXTS.items():
        assert len(pair) == 2, k
        f = [sorted({x[1] for x in string.Formatter().parse(v) if x[1]}) for v in pair]
        assert f[0] == f[1], (k, f)  # ikkala tilda bir xil o'rinbosarlar
    print("ok", len(TEXTS))
