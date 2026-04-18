import 'package:flutter/material.dart';
import '../services/sheets_service.dart';

class BilgilendirmeScreen extends StatefulWidget {
  const BilgilendirmeScreen({super.key});

  @override
  State<BilgilendirmeScreen> createState() => _BilgilendirmeScreenState();
}

class _BilgilendirmeScreenState extends State<BilgilendirmeScreen> {
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
      final data = await SheetsService.fetchBilgilendirme();
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
        title: const Text('Güncel Bilgilendirme'),
        backgroundColor: const Color(0xFF4A148C),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _load,
          ),
        ],
      ),
      body: _loading
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
                      child: Text('Henüz bilgilendirme yok', style: TextStyle(color: Colors.white54)),
                    )
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _items.length,
                        itemBuilder: (_, i) => _BilgilendirmeCard(item: _items[i]),
                      ),
                    ),
    );
  }
}

class _BilgilendirmeCard extends StatelessWidget {
  final Map<String, dynamic> item;
  const _BilgilendirmeCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final baslik = item['Başlık']?.toString() ?? '';
    final icerik = item['İçerik']?.toString() ?? '';
    final tarih = item['Tarih']?.toString() ?? '';
    final gorselUrl = item['Görsel URL']?.toString() ?? '';

    return Card(
      color: const Color(0xFF1A1A1A),
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (gorselUrl.isNotEmpty)
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Image.network(
                  gorselUrl,
                  width: double.infinity,
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => const SizedBox(),
                ),
              ),
            if (gorselUrl.isNotEmpty) const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: Text(
                    baslik,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                if (tarih.isNotEmpty)
                  Text(tarih, style: const TextStyle(color: Colors.white38, fontSize: 12)),
              ],
            ),
            if (icerik.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                icerik,
                style: const TextStyle(color: Colors.white70, fontSize: 14, height: 1.5),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
