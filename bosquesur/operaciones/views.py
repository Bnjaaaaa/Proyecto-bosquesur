import csv
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from auditoria.models import RegistroAuditoria
from cuentas.models import Usuario
from cuentas.permisos import permiso_requerido, puede
from maestros.models import Faena, Patio, Producto, UbicacionBodega

from . import servicios
from .consultas import datos_reportes, guias_visibles, resumen_dashboard, trazabilidad_paquete
from .forms import (
    DespachoVentaForm,
    GuiaDespachoForm,
    LoteCosechaForm,
    MovimientoPaqueteForm,
    OrdenCompraForm,
    OrdenProduccionForm,
    PaqueteForm,
    PedidoVentaForm,
    ProcesoPaqueteForm,
    RecepcionCompraForm,
    RecepcionForm,
)
from .models import (
    GuiaDespacho,
    Inventario,
    LoteCosecha,
    MovimientoInventario,
    OrdenCompra,
    OrdenProduccion,
    Paquete,
    PedidoVenta,
)
from .qr_utils import generar_qr_svg


# ------------------------------------------------------------------ Bosque / Cosecha
@permiso_requerido("ver_cosecha")
def cosecha_lista(request):
    faenas = Faena.objects.filter(activa=True).select_related("proveedor")
    lotes = LoteCosecha.objects.select_related("faena", "faena__proveedor", "producto", "registrado_por")
    u = request.user
    if u.rol == Usuario.Rol.FAENA and u.faena_id and not u.is_superuser:
        faenas = faenas.filter(pk=u.faena_id)
        lotes = lotes.filter(faena_id=u.faena_id)
    pagina = Paginator(lotes, 20).get_page(request.GET.get("pagina"))
    return render(
        request,
        "operaciones/cosecha_lista.html",
        {
            "faenas": faenas,
            "pagina": pagina,
            "puede_registrar": puede(u, "registrar_cosecha"),
        },
    )


@permiso_requerido("registrar_cosecha")
def cosecha_nueva(request):
    form = LoteCosechaForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            lote = servicios.registrar_lote_cosecha(usuario=request.user, request=request, **form.cleaned_data)
        except servicios.ErrorNegocio as error:
            servicios.registrar_rechazo(
                usuario=request.user, operacion="Registro de lote de cosecha", motivo=str(error), request=request
            )
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Lote {lote.codigo} registrado ({lote.volumen_cosechado} m³).")
            return redirect("cosecha_lista")
    return render(request, "operaciones/cosecha_form.html", {"form": form})


# ------------------------------------------------------------------ Guías
@permiso_requerido("ver_guias")
def guias_lista(request):
    guias = guias_visibles(request.user)
    estado = request.GET.get("estado", "")
    texto = request.GET.get("q", "").strip()
    if estado:
        guias = guias.filter(estado=estado)
    if texto:
        guias = guias.filter(
            Q(numero__icontains=texto) | Q(patente_camion__icontains=texto) | Q(conductor__icontains=texto)
        )
    pagina = Paginator(guias, 20).get_page(request.GET.get("pagina"))
    return render(
        request,
        "operaciones/guias_lista.html",
        {
            "pagina": pagina,
            "estado": estado,
            "q": texto,
            "estados": GuiaDespacho.Estado.choices,
            "puede_emitir": puede(request.user, "emitir_guia"),
        },
    )


@permiso_requerido("emitir_guia")
def guia_nueva(request):
    form = GuiaDespachoForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            guia = servicios.emitir_guia(usuario=request.user, request=request, **form.cleaned_data)
        except servicios.ErrorNegocio as error:
            servicios.registrar_rechazo(usuario=request.user, operacion="Emisión de guía", motivo=str(error), request=request)
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Guía {guia.numero} emitida. El camión ya puede salir hacia {guia.patio_destino}.")
            return redirect("guia_detalle", pk=guia.pk)
    return render(request, "operaciones/guia_form.html", {"form": form})


