---
name: yangin-hesap
description: Yangın tesisatı (sprinkler, yangın dolabı, hidrant) hidrolik hesabı ve BYKHY / TS EN 12845 uygunluk kontrolü. Kullanıcı sprinkler hesabı, yangın pompası/depo seçimi, yangın dolabı kontrolü, yangın tesisatı proje raporu istediğinde veya /yangin-hesap yazdığında kullan.
---

# Yangın tesisatı hesabı

Hesap motoru: `tesisat/` (Python). Hesabı **asla elle veya tahminle yapma**. Her sayı motordan gelmeli.

## İş akışı

1. **Bilgi topla.** Eksik olanları kullanıcıya sor:
   - Bina: kullanım, yapı yüksekliği, kapalı otopark alanı, kat alanları. Bunlar zorunluluk kontrolü için gerekir.
   - Tehlike sınıfı (BYKHY md. 19 / Ek-1). Emin değilsen gerekçesiyle öner ve kullanıcıya onaylat.
   - Islak/kuru sistem, boru malzemesi, pompa ve depo kotları.
   - Çizimden alınacaklar: sprinkler ızgarası (S×D), branşman ve kolon güzergâhları, uzunluklar, kotlar, parçalar, dolap konumları.
2. **YAML'ı oluştur.** Format için `tesisat/README.md` ve `tesisat/ornekler/ornek_otopark.yaml` dosyalarına bak.
   - Tekrarlı ağlar (ızgara) için elle yazmak yerine `ornekler/ornek_otopark_olustur.py` gibi küçük bir üretici betik yaz.
   - Her hattın `ust` değeri, beslendiği hattın id'sidir.
   - `kot_farki_m` = bitiş kotu − başlangıç kotu.
   - **Kapsama alanı:** Her mahal için `mahaller` altında `poligon` ver (çizimden, metre cinsinden). Her sprinklere `mahal` ve `konum: [x, y]` ekle. Alanı elle yazma; araç plandan hesaplar.
   - Sprinkler konmayan mahaller (ıslak hacim, yangın merdiveni, asansör kuyusu) için `muaf: true` ve `muaf_nedeni` ver (BYKHY md. 96/3).
3. **Senaryoları tanımla.**
   - Tasarım alanı = BYKHY Ek-8/B alanı. Sprinkler sayısı = ⌈alan / sprinkler başına alan⌉.
   - Alanın uzun kenarı ≥ 1,2·√A olmalı ve branşmanlara paralel uzanmalı.
   - **En az iki aday alan** ver: hidrolik olarak en uzak olan ve en yüksek kottaki. Araç en kötüsünü seçer.
   - Dolap varsa "en uzak alan + en uzak dolap" senaryosunu da ekle.
4. **Çalıştır:**
   ```bash
   cd tesisat && python -m tesisat hesapla <proje>.yaml -o <proje>_rapor.html --json <proje>.json
   ```
   Çıkış kodları: `0` uygun, `1` HATA var, `2` girdi hatası.
5. **HATA'ları düzelt ve yeniden çalıştır.** Tipik düzeltmeler:
   - Hız aşımı → ilgili hattın çapını büyüt.
   - Pompa yetersiz → raporun "Önerilen anma noktası" satırını kullan.
   - Depo yetersiz → hesaplanan hacmi yukarı yuvarla.
   - Dolapta 9 bar aşımı → basınç düşürücü ekle (bunu çizime not et).
   - Tasarım alanı eksik → senaryoya sprinkler ekle.
   - Korunmayan bölge (✕) veya duvar mesafesi aşımı → ilgili sıraya sprinkler ekle ya da ızgarayı kaydır. Bunu çizimde de düzeltmesi için kullanıcıya bildir.

   Kullanıcının kararı olan şeyleri (tehlike sınıfı, pompa markası/modeli) kendin değiştirme. Öner ve onay iste.
6. **Teslim et.**
   - HTML raporu kullanıcıya gönder.
   - Kısa bir özet ver: belirleyici senaryo, pompa noktası (l/dk @ bar), depo hacmi, kalan UYARI/BİLGİ'ler.
   - Raporun en altındaki "mühendis sorumluluğu" notunu ve `DOGRULAMA.md` dosyasındaki ⚠️ işaretli değerleri hatırlat.

## Kurallar

- Kural değerleri `tesisat/tesisat/kurallar_varsayilan.yaml` dosyasındadır. Projeye özel farklılıklar (idare şartnamesi) için kural dosyasını değiştirme; proje YAML'ındaki `kurallar_ek:` bölümünü kullan.
- Yeni bir kural değeri eklersen kaynağını `tesisat/DOGRULAMA.md` dosyasına yaz ve bir test ekle (`tesisat/tests/`).
- Döngülü veya ızgara ağlar henüz desteklenmiyor. Böyle bir projede bunu kullanıcıya açıkça söyle; ağaç yapıya indirgemeye çalışma.
