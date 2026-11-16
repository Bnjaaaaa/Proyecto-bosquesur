# BosqueSur Móvil (`bosquesur_mobile`)

Aplicación móvil multiplataforma en **Flutter (Dart)** desarrollada como módulo nativo conectado en tiempo real al backend **Django REST Framework + SimpleJWT** de **BosqueSur Maderas SpA**. Configurada para las plataformas **Android**, **Windows** y **Web**.

## Pantallas Operativas Incluidas
1. **Autenticación JWT (`LoginScreen`)**: Solicita `access` y `refresh` token en `POST /api/token/`, adapta los perfiles rápidos (`faena`, `patio`, `gerente`) y permite apuntar al servidor local (`http://10.0.2.2:8000/api` en Emulador Android o `http://127.0.0.1:8000/api` en Windows/Desktop/USB `adb reverse`).
2. **Operación en Bosque (`FaenaScreen`)**: Registro de lotes de cosecha (`POST /api/lotes-cosecha/`) y emisión de guías de despacho forestal asociadas (`POST /api/guias/`).
3. **Recepción en Patio (`PatioRecepcionScreen`)**: Listado de guías en tránsito (`GET /api/guias/?estado=EMITIDA`) y registro de recepción volumétrica con alerta automática de merma (`POST /api/guias/{id}/recepcionar/`).
4. **Bodega y Trazabilidad QR (`BodegaQrScreen`)**: Consulta de paquetes por código QR mediante ingreso manual o selección rápida (`GET /api/paquetes/?codigo_qr=...`), árbol completo de trazabilidad (`GET /api/paquetes/{id}/trazabilidad/`), registro de procesos posteriores (`POST /api/paquetes/{id}/procesar/`) y traslados físicos entre ubicaciones (`POST /api/paquetes/{id}/mover/`).

> **Trabajo futuro:** integración de lectura óptica por cámara mediante `mobile_scanner` en dispositivos Android/iOS (manteniendo el ingreso manual como respaldo).

## Configuración de Red y Seguridad JWT
- **Android (`android/app/src/main/AndroidManifest.xml`)**: incluye `<uses-permission android:name="android.permission.INTERNET"/>` y `android:usesCleartextTraffic="true"` en `<application>` para permitir peticiones HTTP locales hacia `http://10.0.2.2:8000/api` durante las pruebas de desarrollo.
- **Renovación automática de token (`lib/services/api_service.dart`)**: todas las peticiones GET y POST pasan por `_request()`, que ante una respuesta HTTP `401` invoca `POST /api/token/refresh/` con el `refresh` token vigente, almacena los nuevos tokens `access` y `refresh` rotados (`ROTATE_REFRESH_TOKENS=True`) y reintenta la petición una vez; si el refresh falla, cierra la sesión (`logout()`) y lanza `ApiException("Sesión expirada")`.

## Ejecución y Verificación
```powershell
# 1. Asegurar el servidor backend Django corriendo en el puerto 8000
python manage.py runserver 0.0.0.0:8000

# 2. En esta carpeta (bosquesur_mobile):
flutter pub get
flutter analyze          # 0 errores ni advertencias
flutter test             # 3 pruebas (widget + renovación JWT)
flutter build web        # o: flutter run -d windows / -d chrome / emulador Android
```

> Nota: Además de este código fuente nativo Flutter, el servidor Django incluye un **Simulador Móvil Interactivo Web** accesible desde la barra superior en `/app-movil/` que consume exactamente los mismos endpoints JWT para pruebas rápidas sin emulador.
