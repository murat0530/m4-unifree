import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
// ignore: avoid_web_libraries_in_flutter
import 'dart:html' as html;

const _sheetId = '1vgnCY7mGFnylVLmqPFg3vuuxyHOlPqK-QCvtgtlVYMY';
const _molaSuresi = 45; // dakika
const _tolerans = 5;   // dakika

class MolaScreen extends StatefulWidget {
  const MolaScreen({super.key});
  @override
  State<MolaScreen> createState() => _MolaScreenState();
}

class _MolaScreenState extends State<MolaScreen> {
  Timer? _timer;
  DateTime _now = DateTime.now();
  List<_MolaGrup> _gruplar = [];
  bool _loading = true;
  final Set<int> _bildirimGonderildi = {};
  String _bildirimIzni = 'default';

  @override
  void initState() {
    super.initState();
    _bildirimIzniniKontrolEt();
    _loadGruplar();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      setState(() => _now = DateTime.now());
      _bildirimKontrol();
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _bildirimIzniniKontrolEt() {
    try {
      setState(() => _bildirimIzni = html.Notification.permission);
    } catch (_) {}
  }

  Future<void> _isteBildirimIzni() async {
    try {
      final izin = await html.Notification.requestPermission();
      setState(() => _bildirimIzni = izin);
    } catch (_) {}
  }

  void _bildirimGonder(String baslik, String mesaj) {
    try {
      if (html.Notification.permission == 'granted') {
        html.Notification(baslik, body: mesaj);
      }
    } catch (_) {}
  }

  // Vardiyaya göre başlangıç saatini belirle
  TimeOfDay get _vardiyaBaslangic {
    final saat = _now.hour;
    // 06:00-18:00 arası sabah vardiyası, geri kalan akşam
    if (saat >= 6 && saat < 18) {
      return const TimeOfDay(hour: 8, minute: 0);
    }
    return const TimeOfDay(hour: 20, minute: 0);
  }

  String get _vardiyaAdi {
    final saat = _now.hour;
    if (saat >= 6 && saat < 18) return 'Sabah Vardiyası';
    return 'Akşam Vardiyası';
  }

  Future<void> _loadGruplar() async {
    setState(() => _loading = true);
    try {
      final url = Uri.parse(
        'https://docs.google.com/spreadsheets/d/$_sheetId/gviz/tq?tqx=out:json',
      );
      final res = await http.get(url);
      final raw = res.body;
      final jsonStr = raw.substring(raw.indexOf('(') + 1, raw.lastIndexOf(')'));
      final data = json.decode(jsonStr);
      final tableRows = data['table']['rows'] as List;
      final colCount = (data['table']['cols'] as List).length;

      List<String> getRow(int idx) {
        if (idx >= tableRows.length) return [];
        return List.generate(colCount, (i) {
          final row = tableRows[idx]['c'] as List;
          if (i >= row.length || row[i] == null || row[i]['v'] == null) return '';
          return row[i]['v'].toString().trim();
        });
      }

      // Satır 15: boş | 20:00 | A | 20:45 | B | 21:30 | C
      // Satır 16-19: isimler
      final timeRow = getRow(15);
      final nameRows = [getRow(16), getRow(17), getRow(18), getRow(19)];

      // Sütun çiftleri: 2,3 | 4,5 | 6,7 için saatleri bul
      final gruplar = <_MolaGrup>[];
      final saatCols = <int>[]; // saat olan sütun indexleri

      for (int i = 0; i < timeRow.length; i++) {
        if (RegExp(r'^\d{1,2}:\d{2}$').hasMatch(timeRow[i])) {
          saatCols.add(i);
        }
      }

      for (int g = 0; g < saatCols.length; g++) {
        final col = saatCols[g];
        final saatStr = timeRow[col];
        final parts = saatStr.split(':');
        final tod = TimeOfDay(hour: int.parse(parts[0]), minute: int.parse(parts[1]));
        final isimler = nameRows
            .map((r) => col < r.length ? r[col] : '')
            .where((n) => n.isNotEmpty && n != '-' && n != 'A' && n != 'B' && n != 'C')
            .toList();

        gruplar.add(_MolaGrup(no: g + 1, baslangic: tod, isimler: isimler));
      }

      // Eğer sheets'ten gelmezse varsayılanları kullan
      if (gruplar.isEmpty) {
        gruplar.addAll([
          const _MolaGrup(no: 1, baslangic: TimeOfDay(hour: 20, minute: 0), isimler: []),
          const _MolaGrup(no: 2, baslangic: TimeOfDay(hour: 20, minute: 45), isimler: []),
          const _MolaGrup(no: 3, baslangic: TimeOfDay(hour: 21, minute: 30), isimler: []),
        ]);
      }

      setState(() { _gruplar = gruplar; _loading = false; });
    } catch (_) {
      // Varsayılan saatler
      final bas = _vardiyaBaslangic;
      setState(() {
        _gruplar = List.generate(3, (i) => _MolaGrup(
          no: i + 1,
          baslangic: TimeOfDay(
            hour: (bas.hour * 60 + bas.minute + i * _molaSuresi) ~/ 60,
            minute: (bas.minute + i * _molaSuresi) % 60,
          ),
          isimler: [],
        ));
        _loading = false;
      });
    }
  }

  // Grubun bitiş zamanı (+ tolerans için bildirim zamanı)
  DateTime _bitis(_MolaGrup g) {
    return DateTime(_now.year, _now.month, _now.day, g.baslangic.hour, g.baslangic.minute)
        .add(const Duration(minutes: _molaSuresi));
  }

  DateTime _bildirimZamani(_MolaGrup g) =>
      _bitis(g).add(const Duration(minutes: _tolerans));

  _GrupDurum _durum(_MolaGrup g) {
    final bas = DateTime(_now.year, _now.month, _now.day, g.baslangic.hour, g.baslangic.minute);
    final bit = _bitis(g);
    if (_now.isBefore(bas)) return _GrupDurum.bekliyor;
    if (_now.isBefore(bit)) return _GrupDurum.aktif;
    return _GrupDurum.bitti;
  }

  void _bildirimKontrol() {
    for (int i = 0; i < _gruplar.length; i++) {
      final g = _gruplar[i];
      final bildirimZ = _bildirimZamani(g);
      final key = i;

      if (!_bildirimGonderildi.contains(key) &&
          _now.isAfter(bildirimZ) &&
          _now.isBefore(bildirimZ.add(const Duration(seconds: 10)))) {
        _bildirimGonderildi.add(key);
        final sonrakiVar = i + 1 < _gruplar.length;
        final mesaj = sonrakiVar
            ? '${g.no}. grup molası bitti! ${g.no + 1}. grup çıkabilir 🟢'
            : '${g.no}. grup molası bitti!';
        _bildirimGonder('Mola Uyarısı', mesaj);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(mesaj),
              backgroundColor: Colors.orange,
              duration: const Duration(seconds: 10),
            ),
          );
        }
      }
    }
  }

  String _formatTod(TimeOfDay t) =>
      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

  String _formatBitis(_MolaGrup g) {
    final b = _bitis(g);
    return '${b.hour.toString().padLeft(2, '0')}:${b.minute.toString().padLeft(2, '0')}';
  }

  String _kalanSure(_MolaGrup g) {
    final bit = _bitis(g);
    final fark = bit.difference(_now);
    if (fark.isNegative) return '00:00';
    final dk = fark.inMinutes;
    final sn = fark.inSeconds % 60;
    return '${dk.toString().padLeft(2, '0')}:${sn.toString().padLeft(2, '0')}';
  }

  double _ilerleme(_MolaGrup g) {
    final bas = DateTime(_now.year, _now.month, _now.day, g.baslangic.hour, g.baslangic.minute);
    final gecen = _now.difference(bas).inSeconds;
    return (gecen / (_molaSuresi * 60)).clamp(0.0, 1.0);
  }

  @override
  Widget build(BuildContext context) {
    final saat = _now.hour.toString().padLeft(2, '0');
    final dakika = _now.minute.toString().padLeft(2, '0');
    final saniye = _now.second.toString().padLeft(2, '0');

    return Scaffold(
      appBar: AppBar(
        title: const Text('Mola Takip'),
        backgroundColor: const Color(0xFF37474F),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadGruplar),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // Bildirim izin banner
                if (_bildirimIzni != 'granted')
                  GestureDetector(
                    onTap: _isteBildirimIzni,
                    child: Container(
                      margin: const EdgeInsets.only(bottom: 12),
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: const Color(0xFF4A148C),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: Colors.purpleAccent),
                      ),
                      child: const Row(
                        children: [
                          Icon(Icons.notifications_active, color: Colors.purpleAccent),
                          SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              '🔔 Mola bildirimlerini almak için buraya dokun',
                              style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                            ),
                          ),
                          Icon(Icons.arrow_forward_ios, color: Colors.purpleAccent, size: 16),
                        ],
                      ),
                    ),
                  ),
                // Saat ve vardiya
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: const Color(0xFF263238),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    children: [
                      Text(
                        '$saat:$dakika:$saniye',
                        style: const TextStyle(
                          fontSize: 48, fontWeight: FontWeight.bold,
                          color: Colors.white, fontFamily: 'monospace',
                        ),
                      ),
                      const SizedBox(height: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.orange.withOpacity(0.2),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(color: Colors.orange),
                        ),
                        child: Text(
                          _vardiyaAdi,
                          style: const TextStyle(color: Colors.orange, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                // Gruplar
                ..._gruplar.map((g) => _GrupKart(
                  grup: g,
                  durum: _durum(g),
                  basStr: _formatTod(g.baslangic),
                  bitStr: _formatBitis(g),
                  kalanSure: _durum(g) == _GrupDurum.aktif ? _kalanSure(g) : null,
                  ilerleme: _durum(g) == _GrupDurum.aktif ? _ilerleme(g) : null,
                  bildirimZamani: _durum(g) == _GrupDurum.bitti
                      ? _formatTod(TimeOfDay.fromDateTime(_bildirimZamani(g)))
                      : null,
                  sonrakiGrupNo: g.no < _gruplar.length ? g.no + 1 : null,
                )),
                const SizedBox(height: 12),
                // Bilgi notu
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.white10,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.info_outline, color: Colors.white38, size: 16),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Mola süresi: $_molaSuresi dk  •  Tolerans: $_tolerans dk  •  Bildirim alabilmek için izin verin',
                          style: const TextStyle(color: Colors.white38, fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
    );
  }
}

