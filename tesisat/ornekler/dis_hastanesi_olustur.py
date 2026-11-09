"""Diş hastanesi — tip kat yangın tesisatı (VARSAYIMSAL plan; gerçek mimari plan gelince
MAHALLER listesi plandan alınan koordinatlarla değiştirilmelidir).

Akış:
  1. Mahaller (sınır çokgeni + tip) tanımlanır → tehlike sınıfı kütüphaneden atanır
     (BYKHY Ek-1/B: Hastaneler → OT1; laboratuvar → OT2; tesisat odası → OT3 ...)
  2. Her mahale, sınıfının kurallarını (aralık, alan, duvar) sağlayan en az sprinklerli
     yerleşim önerilir (kapsama.yerlesim_oner)
  3. Koridor boyunca ana dağıtım + her mahale branşman ile ağaç ağ kurulur; çaplar
     akış yönünde beslenen sprinkler sayısına göre seçilir
  4. Tasarım alanları otomatik üretilir (en uzak / en yüksek kot / dolap eşzamanlı)

Çalıştırma:  python ornekler/dis_hastanesi_olustur.py  → ornekler/dis_hastanesi.yaml
"""
import math
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tesisat import kapsama  # noqa: E402
from tesisat.ortak import kurallari_yukle  # noqa: E402

KAT_KOTU = 8.0          # 3. kat döşeme kotu (m, ±0,00 = zemin kat)
TAVAN = 3.0             # döşemeden sprinkler deflektörüne
POMPA_KOT = -4.0        # bodrum pompa dairesi
KORIDOR_Y = 9.0         # ana dağıtım hattı ekseni (koridor ortası)
KOLON_X = 15.0          # yangın kolonu (şaft) konumu

# (id, ad, tip, x0, y0, x1, y1) — dikdörtgen mahaller, metre
MAHALLER = [
    ("KOR", "Poliklinik koridoru", "poliklinik", 0, 8, 30, 10),
    ("U1", "Diş tedavi ünitesi 1", "muayene_tedavi", 0, 10, 6, 16),
    ("U2", "Diş tedavi ünitesi 2", "muayene_tedavi", 6, 10, 12, 16),
    ("U3", "Diş tedavi ünitesi 3", "muayene_tedavi", 12, 10, 18, 16),
    ("U4", "Cerrahi müdahale odası", "ameliyathane", 18, 10, 24, 16),
    ("STR", "Sterilizasyon", "sterilizasyon", 24, 10, 30, 16),
    ("BEK", "Hasta bekleme", "poliklinik", 0, 16, 18, 20),
    ("RON", "Panoramik röntgen", "goruntuleme", 18, 16, 24, 20),
    ("ARS", "Hasta dosya arşivi", "arsiv", 24, 16, 30, 20),
    ("LAB", "Diş protez laboratuvarı", "dis_protez_lab", 0, 0, 10, 8),
    ("WC", "WC'ler", "islak_hacim", 10, 0, 14, 8),
    ("TES", "Mekanik tesisat odası", "tesisat_odasi", 14, 0, 18, 8),
    ("DEP", "Sarf malzeme deposu", "depo", 18, 0, 22, 8),
    ("IDR", "İdari ofisler", "buro", 22, 0, 30, 8),
]


def cap_sec(n: int) -> str:
    """Beslenen sprinkler sayısına göre başlangıç çapı (hidrolik hesapla doğrulanır)."""
    for sinir, dn in [(2, "25"), (3, "32"), (5, "40"), (9, "50"), (18, "65"), (48, "80")]:
        if n <= sinir:
            return dn
    return "100"


