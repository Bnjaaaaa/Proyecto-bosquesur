# Plan de Desarrollo del Prototipo · BosqueSur Maderas SpA (ES3)

**Asignatura:** Proyecto de Integración (`TIHI63`) · **Sección:** `D-IEI-N6-P1-C1`  
**Equipo:** Víctor Cancino, Felipe Mardones y Benjamín Contesso  
**Metodología:** Scrumban (iteraciones semanales con flujo continuo y rotación de Jefe de Proyecto)

---

## 1. Objetivo del Prototipo ES3

Materializar un sistema completamente integrado web + API REST JWT + cliente móvil multiplataforma sobre una base relacional única, demostrando de punta a punta los **17 requisitos obligatorios de la Sección 5.2 de `caso_bosquesur.pdf`**: desde el abastecimiento y cosecha en predio hasta paquetes con código QR SVG, procesos posteriores, compras externas aprobadas, ventas con documento interno simulado (sin SII), dashboard real, reportes exportables y auditoría SHA-256.

---

## 2. Alcance Implementado vs. Exclusiones Normativas

### Alcance Funcional Implementado (17/17 Requisitos ES3)

| Módulo | Capacidades Implementadas |
|---|---|
| Seguridad y RBAC (`cuentas/`) | 4 roles (`GERENTE`, `ADMINISTRATIVO`, `FAENA`, `PATIO`), matriz de 21 permisos para web y API, logs automáticos de `ACCESO_DENEGADO`. |
| Origen y Cosecha (`maestros/`, `operaciones/`) | Proveedores forestales con contrato vigente, predios (`Faena`), lotes `LC-000XXX` con volumen m³. |
| Transporte y Recepción (`operaciones/`) | Emisión de guías `GD-000XXX` (`EMITIDA`), recepción en patio con cálculo de merma %, alerta sobre `3.0 %` y resolución gerencial de discrepancias. |
| Producción y Paquetes QR (`operaciones/`) | Órdenes `OP-000XXX` atómicas, generación de `Paquete` (`BS-PKT-XXXXXX`) con SVG QR (`qrcode 8.2`), procesos (`SECADO`, `IMPREGNADO`, `CEPILLADO`, `REPROCESO`), traslados en `UbicacionBodega` e `HistorialPaquete`. |
| Compras y Ventas (`operaciones/`) | `OrdenCompra` (`OC-`: solicitud -> aprobación obligatoria `GERENTE` -> recepción suma inventario); `PedidoVenta` (`PV-`) con reserva, anulación con liberación de paquetes y guía interna simulada `GDC-INT-XXXXXX`. |
| Analítica, Reportes y Auditoría | Dashboard Chart.js real (`/dashboard/`), 3 reportes con filtro por fechas y exportación CSV (`/reportes/`), bitácora SHA-256 (`/auditoria/`) y CLI `verificar_auditoria`. |
| Integración Móvil (`api/`, `bosquesur_mobile/`) | 14 ViewSets DRF + SimpleJWT, simulador interactivo `/app-movil/` y aplicación nativa Flutter `bosquesur_mobile/` (Dart + JWT). |

### Fuera de Alcance Explícito

- Integración tributaria real con el **Servicio de Impuestos Internos (SII)**, emisión de DTE, timbraje CAF y certificados tributarios. Los documentos comerciales de despacho son internos/simulados (`GDC-INT-`, leyenda `NO VÁLIDO COMO DTE`).

---

## 3. Arquitectura e Integración de Datos

```text
  Flutter (bosquesur_mobile) / Simulador /app-movil/      Portal Web (Oficina / Bodega / Gerencia)
                   │ JSON + Bearer JWT                                     │ HTTP / Sesión CSRF
                   └───────────────────────────┬───────────────────────────┘
                                               ▼
                             Capa de Servicios (operaciones/servicios.py)
                     @transaction.atomic + select_for_update() + auditoria SHA-256
                                               │
                                               ▼
                         Base Relacional Única (MariaDB XAMPP / SQLite / PostgreSQL)
```

