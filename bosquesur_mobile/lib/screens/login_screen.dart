import 'package:flutter/material.dart';

import '../services/api_service.dart';

class LoginScreen extends StatefulWidget {
  final VoidCallback onLoginSuccess;
  const LoginScreen({super.key, required this.onLoginSuccess});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _userCtrl = TextEditingController(text: 'faena');
  final _passCtrl = TextEditingController(text: 'Bosque2026!');
  final _urlCtrl = TextEditingController(text: BosqueSurApiService.instance.baseUrl);
  bool _cargando = false;
  String? _error;

  Future<void> _ingresar() async {
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      await BosqueSurApiService.instance.login(
        username: _userCtrl.text,
        password: _passCtrl.text,
        customBaseUrl: _urlCtrl.text,
      );
      widget.onLoginSuccess();
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  void _seleccionarPerfil(String username) {
    setState(() {
      _userCtrl.text = username;
      _passCtrl.text = 'Bosque2026!';
    });
  }

  @override
  void dispose() {
    _userCtrl.dispose();
    _passCtrl.dispose();
    _urlCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F6F4),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Card(
            elevation: 2,
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Icon(Icons.forest, size: 52, color: Color(0xFF17301D)),
                    const SizedBox(height: 8),
                    const Text(
                      'BosqueSur Maderas SpA',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                    ),
                    const Text(
                      'App Terreno y Bodega · API REST JWT',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.black54),
                    ),
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 8,
                      alignment: WrapAlignment.center,
                      children: [
                        ActionChip(label: const Text('Faena'), onPressed: () => _seleccionarPerfil('faena')),
                        ActionChip(label: const Text('Patio'), onPressed: () => _seleccionarPerfil('patio')),
                        ActionChip(label: const Text('Gerencia'), onPressed: () => _seleccionarPerfil('gerente')),
                      ],
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _urlCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Endpoint API REST',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _userCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Usuario',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _passCtrl,
                      obscureText: true,
                      decoration: const InputDecoration(
                        labelText: 'Contraseña',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      Text(_error!, style: const TextStyle(color: Colors.red)),
                    ],
                    const SizedBox(height: 20),
                    FilledButton.icon(
                      onPressed: _cargando ? null : _ingresar,
                      icon: const Icon(Icons.lock_open),
                      label: Text(_cargando ? 'Autenticando...' : 'Obtener Token JWT e Ingresar'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
