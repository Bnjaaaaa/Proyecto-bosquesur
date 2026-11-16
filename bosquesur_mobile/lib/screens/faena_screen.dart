import 'package:flutter/material.dart';

import '../services/api_service.dart';

class FaenaScreen extends StatefulWidget {
  const FaenaScreen({super.key});

  @override
  State<FaenaScreen> createState() => _FaenaScreenState();
}

class _FaenaScreenState extends State<FaenaScreen> {
  final _api = BosqueSurApiService.instance;
  bool _cargando = true;
  List<Map<String, dynamic>> _faenas = [];
  List<Map<String, dynamic>> _patios = [];
  List<Map<String, dynamic>> _rollizos = [];
  List<Map<String, dynamic>> _lotes = [];

  int? _faenaId;
  int? _patioId;
  int? _productoId;
  int? _loteId;

  final _volCosechaCtrl = TextEditingController();
  final _cuadrillaCtrl = TextEditingController(text: 'Cuadrilla Forestal 1');
  final _volGuiaCtrl = TextEditingController();
  final _patenteCtrl = TextEditingController();
  final _conductorCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _cargarCatalogos();
  }

  Future<void> _cargarCatalogos() async {
    setState(() => _cargando = true);
    try {
      final results = await Future.wait([
        _api.getFaenas(),
        _api.getPatios(),
        _api.getProductos(),
        _api.getLotesCosecha(),
      ]);
      var faenas = results[0];
      // Un usuario FAENA solo puede operar en su predio asignado: se muestra solo ese.
      final faenaAsignada = _api.usuarioActual?['faena_id'] as int?;
      if (faenaAsignada != null) {
        final propias = faenas.where((f) => f['id'] == faenaAsignada).toList();
        if (propias.isNotEmpty) faenas = propias;
      }
      final patios = results[1];
      final productos = results[2].where((p) => p['tipo'] == 'ROLLIZO').toList();
      final lotes = results[3];

      if (!mounted) return;
      setState(() {
        _faenas = faenas;
        _patios = patios;
        _rollizos = productos;
        _lotes = lotes;
        _faenaId = faenas.isNotEmpty ? faenas.first['id'] as int : null;
        _patioId = patios.isNotEmpty ? patios.first['id'] as int : null;
        _productoId = productos.isNotEmpty ? productos.first['id'] as int : null;
      });
    } catch (e) {
      _notificar(e.toString(), esError: true);
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  void _notificar(String msg, {bool esError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: esError ? Colors.red.shade800 : const Color(0xFF17301D)),
    );
  }

  Future<void> _registrarCosecha() async {
    if (_faenaId == null || _productoId == null) return;
    try {
      final lote = await _api.registrarLoteCosecha(
        faenaId: _faenaId!,
        productoId: _productoId!,
        volumenCosechado: _volCosechaCtrl.text.trim(),
        cuadrilla: _cuadrillaCtrl.text.trim(),
      );
      _volCosechaCtrl.clear();
      _notificar('Lote ${lote['codigo']} registrado correctamente.');
      await _cargarCatalogos();
    } catch (e) {
      _notificar(e.toString(), esError: true);
    }
  }

  Future<void> _emitirGuia() async {
    if (_faenaId == null || _patioId == null || _productoId == null) return;
    try {
      final guia = await _api.emitirGuia(
        faenaId: _faenaId!,
        loteCosechaId: _loteId,
        patioDestinoId: _patioId!,
        productoId: _productoId!,
        volumenEnviado: _volGuiaCtrl.text.trim(),
        patenteCamion: _patenteCtrl.text.trim(),
        conductor: _conductorCtrl.text.trim(),
      );
      _volGuiaCtrl.clear();
      _patenteCtrl.clear();
      _conductorCtrl.clear();
      _notificar('Guía ${guia['numero']} emitida en tránsito.');
    } catch (e) {
      _notificar(e.toString(), esError: true);
    }
  }

  @override
  void dispose() {
    _volCosechaCtrl.dispose();
    _cuadrillaCtrl.dispose();
    _volGuiaCtrl.dispose();
    _patenteCtrl.dispose();
    _conductorCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_cargando) {
      return const Center(child: CircularProgressIndicator());
    }
    return RefreshIndicator(
      onRefresh: _cargarCatalogos,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('1. Registrar Lote de Cosecha', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<int>(
                    key: ValueKey('faena_$_faenaId'),
                    initialValue: _faenaId,
                    decoration: const InputDecoration(labelText: 'Faena / Predio', border: OutlineInputBorder()),
                    items: _faenas.map((f) => DropdownMenuItem(value: f['id'] as int, child: Text(f['nombre'] as String))).toList(),
                    onChanged: (v) => setState(() => _faenaId = v),
                  ),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<int>(
                    key: ValueKey('prod_$_productoId'),
                    initialValue: _productoId,
                    decoration: const InputDecoration(labelText: 'Rollizo', border: OutlineInputBorder()),
                    items: _rollizos.map((p) => DropdownMenuItem(value: p['id'] as int, child: Text(p['nombre'] as String))).toList(),
                    onChanged: (v) => setState(() => _productoId = v),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _volCosechaCtrl,
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          decoration: const InputDecoration(labelText: 'Volumen (m³)', border: OutlineInputBorder()),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextField(
                          controller: _cuadrillaCtrl,
                          decoration: const InputDecoration(labelText: 'Cuadrilla', border: OutlineInputBorder()),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  FilledButton(onPressed: _registrarCosecha, child: const Text('Guardar Lote de Cosecha')),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('2. Emitir Guía de Despacho Forestal', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<int?>(
                    key: ValueKey('lote_$_loteId'),
                    initialValue: _loteId,
                    decoration: const InputDecoration(labelText: 'Lote asociado (opcional)', border: OutlineInputBorder()),
                    items: [
                      const DropdownMenuItem<int?>(value: null, child: Text('Sin lote específico')),
                      ..._lotes.map((l) => DropdownMenuItem<int?>(
                            value: l['id'] as int,
                            child: Text('${l['codigo']} · ${l['faena_nombre']}'),
                          )),
                    ],
                    onChanged: (v) => setState(() => _loteId = v),
                  ),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<int>(
                    key: ValueKey('patio_$_patioId'),
                    initialValue: _patioId,
                    decoration: const InputDecoration(labelText: 'Patio de destino', border: OutlineInputBorder()),
                    items: _patios.map((p) => DropdownMenuItem(value: p['id'] as int, child: Text(p['nombre'] as String))).toList(),
                    onChanged: (v) => setState(() => _patioId = v),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _volGuiaCtrl,
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          decoration: const InputDecoration(labelText: 'Vol. enviado (m³)', border: OutlineInputBorder()),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextField(
                          controller: _patenteCtrl,
                          textCapitalization: TextCapitalization.characters,
                          decoration: const InputDecoration(labelText: 'Patente (ABCD12)', border: OutlineInputBorder()),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _conductorCtrl,
                    decoration: const InputDecoration(labelText: 'Conductor', border: OutlineInputBorder()),
                  ),
                  const SizedBox(height: 12),
                  FilledButton.icon(
                    onPressed: _emitirGuia,
                    icon: const Icon(Icons.send),
                    label: const Text('Emitir Guía a Patio'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
