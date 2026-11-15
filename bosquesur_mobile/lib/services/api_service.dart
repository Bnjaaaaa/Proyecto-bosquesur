import 'dart:convert';

import 'package:flutter/foundation.dart';
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

  http.Client _client = http.Client();
  Future<void>? _refreshEnCurso;

  @visibleForTesting
  void setHttpClient(http.Client client) {
    _client = client;
  }

  @visibleForTesting
  void setTokensForTest({String? access, String? refresh}) {
    _accessToken = access;
    _refreshToken = refresh;
  }

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

  Future<void> _refrescarToken() async {
    if (_refreshEnCurso != null) {
      return _refreshEnCurso!;
    }
    final futuro = _ejecutarRefresh();
    _refreshEnCurso = futuro;
    try {
      await futuro;
    } finally {
      _refreshEnCurso = null;
    }
  }

  Future<void> _ejecutarRefresh() async {
    final refresh = _refreshToken;
    if (refresh == null || refresh.isEmpty) {
      logout();
      throw ApiException('Sesión expirada', 401);
    }
    final resp = await _client.post(
      Uri.parse('$baseUrl/token/refresh/'),
      headers: _headers(conAuth: false),
      body: jsonEncode({'refresh': refresh}),
    );
    if (resp.statusCode >= 200 && resp.statusCode < 300) {
      final decoded = jsonDecode(utf8.decode(resp.bodyBytes));
      if (decoded is Map<String, dynamic> && decoded['access'] is String) {
        _accessToken = decoded['access'] as String;
        if (decoded['refresh'] is String && (decoded['refresh'] as String).isNotEmpty) {
          _refreshToken = decoded['refresh'] as String;
        }
        return;
      }
    }
    logout();
    throw ApiException('Sesión expirada', 401);
  }

  Future<dynamic> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    Future<http.Response> enviar() {
      final uri = Uri.parse('$baseUrl$path');
      final headers = _headers();
      if (method == 'POST') {
        return _client.post(
          uri,
          headers: headers,
          body: body != null ? jsonEncode(body) : null,
        );
      }
      return _client.get(uri, headers: headers);
    }

    var resp = await enviar();
    if (resp.statusCode == 401) {
      await _refrescarToken();
      resp = await enviar();
    }
    return _parseResponse(resp);
  }

  Future<Map<String, dynamic>> login({
    required String username,
    required String password,
    String? customBaseUrl,
  }) async {
    if (customBaseUrl != null && customBaseUrl.trim().isNotEmpty) {
      baseUrl = customBaseUrl.trim().replaceAll(RegExp(r'/+$'), '');
    }
    final resp = await _client.post(
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
    return _extractList(await _request('GET', '/faenas/'));
  }

  Future<List<Map<String, dynamic>>> getPatios() async {
    return _extractList(await _request('GET', '/patios/'));
  }

  Future<List<Map<String, dynamic>>> getProductos() async {
    return _extractList(await _request('GET', '/productos/'));
  }

  Future<List<Map<String, dynamic>>> getUbicaciones() async {
    return _extractList(await _request('GET', '/ubicaciones/'));
  }

  Future<List<Map<String, dynamic>>> getLotesCosecha() async {
    return _extractList(await _request('GET', '/lotes-cosecha/'));
  }

  Future<Map<String, dynamic>> registrarLoteCosecha({
    required int faenaId,
    required int productoId,
    required String volumenCosechado,
    required String cuadrilla,
    String observacion = '',
  }) async {
    return await _request(
      'POST',
      '/lotes-cosecha/',
      body: {
        'faena': faenaId,
        'producto': productoId,
        'volumen_cosechado': volumenCosechado,
        'cuadrilla': cuadrilla,
        'observacion': observacion,
      },
    ) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> getGuias({String? estado}) async {
    final suffix = estado != null ? '?estado=$estado' : '';
    return _extractList(await _request('GET', '/guias/$suffix'));
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
    return await _request('POST', '/guias/', body: body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> recepcionarGuia({
    required int guiaId,
    required String volumenRecibido,
    String observacion = '',
  }) async {
    return await _request(
      'POST',
      '/guias/$guiaId/recepcionar/',
      body: {
        'volumen_recibido': volumenRecibido,
        'observacion': observacion,
      },
    ) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> getPaquetes({String? codigoQr}) async {
    final q = (codigoQr != null && codigoQr.trim().isNotEmpty)
        ? '?codigo_qr=${Uri.encodeQueryComponent(codigoQr.trim())}'
        : '';
    return _extractList(await _request('GET', '/paquetes/$q'));
  }

  Future<Map<String, dynamic>> getTrazabilidadPaquete(int paqueteId) async {
    return await _request('GET', '/paquetes/$paqueteId/trazabilidad/') as Map<String, dynamic>;
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
    return await _request(
      'POST',
      '/paquetes/$paqueteId/procesar/',
      body: body,
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> moverPaquete({
    required int paqueteId,
    required int ubicacionDestinoId,
    String observacion = '',
  }) async {
    return await _request(
      'POST',
      '/paquetes/$paqueteId/mover/',
      body: {
        'ubicacion_destino': ubicacionDestinoId,
        'observacion': observacion,
      },
    ) as Map<String, dynamic>;
  }
}
