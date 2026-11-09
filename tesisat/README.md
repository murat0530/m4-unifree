# tesisat — Mekanik Tesisat Hesap ve Kontrol Aracı

Proje bilgilerini bir YAML dosyasından okur, hidrolik hesabı yapar ve sonucu yönetmelik ve standart sınırlarına göre kontrol eder. Çıktı olarak imza bloklu, yazdırılabilir bir **HTML hesap raporu** ve isteğe bağlı **JSON** sonuç üretir.

| Modül | Durum | Dayanak |
|---|---|---|
| **Yangın** (sprinkler, yangın dolabı, hidrant, pompa, depo) | ✅ Kullanıma hazır | BYKHY (md. 19, 91–96, Ek-8), TS EN 12845 |
| Temiz su | ⏳ Planlandı (kurallar hazır) | DIN 1988-300, TS EN 806 |
| Atık su | ⏳ Planlandı (kurallar hazır) | TS EN 12056-2 |
| Havalandırma | ⏳ Planlandı (kurallar hazır) | EN 16798-1/-3 |
| DXF çizim kontrolü | ⏳ Planlandı | — |

## Kurulum ve çalıştırma

```bash
cd tesisat
pip install pyyaml pytest
python -m tesisat hesapla ornekler/ornek_otopark.yaml -o rapor.html --json sonuc.json
python -m pytest -q tests        # 18 doğrulama testi
```

Çıkış kodları:
- `0`: uygun
- `1`: en az bir HATA var
- `2`: girdi hatası

Bu kodlar sayesinde araç CI'da veya bir otomasyonda da kullanılabilir.

Örnek proje ve raporu:
- `ornekler/ornek_otopark.yaml`: konut altı 1.250 m² kapalı otopark, OT-2, 36 sprinkler, 2 yangın dolabı
- `ornekler/ornek_otopark_rapor.html`: bu projenin ürettiği rapor

## Yangın modülü — ne yapar?

1. **Zorunluluk (BYKHY md. 96/2, 94/1-b-1):** Bina bilgilerinden sprinkler ve yangın dolabının zorunlu olup olmadığını belirler. Zorunlu olup projede yoksa HATA verir.
2. **Tasarım kriterleri (Ek-8/B, EN 12845 Tablo 3):** Tehlike sınıfına ve ıslak/kuru sisteme göre yoğunluğu, tasarım alanını, minimum basıncı ve süreyi atar.
3. **Tam hidrolik çözüm:**
   - Hazen-Williams (p = 6,05·10⁵·Q^1,85 / C^1,85·d^4,87) ve eşdeğer boylar kullanılır.
   - Her açık sprinklerin ve dolabın debisi, o noktadaki gerçek basınçtan hesaplanır (Q = K√P).
   - Ağdaki tüm açık çıkışların gereksinimini karşılayan en düşük pompa çıkış basıncı bulunur.
4. **Senaryolar:**
   - Her tasarım alanı (en uzak, en yüksek vb.) ve dolap eşzamanlılığı ayrı ayrı hesaplanır.
   - En büyük basınç talebi belirleyici olur.
   - Dolapla eşzamanlı senaryoda sprinklerler fazla basınç altında daha çok su atar. Bu fiziksel etki hesaba dahildir.
