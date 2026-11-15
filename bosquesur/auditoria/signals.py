"""Registra en la bitácora los inicios y cierres de sesión."""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .servicios import Accion, registrar


@receiver(user_logged_in)
def al_iniciar_sesion(sender, request, user, **kwargs):
    registrar(Accion.LOGIN, "Inicio de sesión web", usuario=user, request=request)


@receiver(user_logged_out)
def al_cerrar_sesion(sender, request, user, **kwargs):
    if user is not None:
        registrar(Accion.LOGOUT, "Cierre de sesión", usuario=user, request=request)


@receiver(user_login_failed)
def al_fallar_login(sender, credentials, request=None, **kwargs):
    nombre = credentials.get("username", "")
    registrar(
        Accion.LOGIN_FALLIDO,
        f"Intento de inicio de sesión fallido para '{nombre}'",
        datos={"username": nombre},
        request=request,
    )
