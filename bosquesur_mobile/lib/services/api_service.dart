import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiException implements Exception {
  final String message;
  final int? statusCode;

  ApiException(this.message, [this.statusCode]);

  @override
  String toString() => message;
}

class BosqueSurApiService {
  BosqueSurApiService._();
  static final BosqueSurApiService instance = BosqueSurApiService._();

  String baseUrl = 'http://10.0.2.2:8000/api';
  String? _accessToken;
  String? _refreshToken;
  Map<String, dynamic>? usuarioActual;

  bool get estaAutenticado => _accessToken != null && _accessToken!.isNotEmpty;

  Map<String, String> _headers({bool conAuth = true}) {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (conAuth && _accessToken != null) {
      headers['Authorization'] = 'Bearer $_accessToken';
    }
    return headers;
  }

  dynamic _parseResponse(http.Response response) {
    final bodyText = utf8.decode(response.bodyBytes);
    final decoded = bodyText.isNotEmpty ? jsonDecode(bodyText) : <String, dynamic>{};
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return decoded;
    }
    if (decoded is Map<String, dynamic>) {
      final msg = decoded['detalle'] ?? decoded['detail'] ?? decoded.toString();
      throw ApiException(msg.toString(), response.statusCode);
    }
    throw ApiException('Error HTTP ${response.statusCode}', response.statusCode);
  }

  List<Map<String, dynamic>> _extractList(dynamic decoded) {
    if (decoded is List) {
      return decoded.cast<Map<String, dynamic>>();
    }
    if (decoded is Map<String, dynamic> && decoded['results'] is List) {
      return (decoded['results'] as List).cast<Map<String, dynamic>>();
    }
    return [];
  }

  Future<Map<String, dynamic>> login({
    required String username,
    required String password,
    String? customBaseUrl,
  }) async {
    if (customBaseUrl != null && customBaseUrl.trim().isNotEmpty) {
      baseUrl = customBaseUrl.trim().replaceAll(RegExp(r'/+$'), '');
    }
    final resp = await http.post(
      Uri.parse('$baseUrl/token/'),
      headers: _headers(conAuth: false),
      body: jsonEncode({'username': username.trim(), 'password': password}),
    );
    final data = _parseResponse(resp) as Map<String, dynamic>;
    _accessToken = data['access'] as String?;
    _refreshToken = data['refresh'] as String?;
    usuarioActual = data['usuario'] as Map<String, dynamic>?;
    return data;
  }

  void logout() {
    _accessToken = null;
    _refreshToken = null;
    usuarioActual = null;
  }

  String? get refreshToken => _refreshToken;

  Future<List<Map<String, dynamic>>> getFaenas() async {
    final resp = await http.get(Uri.parse('$baseUrl/faenas/'), headers: _headers());
    return _extractList(_parseResponse(resp));
  }

  Future<List<Map<String, dynamic>>> getPatios() async {
    final resp = await http.get(Uri.parse('$baseUrl/patios/'), headers: _headers());
    return _extractList(_parseResponse(resp));
  }

  Future<List<Map<String, dynamic>>> getProductos() async {
    final resp = await http.get(Uri.parse('$baseUrl/productos/'), headers: _headers());
    return _extractList(_parseResponse(resp));
  }

  Future<List<Map<String, dynamic>>> getUbicaciones() async {
    final resp = await http.get(Uri.parse('$baseUrl/ubicaciones/'), headers: _headers());
    return _extractList(_parseResponse(resp));
  }

  Future<List<Map<String, dynamic>>> getLotesCosecha() async {
    final resp = await http.get(Uri.parse('$baseUrl/lotes-cosecha/'), headers: _headers());
    return _extractList(_parseResponse(resp));
  }

  Future<Map<String, dynamic>> registrarLoteCosecha({
    required int faenaId,
    required int productoId,
    required String volumenCosechado,
    required String cuadrilla,
    String observacion = '',
  }) async {
    final resp = await http.post(
      Uri.parse('$baseUrl/lotes-cosecha/'),
      headers: _headers(),
      body: jsonEncode({
        'faena': faenaId,
        'producto': productoId,
        'volumen_cosechado': volumenCosechado,
        'cuadrilla': cuadrilla,
        'observacion': observacion,
      }),
    );
    return _parseResponse(resp) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> getGuias({String? estado}) async {
    final suffix = estado != null ? '?estado=$estado' : '';
    final resp = await http.get(Uri.parse('$baseUrl/guias/$suffix'), headers: _headers());
    return _extractList(_parseResponse(resp));
  }

  Future<Map<String, dynamic>> emitirGuia({
    required int faenaId,
    int? loteCosechaId,
    required int patioDestinoId,
    required int productoId,
    required String volumenEnviado,
    required String patenteCamion,
    required String conductor,
  }) async {
    final body = <String, dynamic>{
      'faena': faenaId,
      'patio_destino': patioDestinoId,
      'producto': productoId,
      'volumen_enviado': volumenEnviado,
      'patente_camion': patenteCamion,
      'conductor': conductor,
    };
    if (loteCosechaId != null) {
      body['lote_cosecha'] = loteCosechaId;
    }
    final resp = await http.post(
      Uri.parse('$baseUrl/guias/'),
      headers: _headers(),
      body: jsonEncode(body),
    );
    return _parseResponse(resp) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> recepcionarGuia({
    required int guiaId,
    required String volumenRecibido,
    String observacion = '',
  }) async {
    final resp = await http.post(
      Uri.parse('$baseUrl/guias/$guiaId/recepcionar/'),
      headers: _headers(),
      body: jsonEncode({
        'volumen_recibido': volumenRecibido,
        'observacion': observacion,
      }),
    );
    return _parseResponse(resp) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> getPaquetes({String? codigoQr}) async {
    final q = (codigoQr != null && codigoQr.trim().isNotEmpty)
        ? '?codigo_qr=${Uri.encodeQueryComponent(codigoQr.trim())}'
        : '';
    final resp = await http.get(Uri.parse('$baseUrl/paquetes/$q'), headers: _headers());
    return _extractList(_parseResponse(resp));
  }

  Future<Map<String, dynamic>> getTrazabilidadPaquete(int paqueteId) async {
    final resp = await http.get(
      Uri.parse('$baseUrl/paquetes/$paqueteId/trazabilidad/'),
      headers: _headers(),
    );
    return _parseResponse(resp) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> procesarPaquete({
    required int paqueteId,
    required String proceso,
    int? ubicacionDestinoId,
    String mermaM3 = '0',
    String observacion = '',
  }) async {
    final body = <String, dynamic>{
      'proceso': proceso,
      'merma_m3': mermaM3,
      'observacion': observacion,
    };
    if (ubicacionDestinoId != null) {
      body['ubicacion_destino'] = ubicacionDestinoId;
    }
    final resp = await http.post(
      Uri.parse('$baseUrl/paquetes/$paqueteId/procesar/'),
      headers: _headers(),
      body: jsonEncode(body),
    );
    return _parseResponse(resp) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> moverPaquete({
    required int paqueteId,
    required int ubicacionDestinoId,
    String observacion = '',
  }) async {
    final resp = await http.post(
      Uri.parse('$baseUrl/paquetes/$paqueteId/mover/'),
      headers: _headers(),
      body: jsonEncode({
        'ubicacion_destino': ubicacionDestinoId,
        'observacion': observacion,
      }),
    );
    return _parseResponse(resp) as Map<String, dynamic>;
  }
}
