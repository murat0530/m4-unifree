---
name: yangin-tesisat
description: Yangın tesisatı (sprinkler, yangın dolabı, hidrant) için uçtan uca otomatik iş akışı — AutoCAD DXF/DWG planından boru ağını okur, BYKHY / TS EN 12845 hidrolik hesabını yapar, metraj cetvelini ve yaklaşık teklifi (Excel) üretir. Kullanıcı bir .dxf veya .dwg dosyası verdiğinde/yüklediğinde, sprinkler hesabı, yangın pompası/depo, metraj, keşif, teklif veya yaklaşık maliyet istediğinde ya da /yangin-tesisat yazdığında MUTLAKA kullan.
---

# Yangın tesisatı — çizimden teklife

Motor: `tesisat/` (Python). **Hiçbir sayıyı elle veya tahminle üretme**; her miktar, basınç ve tutar motordan gelir.
Kurallar ve kaynakları: `tesisat/DOGRULAMA.md`, `tesisat/METRAJ_KURALLARI.md`.

## 0. Hazırlık (oturum başına bir kez)

```bash
cd tesisat && pip install -q -r requirements.txt
```

## 1. Dosyayı al

- **DXF:** doğrudan kullan.
- **DWG:** `python -m tesisat otomatik` ODA File Converter kuruluysa kendisi dönüştürür. Kurulu değilse kullanıcıdan **AutoCAD → Farklı Kaydet → DXF (2013+)** iste. Başka bir dönüştürücü indirip kurma.
- Proje dosyalarını `tesisat/projeler/<proje-adı>/` altına kopyala. Bu klasör git'e girmez; müşteri verisi repoya **commit edilmez**.

## 2. Ayar taslağını otomatik üret

```bash
python -m tesisat ayar-oner projeler/<ad>/plan.dxf -o projeler/<ad>/ayar.yaml
python -m tesisat dxf-ozet projeler/<ad>/plan.dxf      # gerekirse katman/blok/yazı envanteri
```

Taslak şunları tahmin eder:
- boru katmanı (adında BORU / PIPE / SPR / YANGIN geçenler)
- sprinkler bloğu (SPR / SPRINK / HEAD / BAŞLIK / PENDENT)
- besleme bloğu (KOLON / RISER / BESLEME)
- dolap bloğu ve birim

Tahminleri `dxf-ozet` çıktısıyla karşılaştır. Açıkça yanlış olanı düzelt (örneğin duvar katmanı boru sanılmışsa).

## 3. Yalnız tahmin edilemeyenleri sor (tek seferde, AskUserQuestion ile)

Aşağıdakileri **asla tahmin etme**. Kullanıcı daha önce söylediyse tekrar sorma:

1. **Tehlike sınıfı:** BYKHY Ek-1. Mahal katmanı varsa mahal tiplerinden öner.
2. **Besleme:**
   - Besleme noktası, eğer bir blok bulunamadıysa.
   - Besleme kotu.
   - Planda görünmeyen düşey hatlar ve kat bağlantı hatları (`yangin.ust_hatlar`). Bunlar kesitten alınır; bilinmiyorsa "varsayım" olarak `uzunluk_yontemi: elle girilen` ile gir ve kullanıcıya söyle.
3. **Plan katlara nasıl dağılıyor:** Aynı plan birden fazla kat için mi kullanılıyor (`cizim.planlar`)?
4. **Sprinkler başına alan:** Mahal katmanı yoksa sor (S × D).

Kullanıcı "otomatik yap" ya da "varsayımla devam et" derse:
- Tehlike sınıfı dışındaki eksikleri şablondaki varsayılanlarla doldur.
- Bunları `kararlar:` listesine **"VARSAYIM: …"** diye yaz.

## 4. Çalıştır

```bash
python -m tesisat otomatik projeler/<ad>/ayar.yaml -o projeler/<ad>/cikti
```

Çıktılar:

| Dosya | İçerik |
|---|---|
| `proje.yaml` | Çizimden kurulan ağ modeli |
| `hidrolik_rapor.html` | Hidrolik hesap ve yönetmelik kontrolleri |
| `metraj_teklif.xlsx` | Teklif durumu, detay metraj, belirsizlikler, keşif, fiyatlar (listeden dolu), doğrulama |
| `ozet.md` | Kısa özet |

Çıkış kodları: `0` uygun · `1` hidrolik HATA var · `2` girdi hatası. Girdi hatasında mesajı oku, ayarı düzelt, tekrar çalıştır.

## 5. Sonucu denetle (teslimden önce)

`ozet.md` dosyasını ve konsol çıktısını oku. Şunlara bak:

- **Çizimden okunan:**
  - Bağlanan sprinkler sayısı çizimdekiyle aynı mı? Değilse hangi sprinklerin boruya bağlanmadığını söyle.
  - "Kesişiyor ama bağlantı sayılmadı" ve "kaynağa bağlı olmayan" uyarıları var mı? Bunları kullanıcıya aynen ilet. Çizgileri kendin birleştirme.
  - Çap etiketi bulunamayan parçalar ("ÖNERİLDİ") var mı?
- **Hidrolik HATA:** Her hatanın nedenini açıkla. Tipik çözümler:
  - **Tasarım alanı katlara sığmıyor:** Komşu alan ya da çatı sprinklerinin tasarım alanına dahil edilmesi gerekir. Bu bir mühendis kararıdır.
  - **Hız aşımı:** Çap büyüt.
  - **Pompa ya da depo yetersiz:** Rapordaki önerilen değerleri kullan.
- **Metraj ve teklif:**
  - Fiyatsız kalemleri listele. Fiyat **uydurma**; kullanıcıdan iste ya da "fiyat yok" bırak.
  - Excel'deki "Teklif durumu" sayfası TEKLİFE HAZIR değilse tutarı **"yaklaşık"** diye sun ve nedenlerini say: açık belirsizlik, onay bekleyen satırlar, fiyatsız kalemler, referans doğrulaması yok.
  - Ön hesap kuralları (askı A1, yivli kaplin K1) üst sınırdır; bunu belirt.

## 6. Teslim et

- `hidrolik_rapor.html` ve `metraj_teklif.xlsx` dosyalarını SendUserFile ile gönder.
- Kısa bir özet yaz:
  - sprinkler adedi ve boru uzunluğu
  - belirleyici senaryo, gerekli besleme basıncı ve debi
  - **yaklaşık teklif (KDV hariç / dahil)**
  - fiyatsız kalemler
  - teklif dışı riskler: mevcut pompa ve depo yeterliliği, depolama (HHS) durumu, tasarım alanı taşması
- ⚠ işaretli kuralları hatırlat (`DOGRULAMA.md`).
- Kullanıcının elinde **kontrol edilmiş bir metraj** varsa `python -m tesisat metraj … --referans ref.csv` ile karşılaştırmayı öner.

## Kurallar

- Fiyat listesi: `tesisat/tesisat/fiyatlar/fiyat_listesi.yaml`. Projeye özel fiyatları ayar dosyasının `fiyat:` bölümüne yaz; listeyi değiştirme.
- Kural değerleri: `tesisat/tesisat/kurallar_varsayilan.yaml`. Projeye özel farklılıklar `kurallar_ek:` bölümüne yazılır.
- Yeni bir kural veya fiyat esası eklenirse kaynağını `DOGRULAMA.md`'ye yaz ve `tesisat/tests/` altına test ekle.
- Döngülü veya ızgara ağlar desteklenmez. Motor hata verir; kullanıcıya açıkça söyle.
- Sorumluluk: rapor bir hesap yardımcısıdır. İmza ve onay yetkili makine mühendisine aittir.
