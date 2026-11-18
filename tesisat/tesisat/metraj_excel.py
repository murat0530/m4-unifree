"""Metraj → Excel (openpyxl).

Sayfalar: Teklif durumu · Detay metraj · Sistem-DN özeti · Belirsizlikler · Keşif özeti · Fiyatlar · Doğrulama
  * Miktarlar Detay metrajdan formülle toplanır; fiyat/poz yalnızca Fiyatlar sayfasında kullanıcı girdisidir.
  * Çıkarım yöntemi (sabit) ile onay durumu (formül) ayrı sütunlardır. Onay durumu, satıra bağlı
    belirsizliklerin Belirsizlikler sayfasındaki "Durum" hücresine göre kendiliğinden değişir.
  * Teklif durumu; açık belirsizlik, kontrol gerekli satır, onay, poz, fiyat, tarih/kaynak ve referans
    doğrulamasından herhangi biri eksikse "TEKLİF TAMAMLANMADI" gösterir.
"""
from __future__ import annotations

import csv
import datetime as _dt
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
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
PEMBE = PatternFill("solid", fgColor="FDECEA")
KIRMIZI = PatternFill("solid", fgColor="F6B8B3")
YESIL = PatternFill("solid", fgColor="CFE9D6")
INCE = Side(style="thin", color="D9DDE5")
KENAR = Border(left=INCE, right=INCE, top=INCE, bottom=INCE)

S_TEKLIF, S_DETAY, S_OZET, S_BEL, S_KESIF, S_FIYAT, S_DOG = (
    "Teklif durumu", "Detay metraj", "Sistem-DN özeti", "Belirsizlikler", "Keşif özeti", "Fiyatlar", "Doğrulama")
D, BL, KS, TD, DG = f"'{S_DETAY}'", S_BEL, f"'{S_KESIF}'", f"'{S_TEKLIF}'", S_DOG
FY = S_FIYAT
FIYAT_ILK = 7          # Fiyatlar tablosunun ilk veri satırı
ONAY_HUCRE = f"{TD}!$B$4"   # "poz zorunlu mu" girdisi
REF_HUCRE = f"{DG}!$B$3"    # referans doğrulama sonucu


def _baslik(ws, satir, basliklar, genislik):
    for i, (b, g) in enumerate(zip(basliklar, genislik), 1):
        c = ws.cell(row=satir, column=i, value=b)
        c.font, c.fill, c.border = BASLIK, BASLIK_DOLGU, KENAR
        c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = g
    ws.row_dimensions[satir].height = 32


def _h(ws, r, c, v, font=NORMAL, fmt=None, dolgu=None, sar=False):
    h = ws.cell(row=r, column=c, value=v)
    h.font, h.border = font, KENAR
    if fmt:
        h.number_format = fmt
    if dolgu:
        h.fill = dolgu
    if sar:
        h.alignment = Alignment(wrap_text=True, vertical="top")
    return h


