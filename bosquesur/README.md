# BosqueSur Maderas SpA · Sistema Integrado de Gestión Forestal y Maderera (ES3)

Solución web, **API REST + JWT** y **aplicación móvil Flutter** construida en **Django 5.0.14** sobre **MySQL/MariaDB (XAMPP)** con conmutación automática transparente a **SQLite (`db.sqlite3`)** cuando XAMPP está detenido, y soporte productivo directo para **PostgreSQL**.

Implementa íntegramente los **17 requisitos obligatorios de la Evaluación Sumativa 3 (ES3)** descritos en la Sección 5.2 de `caso_bosquesur.pdf`: desde el origen forestal/proveedor y lotes de cosecha hasta guías de despacho, recepción con tolerancia de merma, producción atómica, paquetes únicos con código QR SVG, procesos posteriores, ubicaciones en bodega, compras externas con aprobación gerencial, pedidos de venta con comprobante interno simulado (**sin integración SII**), dashboard en tiempo real, reportes CSV y bitácora inmutable SHA-256.

---

## 1. Requisitos

| Programa | Versión | Uso |
|---|---|---|
| Python | 3.10 – 3.13 | Ejecutar backend Django, servicios, CLI y pruebas |
| XAMPP (opcional) | 8.x (MariaDB 10.4+) | Base de datos local por defecto en puerto 3306 y phpMyAdmin |
| SQLite (incluido) | Integrado en Python | Fallback automático a `db.sqlite3` si MySQL (3306) no responde |
| Flutter SDK (opcional) | `>= 3.2.0` | Ejecutar o compilar el cliente móvil nativo `../bosquesur_mobile/` |

> En Windows, marque **"Add python.exe to PATH"** al instalar Python.

---

## 2. Instalación y Ejecución Rápida (Windows)

1. *(Opcional)* Abra **XAMPP Control Panel** e inicie **MySQL** (si no lo inicia, Django usará automáticamente `db.sqlite3`).
2. Ejecute **`instalar.bat`** para crear el entorno virtual, instalar `requirements.txt`, migrar el esquema y poblar la base de demostración.
3. Ejecute **`iniciar.bat`** para abrir la plataforma web en `http://127.0.0.1:8000`.

### Instalación manual (cualquier sistema operativo)

```bash
python -m venv .venv
.venv\Scripts\activate            # En Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python manage.py crear_bd         # Opcional si utiliza MySQL en XAMPP
python manage.py migrate
python manage.py cargar_demo
python manage.py runserver 0.0.0.0:8000
```

---

## 3. Usuarios de Demostración

Todos utilizan la contraseña **`Bosque2026!`**

| Usuario | Rol | Alcance y permisos principales |
|---|---|---|
| `gerente` | `GERENTE` | Dashboard, reportes CSV, aprobación de órdenes de compra, supervisión total y bitácora SHA-256 |
| `administrativo` | `ADMINISTRATIVO` | Dashboard, reportes, guías, recepción, producción, paquetes QR, compras (solicitud/recepción), ventas y maestros |
| `faena` | `FAENA` | Registro de lotes de cosecha y emisión de guías exclusivamente en **Predio Los Coigües** |
| `faena2` | `FAENA` | Registro de lotes de cosecha y emisión de guías exclusivamente en **Predio El Manzano** |
| `patio` | `PATIO` | Recepción en **Patio Central**, órdenes de producción, creación/proceso/traslado de paquetes QR e inventario |
| `admin` | Superusuario | Control completo incluyendo `/admin/` |

---

## 4. Módulos y Arquitectura

```text
config/            Configuración (autodetección MySQL->SQLite/PostgreSQL, JWT, seguridad HTTP)
maestros/          Proveedor, Faena, Patio, UbicacionBodega, Producto, Cliente
cuentas/           Usuario con rol, asignación faena/patio y matriz única de 20 permisos (RBAC)
operaciones/       10 modelos, servicios.py (12 transacciones @atomic), consultas.py, qr_utils.py y 31 rutas web
auditoria/         RegistroAuditoria inmutable con cadena de hashes SHA-256 + verificar_auditoria
api/               DRF + SimpleJWT (14 ViewSets en /api/*, Bearer tokens 30 min / refresh 12 h)
templates/         Interfaz Bootstrap 5 + Chart.js 4 locales + simulador /app-movil/
../bosquesur_mobile/ Cliente móvil multiplataforma Flutter (login, faena, patio y escaneo/bodega QR)
```

### Reglas de negocio clave implementadas