@permiso_requerido("ver_guias")
def guia_detalle(request, pk):
    guia = get_object_or_404(guias_visibles(request.user), pk=pk)
    movimientos = guia.movimientos.select_related("producto", "patio", "usuario")
    eventos = RegistroAuditoria.objects.filter(entidad="GuiaDespacho", entidad_id=guia.numero).order_by("id")
    return render(
        request,
        "operaciones/guia_detalle.html",
        {
            "guia": guia,
            "recepcion": getattr(guia, "recepcion", None),
            "movimientos": movimientos,
            "eventos": eventos,
            "puede_recepcionar": puede(request.user, "recepcionar") and guia.estado == GuiaDespacho.Estado.EMITIDA,
        },
    )


# ------------------------------------------------------------------ Recepción
@permiso_requerido("recepcionar")
def recepciones_pendientes(request):
    guias = guias_visibles(request.user).filter(estado=GuiaDespacho.Estado.EMITIDA).order_by("fecha_emision")
    texto = request.GET.get("q", "").strip().upper()
    if texto:
        guias = guias.filter(Q(numero__icontains=texto) | Q(patente_camion__icontains=texto))
    return render(request, "operaciones/recepciones_pendientes.html", {"guias": guias, "q": texto})


@permiso_requerido("recepcionar")
def recepcionar(request, pk):
    guia = get_object_or_404(guias_visibles(request.user), pk=pk)
    if guia.estado != GuiaDespacho.Estado.EMITIDA:
        messages.info(request, f"La guía {guia.numero} ya fue recepcionada.")
        return redirect("guia_detalle", pk=guia.pk)

    form = RecepcionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            recepcion = servicios.recepcionar_guia(
                usuario=request.user,
                guia_id=guia.pk,
                request=request,
                **form.cleaned_data,
            )
        except servicios.ErrorNegocio as error:
            servicios.registrar_rechazo(
                usuario=request.user, operacion=f"Recepción de {guia.numero}", motivo=str(error), request=request
            )
            form.add_error(None, str(error))
        else:
            if recepcion.requiere_revision:
                messages.warning(
                    request,
                    f"Guía {guia.numero} recepcionada con discrepancia de {recepcion.porcentaje_discrepancia}% "
                    f"(sobre la tolerancia). Quedó marcada para revisión.",
                )
            else:
                messages.success(
                    request,
                    f"Guía {guia.numero} recepcionada. Se sumaron {recepcion.volumen_recibido} m³ al inventario.",
                )
            return redirect("recepciones_pendientes")
    return render(
        request,
        "operaciones/recepcion_form.html",
        {"form": form, "guia": guia, "tolerancia": servicios.tolerancia_discrepancia()},
    )


# ------------------------------------------------------------------ Inventario
@permiso_requerido("ver_inventario")
def inventario(request):
    saldos = Inventario.objects.select_related("patio", "producto")
    movimientos = MovimientoInventario.objects.select_related(
        "patio", "producto", "guia", "orden", "compra", "venta", "paquete", "usuario"
    )
    ubicaciones = UbicacionBodega.objects.filter(activa=True).select_related("patio")
    patio_id = request.GET.get("patio", "")
    usuario = request.user
    if usuario.rol == Usuario.Rol.PATIO and usuario.patio_id and not usuario.is_superuser:
        patio_id = str(usuario.patio_id)
    if patio_id:
        saldos = saldos.filter(patio_id=patio_id)
        movimientos = movimientos.filter(patio_id=patio_id)
        ubicaciones = ubicaciones.filter(patio_id=patio_id)
    totales = {
        fila["producto__tipo"]: fila["total"]
        for fila in saldos.order_by().values("producto__tipo").annotate(total=Sum("cantidad"))
    }
    return render(
        request,
        "operaciones/inventario.html",
        {
            "saldos": saldos,
            "movimientos": movimientos[:30],
            "ubicaciones": ubicaciones,
            "patios": Patio.objects.filter(activo=True),
            "patio_id": patio_id,
            "total_rollizo": totales.get(Producto.Tipo.ROLLIZO, 0),
            "total_aserrado": totales.get(Producto.Tipo.ASERRADO, 0),
            "total_insumo": totales.get(Producto.Tipo.INSUMO, 0),
        },
    )


