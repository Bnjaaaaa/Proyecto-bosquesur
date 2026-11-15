from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import Usuario

# Pantalla de inicio de cada rol después de iniciar sesión.
INICIO_POR_ROL = {
    Usuario.Rol.GERENTE: "dashboard",
    Usuario.Rol.ADMINISTRATIVO: "dashboard",
    Usuario.Rol.FAENA: "guias_lista",
    Usuario.Rol.PATIO: "recepciones_pendientes",
}


@login_required
def inicio(request):
    if request.user.is_superuser:
        return redirect("dashboard")
    return redirect(INICIO_POR_ROL.get(request.user.rol, "guias_lista"))
