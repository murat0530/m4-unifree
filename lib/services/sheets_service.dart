import 'package:http/http.dart' as http;
import 'dart:convert';

// Google Sheets'i "publish to web" yapıp CSV olarak çekiyoruz
// Her sayfa için ayrı bir sheet tab'ı kullanılır
// Format: https://docs.google.com/spreadsheets/d/SHEET_ID/gviz/tq?tqx=out:json&sheet=SAYFA_ADI

class SheetsService {
  // Bu ID'yi kendi Google Sheets ID'nizle değiştirin
  static const _sheetId = '1vgnCY7mGFnylVLmqPFg3vuuxyHOlPqK-QCvtgtlVYMY';

  static Future<List<Map<String, dynamic>>> fetchSheet(String sheetName) async {
    final url = Uri.parse(
      'https://docs.google.com/spreadsheets/d/$_sheetId/gviz/tq?tqx=out:json&sheet=${Uri.encodeComponent(sheetName)}',
    );

    try {
      final response = await http.get(url);
      if (response.statusCode != 200) return [];

      // Google'ın döndürdüğü JSON paketini temizle
      final raw = response.body;
      final jsonStr = raw.substring(raw.indexOf('(') + 1, raw.lastIndexOf(')'));
      final data = json.decode(jsonStr);

      final cols = (data['table']['cols'] as List)
          .map((c) => c['label']?.toString() ?? '')
          .toList();

      final rows = <Map<String, dynamic>>[];
      for (final row in data['table']['rows'] as List) {
        final cells = row['c'] as List;
        final map = <String, dynamic>{};
        for (int i = 0; i < cols.length; i++) {
          if (cols[i].isNotEmpty) {
            map[cols[i]] = cells[i] != null ? cells[i]['v'] : null;
          }
        }
        rows.add(map);
      }
      return rows;
    } catch (_) {
      return [];
    }
  }

  // Duyuru sayfasını çek (A:İçerik, B:Tarih, C:Tip sütunları)
  static Future<List<Map<String, dynamic>>> fetchDuyurular() =>
      fetchSheet('Duyurular');

  // Kasa hattı sayfasını çek
  static Future<List<Map<String, dynamic>>> fetchKasaHatti() =>
      fetchSheet('KasaHatti');

  // Bilgilendirme sayfasını çek
  static Future<List<Map<String, dynamic>>> fetchBilgilendirme() =>
      fetchSheet('Bilgilendirme');
}
