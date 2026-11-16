import 'package:flutter/material.dart';

import '../services/api_service.dart';

class PatioRecepcionScreen extends StatefulWidget {
  const PatioRecepcionScreen({super.key});

  @override
  State<PatioRecepcionScreen> createState() => _PatioRecepcionScreenState();
}

class _PatioRecepcionScreenState extends State<PatioRecepcionScreen> {
  final _api = BosqueSurApiService.instance;
  bool _cargando = true;
  List<Map<String, dynamic>> _guiasPendientes = [];

  @override
  void initState() {
    super.initState();
    _cargarGuias();
  }

  Future<void> _cargarGuias() async {
    setState(() => _cargando = true);
    try {
      final guias = await _api.getGuias(estado: 'EMITIDA');
      if (!mounted) return;
      setState(() => _guiasPendientes = guias);
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

  Future<void> _abrirDialogoRecepcion(Map<String, dynamic> guia) async {
    final datos = await showDialog<({String volumen, String observacion})>(
      context: context,
      builder: (ctx) => _DialogoRecepcion(guia: guia),
    );
    if (datos == null) return;
    try {
      await _api.recepcionarGuia(
        guiaId: guia['id'] as int,
        volumenRecibido: datos.volumen,
        observacion: datos.observacion,
      );
      _notificar('Guía ${guia['numero']} recepcionada en inventario.');
      await _cargarGuias();
    } catch (e) {
      _notificar(e.toString(), esError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_cargando) {
      return const Center(child: CircularProgressIndicator());
    }
    return RefreshIndicator(
      onRefresh: _cargarGuias,
      child: _guiasPendientes.isEmpty
          ? ListView(
              children: const [
                Padding(
                  padding: EdgeInsets.all(32),
                  child: Center(child: Text('No hay guías pendientes en tránsito.')),
                ),
              ],
            )
          : ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: _guiasPendientes.length,
              itemBuilder: (context, i) {
                final g = _guiasPendientes[i];
                return Card(
                  child: ListTile(
                    leading: const CircleAvatar(child: Icon(Icons.local_shipping)),
                    title: Text('${g['numero']} · ${g['volumen_enviado']} m³'),
                    subtitle: Text('${g['faena_nombre']} → ${g['patio_destino_nombre']}\n${g['producto_nombre']} (${g['patente_camion']})'),
                    isThreeLine: true,
                    trailing: FilledButton(
                      onPressed: () => _abrirDialogoRecepcion(g),
                      child: const Text('Recibir'),
                    ),
                  ),
                );
              },
            ),
    );
  }
}


/// Diálogo con sus propios controladores: se liberan en dispose(), cuando la
/// animación de cierre ya terminó (evita usar un controlador ya liberado).
class _DialogoRecepcion extends StatefulWidget {
  const _DialogoRecepcion({required this.guia});
  final Map<String, dynamic> guia;

  @override
  State<_DialogoRecepcion> createState() => _DialogoRecepcionState();
}

class _DialogoRecepcionState extends State<_DialogoRecepcion> {
  late final TextEditingController _volCtrl =
      TextEditingController(text: widget.guia['volumen_enviado'].toString());
  final _obsCtrl = TextEditingController();

  @override
  void dispose() {
    _volCtrl.dispose();
    _obsCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final guia = widget.guia;
    return AlertDialog(
      title: Text('Recepcionar ${guia['numero']}'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('Origen: ${guia['faena_nombre']} · Camión ${guia['patente_camion']}'),
          const SizedBox(height: 12),
          TextField(
            controller: _volCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'Volumen recibido en patio (m³)', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _obsCtrl,
            decoration: const InputDecoration(labelText: 'Observación', border: OutlineInputBorder()),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancelar')),
        FilledButton(
          onPressed: () => Navigator.pop(
            context,
            (volumen: _volCtrl.text.trim(), observacion: _obsCtrl.text.trim()),
          ),
          child: const Text('Confirmar'),
        ),
      ],
    );
  }
}
