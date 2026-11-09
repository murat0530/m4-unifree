"""HTML (yazdırılabilir) ve JSON rapor üretimi."""
from __future__ import annotations

import datetime as _dt
import html
import json

from .ortak import BILGI, HATA, UYARI, ModulSonucu

_CSS = """
:root{--ink:#1d2433;--muted:#5b6475;--line:#d9dde5;--bg:#ffffff;--soft:#f4f6f9;
--err:#b3261e;--errbg:#fdecea;--warn:#8a5a00;--warnbg:#fff4dc;--ok:#1e6b34;--okbg:#e7f5ec;--info:#1f4e8c;--infobg:#e8f0fb}
*{box-sizing:border-box}body{font:13px/1.45 "Segoe UI",Roboto,Arial,sans-serif;color:var(--ink);background:var(--bg);margin:0}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:32px 0 8px;padding-bottom:4px;border-bottom:2px solid var(--ink)}
h3{font-size:14px;margin:20px 0 6px}.muted{color:var(--muted)}
.kart{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}.kart div{flex:1 1 160px;border:1px solid var(--line);border-radius:6px;padding:10px 12px;background:var(--soft)}
.kart b{display:block;font-size:20px}.kart .e b{color:var(--err)}.kart .w b{color:var(--warn)}.kart .o b{color:var(--ok)}
.tablo{overflow-x:auto}table{border-collapse:collapse;width:100%;margin:4px 0 12px;font-variant-numeric:tabular-nums}
th,td{border:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}th{background:var(--soft);font-weight:600}
td.n{text-align:right}tr.HATA td{background:var(--errbg)}tr.UYARI td{background:var(--warnbg)}tr.BİLGİ td{background:var(--infobg)}
.etiket{display:inline-block;padding:1px 6px;border-radius:3px;font-size:11px;font-weight:700}
.HATA .etiket{background:var(--err);color:#fff}.UYARI .etiket{background:var(--warn);color:#fff}.BİLGİ .etiket{background:var(--info);color:#fff}
.durum-ok{color:var(--ok);font-weight:600}.durum-kotu{color:var(--err);font-weight:700}
.imza{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-top:40px}
.imza div{border-top:1px solid var(--ink);padding-top:6px;min-height:70px}
.not{border-left:4px solid var(--warn);background:var(--warnbg);padding:8px 12px;margin:16px 0}
@media print{main{max-width:none;padding:0}h2{break-after:avoid}table{break-inside:auto}tr{break-inside:avoid}.kart div{background:none}}
"""


def _hucre(v) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f'<td class="n">{html.escape(str(v))}</td>'
    s = html.escape(str(v))
    if s in ("OK",):
        return f'<td class="durum-ok">{s}</td>'
    if s in ("YETERSİZ",) or "aşımı" in s:
        return f'<td class="durum-kotu">{s}</td>'
    return f"<td>{s}</td>"


def _tablo(t) -> str:
    bas = "".join(f"<th>{html.escape(str(k))}</th>" for k in t.kolonlar)
    govde = "".join("<tr>" + "".join(_hucre(v) for v in satir) + "</tr>" for satir in t.satirlar)
    return f'<h3>{html.escape(t.baslik)}</h3><div class="tablo"><table><thead><tr>{bas}</tr></thead><tbody>{govde}</tbody></table></div>'


def sayac(sonuclar: list[ModulSonucu]) -> dict:
    c = {HATA: 0, UYARI: 0, BILGI: 0}
    for s in sonuclar:
        for b in s.bulgular:
            c[b.seviye] += 1
    return c