---

## 4. Cronograma Ajustado (Semanas 7 – 15)

| Sprint | Semanas | Jefe de Proyecto Rotativo | Entregables Ejecutados |
|---|---|---|---|
| 0 · Arquitectura y Base | Sem. 7–8 | Víctor Cancino | Diseño en 3 capas, autodetección XAMPP/SQLite y esquema relacional |
| 1 · Seguridad y Maestros | Sem. 9–10 | Felipe Mardones | Catálogos maestros, 4 roles, 21 permisos RBAC y cadena SHA-256 |
| 2 · Núcleo Forestal | Sem. 11–12 | Benjamín Contesso | Cosecha `LC-`, guías `GD-`, recepción con merma y kárdex con CHECK |
| 3 · Expansión ES3 | Sem. 13 | Víctor Cancino | Producción, paquetes QR SVG, procesos, ubicaciones, compras y ventas sin SII |
| 4 · Móvil, API y QA | Sem. 14 | Felipe Mardones | 14 ViewSets JWT, cliente Flutter `bosquesur_mobile`, `/app-movil/` y 37 tests |
| 5 · Cierre ES3 | Sem. 15 | Benjamín Contesso | Repositorio Git local, `cargar_demo` + `verificar_auditoria` (196 registros), Informe 3 y Manual |

---

## 5. Evidencia de Verificación

- `python manage.py test --verbosity=2`: **37 pruebas aprobadas** (trazabilidad completa ES3, consistencia ACID y rollback por falta de stock, RBAC web/API con `ACCESO_DENEGADO`, autenticación JWT, resolución gerencial, anulación de ventas y detección de alteraciones en bitácora SHA-256).
- `python manage.py cargar_demo`: genera **19 lotes de cosecha, 53 guías, 49 recepciones, 9 órdenes de producción, 18 paquetes QR, 4 órdenes de compra y 3 pedidos de venta**.
- `python manage.py verificar_auditoria`: verifica **196 registros íntegros** en la cadena criptográfica SHA-256.
- **Flutter (`bosquesur_mobile/`)**: plataformas `android`, `windows` y `web` generadas; `flutter analyze` con **0 problemas**, `flutter test` con **3/3 pruebas aprobadas** (incluyendo renovación JWT ante HTTP 401) y `flutter build web` compilado sin errores. (No se ejecutó prueba en vivo sobre dispositivo Android físico ni emulador por ausencia de dispositivo conectado).

---

## 6. Correcciones post-auditoría (15/11/2026)

- **G1:** Inicialización del repositorio Git local en `OneDrive_2_15-11-2026/bosquesur_prototipo/` con `.gitignore` y commits por bloque.
- **G2 / D6:** Generación de plataformas Flutter (`android`, `windows`, `web`), permiso `INTERNET` + `usesCleartextTraffic="true"` en Android y eliminación de 7 avisos de análisis estático.
- **G3 / G4 / G8 / G9:** Restricción de traslado entre patios para paquetes `RESERVADO` y validación en despacho; rechazo de sobre-recepción en órdenes de compra con registro de diferencia parcial; aislamiento por patio para rol `PATIO` en vistas de detalle y servicios; consideración de mermas previas al validar volumen disponible de `OrdenProduccion`.
- **G5 / G6:** Registro de `ACCESO_DENEGADO` en la capa de permisos DRF y validación defensiva de fechas en `/reportes/` y `/reportes/exportar-csv/`.
- **G7-A:** Renovación automática de JWT (`POST /api/token/refresh/`) con soporte de rotación de refresh token y cierre de sesión ante expiración. (El escáner de cámara con `mobile_scanner`, G7-B, queda como trabajo futuro manteniendo el ingreso manual/búsqueda rápida QR).
- **G10 / G11:** Servicios, vistas, plantillas y endpoints `/api/guias/{id}/resolver-discrepancia/` y `/api/ventas/{id}/anular/`, además de `requirements-postgres.txt` con `psycopg[binary]`.
