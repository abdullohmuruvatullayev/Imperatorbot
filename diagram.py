"""O'lcham kiritishda mijozga chizma (PNG) ko'rsatish.

Nima uchun Pillow, SVG emas:
  * Telegram Bot API SVG'ni qabul qilmaydi — faqat JPG/PNG/WEBP.
  * CairoSVG SVG->PNG uchun operatsion tizom darajasidagi libcairo kutadi
    (Railway'da: OSError: no library called "libcairo-2" was found) va
    shriftlarni tizimdan izlaydi — konteynerda shrift bo'lmasa matn
    umuman chizilmaydi.
  * Chizma sodda: to'rtburchak, o'qlar, raqamlar. Pillow buni o'zi bajaradi,
    qo'shimcha tizom kutubisiz.

Shrift: fonts/DejaVuSans.ttf (ochiq kodli, kirill + lotin to'liq).
PIL ning o'z default shriftida KIRILL YO'Q — "ВЫСОТА" bo'sh kvadrat (tofu)
bo'lib chiziladi, shuning uchun shrift fayli majburiy.

Xavfsizlik: diagram() xato bersa None qaytaradi — bot oddiy matn bilan
davom etadi, mijoz oqimi uzilmaydi.
"""

import logging
import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(ROOT, "fonts")

# --- o'lchamlar (piksel) ---
W, H = 1000, 780
BOX_TOP, BOX_BOTTOM = 140, 580   # fasad to'rtburchaki vertikal maydon
BOX_LEFT, BOX_RIGHT = 210, 690   # gorizontal maydon
MAX_MM = 2800                    # prices.MAX_MM bilan bir xil (chizma mustaqil tursin)

# --- ranglar ---
BG = (247, 249, 252)
BOX_FILL = (226, 240, 252)
BOX_LINE = (58, 130, 196)
GREEN = (22, 140, 72)      # kiritilgan / hozir so'ralayotgan
GREY = (152, 160, 172)     # hali kiritilmagan
DARK = (28, 36, 48)
RED = (200, 60, 60)

_fonts = {}


def _font(bold=False, size=40):
    """Shriftni keshlaydi. Topilmasa None — chizish matnsiz davom etadi."""
    key = (bold, size)
    if key not in _fonts:
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        path = os.path.join(FONT_DIR, name)
        try:
            _fonts[key] = ImageFont.truetype(path, size) if os.path.exists(path) else None
        except Exception:
            logging.exception("Shriftni yuklab bo'lmadi: %s", path)
            _fonts[key] = None
    return _fonts[key]


def _lbl(texts, key, default=""):
    return (texts or {}).get(key, default)


def _text(d, xy, s="", *, bold=False, size=40, fill=DARK, anchor=None):
    f = _font(bold, size)
    if f is None:
        return
    try:
        d.text(xy, s, font=f, fill=fill, anchor=anchor)
    except Exception:
        logging.exception("Matn chizib bo'lmadi: %r", s)


