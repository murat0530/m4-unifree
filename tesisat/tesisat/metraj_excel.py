"""Metraj → Excel (openpyxl). Özet ve keşif sayfaları formüllerle Detay metraja bağlıdır;
fiyatlar ayrı 'Fiyatlar' sayfasında kullanıcı tarafından girilir (poz numarası üretilmez).
"""
from __future__ import annotations

import csv
import datetime as _dt
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .metraj import YONTEMLER, Metraj

F = "Arial"
BASLIK = Font(name=F, bold=True, color="FFFFFF")
BASLIK_DOLGU = PatternFill("solid", fgColor="1D2433")
NORMAL = Font(name=F)
KALIN = Font(name=F, bold=True)
GIRDI = Font(name=F, color="0000FF")
BAG = Font(name=F, color="008000")
SARI = PatternFill("solid", fgColor="FFFF00")
KONTROL = PatternFill("solid", fgColor="FDECEA")
INCE = Side(style="thin", color="D9DDE5")
KENAR = Border(left=INCE, right=INCE, top=INCE, bottom=INCE)
SAYFA = {"detay": "Detay metraj", "ozet": "Sistem-DN özeti", "belirsiz": "Belirsizlikler",
         "kesif": "Keşif özeti", "fiyat": "Fiyatlar", "dogrulama": "Doğrulama"}
D = f"'{SAYFA['detay']}'"
FY = "Fiyatlar"


def _baslik(ws, satir, basliklar, genislik):
    for i, (b, g) in enumerate(zip(basliklar, genislik), 1):
        c = ws.cell(row=satir, column=i, value=b)
        c.font, c.fill, c.border = BASLIK, BASLIK_DOLGU, KENAR
        c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = g
    ws.row_dimensions[satir].height = 30


def _hucre(ws, r, c, v, font=NORMAL, fmt=None, dolgu=None):
    h = ws.cell(row=r, column=c, value=v)
    h.font, h.border = font, KENAR
    if fmt:
        h.number_format = fmt
    if dolgu:
        h.fill = dolgu
    return h


