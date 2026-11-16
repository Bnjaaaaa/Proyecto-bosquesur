import 'package:flutter/material.dart';

import 'screens/bodega_qr_screen.dart';
import 'screens/faena_screen.dart';
import 'screens/login_screen.dart';
import 'screens/patio_recepcion_screen.dart';
import 'services/api_service.dart';

void main() {
  runApp(const BosqueSurApp());
}

class BosqueSurApp extends StatelessWidget {
  const BosqueSurApp({super.key});

  @override
  Widget build(BuildContext context) {
    const verdeBosque = Color(0xFF17301D);
    const cafeMadera = Color(0xFF6B4423);

    return MaterialApp(
      title: 'BosqueSur Móvil',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: verdeBosque,
          primary: verdeBosque,
          secondary: cafeMadera,
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: verdeBosque,
          foregroundColor: Colors.white,
        ),
      ),
      home: const RootGate(),
    );
  }
}

class RootGate extends StatefulWidget {
  const RootGate({super.key});

  @override
  State<RootGate> createState() => _RootGateState();
}

class _RootGateState extends State<RootGate> {
  void _actualizarEstado() => setState(() {});

  @override
  Widget build(BuildContext context) {
    if (!BosqueSurApiService.instance.estaAutenticado) {
      return LoginScreen(onLoginSuccess: _actualizarEstado);
    }
    return HomeShell(onLogout: _actualizarEstado);
  }
}

class HomeShell extends StatefulWidget {
  final VoidCallback onLogout;
  const HomeShell({super.key, required this.onLogout});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  void initState() {
    super.initState();
    final rol = BosqueSurApiService.instance.usuarioActual?['rol'] as String? ?? '';
    if (rol == 'PATIO') {
      _index = 1;
    }
  }

  @override
  Widget build(BuildContext context) {
    final usuario = BosqueSurApiService.instance.usuarioActual ?? {};
    final nombre = '${usuario['first_name'] ?? ''} ${usuario['last_name'] ?? ''}'.trim();
    final rol = usuario['rol'] ?? '';

    const pantallas = [
      FaenaScreen(),
      PatioRecepcionScreen(),
      BodegaQrScreen(),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('BosqueSur Terreno & Planta', style: TextStyle(fontSize: 17)),
            Text(
              '$nombre · Rol $rol',
              style: const TextStyle(fontSize: 12, color: Colors.white70),
            ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Cerrar sesión JWT',
            icon: const Icon(Icons.logout),
            onPressed: () {
              BosqueSurApiService.instance.logout();
              widget.onLogout();
            },
          ),
        ],
      ),
      body: pantallas[_index],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.forest), label: 'Bosque / Guías'),
          NavigationDestination(icon: Icon(Icons.local_shipping), label: 'Recepción Patio'),
          NavigationDestination(icon: Icon(Icons.qr_code_scanner), label: 'Bodega QR'),
        ],
      ),
    );
  }
}