def _arrow_h(d, x1, x2, y, color, width=4, head=16):
    """Gorizontal o'q."""
    d.line([(x1, y), (x2, y)], fill=color, width=width)
    d.polygon([(x1, y), (x1 + head, y - head // 2), (x1 + head, y + head // 2)], fill=color)
    d.polygon([(x2, y), (x2 - head, y - head // 2), (x2 - head, y + head // 2)], fill=color)


def _arrow_v(d, x, y1, y2, color, width=4, head=16):
    """Vertikal o'q."""
    d.line([(x, y1), (x, y2)], fill=color, width=width)
    d.polygon([(x, y1), (x - head // 2, y1 + head), (x + head // 2, y1 + head)], fill=color)
    d.polygon([(x, y2), (x - head // 2, y2 - head), (x + head // 2, y2 - head)], fill=color)


def _mm(v):
    """O'lchamni tekshiradi: musbat butun son -> int, aks holda None.

    Noto'g'ri qiymat (matn, 0, manfiy) chizma chizilmasligi kerak —
    aks holda mijoz noto'g'ri o'lchamli rasm ko'radi.
    """
    try:
        v = int(v)
    except (TypeError, ValueError):
        return None
    return v if 1 <= v <= MAX_MM else None


def diagram(n, n_all, height=None, width=None, handle=None, texts=None, ask=None):
    """Fasad chizmasi -> PNG bytes, yoki None (xato bo'lsa).

    n, n_all — fasad raqami va jami soni
    height   — bo'yi (mm) yoki None
    width    — eni (mm) yoki None
    handle   — None | 'chap' | 'ong'  (ruchka tomoni)
    ask      — 'h' (bo'yi so'ralmoqda) | 'w' (eni) | None — yashil bo'ladi
    texts    — tilga bog'liq yozuvlar lug'ati
    """
    try:
        n, n_all = int(n), int(n_all or 0)
        height, width = _mm(height), _mm(width)
        if handle not in (None, "chap", "ong"):
            handle = None
        im = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(im)

        # ---- sarlavha: nechanchi fasad ----
        title = _lbl(texts, "title", f"{n}-FASAD")
        if n_all:
            title += f"   {n}/{n_all}"
        _text(d, (W // 2, 54), title, bold=True, size=52, fill=DARK, anchor="mm")

        # ---- to'rtburchak o'lchami: haqiqiy nisbat, masshtabli ----
        if height and width:
            ratio = width / height
        elif height:
            ratio = 0.62      # bo'yi bor, eni yo'q — taxminiy nisbat
        elif width:
            ratio = 1.6       # eni bor, bo'yi yo'q
        else:
            ratio = 0.62      # ikkalasi ham yo'q

        max_w, max_h = BOX_RIGHT - BOX_LEFT, BOX_BOTTOM - BOX_TOP
        if ratio >= 1:
            bw, bh = max_w, int(max_w / ratio)
            if bh > max_h:
                bh, bw = max_h, int(max_h * ratio)
        else:
            bh, bw = max_h, int(max_h * ratio)
            if bw > max_w:
                bw, bh = max_w, int(max_w / ratio)

        x0 = (W - bw) // 2
        y0 = BOX_TOP + (max_h - bh) // 2
        x1, y1 = x0 + bw, y0 + bh
        d.rectangle([x0, y0, x1, y1], fill=BOX_FILL, outline=BOX_LINE, width=6)

        # ---- ruchka (belgilangan bo'lsa) ----
        if handle in ("chap", "ong"):
            hx = x0 if handle == "chap" else x1
            d.line([(hx, y0), (hx, y1)], fill=RED, width=14)
            _text(d, (hx, y0 - 26), _lbl(texts, "handle", "ruchka"), bold=True, size=30,
                  fill=RED, anchor="ms")

        # ---- BO'YI o'qi (chapda, vertikal) ----
        h_on = bool(height)
        h_color = GREEN if h_on else GREY
        _arrow_v(d, x0 - 64, y0, y1, h_color)
        h_lbl = f"{height} {_lbl(texts, 'mm', 'mm')}" if h_on else _lbl(texts, "no_height", "bo'yi")
        _text(d, (x0 - 88, (y0 + y1) // 2), h_lbl, bold=h_on, size=38, fill=h_color, anchor="rm")
        _text(d, (x0 - 88, (y0 + y1) // 2 + 34), _lbl(texts, "t_height", "BO'YI"), size=25,
              fill=h_color, anchor="rm")

        # ---- ENI o'qi (pastda, gorizontal) ----
        w_on = bool(width)
        w_color = GREEN if w_on else GREY
        _arrow_h(d, x0, x1, y1 + 64, w_color)
        w_lbl = f"{width} {_lbl(texts, 'mm', 'mm')}" if w_on else _lbl(texts, "no_width", "eni")
        _text(d, ((x0 + x1) // 2, y1 + 88), w_lbl, bold=w_on, size=38, fill=w_color, anchor="ma")
        _text(d, ((x0 + x1) // 2, y1 + 126), _lbl(texts, "t_width", "ENI"), size=25,
              fill=w_color, anchor="ma")

        # ---- PNG bytes ----
        buf = BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        logging.exception("Chizma yasab bo'lmadi (n=%s)", n)
        return None


if __name__ == "__main__":
    import sys

    T = {"title": "{n}-FASAD", "mm": "mm", "t_height": "BO'YI", "t_width": "ENI",
         "no_height": "bo'yi ?", "no_width": "eni ?", "handle": "ruchka"}
    # 1) oddiy holatlar PNG beradi
    assert diagram(1, 4, texts=T, ask="h")
    assert diagram(1, 4, height=1800, texts=T, ask="w")
    assert diagram(1, 4, height=1800, width=900, texts=T)
    assert diagram(2, 4, height=2000, width=1000, handle="ong", texts=T)
    # 2) shrift bor va kirill chiziladi (uz va ru rasmlar har xil bo'lishi kerak)
    assert _font(bold=True, size=40) is not None, "fonts/DejaVuSans-Bold.ttf topilmadi"
    ru = {"title": "{n}-ФАСАД", "mm": "мм", "t_height": "ВЫСОТА", "t_width": "ШИРИНА",
          "no_height": "высота ?", "no_width": "ширина ?", "handle": "ручка"}
    assert diagram(1, 4, height=1800, width=900, texts=ru) != diagram(1, 4, height=1800, width=900, texts=T), \
        "kirill chizilmadi — shrift muammosi"
    # 3) noto'g'ri o'lcham e'tiborsiz qolinadi (chizma chizilmaydi)
    assert diagram(1, 4, height="abc", texts=T) == diagram(1, 4, texts=T)
    assert diagram(1, 4, height=0, texts=T) == diagram(1, 4, texts=T)
    assert diagram(1, 4, height=99999, texts=T) == diagram(1, 4, texts=T)
    assert diagram(1, 4, height=1800, width=900, handle="XXX", texts=T) == \
        diagram(1, 4, height=1800, width=900, texts=T)
    # 4) juda ko'p fasad ham ishlaydi
    assert diagram(100, 100, height=1800, width=900, texts=T)
    # 5) PNG haqiqatan to'g'ri formatda
    png = diagram(1, 4, height=1800, width=900, texts=T)
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "PNG emas"
    print("ok")
