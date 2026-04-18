import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;

const _sheetId = '1vgnCY7mGFnylVLmqPFg3vuuxyHOlPqK-QCvtgtlVYMY';

class HakedisScreen extends StatefulWidget {
  const HakedisScreen({super.key});
  @override
  State<HakedisScreen> createState() => _HakedisScreenState();
}

class _HakedisScreenState extends State<HakedisScreen> {
  List<_Kisi> _grup1 = [];
  List<_Kisi> _grup2 = [];
  bool _loading = true;
  String? _error;
  String _tarih = '';
  String _gun = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
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

      // Tüm hücreleri düz liste olarak al
      List<List<String>> rows = tableRows.map((r) {
        final row = r['c'] as List;
        return List.generate(colCount, (i) {
          if (i >= row.length || row[i] == null || row[i]['v'] == null) return '';
          final v = row[i]['v'].toString();
          if (v.startsWith('Date(')) {
            final m = RegExp(r'Date\((\d+),(\d+),(\d+)\)').firstMatch(v);
            if (m != null) {
              return '${m.group(3)}.${(int.parse(m.group(2)!) + 1).toString().padLeft(2, '0')}.${m.group(1)}';
            }
          }
          return v;
        });
      }).toList();

      // Tarih ve gün
      for (final r in rows.take(5)) {
        for (final c in r) {
          if (RegExp(r'^\d{2}\.\d{2}\.\d{4}$').hasMatch(c)) _tarih = c;
        }
      }

      // Grup 1: satır indeksleri 1=fiş, 2=ispos, 3=isim+not, 4=incentive, 5=istpos, 7=vmi
      _grup1 = _parseGrup(rows, fisIdx: 1, isposIdx: 2, nameIdx: 3, incentiveIdx: 4, istposIdx: 5, vmiIdx: 7);
      // Grup 2: satır indeksleri 9=fiş, 10=ispos, 11=isim+not, 12=incentive, 13=istpos
      _grup2 = _parseGrup(rows, fisIdx: 9, isposIdx: 10, nameIdx: 11, incentiveIdx: 12, istposIdx: 13, vmiIdx: -1);

      setState(() { _loading = false; });
    } catch (e) {
      setState(() { _error = 'Veri yüklenemedi'; _loading = false; });
    }
  }

  List<_Kisi> _parseGrup(List<List<String>> rows, {
    required int fisIdx, required int isposIdx, required int nameIdx,
    required int incentiveIdx, required int istposIdx, required int vmiIdx,
  }) {
    if (nameIdx >= rows.length) return [];
    final nameRow = rows[nameIdx];
    final result = <_Kisi>[];

    for (int i = 1; i < nameRow.length - 1; i += 2) {
      final isim = nameRow[i].trim();
      final not = (i + 1 < nameRow.length) ? nameRow[i + 1].trim() : '';
      if (isim.isEmpty || isim == '-') continue;
      if (not != 'A' && not != 'B' && not != 'C') continue;

      String cell(int rowIdx, int col) {
        if (rowIdx < 0 || rowIdx >= rows.length || col >= rows[rowIdx].length) return '';
        return rows[rowIdx][col].trim();
      }

      result.add(_Kisi(
        isim: isim,
        not: not,
        fis: cell(fisIdx, i),
        ispos: cell(isposIdx, i),
        incentive: cell(incentiveIdx, i),
        istpos: cell(istposIdx, i),
        vmi: vmiIdx >= 0 ? cell(vmiIdx, i) : '',
      ));
    }
    return result;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFE8F0F8),
      appBar: AppBar(
        title: const Text('Oturma & Mola Planı'),
        backgroundColor: const Color(0xFF1A73E8),
        foregroundColor: Colors.white,
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  const Icon(Icons.error_outline, color: Colors.red, size: 48),
                  const SizedBox(height: 12),
                  Text(_error!),
                  const SizedBox(height: 16),
                  ElevatedButton(onPressed: _load, child: const Text('Tekrar Dene')),
                ]))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Tarih
                        if (_tarih.isNotEmpty)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 16),
                            child: Text(
                              _tarih,
                              style: const TextStyle(
                                fontSize: 18, fontWeight: FontWeight.bold,
                                color: Color(0xFF1A1A1A),
                              ),
                            ),
                          ),
                        // GÜVENLİ ÇIKIŞ başlığı
                        const Text(
                          'GÜVENLİ ÇIKIŞ',
                          style: TextStyle(
                            fontSize: 14, fontWeight: FontWeight.bold,
                            color: Color(0xFF1A73E8),
                          ),
                        ),
                        const SizedBox(height: 12),
                        // Grup 1
                        SingleChildScrollView(
                          scrollDirection: Axis.horizontal,
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: _grup1.map((k) => _KisiKutu(kisi: k)).toList(),
                          ),
                        ),
                        const SizedBox(height: 24),
                        // Grup 2
                        if (_grup2.isNotEmpty) ...[
                          const Divider(),
                          const SizedBox(height: 8),
                          SingleChildScrollView(
                            scrollDirection: Axis.horizontal,
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: _grup2.map((k) => _KisiKutu(kisi: k)).toList(),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
    );
  }
}

class _Kisi {
  final String isim, not, fis, ispos, incentive, istpos, vmi;
  const _Kisi({
    required this.isim, required this.not, required this.fis,
    required this.ispos, required this.incentive, required this.istpos,
    required this.vmi,
  });
}

class _KisiKutu extends StatelessWidget {
  final _Kisi kisi;
  const _KisiKutu({required this.kisi});

  Color get _bgColor {
    switch (kisi.not) {
      case 'A': return const Color(0xFF34A853); // yeşil
      case 'B': return const Color(0xFFFFB300); // sarı
      case 'C': return const Color(0xFFEA4335); // kırmızı
      default:  return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 110,
      margin: const EdgeInsets.only(right: 10),
      child: Column(
        children: [
          // Fiş sayısı (üstte)
          if (kisi.fis.isNotEmpty)
            Text(
              kisi.fis,
              style: const TextStyle(
                fontSize: 18, fontWeight: FontWeight.bold, color: Colors.black87,
              ),
            ),
          const SizedBox(height: 4),
          // Ana kutu
          Container(
            decoration: BoxDecoration(
              border: Border.all(color: Colors.black54, width: 1.5),
            ),
            child: Column(
              children: [
                // İspos
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 5),
                  color: Colors.white,
                  child: Text(
                    kisi.ispos,
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                  ),
                ),
                // İsim (renkli arka plan)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  color: _bgColor,
                  child: Text(
                    kisi.isim,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 13, fontWeight: FontWeight.bold, color: Colors.white,
                    ),
                  ),
                ),
                // İncentive
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 5),
                  color: Colors.white,
                  child: Text(
                    kisi.incentive,
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 11, color: Colors.black87),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 4),
          // İstpos
          Text(
            kisi.istpos,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 11, color: Colors.black54),
          ),
          // VMI
          if (kisi.vmi.isNotEmpty) ...[
            const SizedBox(height: 6),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 5),
              color: kisi.not == 'A'
                  ? const Color(0xFFB7E1CD)
                  : kisi.not == 'B'
                      ? const Color(0xFFFFE599)
                      : const Color(0xFFF4CCCC),
              child: Text(
                kisi.vmi,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
