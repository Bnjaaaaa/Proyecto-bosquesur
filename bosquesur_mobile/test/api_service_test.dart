import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:bosquesur_mobile/services/api_service.dart';

void main() {
  final api = BosqueSurApiService.instance;

  tearDown(() {
    api.logout();
    api.setHttpClient(http.Client());
  });

  test('Renueva access y refresh token ante 401 y reintenta la peticion una vez', () async {
    api.setTokensForTest(access: 'access_vencido', refresh: 'refresh_inicial');
    var llamadasFaenas = 0;
    var llamadasRefresh = 0;

    api.setHttpClient(MockClient((req) async {
      if (req.url.path.endsWith('/faenas/')) {
        llamadasFaenas++;
        if (llamadasFaenas == 1) {
          expect(req.headers['Authorization'], 'Bearer access_vencido');
          return http.Response(jsonEncode({'detail': 'Token expired'}), 401);
        }
        expect(req.headers['Authorization'], 'Bearer access_nuevo');
        return http.Response(jsonEncode([{'id': 1, 'nombre': 'Predio 1'}]), 200);
      }
      if (req.url.path.endsWith('/token/refresh/')) {
        llamadasRefresh++;
        final payload = jsonDecode(req.body) as Map<String, dynamic>;
        expect(payload['refresh'], 'refresh_inicial');
        return http.Response(
          jsonEncode({'access': 'access_nuevo', 'refresh': 'refresh_rotado'}),
          200,
        );
      }
      return http.Response('Not found', 404);
    }));

    final faenas = await api.getFaenas();
    expect(faenas, hasLength(1));
    expect(llamadasFaenas, 2);
    expect(llamadasRefresh, 1);
    expect(api.refreshToken, 'refresh_rotado');
    expect(api.estaAutenticado, isTrue);
  });

  test('Cierra sesion y lanza ApiException("Sesión expirada") si falla el refresh', () async {
    api.setTokensForTest(access: 'access_vencido', refresh: 'refresh_invalido');
    api.usuarioActual = {'username': 'faena'};

    api.setHttpClient(MockClient((req) async {
      if (req.url.path.endsWith('/token/refresh/')) {
        return http.Response(jsonEncode({'detail': 'Token is blacklisted'}), 401);
      }
      return http.Response(jsonEncode({'detail': 'Token expired'}), 401);
    }));

    await expectLater(
      api.getFaenas(),
      throwsA(
        isA<ApiException>().having((e) => e.message, 'message', 'Sesión expirada'),
      ),
    );
    expect(api.estaAutenticado, isFalse);
    expect(api.refreshToken, isNull);
    expect(api.usuarioActual, isNull);
  });
}
