"""Örnek proje üretici: konut altı kapalı otopark sprinkler + yangın dolabı.

Yerleşim (bodrum kat, tavan kotu +3,20 m, pompa çıkışı −1,00 m):
  * 6 branşman (R1…R6), her birinde 6 sprinkler, 3,40 × 3,40 m ızgara
    → sprinkler başına 11,56 m² (OT-2 sınırı 12 m²)
  * Ana dağıtım (CM) branşmanları 3,40 m aralıkla besler (uçtan besleme)
  * 2 adet yarı-sert hortumlu yangın dolabı, aralarında 25 m

Çalıştırma:  python ornekler/ornek_otopark_olustur.py  → ornekler/ornek_otopark.yaml
"""
from pathlib import Path

import yaml

ARALIK = 3.4
BRANS_CAPLARI = ["50", "40", "40", "32", "25", "25"]   # j=1..6 (besleme ucundan uca)
N_BRANS, N_SPR = 6, 6

hatlar = [
    {"id": "POMPA-KOL", "ust": None, "uzunluk_m": 4.0, "kot_farki_m": 0.0, "cap": "100",
     "parcalar": {"kelebek_vana": 2, "cekvalf": 1, "dirsek_90": 2}, "vana_noktasi": True,
     "aciklama": "Pompa basma kollektörü"},
    {"id": "KOLON", "ust": "POMPA-KOL", "uzunluk_m": 4.2, "kot_farki_m": 4.2, "cap": "100",
     "parcalar": {"alarm_vanasi": 1, "kelebek_vana": 1, "dirsek_90": 1}, "vana_noktasi": True,
     "aciklama": "Alarm vana istasyonu + kolon"},
    {"id": "ANA-1", "ust": "KOLON", "uzunluk_m": 15.0, "kot_farki_m": 0.0, "cap": "100",
     "parcalar": {"dirsek_90": 1}, "aciklama": "Tavan ana dağıtım"},
]
for i in range(1, N_BRANS + 1):
    hatlar.append({"id": f"CM-{i}", "ust": "ANA-1" if i == 1 else f"CM-{i - 1}",
                   "uzunluk_m": 1.7 if i == 1 else ARALIK, "kot_farki_m": 0.0,
                   "cap": "80" if i <= 4 else "65",
                   "parcalar": {"te_donus": 1} if i == 1 else {}})
    for j in range(1, N_SPR + 1):
        hatlar.append({"id": f"R{i}-{j}", "ust": f"CM-{i}" if j == 1 else f"R{i}-{j - 1}",
                       "uzunluk_m": ARALIK / 2 if j == 1 else ARALIK, "kot_farki_m": 0.0,
                       "cap": BRANS_CAPLARI[j - 1],
                       "parcalar": {"te_donus": 1} if j == 1 else {}})
        hatlar.append({"id": f"S{i}-{j}", "ust": f"R{i}-{j}", "uzunluk_m": 0.3, "kot_farki_m": -0.3,
                       "cap": "25", "parcalar": {"te_donus": 1}, "sprinkler": True})

# Yangın dolapları (kolon ayağından ayrı hat, dolap vanası +1,60 m)
hatlar += [
    {"id": "YD-HAT-1", "ust": "KOLON", "uzunluk_m": 18.0, "kot_farki_m": -1.6, "cap": "50",
     "parcalar": {"te_donus": 1, "dirsek_90": 3, "surgulu_vana": 1}, "aciklama": "Dolap besleme hattı"},
    {"id": "YD-1", "ust": "YD-HAT-1", "uzunluk_m": 1.0, "kot_farki_m": 0.0, "cap": "25",
     "parcalar": {"dirsek_90": 1}, "cikis": "dolap_yari_sert", "kat": "-1", "konum": [0.0, 0.0]},
    {"id": "YD-HAT-2", "ust": "YD-HAT-1", "uzunluk_m": 25.0, "kot_farki_m": 0.0, "cap": "50",
     "parcalar": {"dirsek_90": 2}},
    {"id": "YD-2", "ust": "YD-HAT-2", "uzunluk_m": 1.0, "kot_farki_m": 0.0, "cap": "25",
     "parcalar": {"dirsek_90": 1}, "cikis": "dolap_yari_sert", "kat": "-1", "konum": [25.0, 0.0]},
]


def sprler(i, js):
    return [f"S{i}-{j}" for j in js]


# Tasarım alanı: 144 m² / 11,56 m² → 13 sprinkler. Uzun kenar ≥ 1,2·√144 = 14,4 m
# → branşman boyunca 5 sprinkler (5 × 3,4 = 17 m). Dizilim 5 + 5 + 3.
alan_uzak = sprler(6, range(2, 7)) + sprler(5, range(2, 7)) + sprler(4, range(4, 7))
alan_yakin = sprler(1, range(2, 7)) + sprler(2, range(2, 7)) + sprler(3, range(4, 7))

proje = {
    "proje": {
        "ad": "Örnek Konut — Bodrum Kat Kapalı Otopark Yangın Tesisatı",
        "isveren": "Örnek Yapı A.Ş.",
        "adres": "Örnek Mah. Örnek Sk. No:1, İstanbul",
        "revizyon": "0",
        "hazirlayan": "Mak. Müh. ...",
        "kontrol": "",
        "onay": "",
    },
    "bina": {
        "kullanim": "konut",
        "yapi_yuksekligi_m": 28.5,
        "kapali_otopark_m2": 1250,
        "kat_adedi": 9,
    },
    "yangin": {
        "tehlike_sinifi": "OT2",
        "sistem": "islak",
        "boru_serisi": "CELIK_EN10255_ORTA",
        "malzeme": "celik",
        "kaynak": {"ad": "Yangın pompası çıkışı", "kot_m": -1.0},
        "sprinkler_varsayilan": {"K": 80, "alan_m2": round(ARALIK * ARALIK, 2)},
        "yedek_sprinkler": 6,
        "pompa": {"adet_asil": 1, "adet_yedek": 1, "emme_basinci_bar": 0.2,
                  "anma_debi_lpm": 1550, "anma_basinc_bar": 4.7,
                  "kapali_vana_basinc_bar": 6.2, "debi_150_basinc_bar": 3.4},
        "depo": {"hacim_m3": 110},
        "hatlar": hatlar,
        "senaryolar": [
            {"ad": "A — En uzak tasarım alanı (R4–R6)", "acik": alan_uzak},
            {"ad": "B — Yakın tasarım alanı (R1–R3)", "acik": alan_yakin},
            {"ad": "C — Alan A + yangın dolabı YD-2", "acik": alan_uzak + ["YD-2"]},
            {"ad": "D — İki yangın dolabı", "acik": ["YD-1", "YD-2"]},
        ],
    },
}

hedef = Path(__file__).with_name("ornek_otopark.yaml")
with open(hedef, "w", encoding="utf-8") as f:
    f.write("# Bu dosya ornek_otopark_olustur.py ile üretilmiştir.\n")
    f.write("# Hesap: python -m tesisat hesapla ornekler/ornek_otopark.yaml\n")
    yaml.safe_dump(proje, f, allow_unicode=True, sort_keys=False, width=120)
print(f"yazıldı: {hedef}  ({len(hatlar)} hat)")
