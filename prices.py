"""Boshlang'ich katalog, sozlamalar va hisoblash formulasi.
Mahsulotlar (oyna, rang, furnitura) va sozlamalar bazada saqlanadi, admin paneldan boshqariladi.
Bu yerdagi ro'yxat faqat baza bo'sh bo'lganda (birinchi ishga tushishda) yoziladi."""

MAX_MM = 2800

# kind -> [(key, nomi, narx)]. Oyna: USD/m², furnitura: USD/dona, rang: narxsiz.
SEED = {
    "glass": [
        ("peppil", "Peppil", 20), ("yodiviy", "Yodiviy", 20), ("prazrachniy", "Prazrachniy", 20),
        ("tosh", "Tosh oyna", 22), ("tosh_tillali", "Tosh oyna tillali", 22), ("tosh_peppili", "Tosh oyna peppili", 22),
        ("ref_prazrachniy", "Reflonniy prazrachniy", 45), ("ref_yodiviy", "Reflonniy yodiviy", 45),
        ("ref_peppil", "Reflonniy peppil", 45), ("ref_matoviy", "Reflonniy matoviy", 50), ("lakabel", "Lakabel", 20),
    ],
    "color": [
        ("qora", "Qora", None), ("tilla_mat", "Tilla matoviy", None),
        ("tilla_glyans", "Tilla glyansoviy", None), ("shanpan", "Shanpan kulrang", None),
    ],
    "fitting": [("blum", "Blum", 5.5), ("hettich", "Hettich", 5.5), ("xitoy", "Xitoy", 3), ("xitoy_dts", "Xitoy DTS", 3)],
}

# Umumiy narx sozlamalari: kalit -> (izoh, qiymat)
SETTINGS = {
    "profile": ("Profil, USD/metr", 6),
    "handle_profile": ("Ruchkali tomon profili, USD/metr", 8.5),
    "assembly_low": ("Yig'ish, balandlik ≤ 1000 mm, USD/fasad", 6),
    "assembly_high": ("Yig'ish, balandlik > 1000 mm, USD/fasad", 8),
    "corner": ("Ugolnik, USD/dona (4 dona/fasad)", 1.5),
    "rubber": ("Rezinka, USD/metr", 0.8),
    "delivery": ("Yetkazib berish, so'm", 100_000),
    "fallback_rate": ("Zaxira kurs (CBU ishlamasa), so'm", 11_800),
}


def calc_usd(p, width_mm, height_mm, count, glass_price, fitting_price, fittings_per_facade, handle):
    """p: sozlamalar {kalit: qiymat}. handle: None (ruchkasiz), 'chap' yoki 'ong'. Bitta fasad x count."""
    w, h = width_mm / 1000, height_mm / 1000
    perimeter = 2 * (w + h)
    if handle:
        profile = h * p["handle_profile"] + (perimeter - h) * p["profile"]
    else:
        profile = perimeter * p["profile"]
    per_facade = (
        profile
        + w * h * glass_price
        + fittings_per_facade * fitting_price
        + (p["assembly_low"] if height_mm <= 1000 else p["assembly_high"])
        + 4 * p["corner"]
        + perimeter * p["rubber"]
    )
    return round(per_facade * count, 2)


def calc_sum(p, usd, rate, delivery):
    return round(usd * rate) + (round(p["delivery"]) if delivery else 0)


if __name__ == "__main__":
    p = {k: v for k, (_, v) in SETTINGS.items()}
    # 1000x1000, ruchkasiz: profil 24 + oyna 20 + furn 2*5.5=11 + yig'ish 6 + ugolnik 6 + rezinka 3.2 = 70.2
    assert calc_usd(p, 1000, 1000, 1, 20, 5.5, 2, None) == 70.2
    # ruchkali: profil 1*8.5 + 3*6 = 26.5 -> 72.7; x2 fasad
    assert calc_usd(p, 1000, 1000, 2, 20, 5.5, 2, "chap") == 145.4
    # 1001 mm -> yig'ish 8
    assert calc_usd(p, 500, 1001, 1, 20, 3, 0, None) - calc_usd(p, 500, 1000, 1, 20, 3, 0, None) > 2
    assert calc_sum(p, 70.2, 12700, True) == 991_540
    print("ok")
