"""Yangın modülü testleri — el hesabı, yayımlanmış örnekler ve yönetmelik maddeleri."""
import math
from pathlib import Path

import pytest

from tesisat import yangin as y
from tesisat.cli import calistir, proje_yukle
from tesisat.ortak import HATA, GirdiHatasi, kurallari_yukle

K = kurallari_yukle()
ORNEK = Path(__file__).resolve().parents[1] / "ornekler" / "ornek_otopark.yaml"


def ag(hatlar, **ek):
    g = {"tehlike_sinifi": "OT2", "sprinkler_varsayilan": {"K": 80, "alan_m2": 12}, "hatlar": hatlar}
    g.update(ek)
    return y.YanginAgi(g, K)


def proje(hatlar, senaryolar, bina=None, **ek):
    g = {"tehlike_sinifi": "OT2", "sprinkler_varsayilan": {"K": 80, "alan_m2": 12},
         "hatlar": hatlar, "senaryolar": senaryolar,
         "pompa": {"adet_asil": 1, "adet_yedek": 1}, "yedek_sprinkler": 6}
    g.update(ek)
    return {"bina": bina or {}, "yangin": g}


def bulgular(s, seviye=HATA):
    return [b for b in s.bulgular if b.seviye == seviye]


# --- Hazen-Williams ----------------------------------------------------------
def test_hazen_williams_el_hesabi():
    # p = 6,05e5 · Q^1,85 / (C^1,85 · d^4,87)
    q, d, c = 500.0, 53.1, 120.0
    beklenen = 6.05e5 * q ** 1.85 / (c ** 1.85 * d ** 4.87)
    assert y.hw_bar_m(q, d, c) == pytest.approx(beklenen)
    # Bağımsız fiziksel kontrol: C=120 "kullanılmış çelik" kabulüdür; Darcy-Colebrook
    # ile yeni çelik (k=0,045 mm) daha az, çok eskimiş çelik (k=0,5 mm) daha çok kayıp vermeli.
    from tesisat.hidrolik import boru_akisi
    yeni = boru_akisi(q / 60000, d / 1000, 0.045e-3, 999.7, 1.307e-6)["R"] / 1e5
    eski = boru_akisi(q / 60000, d / 1000, 0.5e-3, 999.7, 1.307e-6)["R"] / 1e5
    assert yeni < y.hw_bar_m(q, d, c) < eski


def test_hiz():
    # 1000 l/dk, DN100 (105,3 mm) → 1,91 m/s
    assert y.hiz_ms(1000, 105.3) == pytest.approx(1.914, rel=1e-3)


# --- Yayımlanmış örnek: OT2 otopark (İtalyan Müh. Odası ders notu) -------------
def test_ot2_sprinkler_min_basinc_ornegi():
    # 144 m² × 5 mm/dk = 720 l/dk; 12 m²/sprinkler → 12 sprinkler, 60 l/dk;
    # P = (60/80)² = 0,5625 bar
    a = ag([{"id": "S", "ust": None, "uzunluk_m": 0.0, "cap": "25", "sprinkler": True}])
    h = a.hatlar["S"]
    assert h.qmin == pytest.approx(60.0)
    assert h.preq == pytest.approx(0.5625)
    assert a.tasarim_alani == 144 and a.tasarim_alani / 12 == 12


def test_tek_sprinkler_kaynak_basinci_el_hesabi():
    a = ag([{"id": "S", "ust": None, "uzunluk_m": 3.0, "kot_farki_m": 2.0, "cap": "25",
             "parcalar": {"dirsek_90": 1}, "sprinkler": True}])
    cz = a.gerekli_kaynak_basinci(["S"])
    leq = 0.61  # DN25 dirsek
    el = 0.5625 + y.hw_bar_m(60, 27.3, 120) * (3.0 + leq) + 0.0981 * 2.0
    assert cz["ps"] == pytest.approx(el, abs=2e-4)
    assert cz["q_cikis"]["S"] == pytest.approx(60.0, abs=0.01)


