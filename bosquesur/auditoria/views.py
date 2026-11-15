from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from cuentas.permisos import permiso_requerido

from .models import RegistroAuditoria
from .servicios import verificar_cadena


@permiso_requerido("ver_auditoria")
def bitacora(request):
    registros = RegistroAuditoria.objects.select_related("usuario")
    accion = request.GET.get("accion", "")
    texto = request.GET.get("q", "").strip()
    if accion:
        registros = registros.filter(accion=accion)
    if texto:
        registros = registros.filter(
            Q(descripcion__icontains=texto) | Q(usuario_nombre__icontains=texto)
        )
    pagina = Paginator(registros, 30).get_page(request.GET.get("pagina"))
    integra, total, alterado = verificar_cadena()
    acciones = (
        RegistroAuditoria.objects.order_by("accion").values_list("accion", flat=True).distinct()
    )
    return render(
        request,
        "auditoria/bitacora.html",
        {
            "pagina": pagina,
            "acciones": acciones,
            "accion": accion,
            "q": texto,
            "integra": integra,
            "total": total,
            "alterado": alterado,
        },
    )
