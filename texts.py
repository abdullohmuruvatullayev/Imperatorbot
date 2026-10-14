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
        "Bu bot <b>alyumin fasad</b> narxini bir necha soniyada hisoblab beradi ✨\n{line}\n",
        "👋 <b>Здравствуйте!</b>\n"
        "Этот бот за несколько секунд рассчитает стоимость <b>алюминиевого фасада</b> ✨\n{line}\n",
    ),
    "ask_count": ("🔢 <b>Nechta fasad</b> hisoblaymiz?\n<i>Masalan: 4</i>\n\n"
                  "Har bir fasadning <b>o'lchamini alohida</b> kiritasiz.",
                  "🔢 <b>Сколько фасадов</b> считаем?\n<i>Например: 4</i>\n\n"
                  "Размер <b>каждого фасада</b> вводится отдельно."),
    "err_count": ("❌ Fasad sonini faqat son bilan yozing (1 dan {fmax} gacha). Masalan: <code>4</code>",
                  "❌ Введите количество числом (от 1 до {fmax}). Например: <code>4</code>"),

    # --- fasad o'lchamlari: har biriga alohida, avval bo'yi, keyin eni ---
    "ask_facade_dims": ("✍️ <b>{n}-fasad BO'YINI</b> kiriting (mm)  ({i}/{n_all})\n\n"
                        "📐 Rasmda <b>chapdagi o'q</b> — aynan bo'yi.\n"
                        "Masalan: <code>1800</code>   ·   eng ko'pi <b>{max}</b>\n"
                        "<i>Keyingi qadamda enini so'rayman.</i>",
                        "✍️ Введите <b>ВЫСОТУ {n}-го фасада</b> (мм)  ({i}/{n_all})\n\n"
                        "📐 На рисунке <b>стрелка слева</b> — это высота.\n"
                        "Например: <code>1800</code>   ·   максимум <b>{max}</b>\n"
                        "<i>На следующем шаге спрошу ширину.</i>"),
    "ask_width": ("✍️ Endi <b>{n}-fasad ENINI</b> kiriting (mm)  ({i}/{n_all})\n\n"
                  "📐 Rasmda <b>pastdagi o'q</b> — aynan eni. Bo'yi <b>{h}</b> mm saqlandi ✅\n"
                  "Masalan: <code>900</code>\n"
                  "<i>Yoki ikkalasini birdan yozing: <code>1800 900</code></i>",
                  "✍️ Теперь введите <b>ШИРИНУ {n}-го фасада</b> (мм)  ({i}/{n_all})\n\n"
                  "📐 На рисунке <b>стрелка снизу</b> — это ширина. Высота <b>{h}</b> мм сохранена ✅\n"
                  "Например: <code>900</code>\n"
                  "<i>Или напишите оба значения сразу: <code>1800 900</code></i>"),
    "err_facade_dims": ("❌ Bo'ynini faqat son bilan yozing (mm), eng ko'pi {max}.\n"
                        "Masalan: <code>1800</code>",
                        "❌ Введите высоту числом (мм), не больше {max}.\n"
                        "Например: <code>1800</code>"),
    "err_width": ("❌ Enini faqat son bilan yozing (mm), eng ko'pi {max}.\n"
                  "Masalan: <code>900</code>",
                  "❌ Введите ширину числом (мм), не больше {max}.\n"
                  "Например: <code>900</code>"),
    "facade_saved": ("✅ <b>{n}-fasad:</b> bo'yi {h} × eni {w} mm", "✅ <b>Фасад {n}:</b> высота {h} × ширина {w} мм"),
    "all_dims_done": ("✅ Barcha <b>{n} ta</b> fasad o'lchami kiritildi.", "✅ Размеры <b>всех {n}</b> фасадов введены."),
    # chizma (diagram.py) ichidagi yozuvlar — rasmda ko'rinadi
    "dg_title": ("{n}-FASAD", "{n}-ФАСАД"),
    "dg_mm": ("mm", "мм"),
    "dg_height": ("BO'YI", "ВЫСОТА"),
    "dg_width": ("ENI", "ШИРИНА"),
    "dg_no_height": ("bo'yi ?", "высота ?"),
    "dg_no_width": ("eni ?", "ширина ?"),
    "dg_handle": ("ruchka", "ручка"),

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
    # --- furnitura soni: har bir fasad alohida (ruchka oqimiga o'xshash) ---
    "ask_fit_list": ("✋ Furnitura: <b>{fitting}</b>\n\n"
                     "Har bir fasadga <b>nechtaligi</b>ni kiriting.\n\n"
                     "👇 Fasad ustiga bosing va sonini yozing.\n"
                     "<b>Barcha {n} ta</b> fasadni albatta to'ldiring.",
                     "✋ Фурнитура: <b>{fitting}</b>\n\n"
                     "Введите <b>количество</b> для каждого фасада.\n\n"
                     "👇 Нажмите на фасад и введите количество.\n"
                     "Обязательно заполните <b>все {n}</b> фасадов."),
    "ask_fit": ("🔢 <b>{n}-fasad</b> ({h}×{w}) — nechta furnitura kerak?\n"
                "<i>Masalan: 2. Kerak bo'lmasa 0 yozing.</i>{cur}",
                "🔢 <b>Фасад {n}</b> ({h}×{w}) — сколько фурнитуры нужно?\n"
                "<i>Например: 2. Если не нужно — напишите 0.</i>{cur}"),
    "b_fit": ("{n}-fasad {h}×{w}", "{n}-фасад {h}×{w}"),
    "b_fit_marked": ("✅ {n}-fasad {h}×{w} · {v} dona", "✅ {n}-фасад {h}×{w} · {v} шт"),
    "fits_progress": ("Kiritilgan: {done}/{n}", "Введено: {done}/{n}"),
    "b_fits_done": ("Tayyor — davom etamiz", "Готово — продолжить"),
    "a_all_fits_done": ("Barcha fasadlar kiritildi ✅", "Все фасады введены ✅"),
    "err_fits_left": ("Avval qolgan fasadlarni to'ldiring: {left}",
                      "Сначала заполните оставшиеся фасады: {left}"),
    "fit_saved": ("✅ <b>{n}-fasad:</b> furnitura {v} dona", "✅ <b>Фасад {n}:</b> фурнитура {v} шт"),
    "err_fit_count": ("❌ Faqat son yozing (0 dan 20 gacha). Masalan: <code>2</code>",
                      "❌ Введите число (от 0 до 20). Например: <code>2</code>"),

    # --- ruchka ---
    "ask_handle": ("✋ Fasad <b>ruchkalimi</b> yoki <b>ruchkasiz</b>?\n<i>Ruchka profilning o'zidan chiqariladi.</i>",
                   "✋ Фасад <b>с ручкой</b> или <b>без ручки</b>?\n<i>Ручка делается из самого профиля.</i>"),
    "b_handle_yes": ("Ruchkali", "С ручкой"),
    "b_handle_no": ("Ruchkasiz", "Без ручки"),
    "ask_handle_list": ("✋ <b>Ruchkali fasadlarni belgilang.</b>\n\n"
                        "👇 Qaysi fasadda ruchka bo'lsa, <b>o'sha fasad ustiga bosing</b>, keyin tomonini tanlang.\n"
                        "<b>Barcha {n} ta</b> fasadni albatta belgilang.",
                        "✋ <b>Отметьте фасады с ручкой.</b>\n\n"
                        "👇 Нажмите на <b>фасад с ручкой</b>, затем выберите сторону.\n"
                        "Обязательно отметьте <b>все {n}</b> фасадов."),
    "b_facade": ("{n}-fasad {h}×{w}", "{n}-фасад {h}×{w}"),
    "b_facade_marked": ("✅ {n}-fasad {h}×{w} · {v}", "✅ {n}-фасад {h}×{w} · {v}"),
    "ask_side": ("✋ <b>{n}-fasad</b> ({h}×{w}) — ruchka qaysi tomonda?", "✋ <b>Фасад {n}</b> ({h}×{w}) — с какой стороны ручка?"),
    "b_left": ("⬅️ Chap", "⬅️ Слева"),
    "b_right": ("O'ng ➡️", "Справа ➡️"),
    "chosen_handle": ("✅ Ruchka: <b>{v}</b>", "✅ Ручка: <b>{v}</b>"),
    "handle_none": ("Ruchkasiz", "Без ручки"),
    "handle_chap": ("Chap tomonda", "Слева"),
    "handle_ong": ("O'ng tomonda", "Справа"),
    "b_facade_list": ("⬅️ Fasadlar ro'yxati", "⬅️ Список фасадов"),
    "b_handles_done": ("Tayyor — davom etamiz", "Готово — продолжить"),
    "handles_progress": ("Belgilangan: {done}/{n}", "Отмечено: {done}/{n}"),
    "err_handles_left": ("Avval qolgan fasadlarni belgilang: {left}", "Сначала отметьте оставшиеся фасады: {left}"),
    "a_all_handles_done": ("Barcha fasadlar belgilandi ✅", "Все фасады отмечены ✅"),

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
        "{dims}"
        "🔢 <b>Soni:</b> {count} dona\n🪟 <b>Oyna:</b> {glass}\n"
        "🎨 <b>Profil rangi:</b> {color}\n🔩 <b>Furnitura:</b> {fitting} · {fit}\n"
        "✋ <b>Ruchka:</b> {handle}\n🚚 <b>Yetkazish:</b> {delivery}</blockquote>\n\n"
        "💰 <b>JAMI: {usd} USD</b>\n💸 <b>So'mda: {sum} so'm</b>{with_dlv}\n📈 Dollar kursi: 1 USD = {rate} so'm",
        "👤 <b>Клиент:</b> {name}\n📞 <b>Телефон:</b> {phone}\n\n<blockquote>"
        "{dims}"
        "🔢 <b>Количество:</b> {count} шт\n🪟 <b>Стекло:</b> {glass}\n"
        "🎨 <b>Цвет профиля:</b> {color}\n🔩 <b>Фурнитура:</b> {fitting} · {fit}\n"
        "✋ <b>Ручка:</b> {handle}\n🚚 <b>Доставка:</b> {delivery}</blockquote>\n\n"
        "💰 <b>ИТОГО: {usd} USD</b>\n💸 <b>В сумах: {sum} сум</b>{with_dlv}\n📈 Курс доллара: 1 USD = {rate} сум",
    ),
    "with_delivery": (" <i>(yetkazish bilan)</i>", " <i>(с доставкой)</i>"),
    # buyurtma kartasidagi har bir fasad qatori: "{n}-fasad: bo'yi {h} × eni {w} mm"
    "dims_line": ("{n}-fasad: bo'yi {h} × eni {w} mm", "{n}-фасад: высота {h} × ширина {w} мм"),
    "dims_title": ("📐 <b>Fasadlar</b> (bo'yi × eni)\n", "📐 <b>Фасады</b> (высота × ширина)\n"),
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