def main():
    K = kurallari_yukle()["yangin"]
    mahaller, hatlar = [], []
    yerlesim = {}
    for mid, ad, tip, x0, y0, x1, y1 in MAHALLER:
        pol = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        mahaller.append({"id": mid, "ad": ad, "tip": tip, "poligon": pol})
        kayit = K["mahal_tipleri"][tip]
        if kayit.get("muaf"):
            mahaller[-1]["muaf_nedeni"] = "Yanıcı malzeme içermeyen ıslak hacim"
            continue
        sc = K["tehlike_siniflari"][kayit["sinif"]]
        smax = sc["max_aralik_m"]
        dmax = min(K["yerlesim"]["duvar_max_standart_m"], smax / 2)
        yerlesim[mid] = kapsama.yerlesim_oner([tuple(p) for p in pol], smax, sc["max_alan_m2"], dmax,
                                              on_ek=f"{mid}-S")

    # --- ağ: pompa → kolon → koridor ana hattı (batı/doğu) → mahal branşmanları ---------
    z_tavan = KAT_KOTU + TAVAN
    toplam = sum(len(v) for v in yerlesim.values())
    hatlar.append({"id": "POMPA", "ust": None, "uzunluk_m": 5.0, "kot_farki_m": 0.0, "cap": "100",
                   "parcalar": {"kelebek_vana": 2, "cekvalf": 1, "dirsek_90": 3}, "vana_noktasi": True})
    hatlar.append({"id": "KOLON", "ust": "POMPA", "uzunluk_m": z_tavan - 0.2 - POMPA_KOT + 6.0,
                   "kot_farki_m": z_tavan - 0.2 - POMPA_KOT, "cap": "100",
                   "parcalar": {"alarm_vanasi": 1, "dirsek_90": 2}, "vana_noktasi": True,
                   "aciklama": "Alarm vana istasyonu + kolon (bodrum → 3. kat)"})
    hatlar.append({"id": "KAT-VANA", "ust": "KOLON", "uzunluk_m": 1.5, "kot_farki_m": 0.0, "cap": "100",
                   "parcalar": {"kelebek_vana": 1, "te_donus": 1}, "vana_noktasi": True,
                   "aciklama": "Kat zon vanası + akış anahtarı (md. 96/7)"})

    # Branşman çıkış noktaları: her mahalin koridora en yakın x'i (mahal merkezi)
    cikislar = []
    for mid, pts in yerlesim.items():
        xs = [p[0] for p in pts.values()]
        cikislar.append((round(sum(xs) / len(xs), 2), mid))

    for yon, filtre, anahtar in [("B", lambda x: x < KOLON_X, lambda c: -c[0]),
                                 ("D", lambda x: x >= KOLON_X, lambda c: c[0])]:
        grup = sorted([c for c in cikislar if filtre(c[0])], key=anahtar)
        onceki_x, onceki_id = KOLON_X, "KAT-VANA"
        kalan = [sum(len(yerlesim[m]) for _, m in grup[k:]) for k in range(len(grup))]
        for k, (x, mid) in enumerate(grup):
            hid = f"ANA-{yon}{k + 1}"
            hatlar.append({"id": hid, "ust": onceki_id, "uzunluk_m": round(abs(x - onceki_x), 2) or 0.3,
                           "kot_farki_m": 0.0, "cap": cap_sec(kalan[k]),
                           "parcalar": {"te_donus": 1} if k == 0 else {}})
            # mahal içi zincir: koridora en yakın sprinklerden başlayarak en yakın komşu
            pts = dict(yerlesim[mid])
            giris = (x, KORIDOR_Y)
            sira = []
            cur = giris
            while pts:
                sid = min(pts, key=lambda q: abs(pts[q][0] - cur[0]) + abs(pts[q][1] - cur[1]))
                sira.append((sid, pts.pop(sid)))
                cur = sira[-1][1]
            ust, cur = hid, giris
            for n, (sid, p) in enumerate(sira):
                bid = f"{mid}-B{n + 1}"
                hatlar.append({"id": bid, "ust": ust, "uzunluk_m": round(abs(p[0] - cur[0]) + abs(p[1] - cur[1]), 2),
                               "kot_farki_m": 0.0, "cap": cap_sec(len(sira) - n),
                               "parcalar": {"te_donus": 1} if n == 0 else {"dirsek_90": 1}})
                hatlar.append({"id": sid, "ust": bid, "uzunluk_m": 0.2, "kot_farki_m": -0.2, "cap": "25",
                               "parcalar": {"te_donus": 1}, "sprinkler": True, "mahal": mid,
                               "konum": [p[0], p[1]]})
                ust, cur = bid, p
            onceki_x, onceki_id = x, hid

    # Yangın dolapları — ıslak sprinkler branşmanından beslenir (md. 94/1-b-2 → 45 m)
    for did, x in [("YD-1", 1.0), ("YD-2", 29.0)]:
        hatlar.append({"id": f"{did}-HAT", "ust": "KAT-VANA", "uzunluk_m": abs(x - KOLON_X) + 1.6,
                       "kot_farki_m": -(TAVAN - 0.2 - 1.6), "cap": "50",
                       "parcalar": {"te_donus": 1, "dirsek_90": 2, "surgulu_vana": 1}})
        hatlar.append({"id": did, "ust": f"{did}-HAT", "uzunluk_m": 1.0, "kot_farki_m": 0.0, "cap": "25",
                       "parcalar": {"dirsek_90": 1}, "cikis": "dolap_yari_sert", "kat": "3",
                       "mahal": "KOR", "konum": [x, 9.6], "sprinkler_hattindan": True})

    proje = {
        "proje": {"ad": "Ağız ve Diş Sağlığı Hastanesi — 3. Kat Yangın Tesisatı (ÖN TASARIM)",
                  "isveren": "", "adres": "", "revizyon": "0-ön",
                  "hazirlayan": "Mak. Müh. ...", "kontrol": "", "onay": "",
                  "not": "Mimari plan varsayımsaldır; gerçek plan koordinatları ile güncellenecektir."},
        "bina": {"kullanim": "saglik", "yapi_yuksekligi_m": 22.0, "kapali_alan_m2": 3600,
                 "yatakli": False, "kat_adedi": 6,
                 "sprinkler_gerekcesi": "İşveren kararı — BYKHY md. 96/2 zorunluluğu olmasa da tüm bina sprinklerle korunacak"},
        "kararlar": [
            "Sprinkler yapılacak (işveren kararı).",
            "Tehlike sınıfında ihtiyatlı değer: protez laboratuvarı OT2, arşiv ve depo OT3.",
            "Pompa seçimi, en uzak tasarım alanı + en uzak yangın dolabının hidrolik olarak eşzamanlı "
            "çalıştığı (en elverişsiz) senaryoya göre yapılır.",
        ],
        "yangin": {
            "sistem": "islak",
            "boru_serisi": "CELIK_EN10255_ORTA",
            "kaynak": {"ad": "Yangın pompası çıkışı (bodrum)", "kot_m": POMPA_KOT},
            "sprinkler_varsayilan": {"K": 80},
            "yedek_sprinkler": 6,
            "pompa": {"adet_asil": 1, "adet_yedek": 1, "emme_basinci_bar": 0.2},
            "mahaller": mahaller,
            "kompartimanlar": [{"id": "K3", "ad": "3. kat (tek kompartıman)", "kullanim": "saglik",
                                "mahaller": [m[0] for m in MAHALLER]}],
            "otomatik_senaryo": {"uzun_eksen": "x"},
            "hatlar": hatlar,
        },
    }
    hedef = Path(__file__).with_name("dis_hastanesi.yaml")
    with open(hedef, "w", encoding="utf-8") as f:
        f.write("# dis_hastanesi_olustur.py ile üretilmiştir — VARSAYIMSAL plan.\n")
        f.write("# Hesap: python -m tesisat hesapla ornekler/dis_hastanesi.yaml\n")
        yaml.safe_dump(proje, f, allow_unicode=True, sort_keys=False, width=140)
    print(f"yazıldı: {hedef}  ({toplam} sprinkler, {len(hatlar)} hat)")


if __name__ == "__main__":
    main()
