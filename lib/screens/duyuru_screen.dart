import 'package:flutter/material.dart';
import '../services/sheets_service.dart';

class DuyuruScreen extends StatefulWidget {
  const DuyuruScreen({super.key});

  @override
  State<DuyuruScreen> createState() => _DuyuruScreenState();
}

class _DuyuruScreenState extends State<DuyuruScreen> {
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
      final data = await SheetsService.fetchDuyurular();
      setState(() {
        _items = data;
        _loading = false;
      });
    } catch (e) {
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
        title: const Text('Duyuru & Eğitimler'),
        backgroundColor: const Color(0xFF1B5E20),
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
              ? _ErrorView(message: _error!, onRetry: _load)
              : _items.isEmpty
                  ? const Center(
                      child: Text(
                        'Henüz duyuru yok',
                        style: TextStyle(color: Colors.white54),
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _items.length,
                        itemBuilder: (_, i) => _DuyuruCard(item: _items[i]),
                      ),
                    ),
    );
  }
}

class _DuyuruCard extends StatelessWidget {
  final Map<String, dynamic> item;
  const _DuyuruCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final baslik = item['Başlık']?.toString() ?? '';
    final icerik = item['İçerik']?.toString() ?? '';
    final tarih = item['Tarih']?.toString() ?? '';
    final tip = item['Tip']?.toString() ?? 'Duyuru';

    Color tipColor;
    switch (tip.toLowerCase()) {
      case 'eğitim':
        tipColor = Colors.blue;
        break;
      case 'uyarı':
        tipColor = Colors.orange;
        break;
      default:
        tipColor = const Color(0xFF1B5E20);
    }

    return Card(
      color: const Color(0xFF1A1A1A),
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: tipColor.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: tipColor),
                  ),
                  child: Text(
                    tip,
                    style: TextStyle(color: tipColor, fontSize: 11, fontWeight: FontWeight.bold),
                  ),
                ),
                const Spacer(),
                if (tarih.isNotEmpty)
                  Text(tarih, style: const TextStyle(color: Colors.white38, fontSize: 12)),
              ],
            ),
            if (baslik.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                baslik,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
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
