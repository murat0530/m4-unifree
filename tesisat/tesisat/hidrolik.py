"""Temel akışkanlar mekaniği fonksiyonları (SI birimleri).

- Darcy-Weisbach + Colebrook-White sürtünme kaybı
- Su ve hava fiziksel özellikleri
- Kısmi dolu dairesel kesitte Prandtl-Colebrook debisi (EN 12056-2 Ek B)
- Dikdörtgen kanal eşdeğer çapı (Huebscher)
"""
from __future__ import annotations

import math

G = 9.81  # m/s²

# Su: sıcaklık [°C] → (yoğunluk [kg/m³], kinematik viskozite [m²/s])
_SU = [
    (5, 999.97, 1.519e-6),
    (10, 999.70, 1.307e-6),
    (20, 998.21, 1.004e-6),
    (30, 995.65, 0.801e-6),
    (40, 992.22, 0.658e-6),
    (50, 988.04, 0.553e-6),
    (60, 983.20, 0.474e-6),
    (70, 977.76, 0.413e-6),
    (80, 971.79, 0.365e-6),
]


def su_ozellik(sicaklik_c: float) -> tuple[float, float]:
    """(ρ, ν) — tablodan doğrusal enterpolasyon."""
    t = min(max(sicaklik_c, _SU[0][0]), _SU[-1][0])
    for (t1, r1, n1), (t2, r2, n2) in zip(_SU, _SU[1:]):
        if t1 <= t <= t2:
            w = (t - t1) / (t2 - t1)
            return r1 + w * (r2 - r1), n1 + w * (n2 - n1)
    return _SU[-1][1], _SU[-1][2]


def hava_ozellik(sicaklik_c: float, basinc_pa: float = 101325.0) -> tuple[float, float]:
    """(ρ, ν) — ideal gaz + Sutherland viskozitesi."""
    T = sicaklik_c + 273.15
    rho = basinc_pa / (287.05 * T)
    mu = 1.458e-6 * T ** 1.5 / (T + 110.4)
    return rho, mu / rho


def surtunme_katsayisi(re: float, k_m: float, d_m: float) -> float:
    """Darcy sürtünme katsayısı λ. Laminerde 64/Re, aksi halde Colebrook-White."""
    if re <= 0:
        return 0.0
    if re < 2300:
        return 64.0 / re
    rel = k_m / (3.71 * d_m)
    # Swamee-Jain başlangıç değeri
    f = 0.25 / (math.log10(k_m / (3.7 * d_m) + 5.74 / re ** 0.9)) ** 2
    for _ in range(100):
        yeni = (-2.0 * math.log10(rel + 2.51 / (re * math.sqrt(f)))) ** -2
        if abs(yeni - f) < 1e-12:
            return yeni
        f = yeni
    return f


def boru_akisi(q_m3s: float, d_m: float, k_m: float, rho: float, nu: float) -> dict:
    """Dolu akışlı dairesel boru. Dönüş: v [m/s], Re, λ, R [Pa/m], pd [Pa] (dinamik basınç)."""
    alan = math.pi * d_m ** 2 / 4
    v = q_m3s / alan if alan > 0 else 0.0
    re = v * d_m / nu
    lam = surtunme_katsayisi(re, k_m, d_m)
    pd = rho * v ** 2 / 2
    r = lam / d_m * pd if d_m > 0 else 0.0
    return {"v": v, "Re": re, "lambda": lam, "R": r, "pd": pd}


def kanal_akisi(q_m3s: float, rho: float, nu: float, k_m: float,
                cap_m: float | None = None, en_m: float | None = None, yuk_m: float | None = None) -> dict:
    """Hava kanalı (daire veya dikdörtgen). Sürtünme Huebscher eşdeğer çapı ile,
    dinamik basınç gerçek kesit hızıyla hesaplanır."""
    if cap_m:
        return boru_akisi(q_m3s, cap_m, k_m, rho, nu) | {"De": cap_m}
    de = esdeger_cap(en_m, yuk_m)
    s = boru_akisi(q_m3s, de, k_m, rho, nu)
    v = q_m3s / (en_m * yuk_m)
    s["v"] = v
    s["pd"] = rho * v ** 2 / 2
    s["De"] = de
    return s


def esdeger_cap(a_m: float, b_m: float) -> float:
    """Huebscher: De = 1,30·(ab)^0,625 / (a+b)^0,25 (eşit sürtünme, eşit debi)."""
    return 1.30 * (a_m * b_m) ** 0.625 / (a_m + b_m) ** 0.25


# ---------------------------------------------------------------- kısmi dolu
def _kesit(d_m: float, h_d: float) -> tuple[float, float]:
    """Kısmi dolu daire: (ıslak alan, ıslak çevre)."""
    h_d = min(max(h_d, 1e-9), 1.0)
    teta = 2 * math.acos(1 - 2 * h_d)
    alan = d_m ** 2 / 8 * (teta - math.sin(teta))
    cevre = d_m * teta / 2
    return alan, cevre


def kismi_dolu_debi(d_m: float, h_d: float, egim: float, k_m: float = 0.001,
                    nu: float = 1.31e-6) -> tuple[float, float]:
    """Prandtl-Colebrook (EN 12056-2 Ek B) — (Q [m³/s], v [m/s]). egim: m/m."""
    if egim <= 0:
        return 0.0, 0.0
    alan, cevre = _kesit(d_m, h_d)
    dh = 4 * alan / cevre
    s = math.sqrt(2 * G * dh * egim)
    v = -2 * s * math.log10(2.51 * nu / (dh * s) + k_m / (3.71 * dh))
    return v * alan, v


def dolma_orani(q_m3s: float, d_m: float, egim: float, k_m: float = 0.001,
                nu: float = 1.31e-6) -> tuple[float, float]:
    """Verilen debi için h/d ve hız (ikiye bölme). Boru taşarsa h/d > 1 döner."""
    q_tam, _ = kismi_dolu_debi(d_m, 0.999, egim, k_m, nu)
    if q_m3s >= q_tam:
        return q_m3s / q_tam if q_tam > 0 else float("inf"), q_m3s / (math.pi * d_m ** 2 / 4)
    lo, hi = 1e-4, 0.999
    for _ in range(80):
        orta = (lo + hi) / 2
        q, _ = kismi_dolu_debi(d_m, orta, egim, k_m, nu)
        if q < q_m3s:
            lo = orta
        else:
            hi = orta
    h = (lo + hi) / 2
    _, v = kismi_dolu_debi(d_m, h, egim, k_m, nu)
    return h, v
