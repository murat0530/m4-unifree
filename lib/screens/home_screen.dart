import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'login_screen.dart';
import 'duyuru_screen.dart';
import 'kasa_screen.dart';
import 'bilgilendirme_screen.dart';
import 'hakedis_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  Future<void> _logout(BuildContext context) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    if (context.mounted) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const LoginScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('M4 UniFree'),
        backgroundColor: Colors.black,
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => _logout(context),
            tooltip: 'Çıkış',
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              const SizedBox(height: 16),
              // Logo
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: Colors.black,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: const Color(0xFFCC0000), width: 1),
                ),
                child: const Column(
                  children: [
                    Text(
                      'M4',
                      style: TextStyle(
                        color: Color(0xFFCC0000),
                        fontSize: 56,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 4,
                      ),
                    ),
                    Text(
                      'UniFree • 2. Grup',
                      style: TextStyle(color: Colors.white60, fontSize: 14),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 32),
              // Menü butonları
              Expanded(
                child: Column(
                  children: [
                    _MenuButton(
                      icon: Icons.table_chart,
                      label: 'KASA HATTI BİLGİ FORMU',
                      color: const Color(0xFF1A237E),
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(builder: (_) => const KasaScreen()),
                      ),
                    ),
                    const SizedBox(height: 16),
                    _MenuButton(
                      icon: Icons.campaign,
                      label: 'DUYURU & EĞİTİMLER',
                      color: const Color(0xFF1B5E20),
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(builder: (_) => const DuyuruScreen()),
                      ),
                    ),
                    const SizedBox(height: 16),
                    _MenuButton(
                      icon: Icons.info_outline,
                      label: 'GÜNCEL BİLGİLENDİRME',
                      color: const Color(0xFF4A148C),
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(builder: (_) => const BilgilendirmeScreen()),
                      ),
                    ),
                    const SizedBox(height: 16),
                    _MenuButton(
                      icon: Icons.monetization_on,
                      label: 'KASA ÖNÜ HAKEDİŞ & VMI',
                      color: const Color(0xFF7C2D12),
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(builder: (_) => const HakedisScreen()),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MenuButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _MenuButton({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton(
        onPressed: onTap,
        style: ElevatedButton.styleFrom(
          backgroundColor: color,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 24),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
        child: Row(
          children: [
            Icon(icon, size: 28),
            const SizedBox(width: 16),
            Expanded(
              child: Text(
                label,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 0.5,
                ),
              ),
            ),
            const Icon(Icons.arrow_forward_ios, size: 16),
          ],
        ),
      ),
    );
  }
}
