"""
Consultas de lectura para el dashboard gerencial, trazabilidad de extremo a extremo
y reportes operacionales/gerenciales (compartidas por la web y la API).

Las agrupaciones por día se hacen en Python y no con funciones de fecha de la
base de datos: así funcionan igual en MariaDB de XAMPP (que no trae cargadas
las tablas de zonas horarias), en SQLite y en PostgreSQL.
"""
from collections import OrderedDict, defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from auditoria.models import RegistroAuditoria
from cuentas.models import Usuario
from maestros.models import Producto, UbicacionBodega

from .models import (
    GuiaDespacho,
    Inventario,
    OrdenCompra,
    OrdenProduccion,
    Paquete,
    PedidoVenta,
    Recepcion,
)

CERO = Decimal("0")


def guias_visibles(usuario):
    """Un encargado de faena solo ve las guías de su faena; un operador, las de su patio."""
    guias = GuiaDespacho.objects.select_related(
        "faena", "faena__proveedor", "lote_cosecha", "patio_destino", "producto", "emitida_por", "recepcion"
    )
    if usuario.is_superuser:
        return guias
    if usuario.rol == Usuario.Rol.FAENA and usuario.faena_id:
        return guias.filter(faena_id=usuario.faena_id)
    if usuario.rol == Usuario.Rol.PATIO and usuario.patio_id:
        return guias.filter(patio_destino_id=usuario.patio_id)
    return guias


def _num(valor):
    return float(valor or 0)


def resumen_dashboard(dias=14):
    ahora = timezone.now()
    desde = ahora - timedelta(days=dias)

    en_transito = GuiaDespacho.objects.filter(estado=GuiaDespacho.Estado.EMITIDA).aggregate(
        cantidad=Count("id"), volumen=Sum("volumen_enviado")
    )
    recepciones = Recepcion.objects.filter(fecha__gte=desde).select_related("guia", "guia__faena")
    totales = recepciones.aggregate(
        cantidad=Count("id"),
        enviado=Sum("guia__volumen_enviado"),
        recibido=Sum("volumen_recibido"),
        merma=Sum("discrepancia"),
    )
    enviado = totales["enviado"] or CERO
    merma_pct = (totales["merma"] or CERO) / enviado * 100 if enviado else CERO

    stock_por_tipo = {
        fila["producto__tipo"]: fila["total"]
        for fila in Inventario.objects.order_by().values("producto__tipo").annotate(total=Sum("cantidad"))
    }
    produccion = OrdenProduccion.objects.filter(fecha__gte=desde).aggregate(
        entrada=Sum("volumen_entrada"), salida=Sum("volumen_salida"), cantidad=Count("id")
    )
    rendimiento = (
        (produccion["salida"] / produccion["entrada"] * 100) if produccion["entrada"] else CERO
    )

    # Indicadores de paquetes QR, compras externas y ventas comerciales
    paquetes_activos = Paquete.objects.exclude(estado=Paquete.Estado.DESPACHADO).aggregate(
        cantidad=Count("id"), volumen=Sum("volumen_m3")
    )
    compras_pendientes = OrdenCompra.objects.filter(estado=OrdenCompra.Estado.SOLICITADA).count()
    ventas_periodo = PedidoVenta.objects.filter(
        estado=PedidoVenta.Estado.DESPACHADO, fecha_despacho__gte=desde
    ).aggregate(cantidad=Count("id"), volumen=Sum("volumen_total_m3"), monto=Sum("monto_neto_clp"))

    # Volumen enviado vs recibido por día (fecha local de Chile).
    serie = OrderedDict()
    for i in range(dias - 1, -1, -1):
        dia = timezone.localdate(ahora - timedelta(days=i))
        serie[dia] = {"enviado": 0.0, "recibido": 0.0}
    for fecha, volumen in GuiaDespacho.objects.filter(fecha_emision__gte=desde).values_list(
        "fecha_emision", "volumen_enviado"
    ):
        dia = timezone.localdate(fecha)
        if dia in serie:
            serie[dia]["enviado"] += _num(volumen)
    for r in recepciones:
        dia = timezone.localdate(r.fecha)
        if dia in serie:
            serie[dia]["recibido"] += _num(r.volumen_recibido)

    # Discrepancia porcentual acumulada por faena.
    por_faena = defaultdict(lambda: {"enviado": CERO, "merma": CERO, "guias": 0})
    for r in recepciones:
        f = por_faena[r.guia.faena.nombre]
        f["enviado"] += r.guia.volumen_enviado
        f["merma"] += r.discrepancia
        f["guias"] += 1
    discrepancia_faena = sorted(
        (
            {
                "faena": nombre,
                "porcentaje": round(_num(v["merma"] / v["enviado"] * 100), 2) if v["enviado"] else 0,
                "guias": v["guias"],
            }
            for nombre, v in por_faena.items()
        ),
        key=lambda x: x["porcentaje"],
        reverse=True,
    )

    stock_producto = [
        {"producto": fila["producto__nombre"], "tipo": fila["producto__tipo"], "cantidad": _num(fila["total"])}
        for fila in Inventario.objects.order_by()
        .values("producto__nombre", "producto__tipo")
        .annotate(total=Sum("cantidad"))
        .order_by("-total")
    ]

    return {
        "periodo_dias": dias,
        "kpis": {
            "guias_en_transito": en_transito["cantidad"] or 0,
            "volumen_en_transito": _num(en_transito["volumen"]),
            "recepciones": totales["cantidad"] or 0,
            "volumen_recibido": _num(totales["recibido"]),
            "merma_m3": _num(totales["merma"]),
            "merma_pct": round(_num(merma_pct), 2),
            "recepciones_en_revision": recepciones.filter(requiere_revision=True).count(),
            "stock_rollizo": _num(stock_por_tipo.get(Producto.Tipo.ROLLIZO)),
            "stock_aserrado": _num(stock_por_tipo.get(Producto.Tipo.ASERRADO)),
            "stock_insumo": _num(stock_por_tipo.get(Producto.Tipo.INSUMO)),
            "ordenes_produccion": produccion["cantidad"] or 0,
            "rendimiento_pct": round(_num(rendimiento), 2),
            "paquetes_activos": paquetes_activos["cantidad"] or 0,
            "paquetes_m3": _num(paquetes_activos["volumen"]),
            "compras_pendientes": compras_pendientes,
            "ventas_despachadas": ventas_periodo["cantidad"] or 0,
            "ventas_volumen_m3": _num(ventas_periodo["volumen"]),
            "ventas_monto_clp": int(ventas_periodo["monto"] or 0),
        },
        "serie_diaria": [
            {"fecha": dia.isoformat(), "enviado": round(v["enviado"], 3), "recibido": round(v["recibido"], 3)}
            for dia, v in serie.items()
        ],
        "discrepancia_por_faena": discrepancia_faena,
        "stock_por_producto": stock_producto,
    }