- **Trazabilidad desde el origen:** `Proveedor` -> `Faena` -> `LoteCosecha` (`LC-`) -> `GuiaDespacho` (`GD-`) -> `Recepcion` -> `OrdenProduccion` (`OP-`) -> `Paquete` (`BS-PKT-XXXXXX` con QR SVG) -> `HistorialPaquete` -> `PedidoVenta` (`PV-`).
- **Discrepancia en recepción:** al recepcionar una guía se calcula `enviado - recibido`. Si supera `TOLERANCIA_DISCREPANCIA_PCT` (`3.0 %`), la recepción se marca para revisión y se registra una alerta en bitácora.
- **Consistencia ACID:** todas las afectaciones a `Inventario` usan `transaction.atomic()` y `SELECT ... FOR UPDATE`, con restricciones `CHECK` en BD para evitar saldos negativos o movimientos sin respaldo documental.
- **Alcance no tributario (sin SII):** el despacho comercial genera una guía interna simulada `GDC-INT-XXXXXX` con la leyenda obligatoria **`DOCUMENTO INTERNO SIMULADO — NO VÁLIDO COMO DTE NI ANTE EL SII`**. No existe integración real con el SII.
- **Control de acceso (RBAC):** la misma matriz de 20 permisos gobierna vistas web y endpoints REST; cualquier acceso denegado genera un evento `ACCESO_DENEGADO` en auditoría.

---

## 5. Rutas Web y API REST (JSON + JWT)

**Principales rutas web:** `/dashboard/`, `/cosecha/`, `/guias/`, `/inventario/`, `/produccion/`, `/paquetes/`, `/compras/`, `/ventas/`, `/reportes/`, `/reportes/exportar-csv/`, `/app-movil/` (simulador móvil JWT en vivo) y `/auditoria/`.

**Principales endpoints `/api/`:**

| Método | Ruta | Roles | Descripción |
|---|---|---|---|
| `POST` | `/api/token/` · `/api/token/refresh/` | Todos | Autenticación JWT (`access` + `refresh` rotativo + perfil) |
| `GET` | `/api/yo/` | Todos | Perfil y permisos efectivos del usuario autenticado |
| `GET/POST` | `/api/lotes-cosecha/` | Faena, Admin, Gerente | Listar o registrar lotes de cosecha `LC-` |
| `GET/POST` | `/api/guias/` | Según rol | Listar (`?estado=EMITIDA`) o emitir guía de despacho |
| `POST` | `/api/guias/{id}/recepcionar/` | Patio, Admin | Recepcionar camión y calcular merma automáticamente |
| `GET/POST` | `/api/ordenes-produccion/` | Patio, Admin, Gerente | Registrar transformación de rollizo a madera aserrada |
| `GET/POST` | `/api/paquetes/` | Patio, Admin, Gerente | Crear o consultar paquetes (`?codigo_qr=`, `?estado=`) |
| `GET/POST` | `/api/paquetes/{id}/trazabilidad/` · `procesar/` · `mover/` | Patio, Admin, Gerente | Historial completo, secado/impregnado/cepillado/reproceso y traslado |
| `GET/POST` | `/api/compras/` · `/{id}/aprobar/` · `recepcionar/` | Admin, Gerente, Patio | Ciclo completo de compras externas con aprobación gerencial |
| `GET/POST` | `/api/ventas/` · `/{id}/despachar/` | Admin, Gerente, Patio | Pedidos comerciales, reserva de paquetes y guía simulada `GDC-INT-` |
| `GET` | `/api/inventario/` · `/api/dashboard/` · `/api/auditoria/` | Según matriz RBAC | Saldos por patio, indicadores reales y bitácora SHA-256 |
| `GET` | `/api/faenas/`, `/patios/`, `/ubicaciones/`, `/productos/`, `/proveedores/`, `/clientes/` | Según rol | Catálogos maestros |

---

## 6. Pruebas Automatizadas y Verificación de Auditoría

```bash
python manage.py test --verbosity=2      # 28 pruebas automatizadas (operaciones, api, auditoria)
python manage.py verificar_auditoria     # Verifica la cadena completa SHA-256 (196 registros tras cargar_demo)
```

---

## 7. Variables de Entorno

| Variable | Por defecto | Uso |
|---|---|---|
| `DB_ENGINE` | `mysql` *(auto-fallback a `sqlite`)* | `mysql`, `postgresql` o `sqlite` |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `bosquesur` / `root` / *(vacía)* | Credenciales de base de datos |
| `DB_HOST` / `DB_PORT` | `127.0.0.1` / `3306` | Host y puerto del motor |
| `DJANGO_DEBUG` | `1` | Establecer en `0` en entorno productivo |
| `DJANGO_SECRET_KEY` | clave local de desarrollo | Reemplazar por secreto robusto en producción |
| `DJANGO_HTTPS` | `0` | `1` activa redirección SSL, cookies seguras y HSTS |
| `TOLERANCIA_DISCREPANCIA_PCT` | `3.0` | Porcentaje de merma tolerable en recepción antes de alertar |
