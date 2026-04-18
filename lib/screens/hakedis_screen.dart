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
  List<_KisiData> _grup1 = [];
  List<_KisiData> _grup2 = [];
  bool _loading = true;
  String? _error;
  String _tarih = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  String _dateStr(String v) {
    final m = RegExp(r'Date\((\d+),(\d+),(\d+)\)').firstMatch(v);
    if (m != null) {
      return '${m.group(3)}.${(int.parse(m.group(2)!) + 1).toString().padLeft(2, '0')}.${m.group(1)}';
    }
    return v;
  }

  List<String> _parseRow(dynamic row, int colCount) {
    final cells = <String>[];
    for (int i = 0; i < colCount; i++) {
      final c = (row['c'] as List).length > i ? (row['c'] as List)[i] : null;
      if (c != null && c['v'] != null) {
        final v = c['v'].toString();
        cells.add(v.startsWith('Date(') ? _dateStr(v) : v);
      } else {
        cells.add('');
      }
    }
    return cells;
  }

  List<_KisiData> _buildGrup(List<List<String>> rows, int nameRowIdx) {
    if (nameRowIdx >= rows.length) return [];
    final nameRow = rows[nameRowIdx];
    final fis = nameRowIdx > 0 ? rows[nameRowIdx - 2] : <String>[];
    final ispos = nameRowIdx > 0 ? rows[nameRowIdx - 1] : <String>[];
    final incentive = nameRowIdx + 1 < rows.length ? rows[nameRowIdx + 1] : <String>[];
    final istpos = nameRowIdx + 2 < rows.length ? rows[nameRowIdx + 2] : <String>[];

    final kisiler = <_KisiData>[];
    for (int i = 1; i < nameRow.length - 1; i += 2) {
      final isim = nameRow[i];
      final not = i + 1 < nameRow.length ? nameRow[i + 1] : '';
      if (isim.isEmpty || isim == '-') continue;
      if (not != 'A' && not != 'B' && not != 'C') continue;

      kisiler.add(_KisiData(
        isim: isim,
        not: not,
        fisSayisi: i < fis.length ? fis[i] : '',
        isposNo: i < ispos.length ? ispos[i] : '',
        incentive: i < incentive.length ? incentive[i] : '',
        istposNo: i < istpos.length ? istpos[i] : '',
      ));
    }
    return kisiler;
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

      final rows = tableRows.map((r) => _parseRow(r, colCount)).toList();

      // Tarihi bul
      for (final row in rows.take(3)) {
        for (final cell in row) {
          if (RegExp(r'^\d{2}\.\d{2}\.\d{4}$').hasMatch(cell)) {
            _tarih = cell;
            break;
          }
        }
        if (_tarih.isNotEmpty) break;
      }

      // Grup 1: satır 3 (index 3) isim satırı
      // Grup 2: satır 11 (index 11) isim satırı
      final grup1 = _buildGrup(rows, 3);
      final grup2 = _buildGrup(rows, 11);

      setState(() {
        _grup1 = grup1;
        _grup2 = grup2;
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = 'Veri yüklenemedi'; _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Kasa Önü Hakedişi & VMI'),
        backgroundColor: const Color(0xFF7C2D12),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _ErrorView(message: _error!, onRetry: _load)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      if (_tarih.isNotEmpty) _TarihBanner(tarih: _tarih),
                      const SizedBox(height: 16),
                      if (_grup1.isNotEmpty) ...[
                        _GrupBaslik(title: 'Güvenli Çıkış — 1. Grup'),
                        const SizedBox(height: 8),
                        ..._grup1.map((k) => _KisiKart(kisi: k)),
                        const SizedBox(height: 16),
                      ],
                      if (_grup2.isNotEmpty) ...[
                        _GrupBaslik(title: '2. Grup'),
                        const SizedBox(height: 8),
                        ..._grup2.map((k) => _KisiKart(kisi: k)),
                      ],
                    ],
                  ),
                ),
    );
  }
}

class _KisiData {
  final String isim, not, fisSayisi, isposNo, incentive, istposNo;
  const _KisiData({
    required this.isim,
    required this.not,
    required this.fisSayisi,
    required this.isposNo,
    required this.incentive,
    required this.istposNo,
  });
}

class _TarihBanner extends StatelessWidget {
  final String tarih;
  const _TarihBanner({required this.tarih});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
      decoration: BoxDecoration(
        color: const Color(0xFF7C2D12),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          const Icon(Icons.calendar_today, color: Colors.white70, size: 18),
          const SizedBox(width: 8),
          Text(
            tarih,
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16),
          ),
        ],
      ),
    );
  }
}

class _GrupBaslik extends StatelessWidget {
  final String title;
  const _GrupBaslik({required this.title});

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold),
    );
  }
}

class _KisiKart extends StatelessWidget {
  final _KisiData kisi;
  const _KisiKart({required this.kisi});

  Color get _notRengi {
    switch (kisi.not) {
      case 'A': return Colors.green;
      case 'B': return Colors.amber;
      case 'C': return Colors.orange;
      default: return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      color: const Color(0xFF1A1A1A),
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: _notRengi.withOpacity(0.4)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Üst: İsim + Not
            Row(
              children: [
                Expanded(
                  child: Text(
                    kisi.isim,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 17,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: _notRengi.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: _notRengi),
                  ),
                  child: Text(
                    kisi.not,
                    style: TextStyle(color: _notRengi, fontWeight: FontWeight.bold, fontSize: 14),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            const Divider(color: Colors.white12, height: 1),
            const SizedBox(height: 10),
            // Alt: Detaylar
            Wrap(
              spacing: 12,
              runSpacing: 8,
              children: [
                if (kisi.fisSayisi.isNotEmpty)
                  _InfoChip(icon: Icons.receipt_long, label: 'Fiş', value: kisi.fisSayisi),
                if (kisi.incentive.isNotEmpty)
                  _InfoChip(icon: Icons.star, label: 'İncentive', value: kisi.incentive),
                if (kisi.istposNo.isNotEmpty)
                  _InfoChip(icon: Icons.point_of_sale, label: 'İstpos', value: kisi.istposNo),
                if (kisi.isposNo.isNotEmpty)
                  _InfoChip(icon: Icons.numbers, label: 'İspos', value: kisi.isposNo),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label, value;
  const _InfoChip({required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white10,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: Colors.white54),
          const SizedBox(width: 5),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(color: Colors.white38, fontSize: 10)),
              Text(value, style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600)),
            ],
          ),
        ],
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, color: Colors.redAccent, size: 48),
          const SizedBox(height: 12),
          Text(message, style: const TextStyle(color: Colors.white70)),
          const SizedBox(height: 16),
          ElevatedButton(onPressed: onRetry, child: const Text('Tekrar Dene')),
        ],
      ),
    );
  }
}