def trazabilidad_paquete(paquete):
    """Construye la cadena histórica completa desde origen forestal hasta destino comercial."""
    orden = paquete.orden_produccion
    guia = orden.guia_origen
    if guia is None:
        # Respaldo referencial: última guía recepcionada del mismo rollizo en el patio de la orden
        guia = (
            GuiaDespacho.objects.filter(
                patio_destino=orden.patio,
                producto=orden.producto_entrada,
                estado=GuiaDespacho.Estado.RECEPCIONADA,
                fecha_emision__lte=orden.fecha,
            )
            .select_related("faena", "faena__proveedor", "lote_cosecha", "recepcion")
            .order_by("-fecha_emision")
            .first()
        )
        trazado_directo = False
    else:
        trazado_directo = True

    lote = guia.lote_cosecha if guia else None
    faena = guia.faena if guia else None
    proveedor = faena.proveedor if faena else None
    recepcion = getattr(guia, "recepcion", None) if guia else None
    pedido = paquete.pedidos_venta.select_related("cliente", "patio_despacho", "despachado_por").first()
    historial = list(
        paquete.historial.select_related("ubicacion_origen", "ubicacion_destino", "usuario").order_by("fecha", "id")
    )
    auditoria = list(
        RegistroAuditoria.objects.filter(entidad="Paquete", entidad_id=paquete.codigo_qr).order_by("id")
    )
    return {
        "trazado_directo": trazado_directo,
        "proveedor": proveedor,
        "faena": faena,
        "lote": lote,
        "guia": guia,
        "recepcion": recepcion,
        "orden": orden,
        "paquete": paquete,
        "historial": historial,
        "pedido": pedido,
        "auditoria": auditoria,
    }


