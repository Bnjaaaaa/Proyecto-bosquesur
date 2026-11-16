import 'package:flutter/material.dart';

import '../services/api_service.dart';

class BodegaQrScreen extends StatefulWidget {
  const BodegaQrScreen({super.key});

  @override
  State<BodegaQrScreen> createState() => _BodegaQrScreenState();
}

class _BodegaQrScreenState extends State<BodegaQrScreen> {
  final _api = BosqueSurApiService.instance;
  final _qrCtrl = TextEditingController();
  final _mermaCtrl = TextEditingController(text: '0.000');

  bool _cargando = false;
  List<Map<String, dynamic>> _ubicaciones = [];
  Map<String, dynamic>? _paquete;
  Map<String, dynamic>? _trazabilidad;
  String _proceso = 'SECADO';
  int? _ubicacionDestinoId;

  @override
  void initState() {
    super.initState();
    _cargarUbicaciones();
  }

  Future<void> _cargarUbicaciones() async {
    try {
      final ubis = await _api.getUbicaciones();
      if (!mounted) return;
      setState(() {
        _ubicaciones = ubis;
        if (ubis.isNotEmpty) _ubicacionDestinoId = ubis.first['id'] as int;
      });
    } catch (_) {}
  }

  void _notificar(String msg, {bool esError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: esError ? Colors.red.shade800 : const Color(0xFF17301D)),
    );
  }

  Future<void> _buscarQr() async {
    final codigo = _qrCtrl.text.trim();
    if (codigo.isEmpty) return;
    setState(() => _cargando = true);
    try {
      final lista = await _api.getPaquetes(codigoQr: codigo);
      if (lista.isEmpty) {
        _notificar('No se encontró el paquete $codigo', esError: true);
        setState(() {
          _paquete = null;
          _trazabilidad = null;
        });
        return;
      }
      final pkt = lista.first;
      final traza = await _api.getTrazabilidadPaquete(pkt['id'] as int);
      if (!mounted) return;
      setState(() {
        _paquete = pkt;
        _trazabilidad = traza;
      });
    } catch (e) {
      _notificar(e.toString(), esError: true);
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  Future<void> _aplicarProceso() async {
    if (_paquete == null) return;
    try {
      await _api.procesarPaquete(
        paqueteId: _paquete!['id'] as int,
        proceso: _proceso,
        ubicacionDestinoId: _ubicacionDestinoId,
        mermaM3: _mermaCtrl.text.trim(),
        observacion: 'Aplicado desde app Flutter',
      );
      _notificar('Proceso $_proceso registrado.');
      await _buscarQr();
    } catch (e) {
      _notificar(e.toString(), esError: true);
    }
  }

  Future<void> _moverUbicacion() async {
    if (_paquete == null || _ubicacionDestinoId == null) return;
    try {
      await _api.moverPaquete(
        paqueteId: _paquete!['id'] as int,
        ubicacionDestinoId: _ubicacionDestinoId!,
        observacion: 'Traslado desde app Flutter',
      );
      _notificar('Paquete trasladado de ubicación.');
      await _buscarQr();
    } catch (e) {
      _notificar(e.toString(), esError: true);
    }
  }

  @override
  void dispose() {
    _qrCtrl.dispose();
    _mermaCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _qrCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Código QR (Ej.: BS-PKT-000001)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton.icon(
                  onPressed: _cargando ? null : _buscarQr,
                  icon: const Icon(Icons.qr_code_2),
                  label: const Text('Consultar'),
                ),
              ],
            ),
          ),
        ),
        if (_paquete != null && _trazabilidad != null) ...[
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${_paquete!['codigo_qr']} · ${_paquete!['estado']}',
                    style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
                  ),
                  Text('${_paquete!['producto_nombre']} (${_paquete!['volumen_m3']} m³ · ${_paquete!['piezas']} pzas)'),
                  Text('Proceso actual: ${_paquete!['proceso_actual']} · Ubicación: ${_paquete!['ubicacion_codigo']}'),
                  const Divider(),
                  Text('Origen forestal: ${_trazabilidad!['faena']?['nombre'] ?? 'Patio'}'),
                  Text('Guía: ${_trazabilidad!['guia']?['numero'] ?? '—'} · Orden: ${_trazabilidad!['orden']?['numero'] ?? '—'}'),
                  Text('Destino venta: ${_trazabilidad!['pedido']?['cliente'] ?? 'Disponible en planta'}'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('Procesar o Trasladar Paquete', style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<String>(
                    key: ValueKey('proceso_$_proceso'),
                    initialValue: _proceso,
                    isExpanded: true,
                    decoration: const InputDecoration(labelText: 'Proceso posterior', border: OutlineInputBorder()),
                    items: const [
                      DropdownMenuItem(value: 'SECADO', child: Text('Secado en cámara')),
                      DropdownMenuItem(value: 'IMPREGNADO', child: Text('Impregnado CCA')),
                      DropdownMenuItem(value: 'CEPILLADO', child: Text('Cepillado / Terminación')),
                      DropdownMenuItem(value: 'REPROCESO', child: Text('Reproceso / Cambio Calidad')),
                    ],
                    onChanged: (v) => setState(() => _proceso = v ?? 'SECADO'),
                  ),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<int>(
                    key: ValueKey('ub_$_ubicacionDestinoId'),
                    initialValue: _ubicacionDestinoId,
                    isExpanded: true,
                    decoration: const InputDecoration(labelText: 'Ubicación de destino', border: OutlineInputBorder()),
                    items: _ubicaciones
                        .map((u) => DropdownMenuItem<int>(
                              value: u['id'] as int,
                              child: Text('${u['codigo']} · ${u['nombre']}', overflow: TextOverflow.ellipsis),
                            ))
                        .toList(),
                    onChanged: (v) => setState(() => _ubicacionDestinoId = v),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _mermaCtrl,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Merma de proceso (m³)', border: OutlineInputBorder()),
                  ),
                  const SizedBox(height: 12),
                  if (_paquete!['estado'] == 'DESPACHADO')
                    const Padding(
                      padding: EdgeInsets.only(bottom: 8),
                      child: Text(
                        'Paquete despachado: ya no admite procesos ni traslados.',
                        style: TextStyle(fontStyle: FontStyle.italic),
                      ),
                    ),
                  Row(
                    children: [
                      Expanded(
                        child: FilledButton(
                          onPressed: _paquete!['estado'] == 'DESPACHADO' ? null : _aplicarProceso,
                          child: const Text('Aplicar Proceso'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OutlinedButton(
                          onPressed: _paquete!['estado'] == 'DESPACHADO' ? null : _moverUbicacion,
                          child: const Text('Solo Mover'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }
}
