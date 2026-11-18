"""Metraj motoru ve Excel çıktısı testleri (METRAJ_KURALLARI.md'deki kurallar)."""
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
from openpyxl import load_workbook

from tesisat import metraj, metraj_excel
from tesisat.cli import main, proje_yukle
from tesisat.ortak import kurallari_yukle

K = kurallari_yukle()
ORNEK = Path(__file__).resolve().parents[1] / "ornekler" / "dis_hastanesi.yaml"
RECALC = next(Path("/root/.claude/skills").rglob("xlsx/scripts/recalc.py"), None) if Path("/root/.claude/skills").exists() else None


def proje(hatlar, **ek):
    return {"yangin": {"tehlike_sinifi": "OT1", "sprinkler_varsayilan": {"K": 80, "alan_m2": 9},
                       "hatlar": hatlar, **ek}}


def say(m, alan="kod"):
    c = Counter()
    for s in m.satirlar:
        c[getattr(s, alan)] += s.miktar
    return c


def spr(i, ust, **ek):
    return {"id": i, "ust": ust, "uzunluk_m": 0.2, "cap": "25", "sprinkler": True, **ek}


def test_U1_zinciri_el_hesabi():
    # P(DN40) → [S1(25), B2(32)] ; B2 → [S2, B3(25)] ; B3(25) → [S3, B4(25)] ; B4 → [S4 (te beyanlı)]
    h = [{"id": "P", "ust": None, "uzunluk_m": 3, "cap": "40"},
         spr("S1", "P", parcalar={"te_donus": 1}), {"id": "B2", "ust": "P", "uzunluk_m": 3, "cap": "32"},
         spr("S2", "B2", parcalar={"te_donus": 1}), {"id": "B3", "ust": "B2", "uzunluk_m": 3, "cap": "25"},
         spr("S3", "B3", parcalar={"te_donus": 1}), {"id": "B4", "ust": "B3", "uzunluk_m": 3, "cap": "25"},
         spr("S4", "B4", parcalar={"te_donus": 1})]
    m = metraj.metraj_cikar(proje(h), K)
    c = say(m)
    assert c["FIT-TE-40x25"] == 1 and c["FIT-RED-40x32"] == 1            # T1 + T2
    assert c["FIT-TE-32x25"] == 1 and c["FIT-RED-32x25"] == 1
    assert c["FIT-TE-25x25"] == 1
    assert sum(v for k, v in c.items() if k.startswith("FIT-TE")) == 3    # uç sprinklerde te yok
    acik = " | ".join(b.aciklama for b in m.belirsizlikler)
    assert "'S4' için te beyan edilmiş" in acik                            # R2: kesinleştirilmedi
    assert "hangi kolun geçiş olduğu" in acik                              # T3 (B2 düğümü)
    assert c["SPR-K80"] == 4
    assert c["BORU-CELIK_EN10255_ORTA-DN25"] == pytest.approx(3 + 3 + 4 * 0.2)


def test_coklu_dugum_kontrol_gerekli_ve_kor_uc():
    h = [{"id": "P", "ust": None, "uzunluk_m": 2, "cap": "80"}] + \
        [{"id": f"C{i}", "ust": "P", "uzunluk_m": 2, "cap": "50"} for i in range(3)] + \
        [spr(f"S{i}", f"C{i}") for i in range(2)]                           # C2 kör uç
    m = metraj.metraj_cikar(proje(h), K)
    coklu = [s for s in m.satirlar if s.kod.startswith("FIT-COKLU")]
    assert len(coklu) == 1 and coklu[0].yontem == metraj.KONTROL
    assert any("Kör uç" in b.aciklama and b.nesne.startswith("C2") for b in m.belirsizlikler)
    assert any(b.nesne == "C2" and "çıkış" in b.aciklama for b in m.belirsizlikler)


def test_cap_buyumesi_belirsizlik():
    h = [{"id": "P", "ust": None, "uzunluk_m": 2, "cap": "40"}, {"id": "C", "ust": "P", "uzunluk_m": 2, "cap": "50"},
         spr("S", "C")]
    m = metraj.metraj_cikar(proje(h), K)
    assert say(m)["FIT-RED-40x50"] == 1
    assert any("çap büyüyor" in b.aciklama for b in m.belirsizlikler)


def test_vana_dirsek_elle_girilen_te_beyani_sayilmaz():
    h = [{"id": "P", "ust": None, "uzunluk_m": 2, "cap": "100",
          "parcalar": {"kelebek_vana": 2, "dirsek_90": 3, "te_donus": 1}}, spr("S", "P")]
    m = metraj.metraj_cikar(proje(h), K)
    c = say(m)
    assert c["VANA-KELEBEK_VANA-DN100"] == 2 and c["FIT-DIRSEK90-DN100"] == 3
    assert not any(k.startswith("FIT-TE") for k in c)
    assert all(s.yontem == metraj.ELLE for s in m.satirlar if s.kod.startswith(("VANA", "FIT-DIRSEK")))


