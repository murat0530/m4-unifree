# M4 Kasa

Kasiyerler için hızlı, hafif bir yardımcı uygulama. Telefonda "lazım olunca aç, bak, kapat" kullanımı için tasarlandı: framework yok, her şey önbellekten anında açılır, internet yokken de çalışır.

## Bölümler

| Sekme | Ne yapar |
|---|---|
| 💶 **Döviz** | Çevirici: tutarı ve para birimini yaz, ₺ / € / $ / £ / ¥ (yuan) / C$ (Kanada doları) / SAR (Suudi riyali) karşılıkları hesap adımlarıyla birlikte anında çıkar (euro üzerinden: `500 $ ÷ 1,17 × 50`). "Müşteriye göster" tam ekranı |
| 🏷️ **İndirim** | % indirim, N al M öde, ikinci ürüne % hesapları; sonucu tek dokunuşla çeviriciye aktarma |
| ▥ **Barkod** | Yazılan kodu ekranda barkod olarak çizer (8/13 haneli rakam → EAN-8/EAN-13, diğerleri → Code 128); kasadaki okuyucuyla ekrandan okutulur. Sık kodlar telefona kaydedilir, ortak kodlar `barkodlar.json`'dan gelir |
| 📋 **Kurallar** | Aranabilir kural / limit / arıza / acil durum kartları |
| 🗣️ **İfadeler** | 16 kasa cümlesi, 7 dilde (EN, DE, RU, AR, FR, ES, ZH); dokununca müşteriye büyük gösterilir |
| 💱 **Kurlar** | Döviz sekmesinin en üstünde, euro bazlı: `1 € = ? ₺` ana kur, diğer dövizler pariteyle (`1 € = 1,17 $`, `1 € = 8,3 ¥`). Yazdıkça uygulanır; bugün güncellenmediyse sarı uyarı ve "Bugünün kurları doğru" onayı çıkar. Yalnızca o telefonda saklanır |
| ⚙ **Kasa kartı** | Kurları ve seçili kuralları tek sayfa yazdırır |

Uygulama simgesine basılı tutunca (Android) doğrudan sekmeye giden kısayollar çıkar. Bağlantılar da doğrudan açılabilir: `…/#doviz`, `…/#kurallar` (kasaya QR olarak yapıştırılabilir).

## İçeriği güncelleme

İçerik `site/data/` altındaki JSON dosyalarındadır. GitHub'da dosyayı açıp ✏️ ile düzenleyin, `main`'e kaydedin; birkaç dakika içinde yayına çıkar.

- `kurallar.json` — `baslik`, `kategori`, `metin` (`\n` = yeni satır), `kart` (`true` ise Kasa kartı çıktısına girer)
- `kampanyalar.json` — `tip`: `yuzde` (+`oran`), `nAlMOde` (+`n`, `m`), `ikinciye` (+`oran`)
- `ifadeler.json` — her cümle için `tr` ve dil kodları
- `barkodlar.json` — herkesin göreceği ortak kodlar: `{ "name": "Poşet", "code": "…" }`

> Şu anki kural ve kampanyalar **ÖRNEK**tir; gerçek içerikle değiştirin.

Uygulama dosyalarını (`app.js`, `app.css`…) değiştirdiğinizde `site/sw.js` içindeki `VERSION` değerini artırın ki telefonlar yeni sürümü alsın.

## Güvenlik

- Dışarıya hiçbir istek atmaz; yalnızca kendi dosyalarını yükler (Content-Security-Policy ile zorlanır).
- Kişisel veri, şifre veya müşteri bilgisi tutmaz. Kurlar ve tercihler yalnızca cihazın kendi deposunda kalır.
- `site/data/` içeriği herkese açık yayınlanır: buraya gizli bilgi (iç fiyat listesi, kişisel numaralar vb.) koymayın.

## Geliştirme

```bash
npm test                              # para hesaplama testleri
python3 -m http.server -d site 8000   # http://localhost:8000
```

`main`'e her push'ta testler çalışır, geçerse GitHub Pages'e yayınlanır.