# ------------------------------------------------------------------ Producción
@permiso_requerido("ver_produccion")
def produccion_lista(request):
    ordenes = OrdenProduccion.objects.select_related(
        "patio", "guia_origen", "producto_entrada", "producto_salida", "creada_por"
    )
    usuario = request.user
    if usuario.rol == Usuario.Rol.PATIO and usuario.patio_id and not usuario.is_superuser:
        ordenes = ordenes.filter(patio_id=usuario.patio_id)
    pagina = Paginator(ordenes, 20).get_page(request.GET.get("pagina"))
    return render(
        request,
        "operaciones/produccion_lista.html",
        {
            "pagina": pagina,
            "puede_registrar": puede(usuario, "registrar_produccion"),
            "puede_empaquetar": puede(usuario, "gestionar_paquetes"),
        },
    )


@permiso_requerido("registrar_produccion")
def produccion_nueva(request):
    form = OrdenProduccionForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            orden = servicios.registrar_produccion(usuario=request.user, request=request, **form.cleaned_data)
        except servicios.ErrorNegocio as error:
            servicios.registrar_rechazo(
                usuario=request.user, operacion="Orden de producción", motivo=str(error), request=request
            )
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Orden {orden.numero} registrada con rendimiento de {orden.rendimiento}%.")
            return redirect("produccion_lista")
    return render(request, "operaciones/produccion_form.html", {"form": form})


# ------------------------------------------------------------------ Paquetes QR y Bodega
@permiso_requerido("ver_paquetes")
def paquetes_lista(request):
    paquetes = Paquete.objects.select_related(
        "orden_produccion", "producto", "ubicacion", "ubicacion__patio", "creado_por"
    )
    u = request.user
    if u.rol == Usuario.Rol.PATIO and u.patio_id and not u.is_superuser:
        paquetes = paquetes.filter(ubicacion__patio_id=u.patio_id)

    texto = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "")
    proceso = request.GET.get("proceso", "")
    ubicacion_id = request.GET.get("ubicacion", "")
    if texto:
        paquetes = paquetes.filter(Q(codigo_qr__icontains=texto) | Q(producto__nombre__icontains=texto))
    if estado:
        paquetes = paquetes.filter(estado=estado)
    if proceso:
        paquetes = paquetes.filter(proceso_actual=proceso)
    if ubicacion_id:
        paquetes = paquetes.filter(ubicacion_id=ubicacion_id)

    pagina = Paginator(paquetes, 20).get_page(request.GET.get("pagina"))
    return render(
        request,
        "operaciones/paquetes_lista.html",
        {
            "pagina": pagina,
            "q": texto,
            "estado": estado,
            "proceso": proceso,
            "ubicacion_id": ubicacion_id,
            "estados": Paquete.Estado.choices,
            "procesos": Paquete.Proceso.choices,
            "ubicaciones": UbicacionBodega.objects.filter(activa=True).select_related("patio"),
            "puede_crear": puede(u, "gestionar_paquetes"),
        },
    )


def _filtrar_por_patio(queryset, usuario, campo="patio_id"):
    if usuario.rol == Usuario.Rol.PATIO and usuario.patio_id and not usuario.is_superuser:
        return queryset.filter(**{campo: usuario.patio_id})
    return queryset