enum _GrupDurum { bekliyor, aktif, bitti }

class _MolaGrup {
  final int no;
  final TimeOfDay baslangic;
  final List<String> isimler;
  const _MolaGrup({required this.no, required this.baslangic, required this.isimler});
}

class _GrupKart extends StatelessWidget {
  final _MolaGrup grup;
  final _GrupDurum durum;
  final String basStr, bitStr;
  final String? kalanSure, bildirimZamani;
  final double? ilerleme;
  final int? sonrakiGrupNo;

  const _GrupKart({
    required this.grup, required this.durum, required this.basStr,
    required this.bitStr, this.kalanSure, this.ilerleme,
    this.bildirimZamani, this.sonrakiGrupNo,
  });

  Color get _renk {
    switch (durum) {
      case _GrupDurum.aktif: return const Color(0xFF2196F3);
      case _GrupDurum.bitti: return Colors.green;
      case _GrupDurum.bekliyor: return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      color: const Color(0xFF1A1A1A),
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: _renk, width: durum == _GrupDurum.aktif ? 2 : 0.5),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: _renk.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: _renk),
                  ),
                  child: Text(
                    '${grup.no}. GRUP',
                    style: TextStyle(color: _renk, fontWeight: FontWeight.bold, fontSize: 13),
                  ),
                ),
                const Spacer(),
                Text(
                  '$basStr – $bitStr',
                  style: const TextStyle(color: Colors.white70, fontSize: 14),
                ),
              ],
            ),
            const SizedBox(height: 12),
            // Durum
            if (durum == _GrupDurum.bekliyor)
              const Row(children: [
                Icon(Icons.schedule, color: Colors.grey, size: 18),
                SizedBox(width: 6),
                Text('Bekliyor', style: TextStyle(color: Colors.grey, fontSize: 14)),
              ]),
            if (durum == _GrupDurum.aktif) ...[
              Row(children: [
                const Icon(Icons.coffee, color: Color(0xFF2196F3), size: 18),
                const SizedBox(width: 6),
                const Text('Molada', style: TextStyle(color: Color(0xFF2196F3), fontSize: 14, fontWeight: FontWeight.bold)),
                const Spacer(),
                Text(
                  kalanSure ?? '',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    fontFamily: 'monospace',
                  ),
                ),
                const Text(' kaldı', style: TextStyle(color: Colors.white54, fontSize: 12)),
              ]),
              const SizedBox(height: 10),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: ilerleme ?? 0,
                  minHeight: 8,
                  backgroundColor: Colors.white12,
                  color: const Color(0xFF2196F3),
                ),
              ),
            ],
            if (durum == _GrupDurum.bitti) ...[
              Row(children: [
                const Icon(Icons.check_circle, color: Colors.green, size: 18),
                const SizedBox(width: 6),
                const Text('Mola bitti', style: TextStyle(color: Colors.green, fontSize: 14)),
                if (sonrakiGrupNo != null) ...[
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: Colors.orange.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: Colors.orange),
                    ),
                    child: Text(
                      '$sonrakiGrupNo. grup çıkabilir',
                      style: const TextStyle(color: Colors.orange, fontSize: 12, fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ]),
              if (bildirimZamani != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4, left: 24),
                  child: Text(
                    'Bildirim: $bildirimZamani',
                    style: const TextStyle(color: Colors.white24, fontSize: 11),
                  ),
                ),
            ],
            // İsimler
            if (grup.isimler.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Divider(color: Colors.white12, height: 1),
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: grup.isimler.map((isim) => Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.white10,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(isim, style: const TextStyle(color: Colors.white70, fontSize: 12)),
                )).toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
