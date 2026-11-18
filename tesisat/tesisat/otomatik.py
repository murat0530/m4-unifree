"""DXF/DWG → hidrolik hesap + metraj + yaklaşık teklif, tek komutla.

    python -m tesisat otomatik ayar.yaml -o cikti_klasoru

Ayar dosyası biçimi: sablonlar/yangin_ayar_sablonu.yaml
Çıktılar: proje.yaml (üretilen ağ modeli), hidrolik_rapor.html, metraj_teklif.xlsx, ozet.md
"""
from __future__ import annotations

import copy
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from . import boru_agi, cizim, fiyat, metraj, metraj_excel, rapor
from .cli import calistir
from .ortak import HATA, UYARI, GirdiHatasi, kurallari_yukle


def dwg_donustur(yol: Path, hedef_klasor: Path) -> Path:
    """DWG → DXF. Yalnızca ODA File Converter kuruluysa (ezdxf odafc eklentisi) çalışır."""
    try:
        from ezdxf.addons import odafc
        if odafc.is_installed():
            hedef = hedef_klasor / (yol.stem + ".dxf")
            odafc.convert(str(yol), str(hedef), version="R2018", replace=True)
            return hedef
    except Exception:  # noqa: BLE001 — ODA yoksa aşağıdaki açıklayıcı hata verilir
        pass
    raise GirdiHatasi("DWG okunamıyor: bu ortamda ODA File Converter yok. AutoCAD'de 'Farklı Kaydet → DXF' "
                      "(AutoCAD 2013 veya üstü) ile kaydedip DXF'i verin.")


def _recalc(xlsx: Path) -> dict | None:
    """LibreOffice varsa formülleri hesaplatır (önizleyicilerde değer görünsün diye)."""
    betik = next(Path.home().joinpath(".claude", "skills").rglob("xlsx/scripts/recalc.py"), None) \
        if Path.home().joinpath(".claude", "skills").exists() else None
    if betik is None or not (shutil.which("soffice") or shutil.which("libreoffice")):
        return None
    try:
        import json
        out = subprocess.run([sys.executable, str(betik), str(xlsx), "180"], capture_output=True, text=True,
                             timeout=300)
        return json.loads(out.stdout)
    except Exception:  # noqa: BLE001
        return None


def proje_uret(ayar: dict, kok: Path, cikti: Path) -> tuple[dict, list[str]]:
    c = ayar.get("cizim") or {}
    if not c.get("dosya"):
        raise GirdiHatasi("ayar.cizim.dosya (DXF/DWG yolu) gerekli")
    dosya = (kok / c["dosya"]).resolve() if not Path(c["dosya"]).is_absolute() else Path(c["dosya"])
    if not dosya.exists():
        raise GirdiHatasi(f"Çizim bulunamadı: {dosya}")
    if dosya.suffix.lower() == ".dwg":
        dosya = dwg_donustur(dosya, cikti)
    notlar = []
    y = copy.deepcopy(ayar.get("yangin") or {})
    hatlar = list(y.pop("ust_hatlar", []) or [])
    planlar = c.get("planlar") or [{"ad": "", "on_ek": "", "kaynak": c.get("kaynak"), "ust": None}]
    for pl in planlar:
        if not pl.get("kaynak"):
            raise GirdiHatasi("Her plan için 'kaynak' (blok deseni veya nokta) gerekli")
        sonuc = boru_agi.ag_cikar(str(dosya), c["boru_katmani"], c["sprinkler_blok"], pl["kaynak"],
                                  c.get("dolap_blok"), c.get("etiket_katmani"), c.get("birim"),
                                  on_ek=pl.get("on_ek", ""), kat=pl.get("ad", ""), ust=pl.get("ust"),
                                  tol=c.get("tolerans"))
        dz = float(pl.get("kot_farki_m", 0.0))
        if dz and sonuc.hatlar:   # plan kotu: ilk hatta düşey fark
            sonuc.hatlar[0]["kot_farki_m"] = dz
        hatlar += sonuc.hatlar
        oz = sonuc.ozet
        notlar.append(f"[{pl.get('ad') or 'plan'}] {oz['sprinkler_agda']}/{oz['sprinkler_cizimde']} sprinkler ağa "
                      f"bağlandı, {oz['toplam_boru_m']} m boru, {oz['cap_etiketi']} çap etiketi, "
                      f"{oz['cap_onerilen_parca']} parçada çap önerildi (birim {oz['birim']})")
        notlar += [f"[{pl.get('ad') or 'plan'}] {n}" for n in sonuc.belirsizlikler]
    # mahaller (isteğe bağlı): kapsama kontrolü + mahal bazında sınıf
    if c.get("mahal_katmani"):
        mh = cizim.dxf_oku(str(dosya), c["mahal_katmani"], etiket_katmani=c.get("mahal_etiket_katmani"),
                           birim=c.get("birim"))
        mahaller = [{k: v for k, v in m.items() if k not in ("alan_m2", "tip_belirsiz")} for m in mh["mahaller"]]
        from .kapsama import icinde
        for h in hatlar:
            if h.get("sprinkler") and h.get("konum"):
                for m in mahaller:
                    if icinde(tuple(h["konum"]), [tuple(p) for p in m["poligon"]]):
                        h["mahal"] = m["id"]
                        break
        y["mahaller"] = mahaller + list(y.get("mahaller") or [])
        notlar += mh["uyarilar"]
    y["hatlar"] = hatlar
    if not y.get("senaryolar"):
        y.setdefault("otomatik_senaryo", {"uzun_eksen": c.get("uzun_eksen", "x")})
    proje = {k: copy.deepcopy(v) for k, v in ayar.items() if k in ("proje", "bina", "kararlar", "kurallar_ek")}
    proje["yangin"] = y
    return proje, notlar