def datos_reportes(*, fecha_desde=None, fecha_hasta=None, faena_id=None, patio_id=None):
    """Genera los datos filtrados para los 3 reportes operacionales/gerenciales y exportación CSV."""
    recepciones = Recepcion.objects.select_related("guia", "guia__faena", "guia__faena__proveedor", "guia__patio_destino")
    compras = OrdenCompra.objects.select_related("proveedor", "patio_destino", "producto")
    ventas = PedidoVenta.objects.select_related("cliente", "patio_despacho")

    if fecha_desde:
        dt_desde = timezone.make_aware(datetime.combine(fecha_desde, time.min))
        recepciones = recepciones.filter(fecha__gte=dt_desde)
        compras = compras.filter(fecha_solicitud__gte=dt_desde)
        ventas = ventas.filter(fecha_creacion__gte=dt_desde)
    if fecha_hasta:
        dt_hasta = timezone.make_aware(datetime.combine(fecha_hasta, time.max))
        recepciones = recepciones.filter(fecha__lte=dt_hasta)
        compras = compras.filter(fecha_solicitud__lte=dt_hasta)
        ventas = ventas.filter(fecha_creacion__lte=dt_hasta)
    if faena_id:
        recepciones = recepciones.filter(guia__faena_id=faena_id)
    if patio_id:
        recepciones = recepciones.filter(guia__patio_destino_id=patio_id)
        compras = compras.filter(patio_destino_id=patio_id)
        ventas = ventas.filter(patio_despacho_id=patio_id)

    # 1. Rendimiento y mermas por faena y proveedor
    por_faena = {}
    for r in recepciones:
        f = r.guia.faena
        item = por_faena.setdefault(
            f.pk,
            {
                "faena": f.nombre,
                "codigo_predio": f.codigo_predio,
                "proveedor": f.proveedor.razon_social if f.proveedor else "Predio Propio BosqueSur",
                "contrato": f.contrato_vigente,
                "guias": 0,
                "enviado_m3": Decimal("0"),
                "recibido_m3": Decimal("0"),
                "merma_m3": Decimal("0"),
                "en_revision": 0,
            },
        )
        item["guias"] += 1
        item["enviado_m3"] += r.guia.volumen_enviado
        item["recibido_m3"] += r.volumen_recibido
        item["merma_m3"] += r.discrepancia
        if r.requiere_revision:
            item["en_revision"] += 1

    reporte_faenas = []
    for item in por_faena.values():
        env = item["enviado_m3"]
        item["merma_pct"] = round(_num(item["merma_m3"] / env * 100), 2) if env else 0.0
        reporte_faenas.append(item)
    reporte_faenas.sort(key=lambda x: x["merma_pct"], reverse=True)

    # 2. Paquetes por ubicación en bodega
    ubicaciones = UbicacionBodega.objects.filter(activa=True).select_related("patio")
    if patio_id:
        ubicaciones = ubicaciones.filter(patio_id=patio_id)
    reporte_ubicaciones = []
    for u in ubicaciones:
        pkts = u.paquetes.exclude(estado=Paquete.Estado.DESPACHADO)
        agg = pkts.aggregate(cant=Count("id"), vol=Sum("volumen_m3"))
        procesados = pkts.filter(estado=Paquete.Estado.PROCESADO).count()
        reporte_ubicaciones.append(
            {
                "codigo": u.codigo,
                "nombre": u.nombre,
                "tipo": u.get_tipo_display(),
                "patio": u.patio.nombre,
                "paquetes": agg["cant"] or 0,
                "volumen_m3": agg["vol"] or Decimal("0"),
                "procesados": procesados,
            }
        )

    # 3. Resumen comercial (Ventas vs Compras Externas)
    ventas_desp = ventas.filter(estado=PedidoVenta.Estado.DESPACHADO)
    ventas_agg = ventas_desp.aggregate(
        cantidad=Count("id"), volumen=Sum("volumen_total_m3"), monto=Sum("monto_neto_clp")
    )
    compras_rec = compras.filter(estado=OrdenCompra.Estado.RECEPCIONADA)
    compras_agg = compras_rec.aggregate(cantidad=Count("id"), monto=Sum("monto_total_clp"))

    return {
        "reporte_faenas": reporte_faenas,
        "reporte_ubicaciones": reporte_ubicaciones,
        "ventas_lista": list(ventas_desp[:20]),
        "compras_lista": list(compras_rec[:20]),
        "resumen_comercial": {
            "ventas_cantidad": ventas_agg["cantidad"] or 0,
            "ventas_volumen_m3": ventas_agg["volumen"] or Decimal("0"),
            "ventas_monto_clp": int(ventas_agg["monto"] or 0),
            "compras_cantidad": compras_agg["cantidad"] or 0,
            "compras_monto_clp": int(compras_agg["monto"] or 0),
        },
    }