def test_yontem_alanlari_ve_gecersiz_yontem():
    h = [{"id": "P", "ust": None, "uzunluk_m": 2, "cap": "50", "uzunluk_yontemi": "ölçülen"},
         spr("S", "P", konum_yontemi="ölçülen")]
    m = metraj.metraj_cikar(proje(h), K)
    yon = {(s.kod, s.kaynak): s.yontem for s in m.satirlar}
    assert yon[("BORU-CELIK_EN10255_ORTA-DN50", "P")] == "ölçülen"       # uzunluk_yontemi
    assert yon[("SPR-K80", "S")] == "ölçülen"                            # konum_yontemi
    assert yon[("BORU-CELIK_EN10255_ORTA-DN25", "S")] == "elle girilen"  # alan yoksa varsayılan
    assert yon[("FIT-RED-50x25", "P bitiş düğümü")] == "hesaplanan"      # topoloji kuralı R1
    h[0]["uzunluk_yontemi"] = "tahmini"
    with pytest.raises(Exception, match="geçersiz yöntem"):
        metraj.metraj_cikar(proje(h), K)


def test_aski_yalniz_kural_varsa():
    h = [{"id": "P", "ust": None, "uzunluk_m": 10, "kot_farki_m": 2, "cap": "50"}, spr("S", "P")]
    m = metraj.metraj_cikar(proje(h), K)
    assert not any(s.kod.startswith("ASKI") for s in m.satirlar)
    assert any(b.kategori == "Askı" for b in m.belirsizlikler)
    k2 = kurallari_yukle(None, {"metraj": {"aski_araligi_m": {50: 3.0}}})
    m = metraj.metraj_cikar(proje(h), k2)
    aski = [s for s in m.satirlar if s.kod == "ASKI-DN50"][0]
    assert aski.miktar == 3 and aski.yontem == metraj.HESAPLANAN   # ⌈(10−2)/3⌉ = 3 (yalnız yatay)


def test_sistem_siniflamasi():
    h = [{"id": "P", "ust": None, "uzunluk_m": 2, "cap": "80"},
         {"id": "A", "ust": "P", "uzunluk_m": 2, "cap": "50"}, spr("S", "A"),
         {"id": "B", "ust": "P", "uzunluk_m": 2, "cap": "50"},
         {"id": "D", "ust": "B", "uzunluk_m": 1, "cap": "25", "cikis": "dolap_yari_sert"}]
    m = metraj.metraj_cikar(proje(h), K)
    sis = {s.kaynak: s.sistem for s in m.satirlar if s.kod.startswith("BORU")}
    assert sis == {"P": "Yangın — ortak besleme", "A": "Yangın — sprinkler", "S": "Yangın — sprinkler",
                   "B": "Yangın — dolap/hidrant", "D": "Yangın — dolap/hidrant"}


def test_poz_uretilmez():
    m = metraj.metraj_cikar(proje_yukle(ORNEK), K)
    for s in m.satirlar:
        assert "poz" not in s.kod.lower()


def test_ornek_ic_tutarlilik():
    m = metraj.metraj_cikar(proje_yukle(ORNEK), K)
    c = say(m)
    assert sum(v for k, v in c.items() if k.startswith("BORU")) == pytest.approx(m.model["Σ boru uzunluğu (m)"])
    assert c["SPR-K80"] == m.model["Sprinkler adedi"] == 55


def _recalc(yol):
    out = subprocess.run([sys.executable, str(RECALC), str(yol), "120"], capture_output=True, text=True, timeout=200)
    return json.loads(out.stdout)


@pytest.mark.skipif(RECALC is None or shutil.which("soffice") is None and not Path("/usr/bin/libreoffice").exists(),
                    reason="LibreOffice/recalc yok")
def test_excel_fiyat_ve_referans(tmp_path):
    ref = tmp_path / "ref.csv"
    ref.write_text("kalem_kodu,miktar\nSPR-K80,55\nBORU-CELIK_EN10255_ORTA-DN25,118.0\nFIT-TE-25x25,12\n",
                   encoding="utf-8")
    x = tmp_path / "m.xlsx"
    assert main(["metraj", str(ORNEK), "-o", str(x), "--referans", str(ref)]) == 0
    wb = load_workbook(x)
    fy = wb["Fiyatlar"]
    for r in range(7, fy.max_row + 1):
        if fy.cell(r, 1).value == "SPR-K80":
            fy.cell(r, 4).value = "TEST-POZ"
            fy.cell(r, 5).value = 100.0
    wb.save(x)
    sonuc = _recalc(x)
    assert sonuc["status"] == "success" and sonuc["total_errors"] == 0
    wb = load_workbook(x, data_only=True)
    kes = {r[0]: r for r in wb["Keşif özeti"].iter_rows(min_row=2, values_only=True) if r[0]}
    assert kes["SPR-K80"][5] == "TEST-POZ" and kes["SPR-K80"][7] == pytest.approx(5500.0)
    assert kes["FIT-TE-25x25"][5] == "POZ YOK" and kes["FIT-TE-25x25"][7] in (None, "")
    dog = {r[0]: r for r in wb["Doğrulama"].iter_rows(min_row=12, values_only=True) if r[0]}
    assert dog["SPR-K80"][6] == "TUTARLI"
    assert dog["BORU-CELIK_EN10255_ORTA-DN25"][6] == "TUTARLI"      # 117,38 vs 118 → %0,5 < %2
    assert dog["FIT-TE-25x25"][6] == "FARK VAR"                       # 13 vs 12, adet toleransı 0
    assert dog["FIT-RED-32x25"][6] == "REFERANSTA YOK"