def referans_oku(yol: str) -> dict:
    ref = {}
    with open(yol, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ref[r["kalem_kodu"].strip()] = ref.get(r["kalem_kodu"].strip(), 0.0) + float(r["miktar"])
    return ref


def yaz(m: Metraj, yol: str | Path) -> None:
    wb = Workbook()
    _detay(wb.active, m)
    kodlar = _kesif_kodlari(m)
    _ozet(wb.create_sheet(SAYFA["ozet"]), m)
    _belirsiz(wb.create_sheet(SAYFA["belirsiz"]), m)
    _kesif(wb.create_sheet(SAYFA["kesif"]), kodlar)
    _fiyat(wb.create_sheet(SAYFA["fiyat"]), kodlar)
    _dogrulama(wb.create_sheet(SAYFA["dogrulama"]), m, kodlar)
    wb.save(yol)


# ---------------------------------------------------------------- sayfalar
DETAY_KOL = ["Sıra", "Kalem kodu", "Kalem", "Sistem", "Kat", "Kaynak nesne / ağ elemanı", "DN", "Birim", "Miktar",
             "Çıkarım yöntemi", "Not"]


def _detay(ws, m: Metraj):
    ws.title = SAYFA["detay"]
    _baslik(ws, 1, DETAY_KOL, [6, 34, 44, 24, 7, 24, 9, 7, 11, 16, 60])
    dv = DataValidation(type="list", formula1='"' + ",".join(YONTEMLER) + '"', allow_blank=False)
    ws.add_data_validation(dv)
    for i, s in enumerate(m.satirlar, 2):
        dolgu = KONTROL if s.yontem == "kontrol gerekli" else None
        degerler = [i - 1, s.kod, s.kalem, s.sistem, s.kat, s.kaynak, s.dn, s.birim, s.miktar, s.yontem, s.not_]
        for j, v in enumerate(degerler, 1):
            fmt = ("#,##0.00" if s.birim == "m" else "#,##0") if j == 9 else None
            _hucre(ws, i, j, v, fmt=fmt, dolgu=dolgu)
        dv.add(f"J{i}")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:K{len(m.satirlar) + 1}"
    son = len(m.satirlar) + 3
    _hucre(ws, son, 2, "Not:", KALIN)
    ws.cell(row=son, column=3, value=f"{m.proje_adi} — ağ modelinden üretildi ({_dt.date.today().isoformat()}). "
            "Fitting kuralları: METRAJ_KURALLARI.md. Pembe satırlar 'kontrol gerekli'.").font = NORMAL


def _ozet(ws, m: Metraj):
    _baslik(ws, 1, ["Sistem", "Kalem kodu", "Kalem", "DN", "Birim", "Miktar", "Bunun kontrol gerekli kısmı"],
            [26, 34, 44, 9, 7, 12, 16])
    gruplar = sorted({(s.sistem, s.kod, s.kalem, s.dn, s.birim) for s in m.satirlar},
                     key=lambda t: (t[0], t[1].split("-")[0], t[4], t[1]))
    for r, (sis, kod, kalem, dn, birim) in enumerate(gruplar, 2):
        for c, v in enumerate([sis, kod, kalem, dn, birim], 1):
            _hucre(ws, r, c, v)
        fmt = "#,##0.00" if birim == "m" else "#,##0"
        _hucre(ws, r, 6, f"=SUMIFS({D}!$I:$I,{D}!$D:$D,$A{r},{D}!$B:$B,$B{r})", BAG, fmt)
        _hucre(ws, r, 7, f'=SUMIFS({D}!$I:$I,{D}!$D:$D,$A{r},{D}!$B:$B,$B{r},{D}!$J:$J,"kontrol gerekli")', BAG, fmt)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:G{len(gruplar) + 1}"


def _belirsiz(ws, m: Metraj):
    _baslik(ws, 1, ["No", "Kategori", "Nesne", "Açıklama", "Etkilenen kalem kodu", "Öneri", "Durum"],
            [5, 16, 24, 70, 28, 50, 12])
    for r, b in enumerate(m.belirsizlikler, 2):
        for c, v in enumerate([r - 1, b.kategori, b.nesne, b.aciklama, b.kalem_kodu, b.oneri, "açık"], 1):
            h = _hucre(ws, r, c, v, GIRDI if c == 7 else NORMAL)
            h.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:G{len(m.belirsizlikler) + 1}"


def _kesif_kodlari(m: Metraj):
    gor = {}
    for s in m.satirlar:
        gor.setdefault(s.kod, (s.kalem, s.birim))
    sira = {"BORU": 0, "FIT": 1, "VANA": 2, "SPR": 3, "CIKIS": 4, "ASKI": 5}
    return sorted(((k, *v) for k, v in gor.items()), key=lambda t: (sira.get(t[0].split("-")[0], 9), t[0]))


def _kesif(ws, kodlar):
    _baslik(ws, 1, ["Kalem kodu", "Kalem", "Birim", "Miktar", "Bunun kontrol gerekli kısmı", "Poz no",
                    "Birim fiyat (TL)", "Tutar (TL)"], [34, 44, 7, 12, 14, 18, 16, 18])
    n = len(kodlar)
    for r, (kod, kalem, birim) in enumerate(kodlar, 2):
        _hucre(ws, r, 1, kod)
        _hucre(ws, r, 2, kalem)
        _hucre(ws, r, 3, birim)
        fmt = "#,##0.00" if birim == "m" else "#,##0"
        _hucre(ws, r, 4, f"=SUMIFS({D}!$I:$I,{D}!$B:$B,$A{r})", BAG, fmt)
        _hucre(ws, r, 5, f'=SUMIFS({D}!$I:$I,{D}!$B:$B,$A{r},{D}!$J:$J,"kontrol gerekli")', BAG, fmt)
        bul = f"INDEX({FY}!$D:$D,MATCH($A{r},{FY}!$A:$A,0))"
        _hucre(ws, r, 6, f'=IFERROR(IF({bul}&""="","POZ YOK",{bul}),"POZ YOK")', BAG)
        fiyat = f"INDEX({FY}!$E:$E,MATCH($A{r},{FY}!$A:$A,0))"
        _hucre(ws, r, 7, f'=IFERROR(IF({fiyat}&""="","",{fiyat}),"")', BAG, "#,##0.00")
        _hucre(ws, r, 8, f'=IF(G{r}="","",D{r}*G{r})', NORMAL, "#,##0.00")
    t = n + 3
    _hucre(ws, t, 7, "Toplam (fiyatı girilenler)", KALIN)
    _hucre(ws, t, 8, f"=SUM(H2:H{n + 1})", KALIN, "#,##0.00")
    _hucre(ws, t + 1, 7, "Fiyatı girilmemiş kalem sayısı", KALIN)
    _hucre(ws, t + 1, 8, f'=COUNTIF(G2:G{n + 1},"")', KALIN, "0")
    _hucre(ws, t + 2, 7, "Pozu girilmemiş kalem sayısı", KALIN)
    _hucre(ws, t + 2, 8, f'=COUNTIF(F2:F{n + 1},"POZ YOK")', KALIN, "0")
    ws.cell(row=t + 4, column=1, value="Not: Miktarlar 'Detay metraj' sayfasından formülle gelir; poz ve fiyat "
            "'Fiyatlar' sayfasından okunur. Toplam, yalnızca fiyatı girilmiş kalemleri içerir — eksik fiyat varken "
            "teklif tutarı olarak kullanılmamalıdır.").font = NORMAL
    ws.freeze_panes = "A2"


def _fiyat(ws, kodlar):
    ws["A1"] = "FİYAT TABLOSU — yalnızca SARI hücreleri doldurun"
    ws["A1"].font = Font(name=F, bold=True, size=12)
    aciklama = [
        "Poz no: kullandığınız birim fiyat listesindeki numarayı AYNEN yazın. Numarası bilinmeyen kalemi BOŞ bırakın "
        "(keşifte 'POZ YOK' görünür). Araç poz numarası üretmez.",
        "Birim fiyat: TL, KDV hariç, kalemin birimine (m / adet) göre. Fiyat tarihi ve kaynağı zorunludur "
        "(ör. '2026-11 Bakanlık birim fiyat listesi' veya 'X firması teklifi, 12.11.2026').",
        "Biçim örneği → Poz no: <listedeki numara>   Birim fiyat: 1250,00   Fiyat tarihi: 2026-11-18   "
        "Kaynak: <liste veya teklif adı>",
    ]
    for i, a in enumerate(aciklama, 2):
        ws.cell(row=i, column=1, value=a).font = NORMAL
    _baslik(ws, 6, ["Kalem kodu", "Kalem", "Birim", "Poz no", "Birim fiyat (TL)", "Fiyat tarihi", "Kaynak"],
            [34, 44, 7, 18, 16, 14, 40])
    for r, (kod, kalem, birim) in enumerate(kodlar, 7):
        _hucre(ws, r, 1, kod)
        _hucre(ws, r, 2, kalem)
        _hucre(ws, r, 3, birim)
        for c, fmt in [(4, "@"), (5, "#,##0.00"), (6, "yyyy-mm-dd"), (7, None)]:
            _hucre(ws, r, c, None, GIRDI, fmt, SARI)
    ws.freeze_panes = "A7"


def _dogrulama(ws, m: Metraj, kodlar):
    ws["A1"] = "DOĞRULAMA"
    ws["A1"].font = Font(name=F, bold=True, size=12)
    if m.referans is None:
        ws["A2"] = "DOĞRULANMADI — kontrol edilmiş referans metraj verilmedi. Aşağıdaki tablo yalnızca iç " \
                   "tutarlılığı (ağ modeli ↔ metraj) gösterir; doğruluk kanıtı değildir."
        ws["A2"].font = Font(name=F, bold=True, color="B3261E")
    _baslik(ws, 4, ["İç tutarlılık kontrolü", "Metrajdan", "Ağ modelinden", "Fark", "Durum"], [40, 16, 16, 12, 14])
    kontroller = [
        ("Σ boru uzunluğu (m)", f'=SUMIFS({D}!$I:$I,{D}!$H:$H,"m",{D}!$B:$B,"BORU-*")'),
        ("Sprinkler adedi", f'=SUMIFS({D}!$I:$I,{D}!$B:$B,"SPR-K*")'),
        ("Dolap/hidrant adedi", f'=SUMIFS({D}!$I:$I,{D}!$B:$B,"CIKIS-*")'),
    ]
    for r, (ad, formul) in enumerate(kontroller, 5):
        _hucre(ws, r, 1, ad)
        _hucre(ws, r, 2, formul, BAG, "#,##0.00")
        h = _hucre(ws, r, 3, m.model[ad], GIRDI, "#,##0.00")
        h.comment = Comment("Kaynak: hidrolik ağ modeli (yangin.YanginAgi), metraj üretimi sırasında okundu.", "tesisat")
        _hucre(ws, r, 4, f"=B{r}-C{r}", NORMAL, "#,##0.00")
        _hucre(ws, r, 5, f'=IF(ABS(D{r})<0.001,"TUTARLI","FARK VAR")', KALIN)
    r0 = 10
    ws.cell(row=r0, column=1, value="Referans (kontrol edilmiş) metraj ile karşılaştırma").font = KALIN
    if m.referans is None:
        ws.cell(row=r0 + 1, column=1, value="Referans yok → karşılaştırma yapılmadı.").font = NORMAL
        return
    _baslik(ws, r0 + 1, ["Kalem kodu", "Metraj", "Referans", "Fark", "Fark %", "Tolerans", "Durum"],
            [40, 16, 16, 12, 10, 10, 14])
    tum = sorted(set(k for k, *_ in kodlar) | set(m.referans))
    birim = {k: b for k, _, b in kodlar}
    for i, kod in enumerate(tum, r0 + 2):
        _hucre(ws, i, 1, kod)
        _hucre(ws, i, 2, f"=SUMIFS({D}!$I:$I,{D}!$B:$B,$A{i})", BAG, "#,##0.00")
        h = _hucre(ws, i, 3, m.referans.get(kod, 0.0), GIRDI, "#,##0.00")
        h.comment = Comment("Kaynak: kullanıcının verdiği kontrol edilmiş metraj (--referans).", "tesisat")
        _hucre(ws, i, 4, f"=B{i}-C{i}", NORMAL, "#,##0.00")
        _hucre(ws, i, 5, f'=IF(C{i}=0,"",D{i}/C{i})', NORMAL, "0.0%")
        _hucre(ws, i, 6, 0.02 if birim.get(kod, "m") == "m" else 0, GIRDI, "0.0%")
        _hucre(ws, i, 7, f'=IF(C{i}=0,IF(B{i}=0,"TUTARLI","REFERANSTA YOK"),IF(ABS(D{i})<=F{i}*C{i}+0.000001,'
                         f'"TUTARLI","FARK VAR"))', KALIN)
    son = r0 + 2 + len(tum)
    ws.cell(row=son + 1, column=1, value="Sonuç").font = KALIN
    _hucre(ws, son + 1, 2, f'=IF(COUNTIF(G{r0 + 2}:G{son - 1},"TUTARLI")={len(tum)},"REFERANSLA TUTARLI",'
                           f'"FARK VAR — inceleyin")', KALIN)
