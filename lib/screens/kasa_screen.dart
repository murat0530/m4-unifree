import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/sheets_service.dart';

class KasaScreen extends StatefulWidget {
  const KasaScreen({super.key});

  @override
  State<KasaScreen> createState() => _KasaScreenState();
}

class _KasaScreenState extends State<KasaScreen> {
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  String? _error;

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
      final data = await SheetsService.fetchKasaHatti();
      setState(() {
        _items = data;
        _loading = false;
      });
    } catch (_) {
      setState(() {
        _error = 'Veriler yüklenemedi';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Kasa Hattı Bilgi Formu'),
        backgroundColor: const Color(0xFF1A237E),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _load,
          ),
        ],
      ),
      body: Column(
        children: [
          // Google Form butonu
          Padding(
            padding: const EdgeInsets.all(16),
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                icon: const Icon(Icons.edit_note),
                label: const Text('Takiye Listesi Formu'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF1A237E),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                onPressed: () => launchUrl(
                  Uri.parse('https://sites.google.com/view/umutsalman/%C3%BCye-giri%C5%9Fi/ek-sayfa'),
                  mode: LaunchMode.externalApplication,
                ),
              ),
            ),
          ),
          const Divider(height: 1),
          // Tablo
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Icon(Icons.error_outline, color: Colors.redAccent, size: 48),
                            const SizedBox(height: 12),
                            Text(_error!, style: const TextStyle(color: Colors.white70)),
                            const SizedBox(height: 16),
                            ElevatedButton(onPressed: _load, child: const Text('Tekrar Dene')),
                          ],
                        ),
                      )
                    : _items.isEmpty
                        ? const Center(
                            child: Text('Veri bulunamadı', style: TextStyle(color: Colors.white54)),
                          )
                        : RefreshIndicator(
                            onRefresh: _load,
                            child: _DataTable(items: _items),
                          ),
          ),
        ],
      ),
    );
  }
}

class _DataTable extends StatelessWidget {
  final List<Map<String, dynamic>> items;
  const _DataTable({required this.items});

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox();
    final cols = items.first.keys.toList();

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: SingleChildScrollView(
        child: DataTable(
          headingRowColor: WidgetStateProperty.all(const Color(0xFF1A237E)),
          dataRowColor: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.selected)
                ? const Color(0xFF1A237E).withOpacity(0.3)
                : const Color(0xFF1A1A1A),
          ),
          columnSpacing: 24,
          columns: cols
              .map((c) => DataColumn(
                    label: Text(
                      c,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ))
              .toList(),
          rows: items
              .map((row) => DataRow(
                    cells: cols
                        .map((c) => DataCell(
                              Text(
                                row[c]?.toString() ?? '-',
                                style: const TextStyle(color: Colors.white70),
                              ),
                            ))
                        .toList(),
                  ))
              .toList(),
        ),
      ),
    );
  }
}
