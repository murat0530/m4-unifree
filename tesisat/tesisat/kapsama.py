"""Sprinkler kapsama alanı geometrisi (plan üzerinde).

Her mahal bir çokgen, her sprinkler bir (x, y) noktasıdır. Mahal, sprinklerler
arasında "en yakın sprinkler" kuralıyla bölünür (çokgene kırpılmış Voronoi
hücreleri). Böylece her sprinklerin GERÇEKTE koruduğu alan bulunur ve hidrolik
hesapta bu alan kullanılır (Q_min = yoğunluk × hücre alanı).

Kontroller (TS EN 12845 md. 12.2–12.4):
  * sprinkler başına alan ≤ tehlike sınıfının sınırı
  * mahal içinde korunmayan nokta kalmaması: her noktanın en yakın sprinklere
    uzaklığı ≤ R_max = √((S_max/2)² + duvar_max²)
  * komşu sprinkler aralığı ≤ S_max, iki sprinkler arası ≥ 2,0 m
  * duvara uzaklık ≤ min(2,0 m, S_max/2)  (şaşırtmalı: 2,3 m; açık kiriş: 1,5 m)

Hesap bağımlılıksızdır (yalnız standart kütüphane). Kırpma Sutherland–Hodgman
yarım düzlem kırpmasıdır; içbükey mahallerde de alan doğru hesaplanır.
"""
from __future__ import annotations

import math

Nokta = tuple[float, float]