def test_dallanmis_ag_dengesi_ve_kutle_korunumu():
    hatlar = [
        {"id": "R", "ust": None, "uzunluk_m": 10, "cap": "50"},
        {"id": "B1", "ust": "R", "uzunluk_m": 4, "cap": "32"},
        {"id": "S1", "ust": "B1", "uzunluk_m": 0.5, "cap": "25", "sprinkler": True},
        {"id": "B2", "ust": "R", "uzunluk_m": 4, "cap": "32"},
        {"id": "S2", "ust": "B2", "uzunluk_m": 0.5, "cap": "25", "sprinkler": True},
        {"id": "B3", "ust": "R", "uzunluk_m": 12, "cap": "25", "kot_farki_m": 2},
        {"id": "S3", "ust": "B3", "uzunluk_m": 0.5, "cap": "25", "sprinkler": True},
    ]
    a = ag(hatlar)
    cz = a.gerekli_kaynak_basinci(["S1", "S2", "S3"])
    q = cz["q_cikis"]
    # kütle dengesi
    assert cz["akis"]["R"] == pytest.approx(q["S1"] + q["S2"] + q["S3"], rel=1e-9)
    # simetrik kollar eşit
    assert q["S1"] == pytest.approx(q["S2"], rel=1e-6)
    # her çıkış Q = K√P (kesin çözüm) ve gereksinimi sağlar; kritik olan tam sınırda
    for i in q:
        assert q[i] == pytest.approx(80 * math.sqrt(cz["p_son"][i]), rel=1e-5)
        assert cz["p_son"][i] >= a.hatlar[i].preq - 1e-4
    assert min(cz["p_son"][i] / a.hatlar[i].preq for i in q) == pytest.approx(1.0, abs=1e-4)
    # enerji: kaynak − hat kayıpları − statik = uç basınç
    s3 = cz["ps"] - y.hw_bar_m(cz["akis"]["R"], 53.1, 120) * 10 \
        - y.hw_bar_m(q["S3"], 27.3, 120) * 12.5 - 0.0981 * 2
    assert s3 == pytest.approx(cz["p_son"]["S3"], abs=1e-6)


def test_esdeger_boy_C_duzeltmesi():
    a = ag([{"id": "S", "ust": None, "uzunluk_m": 1, "cap": "50", "parcalar": {"te_donus": 2},
             "sprinkler": True}], C=100)
    assert a.hatlar["S"].leq == pytest.approx(2 * 3.05 * (100 / 120) ** 1.85)
    assert (100 / 120) ** 1.85 == pytest.approx(0.714, abs=1e-3)


# --- Yönetmelik kontrolleri -----------------------------------------------------
TEK = [{"id": "R", "ust": None, "uzunluk_m": 5, "cap": "50"},
       {"id": "S1", "ust": "R", "uzunluk_m": 0.3, "cap": "25", "sprinkler": True}]


def test_kapsama_alani_asimi_hata():
    p = proje([TEK[0], {**TEK[1], "sprinkler": {"K": 80, "alan_m2": 14}}],
              [{"ad": "x", "acik": ["S1"]}])
    s = y.hesapla(p, K)
    assert any(b.mesaj.startswith("Sprinkler kapsama alanı 14") for b in bulgular(s))


def test_ot1_icin_21m2_byky_96_5():
    p = proje([TEK[0], {**TEK[1], "sprinkler": {"K": 80, "alan_m2": 20}}],
              [{"ad": "x", "acik": ["S1"]}], tehlike_sinifi="OT1")
    s = y.hesapla(p, K)
    assert not any(b.mesaj.startswith("Sprinkler kapsama alanı") for b in bulgular(s))


def test_tasarim_alani_eksik_hata():
    s = y.hesapla(proje(TEK, [{"ad": "x", "acik": ["S1"]}]), K)
    assert any("tasarım alanı" in b.mesaj for b in bulgular(s))


def test_kuru_sistem_alan_artisi_ve_yasak():
    a = ag(TEK, sistem="kuru")
    assert a.tasarim_alani == 180  # OT2 kuru
    with pytest.raises(GirdiHatasi):
        y.YanginAgi({"tehlike_sinifi": "DT", "sistem": "kuru", "hatlar": TEK,
                     "sprinkler_varsayilan": {"K": 57, "alan_m2": 21}}, K)


def test_pompa_karakteristigi_byky_93():
    p = proje(TEK, [{"ad": "x", "acik": ["S1"]}],
              pompa={"adet_asil": 1, "adet_yedek": 0, "anma_debi_lpm": 100, "anma_basinc_bar": 5,
                     "kapali_vana_basinc_bar": 7.5, "debi_150_basinc_bar": 3.0})
    msj = " | ".join(b.mesaj for b in bulgular(y.hesapla(p, K)))
    assert "Kapalı vana basıncı 7.5" in msj      # > %140
    assert "%150 debideki basınç 3.0" in msj     # < %65
    assert "Yedek pompa" in msj                  # md. 93/2


