from rest_framework.permissions import BasePermission

from cuentas.permisos import puede


def requiere(permiso):
    """Crea una clase de permiso DRF a partir de la misma matriz de roles que usa la web."""

    class _Permiso(BasePermission):
        message = f"Su rol no tiene el permiso '{permiso}'."

        def has_permission(self, request, view):
            return bool(request.user and request.user.is_authenticated and puede(request.user, permiso))

    _Permiso.__name__ = f"Permiso_{permiso}"
    return _Permiso