def alan(p: list[Nokta]) -> float:
    s = 0.0
    for (x1, y1), (x2, y2) in zip(p, p[1:] + p[:1]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def _kirp(p: list[Nokta], a: float, b: float, c: float) -> list[Nokta]:
    """a·x + b·y ≤ c yarım düzlemi ile kırp."""
    if not p:
        return p
    cikti = []
    for i in range(len(p)):
        s, e = p[i - 1], p[i]
        ds, de = a * s[0] + b * s[1] - c, a * e[0] + b * e[1] - c
        if de <= 0:
            if ds > 0:
                t = ds / (ds - de)
                cikti.append((s[0] + t * (e[0] - s[0]), s[1] + t * (e[1] - s[1])))
            cikti.append(e)
        elif ds <= 0:
            t = ds / (ds - de)
            cikti.append((s[0] + t * (e[0] - s[0]), s[1] + t * (e[1] - s[1])))
    return cikti


def hucreler(poligon: list[Nokta], noktalar: list[Nokta]) -> list[list[Nokta]]:
    sonuc = []
    for i, (xi, yi) in enumerate(noktalar):
        h = list(poligon)
        for j, (xj, yj) in enumerate(noktalar):
            if i == j:
                continue
            a, b = xj - xi, yj - yi
            c = (xj * xj + yj * yj - xi * xi - yi * yi) / 2
            h = _kirp(h, a, b, c)
            if not h:
                break
        sonuc.append(h)
    return sonuc


def icinde(p: Nokta, poligon: list[Nokta]) -> bool:
    x, y = p
    ic = False
    for (x1, y1), (x2, y2) in zip(poligon, poligon[1:] + poligon[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            ic = not ic
    return ic


def nokta_dogru_parcasi(p: Nokta, a: Nokta, b: Nokta) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _ortak_kenar(h1: list[Nokta], h2: list[Nokta], tol: float = 1e-6) -> float:
    """İki hücrenin paylaştığı kenar uzunluğu (komşuluk testi)."""
    toplam = 0.0
    for a, b in zip(h1, h1[1:] + h1[:1]):
        for c, d in zip(h2, h2[1:] + h2[:1]):
            if (math.dist(a, d) < tol and math.dist(b, c) < tol) or (math.dist(a, c) < tol and math.dist(b, d) < tol):
                toplam += math.dist(a, b)
    return toplam


def mahal_analizi(poligon: list[Nokta], spr: dict[str, Nokta], s_max: float, duvar_max: float,
                  min_aralik: float, alan_max: float) -> dict:
    """Bir mahal için hücreler, alanlar ve kural ihlalleri."""
    idler = list(spr)
    noktalar = [spr[i] for i in idler]
    hc = hucreler(poligon, noktalar)
    alanlar = {i: alan(h) for i, h in zip(idler, hc)}
    r_max = math.hypot(s_max / 2, min(duvar_max, s_max / 2))
    ihlal = []

    for i, p in zip(idler, noktalar):
        if not icinde(p, poligon):
            ihlal.append(("disarida", i, f"Sprinkler mahal sınırı dışında ({p[0]:.2f}, {p[1]:.2f})"))
    for i in idler:
        if alanlar[i] > alan_max + 1e-6:
            ihlal.append(("alan", i, f"Koruduğu alan {alanlar[i]:.2f} m² > {alan_max:g} m²"))
    # korunmayan bölge: hücre köşesinin sprinklere uzaklığı
    korunmayan, gorulen = [], set()
    for i, p, h in zip(idler, noktalar, hc):
        for v in h:
            d = math.dist(p, v)
            anahtar = (round(v[0], 2), round(v[1], 2))
            if d > r_max + 1e-6 and anahtar not in gorulen:
                gorulen.add(anahtar)
                korunmayan.append((i, v, d))
    for i, v, d in sorted(korunmayan, key=lambda t: -t[2])[:20]:
        ihlal.append(("korunmayan", i, f"({v[0]:.2f}, {v[1]:.2f}) noktası en yakın sprinklere {d:.2f} m "
                      f"> {r_max:.2f} m — korunmayan bölge"))
    # aralıklar
    for a in range(len(idler)):
        for b in range(a + 1, len(idler)):
            d = math.dist(noktalar[a], noktalar[b])
            if d < min_aralik - 1e-6:
                ihlal.append(("yakin", idler[a], f"{idler[b]} ile arası {d:.2f} m < {min_aralik:g} m"))
            elif d > s_max + 1e-6 and _ortak_kenar(hc[a], hc[b]) > 0.2:
                ihlal.append(("aralik", idler[a], f"Komşu {idler[b]} ile arası {d:.2f} m > {s_max:g} m"))
    # duvar mesafesi: her duvarı örnekle, en yakın sprinklerin duvara uzaklığı
    duvar_ihlal = {}
    for k, (a, b) in enumerate(zip(poligon, poligon[1:] + poligon[:1])):
        L = math.dist(a, b)
        n = max(2, int(L / 0.25))
        for t in range(n + 1):
            q = (a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n)
            j = min(range(len(noktalar)), key=lambda m: math.dist(q, noktalar[m]))
            d = nokta_dogru_parcasi(noktalar[j], a, b)
            if d > duvar_max + 1e-6:
                anahtar = (idler[j], k)
                duvar_ihlal[anahtar] = max(d, duvar_ihlal.get(anahtar, 0))
    for (i, k), d in duvar_ihlal.items():
        ihlal.append(("duvar", i, f"{k + 1}. duvara uzaklık {d:.2f} m > {duvar_max:g} m"))

    toplam = sum(alanlar.values())
    return {"idler": idler, "hucreler": dict(zip(idler, hc)), "alanlar": alanlar, "ihlaller": ihlal,
            "mahal_alani": alan(poligon), "hucre_toplami": toplam, "r_max": r_max,
            "korunmayan": korunmayan, "_konum": dict(spr)}


def sinir_kutusu(hucre_listesi: list[list[Nokta]]) -> tuple[float, float]:
    xs = [x for h in hucre_listesi for x, _ in h]
    ys = [y for h in hucre_listesi for _, y in h]
    if not xs:
        return 0.0, 0.0
    return max(xs) - min(xs), max(ys) - min(ys)


# ---------------------------------------------------------------- çizim (SVG)
def svg_plan(baslik: str, poligon: list[Nokta], analiz: dict, alan_max: float,
             acik: set[str] | None = None, dolaplar: list[tuple[str, Nokta]] | None = None,
             genislik: int = 860) -> str:
    from html import escape
    xs = [p[0] for p in poligon]
    ys = [p[1] for p in poligon]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    pad = 30
    olcek = (genislik - 2 * pad) / max(x1 - x0, 1e-6)
    yuk = (y1 - y0) * olcek + 2 * pad + 40

    def T(p):  # plan → ekran (y yukarı)
        return pad + (p[0] - x0) * olcek, pad + (y1 - p[1]) * olcek

    def yol(pp):
        return " ".join(f"{a:.1f},{b:.1f}" for a, b in map(T, pp))

    acik = acik or set()
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {genislik} {yuk:.0f}" '
         f'role="img" aria-label="{escape(baslik)}" style="width:100%;height:auto;max-width:{genislik}px;'
         f'background:#fff;border:1px solid #d9dde5;border-radius:6px">']
    for i in analiz["idler"]:
        h = analiz["hucreler"][i]
        if not h:
            continue
        oran = analiz["alanlar"][i] / alan_max
        renk = "#cfe9d6" if oran <= 0.9 else ("#fde7b0" if oran <= 1.0 + 1e-9 else "#f6b8b3")
        o.append(f'<polygon points="{yol(h)}" fill="{renk}" stroke="#8a93a3" stroke-width="0.6" '
                 f'stroke-dasharray="3 2"/>')
    if acik:
        for i in analiz["idler"]:
            if i in acik and analiz["hucreler"][i]:
                o.append(f'<polygon points="{yol(analiz["hucreler"][i])}" fill="#2f6fd6" fill-opacity="0.18" '
                         f'stroke="#2f6fd6" stroke-width="1.2"/>')
    o.append(f'<polygon points="{yol(poligon)}" fill="none" stroke="#1d2433" stroke-width="2.5"/>')
    for i, v, d in analiz["korunmayan"][:40]:
        x, y = T(v)
        o.append(f'<g stroke="#b3261e" stroke-width="2"><line x1="{x - 5:.1f}" y1="{y - 5:.1f}" '
                 f'x2="{x + 5:.1f}" y2="{y + 5:.1f}"/><line x1="{x - 5:.1f}" y1="{y + 5:.1f}" '
                 f'x2="{x + 5:.1f}" y2="{y - 5:.1f}"/></g>')
    yazi = olcek > 18
    for i in analiz["idler"]:
        sx, sy = T(_spr_konum(analiz, i))
        renk = "#2f6fd6" if i in acik else "#1d2433"
        o.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="3.6" fill="{renk}"/>')
        if yazi:
            o.append(f'<text x="{sx + 5:.1f}" y="{sy - 4:.1f}" font-size="9" fill="#1d2433" '
                     f'font-family="Arial">{escape(i)}</text>')
            o.append(f'<text x="{sx + 5:.1f}" y="{sy + 10:.1f}" font-size="8.5" fill="#5b6475" '
                     f'font-family="Arial">{analiz["alanlar"][i]:.1f} m²</text>')
    for ad, p in dolaplar or []:
        x, y = T(p)
        o.append(f'<rect x="{x - 6:.1f}" y="{y - 6:.1f}" width="12" height="12" fill="#b3261e"/>'
                 f'<text x="{x + 9:.1f}" y="{y + 4:.1f}" font-size="10" fill="#b3261e" '
                 f'font-family="Arial" font-weight="bold">{escape(ad)}</text>')
    # ölçek çubuğu ve lejant
    ly = yuk - 18
    o.append(f'<line x1="{pad}" y1="{ly}" x2="{pad + 5 * olcek:.1f}" y2="{ly}" stroke="#1d2433" stroke-width="2"/>'
             f'<text x="{pad}" y="{ly - 4}" font-size="10" font-family="Arial">5 m</text>')
    lej = [("#cfe9d6", f"≤ %90 sınır"), ("#fde7b0", "%90–100"), ("#f6b8b3", f"> {alan_max:g} m²"),
           ("#2f6fd6", "tasarım alanı")]
    lx = pad + 5 * olcek + 30
    for r, t in lej:
        op = ' fill-opacity="0.35"' if r == "#2f6fd6" else ""
        o.append(f'<rect x="{lx:.1f}" y="{ly - 9}" width="12" height="10" fill="{r}"{op} stroke="#8a93a3"/>'
                 f'<text x="{lx + 16:.1f}" y="{ly}" font-size="10" font-family="Arial">{escape(t)}</text>')
        lx += 110
    o.append("</svg>")
    return "".join(o)


def _spr_konum(analiz, i):
    return analiz["_konum"][i]
