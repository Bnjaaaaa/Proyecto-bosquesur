from rest_framework.permissions import BasePermission

from auditoria.servicios import Accion, registrar
from cuentas.permisos import puede


def requiere(permiso):
    """Crea una clase de permiso DRF a partir de la misma matriz de roles que usa la web."""

    class _Permiso(BasePermission):
        message = f"Su rol no tiene el permiso '{permiso}'."

        def has_permission(self, request, view):
            if not (request.user and request.user.is_authenticated):
                return False
            if puede(request.user, permiso):
                return True
            registrar(
                Accion.ACCESO_DENEGADO,
                f"Intento API sin permiso '{permiso}' a {request.path}",
                usuario=request.user,
                request=request,
            )
            return False

    _Permiso.__name__ = f"Permiso_{permiso}"
    return _Permiso