def referans_oku(yol: str) -> dict:
    ref = {}
    with open(yol, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            k = r["kalem_kodu"].strip()
            ref[k] = ref.get(k, 0.0) + float(r["miktar"])
    return ref


def _kodlar(m: Metraj):
    gor = {}
    for s in m.satirlar:
        gor.setdefault(s.kod, (s.kalem, s.birim))
    sira = {"BORU": 0, "FIT": 1, "VANA": 2, "SPR": 3, "CIKIS": 4, "ASKI": 5}
    return sorted(((k, *v) for k, v in gor.items()), key=lambda t: (sira.get(t[0].split("-")[0], 9), t[0]))


def yaz(m: Metraj, yol: str | Path, fiyat_listesi: dict | None = None) -> None:
    wb = Workbook()
    kodlar = _kodlar(m)
    nd, nb, nk = len(m.satirlar), len(m.belirsizlikler), len(kodlar)
    _teklif(wb.active, nd, nb, nk)
    _detay(wb.create_sheet(S_DETAY), m, nb)
    _ozet(wb.create_sheet(S_OZET), m)
    _belirsiz(wb.create_sheet(S_BEL), m, nd)
    _kesif(wb.create_sheet(S_KESIF), kodlar)
    _fiyat(wb.create_sheet(S_FIYAT), kodlar, fiyat_listesi)
    _dogrulama(wb.create_sheet(S_DOG), m, kodlar)
    wb.save(yol)


# ---------------------------------------------------------------- Teklif durumu
def _teklif(ws, nd, nb, nk):
    ws.title = S_TEKLIF
    ws.column_dimensions["A"].width = 62
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 70
    ws["A1"] = "TEKLİF DURUMU"
    ws["A1"].font = Font(name=F, bold=True, size=14)
    ws["A2"] = "Bu sayfa diğer sayfalardan formülle beslenir; yalnızca B4 hücresi girdidir."
    ws["A2"].font = NORMAL
    _h(ws, 4, 1, "Poz numarası zorunlu mu? (kamu işi: evet · özel teklif: hayır)", KALIN)
    _h(ws, 4, 2, "evet", GIRDI, dolgu=SARI)
    dv = DataValidation(type="list", formula1='"evet,hayır"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("B4")
    _baslik(ws, 6, ["Kontrol", "Değer", "Engel mi?", "Açıklama"], [62, 26, 14, 70])
    dsonu, ksonu, fsonu = nd + 1, nk + 1, FIYAT_ILK + nk - 1
    satirlar = [
        ("Açık belirsizlik (adet)", f'=COUNTIF({BL}!$I$2:$I${nb + 1},"açık")', True,
         "Belirsizlikler sayfasında 'Durum' = açık olan kayıtlar"),
        ("  bunlardan kapsam eksikliği", f'=COUNTIFS({BL}!$E$2:$E${nb + 1},"kapsam",{BL}!$I$2:$I${nb + 1},"açık")',
         False, "Teklifte hiç yer almayan kalem grupları (askı, işçilik, boya, ekipman…)"),
        ("Çıkarım yöntemi 'kontrol gerekli' olan detay satırı", f'=COUNTIF({D}!$J$2:$J${dsonu},"kontrol gerekli")',
         True, "Kural karar veremedi; çizimden doğrulanıp yöntem güncellenmeli"),
        ("Onay durumu 'belirsizlik açık' olan detay satırı", f'=COUNTIF({D}!$M$2:$M${dsonu},"belirsizlik açık")', True,
         "Bağlı belirsizlik çözülünce kendiliğinden değişir"),
        ("Mühendis onayı bekleyen detay satırı", f'=COUNTIF({D}!$M$2:$M${dsonu},"onay bekliyor")', True,
         "Detay metraj L sütununa 'evet' yazılarak onaylanır"),
        ("Pozu eksik kalem", f'=IF($B$4="evet",COUNTIF({KS}!$H$2:$H${ksonu},"POZ YOK"),0)', True,
         "B4 = hayır ise engel sayılmaz"),
        ("Fiyatı eksik kalem", f'=COUNTIF({FY}!$H${FIYAT_ILK}:$H${fsonu},"fiyat yok")', True, ""),
        ("Fiyat tarihi veya kaynağı eksik kalem", f'=COUNTIF({FY}!$H${FIYAT_ILK}:$H${fsonu},"tarih/kaynak eksik")', True,
         "Fiyat girildiyse tarih ve kaynak zorunlu"),
        ("Referans (kontrol edilmiş) metraj doğrulaması", f"={REF_HUCRE}", True, "Doğrulama sayfası"),
        ("Çizimden ölçülmemiş detay satırı (bilgi)",
         f'=COUNTA({D}!$J$2:$J${dsonu})-COUNTIF({D}!$J$2:$J${dsonu},"ölçülen")', False,
         "DXF'ten ölçüm yapılmadıkça miktarlar model/girdi değeridir"),
    ]
    r0 = 7
    for i, (ad, formul, engel, acik) in enumerate(satirlar):
        r = r0 + i
        _h(ws, r, 1, ad, KALIN if not ad.startswith("  ") else NORMAL)
        _h(ws, r, 2, formul, BAG, "0" if "Referans" not in ad else None)
        _h(ws, r, 3, "evet" if engel else "hayır")
        _h(ws, r, 4, acik, sar=True)
    son = r0 + len(satirlar) - 1
    engel_kosul = ",".join(f"B{r0 + i}=0" for i, s in enumerate(satirlar) if s[2] and "Referans" not in s[0])
    ref_r = r0 + [s[0] for s in satirlar].index("Referans (kontrol edilmiş) metraj doğrulaması")
    _h(ws, son + 2, 1, "TEKLİF DURUMU", Font(name=F, bold=True, size=13))
    c = _h(ws, son + 2, 2, f'=IF(AND({engel_kosul},B{ref_r}="REFERANSLA TUTARLI"),"TEKLİFE HAZIR",'
                           f'"TEKLİF TAMAMLANMADI")', Font(name=F, bold=True, size=13))
    ws.conditional_formatting.add(f"B{son + 2}", FormulaRule(formula=[f'B{son + 2}="TEKLİFE HAZIR"'], fill=YESIL))
    ws.conditional_formatting.add(f"B{son + 2}", FormulaRule(formula=[f'B{son + 2}<>"TEKLİFE HAZIR"'], fill=KIRMIZI))
    for r in range(r0, son + 1):
        ws.conditional_formatting.add(f"B{r}", FormulaRule(formula=[f'AND($C{r}="evet",ISNUMBER(B{r}),B{r}>0)'],
                                                           fill=KIRMIZI))
    ws.cell(row=son + 4, column=1, value="Tutar, Keşif özeti sayfasındadır. TEKLİFE HAZIR görünmeden toplam tutar "
            "teklif olarak kullanılmamalıdır.").font = NORMAL
    _ = c


# ---------------------------------------------------------------- Detay metraj
DETAY_KOL = ["Sıra", "Kalem kodu", "Kalem", "Sistem", "Kat", "Kaynak nesne / ağ elemanı", "DN", "Birim", "Miktar",
             "Çıkarım yöntemi", "Belirsizlik no", "Mühendis onayı (evet)", "Onay durumu", "Not"]


def _detay(ws, m: Metraj, nb):
    _baslik(ws, 1, DETAY_KOL, [6, 30, 52, 22, 7, 24, 11, 7, 10, 15, 14, 12, 17, 60])
    dv_y = DataValidation(type="list", formula1='"' + ",".join(YONTEMLER) + '"', allow_blank=False)
    dv_o = DataValidation(type="list", formula1='"evet"', allow_blank=True)
    ws.add_data_validation(dv_y)
    ws.add_data_validation(dv_o)
    ids = f"{BL}!$A$2:$A${nb + 1}"
    durum = f"{BL}!$I$2:$I${nb + 1}"
    for r, s in enumerate(m.satirlar, 2):
        degerler = [r - 1, s.kod, s.kalem, s.sistem, s.kat, s.kaynak, s.dn, s.birim, s.miktar, s.yontem,
                    ",".join(s.belirsizlik_ids)]
        for c, v in enumerate(degerler, 1):
            fmt = ("#,##0.00" if s.birim == "m" else "#,##0") if c == 9 else None
            _h(ws, r, c, v, fmt=fmt)
        _h(ws, r, 12, None, GIRDI, dolgu=SARI)
        if nb:
            onay = (f'=IF(SUMPRODUCT(ISNUMBER(SEARCH(","&{ids}&",",","&$K{r}&","))*({durum}="açık"))>0,'
                    f'"belirsizlik açık",IF($L{r}="evet","onaylandı","onay bekliyor"))')
        else:
            onay = f'=IF($L{r}="evet","onaylandı","onay bekliyor")'
        _h(ws, r, 13, onay, BAG)
        _h(ws, r, 14, s.not_)
        dv_y.add(f"J{r}")
        dv_o.add(f"L{r}")
    son = len(m.satirlar) + 1
    ws.conditional_formatting.add(f"A2:N{son}", FormulaRule(formula=['$M2="belirsizlik açık"'], fill=PEMBE))
    ws.conditional_formatting.add(f"A2:N{son}", FormulaRule(formula=['$J2="kontrol gerekli"'], fill=KIRMIZI))
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:N{son}"
    ws.cell(row=son + 2, column=2, value="Not:").font = KALIN
    ws.cell(row=son + 2, column=3, value=f"{m.proje_adi} — ağ modelinden üretildi ({_dt.date.today().isoformat()}). "
            "Kurallar: METRAJ_KURALLARI.md. Çıkarım yöntemi = miktarın kaynağı; Onay durumu = teklife girebilirlik "
            "(formül). Onay için L sütununa 'evet' yazın.").font = NORMAL


# ---------------------------------------------------------------- Sistem-DN özeti
def _ozet(ws, m: Metraj):
    _baslik(ws, 1, ["Sistem", "Kalem kodu", "Kalem", "DN", "Birim", "Miktar", "Kontrol gerekli (yöntem)",
                    "Belirsizliği açık"], [24, 30, 52, 11, 7, 12, 14, 14])
    gruplar = sorted({(s.sistem, s.kod, s.kalem, s.dn, s.birim) for s in m.satirlar},
                     key=lambda t: (t[0], t[1].split("-")[0], t[4], t[1]))
    for r, (sis, kod, kalem, dn, birim) in enumerate(gruplar, 2):
        for c, v in enumerate([sis, kod, kalem, dn, birim], 1):
            _h(ws, r, c, v)
        fmt = "#,##0.00" if birim == "m" else "#,##0"
        temel = f"{D}!$I:$I,{D}!$D:$D,$A{r},{D}!$B:$B,$B{r}"
        _h(ws, r, 6, f"=SUMIFS({temel})", BAG, fmt)
        _h(ws, r, 7, f'=SUMIFS({temel},{D}!$J:$J,"kontrol gerekli")', BAG, fmt)
        _h(ws, r, 8, f'=SUMIFS({temel},{D}!$M:$M,"belirsizlik açık")', BAG, fmt)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:H{len(gruplar) + 1}"


# ---------------------------------------------------------------- Belirsizlikler
def _belirsiz(ws, m: Metraj, nd):
    _baslik(ws, 1, ["No", "Kategori", "Nesne", "Açıklama", "Etki", "Bağlı kalem kodları", "Bağlı detay satırı",
                    "Öneri", "Durum", "Çözüm notu"], [6, 14, 22, 64, 12, 32, 10, 46, 11, 34])
    dv = DataValidation(type="list", formula1='"açık,çözüldü"', allow_blank=False)
    ws.add_data_validation(dv)
    for r, b in enumerate(m.belirsizlikler, 2):
        kod = ", ".join(b.kalem_kodlari[:6]) + (f" (+{len(b.kalem_kodlari) - 6})" if len(b.kalem_kodlari) > 6 else "")
        for c, v in enumerate([b.id, b.kategori, b.nesne, b.aciklama, b.etki, kod or "— (satır yok)"], 1):
            _h(ws, r, c, v, sar=c in (3, 4, 6))
        _h(ws, r, 7, f'=SUMPRODUCT(--ISNUMBER(SEARCH(","&$A{r}&",",","&{D}!$K$2:$K${nd + 1}&",")))', BAG, "0")
        _h(ws, r, 8, b.oneri, sar=True)
        _h(ws, r, 9, "açık", GIRDI, dolgu=SARI)
        _h(ws, r, 10, None, GIRDI, dolgu=SARI)
        dv.add(f"I{r}")
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:J{len(m.belirsizlikler) + 1}"


# ---------------------------------------------------------------- Keşif özeti
def _kesif(ws, kodlar):
    _baslik(ws, 1, ["Kalem kodu", "Kalem", "Birim", "Miktar", "Kontrol gerekli (yöntem)", "Belirsizliği açık",
                    "Onay bekleyen", "Poz no", "Birim fiyat (TL)", "Tutar (TL)", "Fiyat durumu", "Kalem durumu"],
            [30, 52, 7, 11, 12, 12, 12, 16, 14, 16, 18, 26])
    n = len(kodlar)
    for r, (kod, kalem, birim) in enumerate(kodlar, 2):
        _h(ws, r, 1, kod)
        _h(ws, r, 2, kalem)
        _h(ws, r, 3, birim)
        fmt = "#,##0.00" if birim == "m" else "#,##0"
        _h(ws, r, 4, f"=SUMIFS({D}!$I:$I,{D}!$B:$B,$A{r})", BAG, fmt)
        _h(ws, r, 5, f'=SUMIFS({D}!$I:$I,{D}!$B:$B,$A{r},{D}!$J:$J,"kontrol gerekli")', BAG, fmt)
        _h(ws, r, 6, f'=SUMIFS({D}!$I:$I,{D}!$B:$B,$A{r},{D}!$M:$M,"belirsizlik açık")', BAG, fmt)
        _h(ws, r, 7, f'=SUMIFS({D}!$I:$I,{D}!$B:$B,$A{r},{D}!$M:$M,"onay bekliyor")', BAG, fmt)
        bul = f"INDEX({FY}!$D:$D,MATCH($A{r},{FY}!$A:$A,0))"
        _h(ws, r, 8, f'=IFERROR(IF({bul}&""="","POZ YOK",{bul}),"POZ YOK")', BAG)
        fiyat = f"INDEX({FY}!$E:$E,MATCH($A{r},{FY}!$A:$A,0))"
        _h(ws, r, 9, f'=IFERROR(IF({fiyat}&""="","",{fiyat}),"")', BAG, "#,##0.00")
        _h(ws, r, 10, f'=IF(I{r}="","",D{r}*I{r})', NORMAL, "#,##0.00")
        _h(ws, r, 11, f'=IFERROR(INDEX({FY}!$H:$H,MATCH($A{r},{FY}!$A:$A,0)),"fiyat satırı yok")', BAG)
        _h(ws, r, 12, f'=IF(E{r}>0,"kontrol gerekli",IF(F{r}>0,"belirsizlik açık",IF(K{r}<>"tamam",K{r},'
                      f'IF(G{r}>0,"onay bekliyor","tamam"))))', KALIN)
    son = n + 1
    ws.conditional_formatting.add(f"L2:L{son}", FormulaRule(formula=['$L2="tamam"'], fill=YESIL))
    ws.conditional_formatting.add(f"L2:L{son}", FormulaRule(formula=['$L2<>"tamam"'], fill=PEMBE))
    t = n + 3
    _h(ws, t, 9, "Toplam (fiyatı girilenler)", KALIN)
    _h(ws, t, 10, f"=SUM(J2:J{son})", KALIN, "#,##0.00")
    _h(ws, t + 1, 9, "Teklif durumu", KALIN)
    _h(ws, t + 1, 10, f"={TD}!$B$18", KALIN)
    ws.cell(row=t + 3, column=1, value="Not: Miktarlar Detay metrajdan formülle gelir; poz ve fiyat Fiyatlar "
            "sayfasından okunur. 'Teklif durumu' TEKLİFE HAZIR değilse toplam tutar teklif olarak kullanılmamalıdır."
            ).font = NORMAL
    ws.freeze_panes = "B2"


# ---------------------------------------------------------------- Fiyatlar
def _fiyat(ws, kodlar, fiyat_listesi=None):
    from .fiyat import esle
    ws["A1"] = "FİYAT TABLOSU — yalnızca SARI hücreleri doldurun"
    ws["A1"].font = Font(name=F, bold=True, size=12)
    for i, a in enumerate([
        "Poz no: kullandığınız birim fiyat listesindeki numarayı AYNEN yazın; bilinmiyorsa BOŞ bırakın. "
        "Araç poz numarası üretmez.",
        "Birim fiyat: TL, KDV hariç, kalemin birimine göre. Fiyat girildiyse Fiyat tarihi ve Kaynak ZORUNLUDUR "
        "(eksikse satır kırmızı olur ve teklif tamamlanmamış sayılır).",
        "Biçim örneği → Poz no: <listedeki numara>   Birim fiyat: 1250,00   Fiyat tarihi: 2026-11-18   "
        "Kaynak: <liste veya teklif adı>",
    ], 2):
        ws.cell(row=i, column=1, value=a).font = NORMAL
    _baslik(ws, FIYAT_ILK - 1, ["Kalem kodu", "Kalem", "Birim", "Poz no", "Birim fiyat (TL)", "Fiyat tarihi", "Kaynak",
                                "Fiyat durumu"], [30, 52, 7, 18, 16, 14, 40, 20])
    dv_f = DataValidation(type="decimal", operator="greaterThan", formula1="0", allow_blank=True,
                          error="Birim fiyat 0'dan büyük bir sayı olmalı", showErrorMessage=True)
    dv_t = DataValidation(type="custom", formula1=f"OR(ISNUMBER(F{FIYAT_ILK}),LEN(F{FIYAT_ILK})=10)",
                          allow_blank=True, error="Tarih girin (tarih hücresi veya yyyy-aa-gg)",
                          showErrorMessage=True)
    ws.add_data_validation(dv_f)
    ws.add_data_validation(dv_t)
    for r, (kod, kalem, birim) in enumerate(kodlar, FIYAT_ILK):
        _h(ws, r, 1, kod)
        _h(ws, r, 2, kalem)
        _h(ws, r, 3, birim)
        e = esle(kod, fiyat_listesi) if fiyat_listesi else None
        degerler = [e["poz"] or None, e["fiyat"], e["tarih"], e["kaynak"]] if e else [None] * 4
        for (c, fmt), v in zip([(4, "@"), (5, "#,##0.00"), (6, "@"), (7, None)], degerler):
            _h(ws, r, c, v, GIRDI, fmt, SARI)
        _h(ws, r, 8, f'=IF(E{r}="","fiyat yok",IF(OR(F{r}="",G{r}=""),"tarih/kaynak eksik",'
                     f'IF(AND(D{r}="",{ONAY_HUCRE}="evet"),"poz yok","tamam")))', BAG)
        dv_f.add(f"E{r}")
        dv_t.add(f"F{r}")
    son = FIYAT_ILK + len(kodlar) - 1
    ws.conditional_formatting.add(f"F{FIYAT_ILK}:G{son}",
                                  FormulaRule(formula=[f'AND($E{FIYAT_ILK}<>"",F{FIYAT_ILK}="")'], fill=KIRMIZI))
    ws.freeze_panes = f"A{FIYAT_ILK}"


# ---------------------------------------------------------------- Doğrulama
def _dogrulama(ws, m: Metraj, kodlar):
    ws.column_dimensions["A"].width = 40
    ws["A1"] = "DOĞRULAMA"
    ws["A1"].font = Font(name=F, bold=True, size=12)
    _h(ws, 3, 1, "Referans doğrulama sonucu", KALIN)
    _baslik(ws, 5, ["İç tutarlılık kontrolü", "Metrajdan", "Ağ modelinden", "Fark", "Durum"], [40, 16, 16, 12, 14])
    kontroller = [
        ("Σ boru uzunluğu (m)", f'=SUMIFS({D}!$I:$I,{D}!$H:$H,"m",{D}!$B:$B,"BORU-*")'),
        ("Sprinkler adedi", f'=SUMIFS({D}!$I:$I,{D}!$B:$B,"SPR-K*")'),
        ("Dolap/hidrant adedi", f'=SUMIFS({D}!$I:$I,{D}!$B:$B,"CIKIS-*")'),
    ]
    for r, (ad, formul) in enumerate(kontroller, 6):
        _h(ws, r, 1, ad)
        _h(ws, r, 2, formul, BAG, "#,##0.00")
        h = _h(ws, r, 3, m.model[ad], GIRDI, "#,##0.00")
        h.comment = Comment("Kaynak: hidrolik ağ modeli (yangin.YanginAgi), metraj üretimi sırasında okundu.", "tesisat")
        _h(ws, r, 4, f"=B{r}-C{r}", NORMAL, "#,##0.00")
        _h(ws, r, 5, f'=IF(ABS(D{r})<0.001,"TUTARLI","FARK VAR")', KALIN)
    ws.cell(row=10, column=1, value="İç tutarlılık doğruluk kanıtı değildir; yalnızca modelin metraja eksiksiz "
            "aktarıldığını gösterir.").font = NORMAL
    r0 = 12
    ws.cell(row=r0, column=1, value="Referans (kontrol edilmiş) metraj ile karşılaştırma").font = KALIN
    if m.referans is None:
        _h(ws, 3, 2, "DOĞRULANMADI", Font(name=F, bold=True, color="B3261E"))
        ws.cell(row=r0 + 1, column=1, value="Referans verilmedi → karşılaştırma yapılmadı. "
                "Kullanım: python -m tesisat metraj proje.yaml --referans kontrol_edilmis.csv").font = NORMAL
        return
    _baslik(ws, r0 + 1, ["Kalem kodu", "Metraj", "Referans", "Fark", "Fark %", "Tolerans", "Durum"],
            [40, 16, 16, 12, 10, 10, 16])
    tum = sorted(set(k for k, *_ in kodlar) | set(m.referans))
    birim = {k: b for k, _, b in kodlar}
    for i, kod in enumerate(tum, r0 + 2):
        _h(ws, i, 1, kod)
        _h(ws, i, 2, f"=SUMIFS({D}!$I:$I,{D}!$B:$B,$A{i})", BAG, "#,##0.00")
        h = _h(ws, i, 3, m.referans.get(kod, 0.0), GIRDI, "#,##0.00")
        h.comment = Comment("Kaynak: kullanıcının verdiği kontrol edilmiş metraj (--referans).", "tesisat")
        _h(ws, i, 4, f"=B{i}-C{i}", NORMAL, "#,##0.00")
        _h(ws, i, 5, f'=IF(C{i}=0,"",D{i}/C{i})', NORMAL, "0.0%")
        _h(ws, i, 6, 0.02 if birim.get(kod, "m") == "m" else 0, GIRDI, "0.0%")
        _h(ws, i, 7, f'=IF(C{i}=0,IF(B{i}=0,"TUTARLI","REFERANSTA YOK"),IF(ABS(D{i})<=F{i}*C{i}+0.000001,'
                     f'"TUTARLI","FARK VAR"))', KALIN)
    ilk, son = r0 + 2, r0 + 1 + len(tum)
    _h(ws, 3, 2, f'=IF(COUNTIF(G{ilk}:G{son},"TUTARLI")={len(tum)},"REFERANSLA TUTARLI","FARK VAR")', KALIN)
