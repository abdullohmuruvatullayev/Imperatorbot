"""Nomlar, boshlang'ich narxlar va hisoblash.
Narxlar bazada saqlanadi (admin /narx bilan o'zgartiradi). Bu yerdagi qiymatlar faqat bazada yo'q kalitlar uchun yoziladi."""

MAX_MM = 2800

GLASS = {
    "peppil": "Peppil",
    "yodiviy": "Yodiviy",
    "prazrachniy": "Prazrachniy",
    "tosh": "Tosh oyna",
    "tosh_tillali": "Tosh oyna tillali",
    "tosh_peppili": "Tosh oyna peppili",
    "ref_prazrachniy": "Reflonniy prazrachniy",
    "ref_yodiviy": "Reflonniy yodiviy",
    "ref_peppil": "Reflonniy peppil",
    "ref_matoviy": "Reflonniy matoviy",
    "lakabel": "Lakabel",
}

COLORS = {
    "qora": "Qora",
    "tilla_mat": "Tilla matoviy",
    "tilla_glyans": "Tilla glyansoviy",
    "shanpan": "Shanpan kulrang",
}

FITTINGS = {
    "blum": "Blum",
    "hettich": "Hettich",
    "xitoy": "Xitoy",
    "xitoy_dts": "Xitoy DTS",
}

GLASS_PRICES = (20, 20, 20, 22, 22, 22, 45, 45, 45, 50, 20)  # GLASS tartibida
FITTING_PRICES = (5.5, 5.5, 3, 3)                           # FITTINGS tartibida

# kalit -> (izoh, qiymat). Oyna narxi None bo'lsa variant mijozga ko'rsatilmaydi.
DEFAULTS = {
    **{f"glass.{k}": (f"Oyna: {n}, USD/m²", v) for (k, n), v in zip(GLASS.items(), GLASS_PRICES)},
    **{f"fit.{k}": (f"Furnitura: {n}, USD/dona", v) for (k, n), v in zip(FITTINGS.items(), FITTING_PRICES)},
    "profile": ("Profil, USD/metr", 6),
    "handle_profile": ("Ruchkali tomon profili, USD/metr", 8.5),
    "assembly_low": ("Yig'ish, balandlik <= 1000 mm, USD/fasad", 6),
    "assembly_high": ("Yig'ish, balandlik > 1000 mm, USD/fasad", 8),
    "corner": ("Ugolnik, USD/dona (4 dona/fasad)", 1.5),
    "rubber": ("Rezinka, USD/metr", 0.8),
    "delivery": ("Yetkazib berish, so'm", 100_000),
    "fallback_rate": ("Zaxira kurs (CBU ishlamasa), so'm", 11_800),
}


def calc_usd(p, width_mm, height_mm, count, glass, fitting, fittings_per_facade, handle):
    """p: narxlar {kalit: qiymat}. handle: None (ruchkasiz), 'chap' yoki 'ong'. Bitta fasad x count."""
    w, h = width_mm / 1000, height_mm / 1000
    perimeter = 2 * (w + h)
    if handle:
        profile = h * p["handle_profile"] + (perimeter - h) * p["profile"]
    else:
        profile = perimeter * p["profile"]
    per_facade = (
        profile
        + w * h * p[f"glass.{glass}"]
        + fittings_per_facade * p[f"fit.{fitting}"]
        + (p["assembly_low"] if height_mm <= 1000 else p["assembly_high"])
        + 4 * p["corner"]
        + perimeter * p["rubber"]
    )
    return round(per_facade * count, 2)


def calc_sum(p, usd, rate, delivery):
    return round(usd * rate) + (round(p["delivery"]) if delivery else 0)


if __name__ == "__main__":
    p = {k: v for k, (_, v) in DEFAULTS.items()}
    assert len(GLASS) == len(GLASS_PRICES) and len(FITTINGS) == len(FITTING_PRICES)
    # 1000x1000, ruchkasiz: profil 24 + oyna 20 + furn 2*5.5=11 + yig'ish 6 + ugolnik 6 + rezinka 3.2 = 70.2
    assert calc_usd(p, 1000, 1000, 1, "peppil", "blum", 2, None) == 70.2
    # ruchkali: profil 1*8.5 + 3*6 = 26.5 -> 72.7; x2 fasad
    assert calc_usd(p, 1000, 1000, 2, "peppil", "blum", 2, "chap") == 145.4
    # 1001 mm -> yig'ish 8
    assert calc_usd(p, 500, 1001, 1, "lakabel", "xitoy", 0, None) - calc_usd(p, 500, 1000, 1, "lakabel", "xitoy", 0, None) > 2
    assert calc_sum(p, 70.2, 12700, True) == 991_540
    print("ok")