def test_sprinkler_zorunlulugu_byky_96_2():
    dolap = [{"id": "H", "ust": None, "uzunluk_m": 5, "cap": "50"},
             {"id": "YD", "ust": "H", "uzunluk_m": 1, "cap": "25", "cikis": "dolap_yari_sert"}]
    p = proje(dolap, [{"ad": "d", "acik": ["YD"]}],
              bina={"kullanim": "ofis", "yapi_yuksekligi_m": 31.0})
    assert any("Sprinkler zorunlu" in b.mesaj for b in bulgular(y.hesapla(p, K)))
    p["bina"] = {"kullanim": "konut", "yapi_yuksekligi_m": 31.0}
    assert not any("Sprinkler zorunlu" in b.mesaj for b in bulgular(y.hesapla(p, K)))


def test_dolap_100_lpm_4_bar_ve_9_bar_siniri():
    dolap = [{"id": "H", "ust": None, "uzunluk_m": 5, "cap": "50"},
             {"id": "YD", "ust": "H", "uzunluk_m": 1, "cap": "25", "cikis": "dolap_yari_sert"}]
    a = y.YanginAgi({"tehlike_sinifi": "OT1", "hatlar": dolap}, K)
    cz = a.gerekli_kaynak_basinci(["YD"])
    assert cz["p_son"]["YD"] == pytest.approx(4.0, abs=1e-3)
    assert cz["q_cikis"]["YD"] == pytest.approx(100.0, abs=0.05)


def test_dolap_araligi_byky_94():
    hatlar = [{"id": "H", "ust": None, "uzunluk_m": 5, "cap": "50"},
              {"id": "Y1", "ust": "H", "uzunluk_m": 1, "cap": "25", "cikis": "dolap_yari_sert",
               "kat": "0", "konum": [0, 0]},
              {"id": "Y2", "ust": "H", "uzunluk_m": 1, "cap": "25", "cikis": "dolap_yari_sert",
               "kat": "0", "konum": [35, 0]}]
    s = y.hesapla(proje(hatlar, [{"ad": "d", "acik": ["Y1"]}]), K)
    assert any("> 30 m" in b.mesaj for b in bulgular(s))


def test_hiz_siniri():
    hatlar = [{"id": "R", "ust": None, "uzunluk_m": 1, "cap": "25", "vana_noktasi": True},
              {"id": "H", "ust": "R", "uzunluk_m": 1, "cap": "50"},
              {"id": "Y", "ust": "H", "uzunluk_m": 1, "cap": "50", "cikis": "hidrant"}]
    s = y.hesapla(proje(hatlar, [{"ad": "h", "acik": ["Y"]}]), K)
    msj = " | ".join(b.mesaj for b in bulgular(s))
    assert "6 m/s" in msj          # vana noktası hızı
    assert "DN25 < DN100" in msj   # hidrant hattı min çap (md. 95/5)


def test_min_cap_tablo_36():
    hatlar = [{"id": "R", "ust": None, "uzunluk_m": 1, "cap": "20"},
              {"id": "S", "ust": "R", "uzunluk_m": 0.3, "cap": "20", "sprinkler": True}]
    s = y.hesapla(proje(hatlar, [{"ad": "x", "acik": ["S"]}]), K)
    hatali = {b.nesne for b in bulgular(s) if "minimum" in b.mesaj}
    assert hatali == {"R"}   # tek sprinkler besleyen K80 hattı DN20 olabilir, diğerleri DN25


def test_depo_hacmi_byky_92():
    s = y.hesapla(proje_yukle(ORNEK), K)
    satir = {r[0]: r[1] for t in s.tablolar if t.baslik == "Pompa ve depo" for r in t.satirlar}
    oz = next(t for t in s.tablolar if t.baslik == "Senaryo özeti")
    q_spr = oz.satirlar[0][oz.kolonlar.index("Q toplam l/dk")]  # Senaryo A debisi
    assert satir["Hidrolik hesaba göre depo hacmi"].startswith(f"{(q_spr + 100) * 60 / 1000:.1f}")


def test_ornek_proje_temiz():
    sonuclar, _ = calistir(proje_yukle(ORNEK))
    assert sum(len(bulgular(s)) for s in sonuclar) == 0
    oz = sonuclar[0].ozet
    assert 4.0 < oz["Pompa çıkışında gerekli basınç [bar]"] < 6.0