def calistir_otomatik(ayar_yolu: str | Path, cikti: str | Path) -> dict:
    ayar_yolu = Path(ayar_yolu)
    cikti = Path(cikti)
    cikti.mkdir(parents=True, exist_ok=True)
    with open(ayar_yolu, encoding="utf-8") as f:
        ayar = yaml.safe_load(f) or {}
    proje, notlar = proje_uret(ayar, ayar_yolu.parent, cikti)
    (cikti / "proje.yaml").write_text(yaml.safe_dump(proje, allow_unicode=True, sort_keys=False, width=140),
                                      encoding="utf-8")

    sonuclar, _ = calistir(proje)
    (cikti / "hidrolik_rapor.html").write_text(rapor.html_rapor(proje, sonuclar), encoding="utf-8")

    kurallar = kurallari_yukle(None, proje.get("kurallar_ek"))
    m = metraj.metraj_cikar(proje, kurallar)
    metraj.ek_kalemler_ekle(m, ayar.get("ek_kalemler"))
    fl = fiyat.yukle(ayar.get("fiyat"))
    xlsx = cikti / "metraj_teklif.xlsx"
    metraj_excel.yaz(m, xlsx, fl)
    hesap = _recalc(xlsx)

    # özet (Python'da, Excel'den bağımsız)
    toplam, fiyatsiz = 0.0, []
    gor = {}
    for s in m.satirlar:
        gor[s.kod] = gor.get(s.kod, 0.0) + s.miktar
    kalem_ad = {s.kod: s.kalem for s in m.satirlar}
    for kod, mik in gor.items():
        e = fiyat.esle(kod, fl)
        if e is None:
            fiyatsiz.append(f"{kod} ({kalem_ad[kod]}, {mik:g})")
        else:
            toplam += mik * e["fiyat"]
    kdv = fl["parametreler"]["kdv"]
    hatalar = [b for s in sonuclar for b in s.bulgular if b.seviye == HATA]
    uyarilar = [b for s in sonuclar for b in s.bulgular if b.seviye == UYARI]
    oz = sonuclar[0].ozet
    acik = len(m.belirsizlikler)
    satir = [
        f"# {proje.get('proje', {}).get('ad', 'Proje')} — otomatik sonuç", "",
        "## Çizimden okunan", *[f"- {n}" for n in notlar], "",
        "## Hidrolik", *[f"- {k}: {v}" for k, v in oz.items()],
        f"- Hata: {len(hatalar)}, uyarı: {len(uyarilar)}",
        *[f"  - HATA {b.nesne}: {b.mesaj}" for b in hatalar[:15]], "",
        "## Metraj ve yaklaşık teklif",
        f"- Detay satırı: {len(m.satirlar)}, açık belirsizlik: {acik}",
        f"- Yaklaşık teklif (fiyatı bulunan kalemler, KDV hariç): {toplam:,.0f} TL".replace(",", "."),
        f"- KDV dahil: {toplam * (1 + kdv):,.0f} TL".replace(",", "."),
        f"- Fiyatı bulunamayan kalem: {len(fiyatsiz)}", *[f"  - {x}" for x in fiyatsiz], "",
        "## Durum",
        "- TEKLİF TAMAMLANMADI: açık belirsizlikler çözülüp satırlar mühendisçe onaylanmadan ve fiyatsız kalemler "
        "girilmeden bu tutar teklif olarak kullanılmamalıdır (Excel → 'Teklif durumu').",
    ]
    (cikti / "ozet.md").write_text("\n".join(satir) + "\n", encoding="utf-8")
    return {"proje": proje, "notlar": notlar, "hidrolik": oz, "hata": len(hatalar), "uyari": len(uyarilar),
            "teklif_kdv_haric": round(toplam, 2), "teklif_kdv_dahil": round(toplam * (1 + kdv), 2),
            "fiyatsiz": fiyatsiz, "belirsizlik": acik, "satir": len(m.satirlar),
            "excel_hesap": hesap, "klasor": str(cikti)}