@permiso_requerido("ver_paquetes")
def paquete_buscar_qr(request, codigo_qr=None):
    codigo = (codigo_qr or request.GET.get("qr", "")).strip().upper()
    if not codigo:
        return redirect("paquetes_lista")
    paquete = _filtrar_por_patio(Paquete.objects.all(), request.user, "ubicacion__patio_id").filter(
        codigo_qr__iexact=codigo
    ).first()
    if paquete is None:
        messages.warning(request, f"No se encontró ningún paquete con el código QR '{codigo}'.")
        return redirect("paquetes_lista")
    return redirect("paquete_detalle", pk=paquete.pk)


@permiso_requerido("gestionar_paquetes")
def paquete_nuevo(request):
    initial = {}
    orden_id = request.GET.get("orden")
    if orden_id and orden_id.isdigit():
        orden = OrdenProduccion.objects.filter(pk=int(orden_id)).first()
        if orden:
            initial["orden_produccion"] = orden
            ub = UbicacionBodega.objects.filter(patio=orden.patio, activa=True).first()
            if ub:
                initial["ubicacion"] = ub
    form = PaqueteForm(request.POST or None, initial=initial, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            paquete = servicios.crear_paquete(usuario=request.user, request=request, **form.cleaned_data)
        except servicios.ErrorNegocio as error:
            servicios.registrar_rechazo(
                usuario=request.user, operacion="Creación de paquete QR", motivo=str(error), request=request
            )
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Paquete {paquete.codigo_qr} creado y etiquetado con QR.")
            return redirect("paquete_detalle", pk=paquete.pk)
    return render(request, "operaciones/paquete_form.html", {"form": form})


@permiso_requerido("ver_paquetes")
def paquete_detalle(request, pk):
    paquete = get_object_or_404(
        _filtrar_por_patio(
            Paquete.objects.select_related(
                "orden_produccion",
                "orden_produccion__patio",
                "orden_produccion__guia_origen",
                "producto",
                "ubicacion",
                "ubicacion__patio",
                "creado_por",
            ),
            request.user,
            "ubicacion__patio_id",
        ),
        pk=pk,
    )
    traza = trazabilidad_paquete(paquete)
    qr_svg = generar_qr_svg(paquete.codigo_qr or f"PKT-{paquete.pk}")
    puede_gestionar = puede(request.user, "gestionar_paquetes") and paquete.estado != Paquete.Estado.DESPACHADO
    form_proceso = ProcesoPaqueteForm()
    form_movimiento = MovimientoPaqueteForm()
    return render(
        request,
        "operaciones/paquete_detalle.html",
        {
            "paquete": paquete,
            "traza": traza,
            "qr_svg": qr_svg,
            "puede_gestionar": puede_gestionar,
            "form_proceso": form_proceso,
            "form_movimiento": form_movimiento,
        },
    )


@permiso_requerido("gestionar_paquetes")
def paquete_procesar(request, pk):
    if request.method != "POST":
        return redirect("paquete_detalle", pk=pk)
    form = ProcesoPaqueteForm(request.POST)
    if form.is_valid():
        try:
            paquete = servicios.aplicar_proceso_paquete(
                usuario=request.user,
                paquete_id=pk,
                request=request,
                **form.cleaned_data,
            )
        except servicios.ErrorNegocio as error:
            servicios.registrar_rechazo(
                usuario=request.user, operacion="Proceso posterior paquete", motivo=str(error), request=request
            )
            messages.error(request, str(error))
        else:
            messages.success(
                request,
                f"Proceso '{paquete.get_proceso_actual_display()}' aplicado a {paquete.codigo_qr}.",
            )
    else:
        messages.error(request, "Datos inválidos al aplicar el proceso posterior.")
    return redirect("paquete_detalle", pk=pk)


@permiso_requerido("gestionar_paquetes")
def paquete_mover(request, pk):
    if request.method != "POST":
        return redirect("paquete_detalle", pk=pk)
    form = MovimientoPaqueteForm(request.POST)
    if form.is_valid():
        try:
            paquete = servicios.mover_paquete(
                usuario=request.user,
                paquete_id=pk,
                request=request,
                **form.cleaned_data,
            )
        except servicios.ErrorNegocio as error:
            servicios.registrar_rechazo(
                usuario=request.user, operacion="Traslado de paquete", motivo=str(error), request=request
            )
            messages.error(request, str(error))
        else:
            messages.success(request, f"Paquete {paquete.codigo_qr} movido a {paquete.ubicacion.codigo}.")
    else:
        messages.error(request, "Debe indicar una ubicación de destino válida.")
    return redirect("paquete_detalle", pk=pk)


# ------------------------------------------------------------------ Compras Externas
@permiso_requerido("ver_compras")
def compras_lista(request):
    compras = OrdenCompra.objects.select_related(
        "proveedor", "patio_destino", "producto", "solicitada_por", "aprobada_por"
    )
    u = request.user
    if u.rol == Usuario.Rol.PATIO and u.patio_id and not u.is_superuser:
        compras = compras.filter(patio_destino_id=u.patio_id)
    estado = request.GET.get("estado", "")
    texto = request.GET.get("q", "").strip()
    if estado:
        compras = compras.filter(estado=estado)
    if texto:
        compras = compras.filter(Q(numero__icontains=texto) | Q(proveedor__razon_social__icontains=texto))
    pagina = Paginator(compras, 20).get_page(request.GET.get("pagina"))
    return render(
        request,
        "operaciones/compras_lista.html",
        {
            "pagina": pagina,
            "estado": estado,
            "q": texto,
            "estados": OrdenCompra.Estado.choices,
            "puede_solicitar": puede(u, "solicitar_compra"),
        },
    )


@permiso_requerido("solicitar_compra")
def compra_nueva(request):
    form = OrdenCompraForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            compra = servicios.solicitar_compra(usuario=request.user, request=request, **form.cleaned_data)
        except servicios.ErrorNegocio as error:
            servicios.registrar_rechazo(
                usuario=request.user, operacion="Solicitud de compra", motivo=str(error), request=request
            )
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Orden de compra {compra.numero} solicitada. Queda pendiente de aprobación.")
            return redirect("compra_detalle", pk=compra.pk)
    return render(request, "operaciones/compra_form.html", {"form": form})


@permiso_requerido("ver_compras")
def compra_detalle(request, pk):
    compra = get_object_or_404(
        _filtrar_por_patio(
            OrdenCompra.objects.select_related(
                "proveedor", "patio_destino", "producto", "solicitada_por", "aprobada_por", "recibida_por"
            ),
            request.user,
            "patio_destino_id",
        ),
        pk=pk,
    )
    movimientos = compra.movimientos.select_related("patio", "producto", "usuario")
    eventos = RegistroAuditoria.objects.filter(entidad="OrdenCompra", entidad_id=compra.numero).order_by("id")
    form_recepcion = RecepcionCompraForm(initial={"cantidad_recibida": compra.cantidad})
    return render(
        request,
        "operaciones/compra_detalle.html",
        {
            "compra": compra,
            "movimientos": movimientos,
            "eventos": eventos,
            "form_recepcion": form_recepcion,
            "puede_aprobar": puede(request.user, "aprobar_compra") and compra.estado == OrdenCompra.Estado.SOLICITADA,
            "puede_recepcionar": (
                puede(request.user, "recepcionar_compra") and compra.estado == OrdenCompra.Estado.APROBADA
            ),
        },
    )


@permiso_requerido("aprobar_compra")
def compra_resolver(request, pk):
    if request.method != "POST":
        return redirect("compra_detalle", pk=pk)
    aprobar = request.POST.get("decision") == "aprobar"
    obs = request.POST.get("observacion", "").strip()
    try:
        compra = servicios.resolver_aprobacion_compra(
            usuario=request.user, compra_id=pk, aprobar=aprobar, observacion=obs, request=request
        )
    except servicios.ErrorNegocio as error:
        servicios.registrar_rechazo(
            usuario=request.user, operacion="Resolución compra externa", motivo=str(error), request=request
        )
        messages.error(request, str(error))
    else:
        messages.success(request, f"Orden {compra.numero} marcada como {compra.get_estado_display()}.")
    return redirect("compra_detalle", pk=pk)


@permiso_requerido("recepcionar_compra")
def compra_recepcionar(request, pk):
    if request.method != "POST":
        return redirect("compra_detalle", pk=pk)
    form = RecepcionCompraForm(request.POST)
    if form.is_valid():
        try:
            compra = servicios.recepcionar_compra(
                usuario=request.user, compra_id=pk, request=request, **form.cleaned_data
            )
        except servicios.ErrorNegocio as error:
            servicios.registrar_rechazo(
                usuario=request.user, operacion="Recepción compra externa", motivo=str(error), request=request
            )
            messages.error(request, str(error))
        else:
            messages.success(
                request,
                f"Compra {compra.numero} recepcionada: +{compra.cantidad_recibida} {compra.producto.unidad} en inventario.",
            )
    else:
        messages.error(request, "Cantidad recibida inválida.")
    return redirect("compra_detalle", pk=pk)


# ------------------------------------------------------------------ Ventas y Despacho Comercial
@permiso_requerido("ver_ventas")
def ventas_lista(request):
    pedidos = PedidoVenta.objects.select_related("cliente", "patio_despacho", "creado_por", "despachado_por")
    u = request.user
    if u.rol == Usuario.Rol.PATIO and u.patio_id and not u.is_superuser:
        pedidos = pedidos.filter(patio_despacho_id=u.patio_id)
    estado = request.GET.get("estado", "")
    texto = request.GET.get("q", "").strip()
    if estado:
        pedidos = pedidos.filter(estado=estado)
    if texto:
        pedidos = pedidos.filter(
            Q(numero__icontains=texto) | Q(documento_interno__icontains=texto) | Q(cliente__razon_social__icontains=texto)
        )
    pagina = Paginator(pedidos, 20).get_page(request.GET.get("pagina"))
    return render(
        request,
        "operaciones/ventas_lista.html",
        {
            "pagina": pagina,
            "estado": estado,
            "q": texto,
            "estados": PedidoVenta.Estado.choices,
            "puede_crear": puede(u, "gestionar_ventas"),
        },
    )


@permiso_requerido("gestionar_ventas")
def venta_nueva(request):
    form = PedidoVentaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            paquetes_ids = [p.pk for p in form.cleaned_data["paquetes"]]
            pedido = servicios.crear_pedido_venta(
                usuario=request.user,
                cliente=form.cleaned_data["cliente"],
                patio_despacho=form.cleaned_data["patio_despacho"],
                paquetes_ids=paquetes_ids,
                precio_m3_clp=form.cleaned_data["precio_m3_clp"],
                observacion=form.cleaned_data["observacion"],
                request=request,
            )
        except servicios.ErrorNegocio as error:
            servicios.registrar_rechazo(
                usuario=request.user, operacion="Creación pedido de venta", motivo=str(error), request=request
            )
            form.add_error(None, str(error))
        else:
            messages.success(
                request,
                f"Pedido {pedido.numero} creado con {pedido.paquetes.count()} paquete(s) reservados.",
            )
            return redirect("venta_detalle", pk=pedido.pk)
    paquetes_disponibles = Paquete.objects.filter(
        estado__in=[Paquete.Estado.ELABORADO, Paquete.Estado.PROCESADO]
    ).select_related("producto", "ubicacion", "ubicacion__patio")
    return render(
        request,
        "operaciones/venta_form.html",
        {"form": form, "paquetes_disponibles": paquetes_disponibles},
    )


@permiso_requerido("ver_ventas")
def venta_detalle(request, pk):
    pedido = get_object_or_404(
        _filtrar_por_patio(
            PedidoVenta.objects.select_related("cliente", "patio_despacho", "creado_por", "despachado_por"),
            request.user,
            "patio_despacho_id",
        ),
        pk=pk,
    )
    paquetes = pedido.paquetes.select_related("producto", "ubicacion")
    movimientos = pedido.movimientos.select_related("patio", "producto", "paquete", "usuario")
    eventos = RegistroAuditoria.objects.filter(entidad="PedidoVenta", entidad_id=pedido.numero).order_by("id")
    form_despacho = DespachoVentaForm()
    return render(
        request,
        "operaciones/venta_detalle.html",
        {
            "pedido": pedido,
            "paquetes": paquetes,
            "movimientos": movimientos,
            "eventos": eventos,
            "form_despacho": form_despacho,
            "puede_despachar": (
                puede(request.user, "despachar_venta") and pedido.estado == PedidoVenta.Estado.PREPARACION
            ),
        },
    )


@permiso_requerido("despachar_venta")
def venta_despachar(request, pk):
    if request.method != "POST":
        return redirect("venta_detalle", pk=pk)
    form = DespachoVentaForm(request.POST)
    if form.is_valid():
        try:
            pedido = servicios.despachar_pedido_venta(
                usuario=request.user, pedido_id=pk, request=request, **form.cleaned_data
            )
        except servicios.ErrorNegocio as error:
            servicios.registrar_rechazo(
                usuario=request.user, operacion="Despacho comercial", motivo=str(error), request=request
            )
            messages.error(request, str(error))
        else:
            messages.success(
                request,
                f"Pedido {pedido.numero} despachado. Documento interno simulado: {pedido.documento_interno} (Sin SII).",
            )
    else:
        for campo, errs in form.errors.items():
            for err in errs:
                messages.error(request, f"{campo}: {err}")
    return redirect("venta_detalle", pk=pk)


@permiso_requerido("ver_ventas")
def venta_documento(request, pk):
    pedido = get_object_or_404(
        _filtrar_por_patio(
            PedidoVenta.objects.select_related("cliente", "patio_despacho", "creado_por", "despachado_por"),
            request.user,
            "patio_despacho_id",
        ),
        pk=pk,
    )
    paquetes = pedido.paquetes.select_related("producto", "ubicacion")
    return render(
        request,
        "operaciones/venta_documento.html",
        {"pedido": pedido, "paquetes": paquetes},
    )


# ------------------------------------------------------------------ Reportes
def _parsear_fecha_opcional(valor, request):
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        messages.warning(request, "Fecha inválida, se ignoró el filtro.")
        return None


def _parsear_filtros_reporte(request):
    desde_str = request.GET.get("desde", "").strip()
    hasta_str = request.GET.get("hasta", "").strip()
    faena_id = request.GET.get("faena", "").strip()
    patio_id = request.GET.get("patio", "").strip()
    fecha_desde = _parsear_fecha_opcional(desde_str, request)
    fecha_hasta = _parsear_fecha_opcional(hasta_str, request)
    if fecha_desde is None:
        desde_str = ""
    if fecha_hasta is None:
        hasta_str = ""
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        fecha_desde, fecha_hasta = fecha_hasta, fecha_desde
        desde_str, hasta_str = fecha_desde.isoformat(), fecha_hasta.isoformat()
        messages.info(request, "La fecha 'desde' era posterior a 'hasta'; se ajustó el rango.")
    return {
        "desde_str": desde_str,
        "hasta_str": hasta_str,
        "faena_id": int(faena_id) if faena_id.isdigit() else None,
        "patio_id": int(patio_id) if patio_id.isdigit() else None,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
    }


@permiso_requerido("ver_reportes")
def reportes(request):
    f = _parsear_filtros_reporte(request)
    datos = datos_reportes(
        fecha_desde=f["fecha_desde"],
        fecha_hasta=f["fecha_hasta"],
        faena_id=f["faena_id"],
        patio_id=f["patio_id"],
    )
    return render(
        request,
        "operaciones/reportes.html",
        {
            "datos": datos,
            "filtros": f,
            "faenas": Faena.objects.filter(activa=True),
            "patios": Patio.objects.filter(activo=True),
        },
    )


@permiso_requerido("ver_reportes")
def reportes_csv(request):
    f = _parsear_filtros_reporte(request)
    datos = datos_reportes(
        fecha_desde=f["fecha_desde"],
        fecha_hasta=f["fecha_hasta"],
        faena_id=f["faena_id"],
        patio_id=f["patio_id"],
    )
    resp = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    resp["Content-Disposition"] = 'attachment; filename="reporte_operacional_bosquesur.csv"'
    writer = csv.writer(resp, delimiter=";")

    writer.writerow(["REPORTE 1: RENDIMIENTO Y MERMAS POR FAENA FORESTAL"])
    writer.writerow(["Predio / Faena", "Codigo Predio", "Proveedor", "Contrato", "Guias", "Enviado (m3)", "Recibido (m3)", "Merma (m3)", "Merma %", "En Revision"])
    for row in datos["reporte_faenas"]:
        writer.writerow([
            row["faena"], row["codigo_predio"], row["proveedor"], row["contrato"],
            row["guias"], row["enviado_m3"], row["recibido_m3"], row["merma_m3"], row["merma_pct"], row["en_revision"],
        ])

    writer.writerow([])
    writer.writerow(["REPORTE 2: EXISTENCIAS DE PAQUETES QR POR UBICACION Y BODEGA"])
    writer.writerow(["Codigo Ubicacion", "Nombre", "Tipo", "Patio", "Paquetes Activos", "Volumen (m3)", "Con Proceso Posterior"])
    for row in datos["reporte_ubicaciones"]:
        writer.writerow([
            row["codigo"], row["nombre"], row["tipo"], row["patio"],
            row["paquetes"], row["volumen_m3"], row["procesados"],
        ])

    writer.writerow([])
    writer.writerow(["REPORTE 3: RESUMEN COMERCIAL (VENTAS DESPACHADAS VS COMPRAS RECEPCIONADAS)"])
    rc = datos["resumen_comercial"]
    writer.writerow(["Ventas Despachadas", rc["ventas_cantidad"], "Volumen Vendido (m3)", rc["ventas_volumen_m3"], "Monto Ventas ($ CLP)", rc["ventas_monto_clp"]])
    writer.writerow(["Compras Recepcionadas", rc["compras_cantidad"], "Monto Compras ($ CLP)", rc["compras_monto_clp"]])
    return resp


# ------------------------------------------------------------------ Dashboard y App Móvil
@permiso_requerido("ver_dashboard")
def dashboard(request):
    try:
        dias = int(request.GET.get("dias", 14))
    except ValueError:
        raise Http404
    dias = dias if dias in (7, 14, 30) else 14
    datos = resumen_dashboard(dias)
    en_revision = (
        GuiaDespacho.objects.filter(recepcion__requiere_revision=True)
        .select_related("faena", "patio_destino", "recepcion")
        .order_by("-recepcion__fecha")[:8]
    )
    return render(
        request,
        "operaciones/dashboard.html",
        {
            "datos": datos,
            "kpis": datos["kpis"],
            "dias": dias,
            "en_revision": en_revision,
            "tolerancia": servicios.tolerancia_discrepancia(),
        },
    )


@login_required
def app_movil(request):
    """Cliente móvil interactivo conectado en tiempo real a la API REST mediante JWT."""
    paquetes_qr = list(
        Paquete.objects.exclude(estado=Paquete.Estado.DESPACHADO)
        .select_related("producto", "ubicacion")
        .order_by("-id")[:8]
    )
    return render(
        request,
        "operaciones/app_movil.html",
        {
            "paquetes_demo": paquetes_qr,
            "usuario_actual": request.user,
        },
    )