5. **Kontroller:**
   - Sprinkler kapsama alanı (DT ve OT-1'de 21 m², diğer orta tehlikelerde 12 m², yüksek tehlikede 9 m²)
   - K faktörü (Tablo 37) ve minimum çap (Tablo 36)
   - Hız (vana noktasında 6 m/s, genel 10 m/s)
   - Dolap lüle basıncı (en fazla 9 bar) ve dolap aralığı (30/45 m)
   - Hidrant hattı (en az DN100) ve en az 6 yedek sprinkler
6. **Pompa (md. 93):**
   - Önerilen anma noktasını verir.
   - Pompanın tüm senaryo taleplerini karşılayıp karşılamadığını, kapalı vana basıncını (≤ %140) ve %150 debideki basıncı (≥ %65) kontrol eder.
   - Yedek pompa olup olmadığını kontrol eder.
7. **Depo (md. 92):**
   - Hacim, en büyük sprinkler debisi ile Ek-8/C'deki dolap ve hidrant debisinin toplamı, süreyle çarpılarak bulunur.
   - Ek-8/A ön hesap değeri karşılaştırma için ayrıca gösterilir.

## Girdi dosyası (özet)

```yaml
proje: {ad: "...", isveren: "...", hazirlayan: "...", revizyon: "0"}
bina:                      # zorunluluk kontrolleri için
  kullanim: konut          # konut | ofis | otel | hastane | okul | depo | ...
  yapi_yuksekligi_m: 28.5
  kapali_otopark_m2: 1250
yangin:
  tehlike_sinifi: OT2      # DT, OT1..OT4, YT1..YT3  (BYKHY md.19 / Ek-1'e göre mühendis belirler)
  sistem: islak            # islak | kuru
  boru_serisi: CELIK_EN10255_ORTA   # veya CELIK_SCH40
  kaynak: {ad: "Pompa çıkışı", kot_m: -1.0}
  sprinkler_varsayilan: {K: 80, alan_m2: 11.56}
  yedek_sprinkler: 6
  pompa: {anma_debi_lpm: 1550, anma_basinc_bar: 4.7, kapali_vana_basinc_bar: 6.2,
          debi_150_basinc_bar: 3.4, emme_basinci_bar: 0.2, adet_asil: 1, adet_yedek: 1}
  depo: {hacim_m3: 110}
  hatlar:                  # ağaç: her hat 'ust' hattının ucundan başlar
    - {id: KOLON, ust: null, uzunluk_m: 4.2, kot_farki_m: 4.2, cap: "100",
       parcalar: {alarm_vanasi: 1, kelebek_vana: 1, dirsek_90: 1}, vana_noktasi: true}
    - {id: R1-1, ust: KOLON, uzunluk_m: 1.7, cap: "50", parcalar: {te_donus: 1}}
    - {id: S1-1, ust: R1-1, uzunluk_m: 0.3, kot_farki_m: -0.3, cap: "25", sprinkler: true}
    - {id: YD-1, ust: KOLON, uzunluk_m: 1, cap: "25", cikis: dolap_yari_sert, kat: "-1", konum: [0, 0]}
  senaryolar:
    - {ad: "En uzak alan", acik: [S1-1, ...]}
    - {ad: "Alan + dolap", acik: [S1-1, ..., YD-1]}
kurallar_ek:               # (isteğe bağlı) idare şartnamesine göre varsayılan kuralları ezer
  yangin: {hiz_max_ms: 8.0}
```

- **Parçalar:** `dirsek_90`, `dirsek_45`, `te_donus`, `surgulu_vana`, `kelebek_vana`, `cekvalf`, `alarm_vanasi`. Ek olarak `es_uzunluk_m` ile doğrudan eşdeğer boy (m) eklenebilir.
- **Çıkışlar:** `sprinkler`, `cikis: dolap_yari_sert | dolap_yassi | hidrant`.
- **Kurallar:** Tüm kural değerleri `tesisat/kurallar_varsayilan.yaml` dosyasındadır. Her değerin kaynağı **[DOGRULAMA.md](DOGRULAMA.md)** dosyasında belgelenmiştir.

## Sınırlar — mühendisin kararı gereken konular

- **Ağ tipi:** Yalnızca **ağaç (dallanmış)** ağlar çözülür. Döngülü (loop) ve ızgara (grid) ağlar için Hardy-Cross çözücü henüz yok.
- **Tasarım alanı:** Alanın yeri ve şekli (uzun kenar ≥ 1,2·√A) mühendis tarafından senaryo olarak verilir. Araç sprinkler sayısını ve kapsama alanını kontrol eder, ancak en elverişsiz alanı **kendisi seçmez**. Bu yüzden birden fazla aday alan tanımlayın; en kötüsü otomatik olarak belirleyici olur.
- **Tehlike sınıfı:** BYKHY Ek-1'e göre mühendis belirler. Ek-1'in bazı kısımları Danıştay kararıyla iptal edilmiştir.
- **Depolama alanları:** Raf ve yüksek istif alanları (HHS) ile ESFR kapsam dışıdır.
- **Teyit edilecek değerler:** Eşdeğer boy tablosu (NFPA 13 kaynaklı) ve EN 12845 hız sınırları ⚠️ olarak işaretlidir. Lisanslı standart metniyle teyit edilmelidir.
- **Sorumluluk:** Bu bir hesap yardımcısıdır. Proje sorumluluğu, projeyi imzalayan yetkili makine mühendisine aittir.

## Claude Code ile kullanım

`/yangin-hesap` komutu (`.claude/skills/yangin-hesap/SKILL.md`) şunları yapar:
1. Projenizin bilgilerinden ve çizimden okunan değerlerden YAML dosyasını hazırlar.
2. Hesabı çalıştırır.
3. HATA'ları yorumlar ve düzeltme önerir: çap büyütme, pompa seçimi, ek senaryo vb.
4. Raporu teslim eder.
