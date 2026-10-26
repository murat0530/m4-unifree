# Kaldığımız yer

_Son güncelleme: 26.10.2026_

## Durum
- Eski Flutter uygulaması kaldırıldı; yerine `site/` altında hafif **M4 Kasa** PWA'sı var.
- Tüm çalışma `claude/jolly-brahmagupta-evf6do` dalında. **`main`'e henüz birleştirilmedi**, yani yayındaki GitHub Pages sitesi hâlâ eski uygulama.
- Deneme linki (özel): https://claude.ai/artifact/FH4NGJ1LWUgpVW6pZyeq8h

## Sekmeler
- **Döviz:** en üstte kurlar (1 € = ? ₺ + euroya göre pariteler: $, £, ¥, C$, SAR), altında "500 ₺ kaç $?" çevirici.
- **İndirim:** % indirim, N al M öde, ikinci ürüne %; sonuç çeviriciye aktarılır.
- **Barkod:** koddan ekranda barkod (EAN-13/EAN-8/Code 128), kaydetme, tam ekran.
- **Kurallar** ve **İfadeler** (7 dil).

## Sırada ne var
- [ ] `site/data/kurallar.json` ve `kampanyalar.json` içindeki **ÖRNEK** içerikleri gerçek bilgilerle değiştir.
- [ ] `ifadeler.json` çevirilerini o dilleri bilen birine kontrol ettir.
- [ ] Barkodu kasadaki okuyucuyla dene (kameralı okuyucu gerekir).
- [ ] Hazır olunca pull request aç ve `main`'e birleştir → otomatik yayına çıkar.

## Geliştirme
```bash
npm test                                   # testler
python3 -m http.server -d site 8000        # yerelde çalıştır
python3 tools/build_preview.py site out.html   # tek sayfalık deneme sürümü
```