# ---------------------------------------------------------------- ayar önerisi
_BORU_RE = r"BORU|PIPE|SPR|SPRINK|YANGIN|FIRE|YAG|SPK"
_SPR_RE = r"SPR|SPRINK|HEAD|BASLIK|BAŞLIK|PENDENT|SARKIK|UPRIGHT"
_KAYNAK_RE = r"KOLON|RISER|BESLEME|FEED|ANA.?HAT|MAIN"
_DOLAP_RE = r"DOLAP|HOSE|YD[-_]|FHC"


def ayar_oner(dxf: str | Path, hedef: str | Path) -> dict:
    """Çizimi tarar, katman/blok adlarından ayar taslağı üretir. Tahminler '★ KONTROL' ile işaretlenir."""
    import re

    o = cizim.dxf_ozet(str(dxf))
    doc = cizim._ac(str(dxf))
    msp = doc.modelspace()
    cizgi = {}
    for e in msp.query("LINE LWPOLYLINE POLYLINE"):
        cizgi[e.dxf.layer] = cizgi.get(e.dxf.layer, 0) + 1
    norm = lambda t: cizim.normal(t)  # noqa: E731
    boru = sorted([k for k in cizgi if re.search(_BORU_RE, norm(k))], key=lambda k: -cizgi[k])
    bloklar = o["bloklar"]
    spr = sorted([b for b in bloklar if re.search(_SPR_RE, norm(b))], key=lambda b: -bloklar[b])
    kay = [b for b in bloklar if re.search(_KAYNAK_RE, norm(b))]
    dol = [b for b in bloklar if re.search(_DOLAP_RE, norm(b))]
    with open(Path(__file__).resolve().parents[1] / "sablonlar" / "yangin_ayar_sablonu.yaml", encoding="utf-8") as f:
        sablon = yaml.safe_load(f)
    a = copy.deepcopy(sablon)
    a["proje"]["ad"] = Path(dxf).stem
    a["kararlar"] = []
    a["cizim"].update({"dosya": Path(dxf).name, "boru_katmani": boru[:3] or ["★ BORU KATMANI"],
                       "sprinkler_blok": spr[:3] or ["★ SPRINKLER BLOĞU"], "dolap_blok": dol[:2]})
    a["cizim"]["planlar"] = [{"ad": "Kat 1", "on_ek": "", "kaynak": {"blok": kay[0]} if kay else
                              {"nokta": ["★ x", "★ y"]}, "ust": None}]
    a["yangin"]["tehlike_sinifi"] = "★ SOR"
    a["yangin"]["ust_hatlar"] = []
    a["yangin"]["kaynak"] = {"ad": "Besleme noktası", "kot_m": 0.0}
    a["ek_kalemler"] = [e for e in sablon["ek_kalemler"] if e["kod"] in
                        ("EK-HEATPLATE", "EK-AKIS-ANAHTARI", "EK-TEST-DRENAJ", "EK-MANOMETRE", "EK-HAVA-ATMA",
                         "EK-BOYA", "EK-TEST", "EK-NAKLIYE", "EK-ASBUILT")]
    eksik = []
    if not boru:
        eksik.append("boru katmanı bulunamadı")
    if not spr:
        eksik.append("sprinkler bloğu bulunamadı")
    if not kay:
        eksik.append("besleme (kolon) bloğu bulunamadı — kaynak noktası sorulmalı")
    eksik += ["tehlike sınıfı (her zaman sorulur)", "besleme kotu / kolon ve kat bağlantı hatları (kesitten)",
              "sprinkler başına alan (mahal katmanı yoksa)"]
    with open(hedef, "w", encoding="utf-8") as f:
        f.write(f"# {Path(dxf).name} için OTOMATİK ÖNERİ — ★ işaretli ve aşağıdaki maddeleri kontrol edin:\n")
        for x in eksik:
            f.write(f"#   - {x}\n")
        f.write(f"# Bulunan: {sum(bloklar.get(b, 0) for b in spr[:1])} sprinkler bloğu ({', '.join(spr[:3]) or '-'}), "
                f"boru katmanları: {', '.join(boru[:3]) or '-'}, birim: {o['birim']}\n")
        yaml.safe_dump(a, f, allow_unicode=True, sort_keys=False, width=140)
    return {"boru_katmani": boru, "sprinkler_blok": spr, "kaynak_blok": kay, "dolap_blok": dol, "eksik": eksik,
            "birim": o["birim"], "sprinkler_adedi": sum(bloklar.get(b, 0) for b in spr[:1])}
