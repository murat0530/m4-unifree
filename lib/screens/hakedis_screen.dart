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
  List<List<String>> _rows = [];
  bool _loading = true;
  String? _error;
  String _tarih = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final url = Uri.parse(
        'https://docs.google.com/spreadsheets/d/$_sheetId/gviz/tq?tqx=out:json',
      );
      final res = await http.get(url);
      final raw = res.body;
      final jsonStr = raw.substring(raw.indexOf('(') + 1, raw.lastIndexOf(')'));
      final data = json.decode(jsonStr);

      final tableRows = data['table']['rows'] as List;
      final rows = <List<String>>[];
      String tarih = '';

      for (final row in tableRows) {
        final cells = (row['c'] as List).map((c) {
          if (c == null || c['v'] == null) return '';
          final v = c['v'].toString();
          // Tarih formatını düzelt: Date(2026,3,18) → 18.04.2026
          if (v.startsWith('Date(')) {
            final parts = RegExp(r'Date\((\d+),(\d+),(\d+)\)').firstMatch(v);
            if (parts != null) {
              final y = parts.group(1)!;
              final m = int.parse(parts.group(2)!) + 1;
              final d = parts.group(3)!;
              tarih = '$d.${m.toString().padLeft(2, '0')}.$y';
              return tarih;
            }
          }
          return v;
        }).toList();

        final nonEmpty = cells.where((c) => c.isNotEmpty).toList();
        if (nonEmpty.isNotEmpty) rows.add(cells);
        if (tarih.isNotEmpty) _tarih = tarih;
      }

      setState(() {
        _rows = rows;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Veri yüklenemedi: $e';
        _loading = false;
      });
    }
  }

  // Kişileri kolon çiftlerinden çıkar (isim, not çiftleri)
  List<Map<String, dynamic>> _parseKisiler() {
    if (_rows.length < 4) return [];
    // İsim satırını bul: sayı olmayan, tek harfli not içeren satır
    List<String>? nameRow;
    for (final row in _rows) {
      final nonEmpty = row.where((c) => c.isNotEmpty).toList();
      final hasGrade = nonEmpty.any((c) => c == 'A' || c == 'B' || c == 'C');
      final hasName = nonEmpty.any((c) =>
          c.length > 1 && !RegExp(r'^[\d.,₺/\-]+$').hasMatch(c) && !c.contains('Date'));
      if (hasGrade && hasName) {
        nameRow = row;
        break;
      }
    }
    if (nameRow == null) return [];

    final kisiler = <Map<String, dynamic>>[];
    for (int i = 0; i < nameRow.length; i++) {
      final val = nameRow[i];
      // Not harfi (A, B, C) ise bir önceki değer isimdir
      if ((val == 'A' || val == 'B' || val == 'C') && i > 0) {
        final isim = nameRow[i - 1];
        if (isim.isNotEmpty && !RegExp(r'^[\d.,₺/\-]+$').hasMatch(isim)) {
          kisiler.add({'isim': isim, 'not': val, 'colIndex': i - 1});
        }
      }
    }
    return kisiler;
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
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Tarih başlığı
                        if (_tarih.isNotEmpty)
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.symmetric(
                                vertical: 12, horizontal: 16),
                            decoration: BoxDecoration(
                              color: const Color(0xFF7C2D12),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Text(
                              'Tarih: $_tarih',
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                                fontSize: 16,
                              ),
                            ),
                          ),
                        const SizedBox(height: 16),
                        // Kişi kartları
                        ..._buildKisiKartlari(),
                        const SizedBox(height: 16),
                        // Ham tablo
                        _buildTablo(),
                      ],
                    ),
                  ),
                ),
    );
  }

  List<Widget> _buildKisiKartlari() {
    final kisiler = _parseKisiler();
    if (kisiler.isEmpty) return [];

    return [
      const Text(
        'Kasa Personeli',
        style: TextStyle(
            color: Colors.white,
            fontSize: 16,
            fontWeight: FontWeight.bold),
      ),
      const SizedBox(height: 8),
      GridView.builder(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 3,
          childAspectRatio: 1.4,
          crossAxisSpacing: 8,
          mainAxisSpacing: 8,
        ),
        itemCount: kisiler.length,
        itemBuilder: (_, i) {
          final k = kisiler[i];
          final not = k['not'] as String;
          Color notRengi;
          switch (not) {
            case 'A':
              notRengi = Colors.green;
              break;
            case 'B':
              notRengi = Colors.lightGreen;
              break;
            case 'C':
              notRengi = Colors.orange;
              break;
            default:
              notRengi = Colors.grey;
          }
          return Container(
            decoration: BoxDecoration(
              color: const Color(0xFF1A1A1A),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: notRengi.withOpacity(0.5)),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  k['isim'] as String,
                  style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 13),
                  textAlign: TextAlign.center,
                ),
                if (not.isNotEmpty)
                  Container(
                    margin: const EdgeInsets.only(top: 4),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: notRengi.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: notRengi),
                    ),
                    child: Text(
                      not,
                      style: TextStyle(
                          color: notRengi,
                          fontWeight: FontWeight.bold,
                          fontSize: 12),
                    ),
                  ),
              ],
            ),
          );
        },
      ),
      const SizedBox(height: 16),
    ];
  }

  Widget _buildTablo() {
    if (_rows.isEmpty) return const SizedBox();

    // Anlamlı satırları filtrele (boş olmayanlar)
    final anlamliSatirlar = _rows
        .where((r) => r.where((c) => c.isNotEmpty).length > 2)
        .toList();

    if (anlamliSatirlar.isEmpty) return const SizedBox();

    // Sütun genişliklerini hesapla
    final maxCols = anlamliSatirlar
        .map((r) => r.length)
        .reduce((a, b) => a > b ? a : b);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Detay Tablo',
          style: TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Table(
            border: TableBorder.all(
              color: Colors.white24,
              width: 0.5,
            ),
            defaultColumnWidth: const FixedColumnWidth(80),
            children: anlamliSatirlar.map((row) {
              return TableRow(
                decoration: BoxDecoration(
                  color: anlamliSatirlar.indexOf(row) == 3
                      ? const Color(0xFF7C2D12).withOpacity(0.3)
                      : const Color(0xFF1A1A1A),
                ),
                children: List.generate(maxCols, (i) {
                  final val = i < row.length ? row[i] : '';
                  return Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 6, vertical: 8),
                    child: Text(
                      val,
                      style: TextStyle(
                        color: val.isEmpty ? Colors.transparent : Colors.white70,
                        fontSize: 12,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  );
                }),
              );
            }).toList(),
          ),
        ),
      ],
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
          Text(message,
              style: const TextStyle(color: Colors.white70),
              textAlign: TextAlign.center),
          const SizedBox(height: 16),
          ElevatedButton(onPressed: onRetry, child: const Text('Tekrar Dene')),
        ],
      ),
    );
  }
}
