"""Sprinkler kapsama alanı geometrisi testleri (el hesabı ile)."""
import pytest

from tesisat import kapsama as k
from tesisat import rapor, yangin as y
from tesisat.ortak import BILGI, HATA, UYARI, kurallari_yukle

K = kurallari_yukle()
KARE = [(0, 0), (20.4, 0), (20.4, 20.4), (0, 20.4)]


def izgara(n=6, s=3.4, w=1.7, atla=()):
    return {f"S{i}-{j}": (w + s * (j - 1), w + s * (i - 1))
            for i in range(1, n + 1) for j in range(1, n + 1) if f"S{i}-{j}" not in atla}


def analiz(poligon, spr, smax=4.0, dmax=2.0):
    return k.mahal_analizi(poligon, spr, smax, dmax, 2.0, 12.0)


def turler(a):
    return {t for t, _, _ in a["ihlaller"]}


def test_kare_izgara_alanlari():
    a = analiz(KARE, izgara())
    assert all(v == pytest.approx(3.4 * 3.4) for v in a["alanlar"].values())
    assert a["hucre_toplami"] == pytest.approx(20.4 * 20.4)
    assert a["ihlaller"] == []
    assert a["r_max"] == pytest.approx((2 ** 2 + 2 ** 2) ** 0.5)   # OT: √(2²+2²)


def test_L_mahal_el_hesabi():
    L = [(0, 0), (12, 0), (12, 6), (6, 6), (6, 12), (0, 12)]
    a = analiz(L, {"A": (2, 2), "B": (6, 2), "C": (10, 2), "D": (2, 6), "E": (2, 10)})
    # A: x≤4, y≤4 → 16 m²; toplam = L alanı 108 m²
    assert a["alanlar"]["A"] == pytest.approx(16.0)
    assert a["hucre_toplami"] == pytest.approx(108.0)


def test_eksik_sprinkler_korunmayan_bolge():
    a = analiz(KARE, izgara(atla={"S3-3"}))
    assert "korunmayan" in turler(a)
    assert "alan" in turler(a)


def test_duvar_mesafesi():
    genis = [(0, 0), (21.4, 0), (21.4, 20.4), (0, 20.4)]   # bir duvar 1 m uzakta → 2,7 m
    a = analiz(genis, izgara())
    assert "duvar" in turler(a)
    assert any("2.70 m > 2 m" in m for t, _, m in a["ihlaller"] if t == "duvar")


def test_min_aralik_2m():
    spr = {"A": (5, 5), "B": (6.5, 5), "C": (15, 5), "D": (5, 15), "E": (15, 15)}
    assert "yakin" in turler(analiz(KARE, spr))


def test_mahal_disi_sprinkler():
    a = analiz(KARE, {**izgara(), "X": (25, 5)})
    assert "disarida" in turler(a)


def test_svg_uretimi():
    a = analiz(KARE, izgara())
    svg = k.svg_plan("Deneme <plan>", KARE, a, 12, {"S1-1"}, [("YD-1", (0.3, 3))])
    assert svg.startswith("<svg") and svg.count("<polygon") >= 36 and "&lt;plan&gt;" in svg


# --- yangın modülü ile bütünleşik ---------------------------------------------
def proje(spr_ek=None, mahal_ek=None, acik=None, atla=()):
    hatlar = [{"id": "R", "ust": None, "uzunluk_m": 5, "cap": "65"}]
    for sid, (x, yy) in izgara(atla=atla).items():
        hatlar.append({"id": sid, "ust": "R", "uzunluk_m": 3, "cap": "32", "sprinkler": dict(spr_ek or {}),
                       "mahal": "M", "konum": [x, yy]})
    mahal = {"id": "M", "ad": "Deneme", "poligon": [list(p) for p in KARE], **(mahal_ek or {})}
    acik = acik or [f"S{i}-{j}" for i in (4, 5, 6) for j in (2, 3, 4, 5, 6)][:13]
    return {"yangin": {"tehlike_sinifi": "OT2", "sprinkler_varsayilan": {"K": 80}, "mahaller": [mahal],
                       "hatlar": hatlar, "senaryolar": [{"ad": "A", "acik": acik}],
                       "pompa": {"adet_yedek": 1}, "yedek_sprinkler": 6}}


def bul(s, seviye):
    return [b for b in s.bulgular if b.seviye == seviye]


def test_plan_alani_hidrolige_girer():
    a = y.YanginAgi(proje()["yangin"], K)
    h = a.hatlar["S1-1"]
    assert h.alan == pytest.approx(11.56) and h.alan_kaynak == "plan"
    assert h.qmin == pytest.approx(5.0 * 11.56)


def test_girilen_alan_planla_celisirse_uyari():
    s = y.hesapla(proje(spr_ek={"alan_m2": 9.0}), K)
    assert any("plandan hesaplanan" in b.mesaj for b in bul(s, UYARI))


def test_eksik_sprinkler_hesapta_hata():
    s = y.hesapla(proje(atla={"S2-2"}), K)
    msj = " ".join(b.mesaj for b in bul(s, HATA))
    assert "korunmayan bölge" in msj and "Sprinkler kapsama alanı" in msj


def test_tasarim_alani_bicimi_uyarisi():
    kare_blok = [f"S{i}-{j}" for i in (3, 4, 5, 6) for j in (3, 4, 5, 6)][:13]   # 13,6 m < 14,4 m
    s = y.hesapla(proje(acik=kare_blok), K)
    assert any("1,2·√A" in b.mesaj for b in bul(s, UYARI))
    s = y.hesapla(proje(), K)   # 5 sprinkler boyunca 17 m
    assert not any("1,2·√A" in b.mesaj for b in s.bulgular)


def test_sprinklersiz_mahal_ve_muafiyet():
    p = proje()
    p["yangin"]["mahaller"].append({"id": "WC", "poligon": [[30, 0], [33, 0], [33, 3], [30, 3]]})
    assert any(b.nesne == "WC" for b in bul(y.hesapla(p, K), HATA))
    p["yangin"]["mahaller"][-1].update({"muaf": True, "muaf_nedeni": "ıslak hacim, yanıcı yük yok"})
    s = y.hesapla(p, K)
    assert not any(b.nesne == "WC" for b in bul(s, HATA))
    assert any(b.nesne == "WC" for b in bul(s, BILGI))


def test_rapora_plan_eklenir():
    p = proje()
    s = y.hesapla(p, K)
    assert len(s.sekiller) == 1
    html = rapor.html_rapor(p, [s])
    assert "<svg" in html and "Kapsama planı" in html
