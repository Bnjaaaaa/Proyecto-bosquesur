"""Construye el menú de navegación según el rol del usuario conectado."""
from django.conf import settings

from .permisos import puede

# (vista destino, texto, permiso requerido, vistas que marcan la opción como activa)
MENU = [
    ("dashboard", "Dashboard", "ver_dashboard", {"dashboard"}),
    ("cosecha_lista", "Bosque", "ver_cosecha", {"cosecha_lista", "cosecha_nueva"}),
    ("guias_lista", "Guías", "ver_guias", {"guias_lista", "guia_nueva", "guia_detalle"}),
    ("recepciones_pendientes", "Recepción", "recepcionar", {"recepciones_pendientes", "recepcionar"}),
    ("inventario", "Inventario", "ver_inventario", {"inventario"}),
    ("produccion_lista", "Producción", "ver_produccion", {"produccion_lista", "produccion_nueva"}),
    (
        "paquetes_lista",
        "Paquetes QR",
        "ver_paquetes",
        {"paquetes_lista", "paquete_nuevo", "paquete_detalle", "paquete_buscar_qr"},
    ),
    ("compras_lista", "Compras", "ver_compras", {"compras_lista", "compra_nueva", "compra_detalle"}),
    ("ventas_lista", "Ventas", "ver_ventas", {"ventas_lista", "venta_nueva", "venta_detalle"}),
    ("reportes", "Reportes", "ver_reportes", {"reportes"}),
    ("bitacora", "Bitácora", "ver_auditoria", {"bitacora"}),
]


def menu(request):
    usuario = getattr(request, "user", None)
    motor_bd = getattr(settings, "DB_MOTOR_ACTIVO", "sqlite")
    if not usuario or not usuario.is_authenticated:
        return {"menu": [], "db_motor": motor_bd}
    actual = getattr(getattr(request, "resolver_match", None), "url_name", None)
    return {
        "menu": [
            {"url_name": url, "texto": texto, "activo": actual in vistas}
            for url, texto, permiso, vistas in MENU
            if puede(usuario, permiso)
        ],
        "db_motor": motor_bd,
    }