def html_rapor(proje: dict, sonuclar: list[ModulSonucu]) -> str:
    meta = proje.get("proje", {}) or {}
    bina = proje.get("bina", {}) or {}
    c = sayac(sonuclar)
    tarih = meta.get("tarih") or _dt.date.today().isoformat()
    p = []
    p.append(f"<!doctype html><html lang='tr'><head><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>{html.escape(meta.get('ad', 'Tesisat Hesap Raporu'))}</title><style>{_CSS}</style></head><body><main>")
    p.append(f"<h1>{html.escape(meta.get('ad', 'Tesisat Hesap Raporu'))}</h1>")
    alt = " · ".join(html.escape(str(x)) for x in [meta.get("isveren"), meta.get("adres"), f"Tarih: {tarih}",
                                                    f"Revizyon: {meta.get('revizyon', '0')}"] if x)
    p.append(f"<div class='muted'>{alt}</div>")
    durum = "UYGUN DEĞİL" if c[HATA] else "UYGUN"
    p.append("<div class='kart'>"
             f"<div class='{'e' if c[HATA] else 'o'}'><span class='muted'>Genel durum</span><b>{durum}</b></div>"
             f"<div class='e'><span class='muted'>Hata</span><b>{c[HATA]}</b></div>"
             f"<div class='w'><span class='muted'>Uyarı</span><b>{c[UYARI]}</b></div>"
             f"<div><span class='muted'>Bilgi</span><b>{c[BILGI]}</b></div></div>")
    if bina:
        p.append("<h2>Bina bilgileri</h2><div class='tablo'><table><tbody>")
        for k, v in bina.items():
            p.append(f"<tr><th>{html.escape(str(k))}</th>{_hucre(v)}</tr>")
        p.append("</tbody></table></div>")

    tum = [b for s in sonuclar for b in s.bulgular]
    sira = {HATA: 0, UYARI: 1, BILGI: 2}
    tum.sort(key=lambda b: sira[b.seviye])
    p.append("<h2>Kontrol bulguları</h2>")
    if tum:
        p.append("<div class='tablo'><table><thead><tr><th>Seviye</th><th>Modül</th><th>Nesne</th>"
                 "<th>Bulgu</th><th>Dayanak</th></tr></thead><tbody>")
        for b in tum:
            p.append(f"<tr class='{b.seviye}'><td><span class='etiket'>{b.seviye}</span></td>"
                     f"<td>{html.escape(b.modul)}</td><td>{html.escape(b.nesne)}</td>"
                     f"<td>{html.escape(b.mesaj)}</td><td>{html.escape(b.referans)}</td></tr>")
        p.append("</tbody></table></div>")
    else:
        p.append("<p class='durum-ok'>Bulgu yok — tüm kontroller sağlandı.</p>")

    for s in sonuclar:
        p.append(f"<h2>{html.escape(s.baslik)}</h2>")
        if s.ozet:
            p.append("<div class='tablo'><table><tbody>" + "".join(
                f"<tr><th>{html.escape(str(k))}</th>{_hucre(v)}</tr>" for k, v in s.ozet.items()) + "</tbody></table></div>")
        for t in s.tablolar:
            p.append(_tablo(t))

    p.append("<div class='not'><b>Not:</b> Bu rapor hesap yardımcı aracı ile üretilmiştir. Kullanılan tablo "
             "değerlerinin kaynakları <code>tesisat/DOGRULAMA.md</code> dosyasında belgelenmiştir. Proje onayı "
             "ve uygulamaya ilişkin sorumluluk projeyi imzalayan yetkili makine mühendisine aittir.</div>")
    p.append("<div class='imza'>" + "".join(
        f"<div><b>{r}</b><br><span class='muted'>{html.escape(str(meta.get(a, '')))}</span></div>"
        for r, a in [("Hazırlayan", "hazirlayan"), ("Kontrol eden", "kontrol"), ("Onay", "onay")]) + "</div>")
    p.append("</main></body></html>")
    return "".join(p)


def json_rapor(proje: dict, sonuclar: list[ModulSonucu]) -> str:
    return json.dumps({"proje": proje.get("proje", {}), "bina": proje.get("bina", {}),
                       "sayac": sayac(sonuclar), "moduller": [s.sozluk() for s in sonuclar]},
                      ensure_ascii=False, indent=2, default=str)
