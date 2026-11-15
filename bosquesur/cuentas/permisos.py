"""Control de acceso por rol para las vistas web."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from auditoria.servicios import Accion, registrar

from .models import Usuario

Rol = Usuario.Rol

# Matriz de permisos del prototipo (una sola fuente de verdad para web y API).
PERMISOS = {
    "ver_guias": (Rol.GERENTE, Rol.ADMINISTRATIVO, Rol.FAENA, Rol.PATIO),
    "emitir_guia": (Rol.FAENA, Rol.ADMINISTRATIVO),
    "recepcionar": (Rol.PATIO, Rol.ADMINISTRATIVO),
    "ver_inventario": (Rol.GERENTE, Rol.ADMINISTRATIVO, Rol.PATIO),
    "ver_produccion": (Rol.GERENTE, Rol.ADMINISTRATIVO, Rol.PATIO),
    "registrar_produccion": (Rol.ADMINISTRATIVO, Rol.PATIO),
    "ver_dashboard": (Rol.GERENTE, Rol.ADMINISTRATIVO),
    "ver_auditoria": (Rol.GERENTE,),
    "ver_cosecha": (Rol.GERENTE, Rol.ADMINISTRATIVO, Rol.FAENA),
    "registrar_cosecha": (Rol.FAENA, Rol.ADMINISTRATIVO),
    "ver_paquetes": (Rol.GERENTE, Rol.ADMINISTRATIVO, Rol.PATIO),
    "gestionar_paquetes": (Rol.PATIO, Rol.ADMINISTRATIVO),
    "ver_compras": (Rol.GERENTE, Rol.ADMINISTRATIVO, Rol.PATIO),
    "solicitar_compra": (Rol.ADMINISTRATIVO, Rol.GERENTE),
    "aprobar_compra": (Rol.GERENTE,),
    "recepcionar_compra": (Rol.PATIO, Rol.ADMINISTRATIVO),
    "ver_ventas": (Rol.GERENTE, Rol.ADMINISTRATIVO, Rol.PATIO),
    "gestionar_ventas": (Rol.ADMINISTRATIVO, Rol.GERENTE),
    "despachar_venta": (Rol.PATIO, Rol.ADMINISTRATIVO),
    "ver_reportes": (Rol.GERENTE, Rol.ADMINISTRATIVO),
}


def puede(usuario, permiso):
    return usuario.is_authenticated and usuario.tiene_rol(*PERMISOS[permiso])


def permiso_requerido(permiso):
    """Decorador: exige sesión iniciada y un rol autorizado; registra los intentos denegados."""

    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            if not puede(request.user, permiso):
                registrar(
                    Accion.ACCESO_DENEGADO,
                    f"Intento de acceso sin permiso '{permiso}' a {request.path}",
                    usuario=request.user,
                    request=request,
                )
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador
