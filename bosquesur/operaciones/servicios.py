"""
Lógica de negocio transaccional completa de BosqueSur Maderas SpA.

Cada operación se ejecuta dentro de transaction.atomic(): o se guardan TODOS
los cambios (documento + inventario + kárdex + bitácora) o no se guarda
ninguno. Las filas de inventario y documentos críticos se bloquean con
SELECT ... FOR UPDATE para evitar descuadres bajo concurrencia.

Las vistas web y la API REST llaman exactamente a estas mismas funciones.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from auditoria.servicios import Accion, registrar
from cuentas.models import Usuario
from maestros.models import Producto

from .models import (
    GuiaDespacho,
    HistorialPaquete,
    Inventario,
    LoteCosecha,
    MovimientoInventario,
    OrdenCompra,
    OrdenProduccion,
    Paquete,
    PedidoVenta,
    Recepcion,
)

DOS_DECIMALES = Decimal("0.01")


class ErrorNegocio(Exception):
    """Regla de negocio violada. El mensaje se muestra tal cual al usuario."""


def tolerancia_discrepancia():
    return Decimal(str(settings.TOLERANCIA_DISCREPANCIA_PCT))


def _a_decimal(valor, campo):
    try:
        numero = Decimal(str(valor))
    except Exception as exc:  # noqa: BLE001
        raise ErrorNegocio(f"El {campo} debe ser un número.") from exc
    if numero <= 0:
        raise ErrorNegocio(f"El {campo} debe ser mayor que cero.")
    return numero.quantize(Decimal("0.001"))


def _ajustar_stock(
    *, patio, producto, delta, usuario, tipo, guia=None, orden=None, compra=None, venta=None, paquete=None
):
    inventario, _ = Inventario.objects.select_for_update().get_or_create(patio=patio, producto=producto)
    nuevo_saldo = inventario.cantidad + delta
    if nuevo_saldo < 0:
        raise ErrorNegocio(
            f"Stock insuficiente de {producto.nombre} en {patio.nombre}: "
            f"disponible {inventario.cantidad} {producto.unidad}, requerido {-delta} {producto.unidad}."
        )
    inventario.cantidad = nuevo_saldo
    inventario.save(update_fields=["cantidad", "actualizado"])
    MovimientoInventario.objects.create(
        tipo=tipo,
        patio=patio,
        producto=producto,
        cantidad=delta,
        saldo_resultante=nuevo_saldo,
        guia=guia,
        orden=orden,
        compra=compra,
        venta=venta,
        paquete=paquete,
        usuario=usuario,
    )
    return inventario


@transaction.atomic
def registrar_lote_cosecha(
    *, usuario, faena, producto, volumen_cosechado, cuadrilla="Cuadrilla Forestal 1", observacion="", request=None
):
    if usuario.rol == Usuario.Rol.FAENA and usuario.faena_id and usuario.faena_id != faena.pk and not usuario.is_superuser:
        raise ErrorNegocio("Solo puede registrar cosecha en la faena que tiene asignada.")
    if producto.tipo != Producto.Tipo.ROLLIZO:
        raise ErrorNegocio("Un lote de cosecha forestal solo produce rollizos (materia prima).")
    volumen = _a_decimal(volumen_cosechado, "volumen cosechado")

    lote = LoteCosecha.objects.create(
        faena=faena,
        producto=producto,
        volumen_cosechado=volumen,
        cuadrilla=cuadrilla.strip() or "Cuadrilla Forestal 1",
        observacion=observacion,
        registrado_por=usuario,
    )
    lote.codigo = f"LC-{lote.pk:06d}"
    lote.save(update_fields=["codigo"])

    registrar(
        Accion.REGISTRAR_COSECHA,
        f"Lote {lote.codigo}: {volumen} m³ de {producto.nombre} en {faena.nombre}",
        usuario=usuario,
        entidad="LoteCosecha",
        entidad_id=lote.codigo,
        datos={"faena": faena.nombre, "volumen_cosechado": volumen, "cuadrilla": lote.cuadrilla},
        request=request,
    )
    return lote


@transaction.atomic
def emitir_guia(
    *,
    usuario,
    faena,
    patio_destino,
    producto,
    volumen_enviado,
    patente_camion,
    conductor,
    lote_cosecha=None,
    request=None,
):
    if usuario.rol == Usuario.Rol.FAENA and usuario.faena_id and usuario.faena_id != faena.pk:
        raise ErrorNegocio("Solo puede emitir guías desde la faena que tiene asignada.")
    if producto.tipo != Producto.Tipo.ROLLIZO:
        raise ErrorNegocio("Las guías de despacho forestal solo transportan rollizos.")
    if lote_cosecha is not None and lote_cosecha.faena_id != faena.pk:
        raise ErrorNegocio("El lote de cosecha seleccionado pertenece a otra faena.")
    volumen = _a_decimal(volumen_enviado, "volumen enviado")

    guia = GuiaDespacho.objects.create(
        faena=faena,
        lote_cosecha=lote_cosecha,
        patio_destino=patio_destino,
        producto=producto,
        volumen_enviado=volumen,
        patente_camion=patente_camion,
        conductor=conductor,
        emitida_por=usuario,
    )
    guia.numero = f"GD-{guia.pk:06d}"
    guia.save(update_fields=["numero"])

    registrar(
        Accion.EMITIR_GUIA,
        f"Guía {guia.numero}: {volumen} m³ de {producto.nombre} desde {faena} hacia {patio_destino}",
        usuario=usuario,
        entidad="GuiaDespacho",
        entidad_id=guia.numero,
        datos={
            "volumen_enviado": volumen,
            "patente": patente_camion,
            "conductor": conductor,
            "lote_cosecha": lote_cosecha.codigo if lote_cosecha else None,
        },
        request=request,
    )
    return guia


@transaction.atomic
def recepcionar_guia(*, usuario, guia_id, volumen_recibido, observacion="", request=None):
    try:
        guia = GuiaDespacho.objects.select_for_update().select_related(
            "patio_destino", "producto", "faena"
        ).get(pk=guia_id)
    except GuiaDespacho.DoesNotExist as exc:
        raise ErrorNegocio("La guía de despacho no existe.") from exc

    if guia.estado != GuiaDespacho.Estado.EMITIDA:
        raise ErrorNegocio(f"La guía {guia.numero} ya fue recepcionada.")
    if usuario.rol == Usuario.Rol.PATIO and usuario.patio_id and usuario.patio_id != guia.patio_destino_id:
        raise ErrorNegocio(f"La guía {guia.numero} está destinada a otro patio ({guia.patio_destino}).")

    recibido = _a_decimal(volumen_recibido, "volumen recibido")
    discrepancia = guia.volumen_enviado - recibido
    porcentaje = (discrepancia / guia.volumen_enviado * 100).quantize(DOS_DECIMALES, ROUND_HALF_UP)
    requiere_revision = abs(porcentaje) > tolerancia_discrepancia()

    recepcion = Recepcion.objects.create(
        guia=guia,
        volumen_recibido=recibido,
        discrepancia=discrepancia,
        porcentaje_discrepancia=porcentaje,
        requiere_revision=requiere_revision,
        observacion=observacion,
        recibida_por=usuario,
    )
    guia.estado = GuiaDespacho.Estado.RECEPCIONADA
    guia.save(update_fields=["estado"])

    _ajustar_stock(
        patio=guia.patio_destino,
        producto=guia.producto,
        delta=recibido,
        usuario=usuario,
        tipo=MovimientoInventario.Tipo.ENTRADA_GUIA,
        guia=guia,
    )

    datos = {
        "volumen_enviado": guia.volumen_enviado,
        "volumen_recibido": recibido,
        "discrepancia": discrepancia,
        "porcentaje": porcentaje,
    }
    registrar(
        Accion.RECEPCIONAR_GUIA,
        f"Recepción de {guia.numero} en {guia.patio_destino}: {recibido} m³ (discrepancia {porcentaje}%)",
        usuario=usuario,
        entidad="GuiaDespacho",
        entidad_id=guia.numero,
        datos=datos,
        request=request,
    )
    if requiere_revision:
        registrar(
            Accion.ALERTA_DISCREPANCIA,
            f"Discrepancia de {porcentaje}% en {guia.numero} supera la tolerancia de {tolerancia_discrepancia()}%",
            usuario=usuario,
            entidad="GuiaDespacho",
            entidad_id=guia.numero,
            datos=datos,
            request=request,
        )
    return recepcion


@transaction.atomic
def resolver_discrepancia(usuario, recepcion_id, aceptar=True, observacion="", *, request=None):
    """Validación gerencial de una recepción con discrepancia fuera de tolerancia (no altera stock)."""
    if not usuario.tiene_rol(Usuario.Rol.GERENTE):
        raise ErrorNegocio("Solo la Gerencia está autorizada para resolver discrepancias de recepción.")
    try:
        recepcion = Recepcion.objects.select_for_update().select_related("guia").get(pk=recepcion_id)
    except Recepcion.DoesNotExist as exc:
        raise ErrorNegocio("La recepción indicada no existe.") from exc

    if not recepcion.requiere_revision:
        raise ErrorNegocio(
            f"La recepción de {recepcion.guia.numero} no tiene discrepancia pendiente de revisión."
        )

    obs_limpia = (observacion or "").strip()
    if not aceptar and not obs_limpia:
        raise ErrorNegocio("Debe indicar una observación al rechazar la discrepancia.")

    decision = "ACEPTADA" if aceptar else "RECHAZADA"
    recepcion.requiere_revision = False
    recepcion.revisada_por = usuario
    recepcion.fecha_revision = timezone.now()
    recepcion.resolucion = f"{decision}: {obs_limpia}" if obs_limpia else decision
    recepcion.save(update_fields=["requiere_revision", "revisada_por", "fecha_revision", "resolucion"])

    registrar(
        Accion.RESOLVER_DISCREPANCIA,
        f"Discrepancia de {recepcion.guia.numero} {decision} por {usuario.nombre_visible}",
        usuario=usuario,
        entidad="GuiaDespacho",
        entidad_id=recepcion.guia.numero,
        datos={
            "recepcion_id": recepcion.pk,
            "decision": decision,
            "discrepancia_m3": recepcion.discrepancia,
            "observacion": obs_limpia,
        },
        request=request,
    )
    return recepcion


@transaction.atomic
def registrar_produccion(
    *,
    usuario,
    patio,
    producto_entrada,
    volumen_entrada,
    producto_salida,
    volumen_salida,
    guia_origen=None,
    observacion="",
    request=None,
):
    if usuario.rol == Usuario.Rol.PATIO and usuario.patio_id and usuario.patio_id != patio.pk:
        raise ErrorNegocio("Solo puede registrar producción en el patio que tiene asignado.")
    if producto_entrada.tipo != Producto.Tipo.ROLLIZO:
        raise ErrorNegocio("La materia prima de una orden de producción debe ser un rollizo.")
    if producto_salida.tipo != Producto.Tipo.ASERRADO:
        raise ErrorNegocio("El producto de una orden de producción debe ser madera aserrada.")
    if guia_origen is not None:
        guia_origen = GuiaDespacho.objects.get(pk=guia_origen.pk)
        if guia_origen.estado != GuiaDespacho.Estado.RECEPCIONADA:
            raise ErrorNegocio("La guía de origen asociada debe estar recepcionada en patio.")
    entrada = _a_decimal(volumen_entrada, "volumen consumido")
    salida = _a_decimal(volumen_salida, "volumen producido")
    if salida > entrada:
        raise ErrorNegocio("El volumen producido no puede superar el volumen de rollizo consumido.")
    rendimiento = (salida / entrada * 100).quantize(DOS_DECIMALES, ROUND_HALF_UP)

    orden = OrdenProduccion.objects.create(
        patio=patio,
        guia_origen=guia_origen,
        producto_entrada=producto_entrada,
        volumen_entrada=entrada,
        producto_salida=producto_salida,
        volumen_salida=salida,
        rendimiento=rendimiento,
        observacion=observacion,
        creada_por=usuario,
    )
    orden.numero = f"OP-{orden.pk:06d}"
    orden.save(update_fields=["numero"])

    # Si no hay stock suficiente, ErrorNegocio revierte también la orden creada arriba.
    _ajustar_stock(
        patio=patio, producto=producto_entrada, delta=-entrada, usuario=usuario,
        tipo=MovimientoInventario.Tipo.SALIDA_PRODUCCION, orden=orden,
    )
    _ajustar_stock(
        patio=patio, producto=producto_salida, delta=salida, usuario=usuario,
        tipo=MovimientoInventario.Tipo.ENTRADA_PRODUCCION, orden=orden,
    )

    registrar(
        Accion.ORDEN_PRODUCCION,
        f"Orden {orden.numero} en {patio}: {entrada} m³ de {producto_entrada.nombre} → "
        f"{salida} m³ de {producto_salida.nombre} (rendimiento {rendimiento}%)",
        usuario=usuario,
        entidad="OrdenProduccion",
        entidad_id=orden.numero,
        datos={
            "volumen_entrada": entrada,
            "volumen_salida": salida,
            "rendimiento": rendimiento,
            "guia_origen": guia_origen.numero if guia_origen else None,
        },
        request=request,
    )
    return orden


@transaction.atomic
def crear_paquete(
    *,
    usuario,
    orden_produccion,
    ubicacion,
    volumen_m3,
    piezas=100,
    calidad=Paquete.Calidad.GRADO_A,
    observacion="",
    request=None,
):
    orden = OrdenProduccion.objects.select_for_update().select_related("patio", "producto_salida").get(
        pk=orden_produccion.pk
    )
    if usuario.rol == Usuario.Rol.PATIO and usuario.patio_id and usuario.patio_id != orden.patio_id and not usuario.is_superuser:
        raise ErrorNegocio("Solo puede empaquetar órdenes de producción de su patio.")
    if ubicacion.patio_id != orden.patio_id:
        raise ErrorNegocio(f"La ubicación {ubicacion.codigo} pertenece a otro patio ({ubicacion.patio.nombre}).")

    vol = _a_decimal(volumen_m3, "volumen del paquete")
    if int(piezas) <= 0:
        raise ErrorNegocio("La cantidad de piezas debe ser mayor que cero.")

    vol_actual = orden.paquetes.aggregate(total=Sum("volumen_m3"))["total"] or Decimal("0")
    merma_previa = (
        HistorialPaquete.objects.filter(paquete__orden_produccion=orden).aggregate(total=Sum("merma_m3"))["total"]
        or Decimal("0")
    )
    empaquetado_previo = vol_actual + merma_previa
    if empaquetado_previo + vol > orden.volumen_salida:
        disponible = orden.volumen_salida - empaquetado_previo
        raise ErrorNegocio(
            f"El paquete ({vol} m³) supera el volumen disponible sin empaquetar de {orden.numero} ({disponible} m³)."
        )

    paquete = Paquete.objects.create(
        orden_produccion=orden,
        producto=orden.producto_salida,
        volumen_m3=vol,
        piezas=int(piezas),
        calidad=calidad,
        estado=Paquete.Estado.ELABORADO,
        proceso_actual=Paquete.Proceso.NINGUNO,
        ubicacion=ubicacion,
        creado_por=usuario,
    )
    paquete.codigo_qr = f"BS-PKT-{paquete.pk:06d}"
    paquete.save(update_fields=["codigo_qr"])

    HistorialPaquete.objects.create(
        paquete=paquete,
        tipo_evento=HistorialPaquete.TipoEvento.CREACION,
        ubicacion_destino=ubicacion,
        calidad_resultante=calidad,
        observacion=observacion or f"Empaquetado desde {orden.numero}",
        usuario=usuario,
    )

    registrar(
        Accion.CREAR_PAQUETE_QR,
        f"Paquete {paquete.codigo_qr} ({vol} m³, {piezas} pzas) generado desde {orden.numero} en {ubicacion.codigo}",
        usuario=usuario,
        entidad="Paquete",
        entidad_id=paquete.codigo_qr,
        datos={"orden": orden.numero, "volumen_m3": vol, "piezas": int(piezas), "ubicacion": ubicacion.codigo},
        request=request,
    )
    return paquete


def _validar_patio_operador(usuario, patio_id, mensaje):
    if (
        usuario.rol == Usuario.Rol.PATIO
        and usuario.patio_id
        and usuario.patio_id != patio_id
        and not usuario.is_superuser
    ):
        raise ErrorNegocio(mensaje)


@transaction.atomic
def aplicar_proceso_paquete(
    *,
    usuario,
    paquete_id,
    proceso,
    ubicacion_destino=None,
    calidad_resultante=None,
    merma_m3=Decimal("0"),
    observacion="",
    request=None,
):
    try:
        paquete = Paquete.objects.select_for_update().select_related(
            "ubicacion", "ubicacion__patio", "producto"
        ).get(pk=paquete_id)
    except Paquete.DoesNotExist as exc:
        raise ErrorNegocio("El paquete indicado no existe.") from exc

    _validar_patio_operador(
        usuario,
        paquete.ubicacion.patio_id,
        "Solo puede procesar paquetes ubicados en su patio.",
    )

    if paquete.estado in (Paquete.Estado.RESERVADO, Paquete.Estado.DESPACHADO):
        raise ErrorNegocio(f"El paquete {paquete.codigo_qr} está {paquete.get_estado_display()} y no puede procesarse.")
    if proceso not in dict(Paquete.Proceso.choices) or proceso == Paquete.Proceso.NINGUNO:
        raise ErrorNegocio("Debe seleccionar un proceso posterior válido (Secado, Impregnado, Cepillado o Reproceso).")

    try:
        merma = Decimal(str(merma_m3 or 0)).quantize(Decimal("0.001"))
    except Exception as exc:  # noqa: BLE001
        raise ErrorNegocio("La merma del proceso debe ser numérica.") from exc
    if merma < 0:
        raise ErrorNegocio("La merma no puede ser negativa.")
    if merma >= paquete.volumen_m3:
        raise ErrorNegocio("La merma del proceso no puede ser igual o mayor al volumen del paquete.")

    ubicacion_origen = paquete.ubicacion
    destino = ubicacion_destino or ubicacion_origen

    if merma > 0:
        paquete.volumen_m3 = (paquete.volumen_m3 - merma).quantize(Decimal("0.001"))
        _ajustar_stock(
            patio=ubicacion_origen.patio,
            producto=paquete.producto,
            delta=-merma,
            usuario=usuario,
            tipo=MovimientoInventario.Tipo.MERMA_PROCESO,
            paquete=paquete,
        )

    if destino.patio_id != ubicacion_origen.patio_id:
        _ajustar_stock(
            patio=ubicacion_origen.patio,
            producto=paquete.producto,
            delta=-paquete.volumen_m3,
            usuario=usuario,
            tipo=MovimientoInventario.Tipo.TRANSFERENCIA_SALIDA,
            paquete=paquete,
        )
        _ajustar_stock(
            patio=destino.patio,
            producto=paquete.producto,
            delta=paquete.volumen_m3,
            usuario=usuario,
            tipo=MovimientoInventario.Tipo.TRANSFERENCIA_ENTRADA,
            paquete=paquete,
        )

    paquete.proceso_actual = proceso
    paquete.estado = Paquete.Estado.PROCESADO
    if calidad_resultante and calidad_resultante in dict(Paquete.Calidad.choices):
        paquete.calidad = calidad_resultante
    paquete.ubicacion = destino
    paquete.save(update_fields=["volumen_m3", "proceso_actual", "estado", "calidad", "ubicacion"])

    HistorialPaquete.objects.create(
        paquete=paquete,
        tipo_evento=HistorialPaquete.TipoEvento.PROCESO,
        proceso_aplicado=proceso,
        ubicacion_origen=ubicacion_origen,
        ubicacion_destino=destino,
        calidad_resultante=paquete.calidad,
        merma_m3=merma,
        observacion=observacion or f"Proceso {paquete.get_proceso_actual_display()} aplicado",
        usuario=usuario,
    )

    registrar(
        Accion.PROCESAR_PAQUETE,
        f"Proceso {paquete.get_proceso_actual_display()} en {paquete.codigo_qr} (merma {merma} m³, ubicación {destino.codigo})",
        usuario=usuario,
        entidad="Paquete",
        entidad_id=paquete.codigo_qr,
        datos={
            "proceso": proceso,
            "merma_m3": merma,
            "ubicacion_destino": destino.codigo,
            "calidad": paquete.calidad,
        },
        request=request,
    )
    return paquete


@transaction.atomic
def mover_paquete(*, usuario, paquete_id, ubicacion_destino, observacion="", request=None):
    try:
        paquete = Paquete.objects.select_for_update().select_related(
            "ubicacion", "ubicacion__patio", "producto"
        ).get(pk=paquete_id)
    except Paquete.DoesNotExist as exc:
        raise ErrorNegocio("El paquete indicado no existe.") from exc

    _validar_patio_operador(
        usuario,
        paquete.ubicacion.patio_id,
        "Solo puede mover paquetes ubicados en su patio.",
    )
    if paquete.estado == Paquete.Estado.DESPACHADO:
        raise ErrorNegocio(f"El paquete {paquete.codigo_qr} ya fue despachado a cliente.")
    if paquete.ubicacion_id == ubicacion_destino.pk:
        raise ErrorNegocio(f"El paquete {paquete.codigo_qr} ya se encuentra en {ubicacion_destino.codigo}.")

    ubicacion_origen = paquete.ubicacion
    if paquete.estado == Paquete.Estado.RESERVADO and ubicacion_origen.patio_id != ubicacion_destino.patio_id:
        raise ErrorNegocio(
            f"El paquete {paquete.codigo_qr} está reservado y no puede trasladarse a otro patio "
            f"(solo dentro de {ubicacion_origen.patio.nombre})."
        )
    if ubicacion_origen.patio_id != ubicacion_destino.patio_id:
        _ajustar_stock(
            patio=ubicacion_origen.patio,
            producto=paquete.producto,
            delta=-paquete.volumen_m3,
            usuario=usuario,
            tipo=MovimientoInventario.Tipo.TRANSFERENCIA_SALIDA,
            paquete=paquete,
        )
        _ajustar_stock(
            patio=ubicacion_destino.patio,
            producto=paquete.producto,
            delta=paquete.volumen_m3,
            usuario=usuario,
            tipo=MovimientoInventario.Tipo.TRANSFERENCIA_ENTRADA,
            paquete=paquete,
        )

    paquete.ubicacion = ubicacion_destino
    paquete.save(update_fields=["ubicacion"])

    HistorialPaquete.objects.create(
        paquete=paquete,
        tipo_evento=HistorialPaquete.TipoEvento.MOVIMIENTO,
        ubicacion_origen=ubicacion_origen,
        ubicacion_destino=ubicacion_destino,
        observacion=observacion or f"Traslado de {ubicacion_origen.codigo} a {ubicacion_destino.codigo}",
        usuario=usuario,
    )

    registrar(
        Accion.MOVER_PAQUETE,
        f"Movimiento de {paquete.codigo_qr}: {ubicacion_origen.codigo} → {ubicacion_destino.codigo}",
        usuario=usuario,
        entidad="Paquete",
        entidad_id=paquete.codigo_qr,
        datos={"origen": ubicacion_origen.codigo, "destino": ubicacion_destino.codigo},
        request=request,
    )
    return paquete


@transaction.atomic
def solicitar_compra(
    *, usuario, proveedor, patio_destino, producto, cantidad, precio_unitario_clp, observacion="", request=None
):
    cant = _a_decimal(cantidad, "cantidad solicitada")
    try:
        precio = int(precio_unitario_clp)
    except (TypeError, ValueError) as exc:
        raise ErrorNegocio("El precio unitario debe ser un entero positivo en CLP.") from exc
    if precio <= 0:
        raise ErrorNegocio("El precio unitario debe ser mayor que cero.")

    monto_total = int((cant * Decimal(precio)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    compra = OrdenCompra.objects.create(
        proveedor=proveedor,
        patio_destino=patio_destino,
        producto=producto,
        cantidad=cant,
        precio_unitario_clp=precio,
        monto_total_clp=monto_total,
        estado=OrdenCompra.Estado.SOLICITADA,
        solicitada_por=usuario,
        observacion=observacion,
    )
    compra.numero = f"OC-{compra.pk:06d}"
    compra.save(update_fields=["numero"])

    registrar(
        Accion.SOLICITAR_COMPRA,
        f"Orden de compra {compra.numero}: {cant} {producto.unidad} de {producto.nombre} a {proveedor.razon_social}",
        usuario=usuario,
        entidad="OrdenCompra",
        entidad_id=compra.numero,
        datos={"proveedor": proveedor.razon_social, "cantidad": cant, "monto_total_clp": monto_total},
        request=request,
    )
    return compra


@transaction.atomic
def resolver_aprobacion_compra(*, usuario, compra_id, aprobar=True, observacion="", request=None):
    if not usuario.tiene_rol(Usuario.Rol.GERENTE):
        raise ErrorNegocio("Solo la Gerencia está autorizada para aprobar o rechazar órdenes de compra.")
    try:
        compra = OrdenCompra.objects.select_for_update().select_related("proveedor", "producto").get(pk=compra_id)
    except OrdenCompra.DoesNotExist as exc:
        raise ErrorNegocio("La orden de compra no existe.") from exc

    if compra.estado != OrdenCompra.Estado.SOLICITADA:
        raise ErrorNegocio(f"La orden {compra.numero} ya fue resuelta ({compra.get_estado_display()}).")

    compra.estado = OrdenCompra.Estado.APROBADA if aprobar else OrdenCompra.Estado.RECHAZADA
    compra.aprobada_por = usuario
    compra.fecha_aprobacion = timezone.now()
    if observacion:
        compra.observacion = f"{compra.observacion}\n[Resolución Gerencia]: {observacion}".strip()
    compra.save(update_fields=["estado", "aprobada_por", "fecha_aprobacion", "observacion"])

    verbo = "APROBADA" if aprobar else "RECHAZADA"
    registrar(
        Accion.APROBAR_COMPRA,
        f"Orden de compra {compra.numero} {verbo} por {usuario.nombre_visible} (${compra.monto_total_clp:,} CLP)",
        usuario=usuario,
        entidad="OrdenCompra",
        entidad_id=compra.numero,
        datos={"estado": compra.estado, "monto_total_clp": compra.monto_total_clp},
        request=request,
    )
    return compra


@transaction.atomic
def recepcionar_compra(*, usuario, compra_id, cantidad_recibida, observacion="", request=None):
    try:
        compra = OrdenCompra.objects.select_for_update().select_related("patio_destino", "producto", "proveedor").get(
            pk=compra_id
        )
    except OrdenCompra.DoesNotExist as exc:
        raise ErrorNegocio("La orden de compra no existe.") from exc

    if compra.estado != OrdenCompra.Estado.APROBADA:
        raise ErrorNegocio(f"La orden {compra.numero} debe estar aprobada antes de recepcionarse.")
    if (
        usuario.rol == Usuario.Rol.PATIO
        and usuario.patio_id
        and usuario.patio_id != compra.patio_destino_id
        and not usuario.is_superuser
    ):
        raise ErrorNegocio(f"La orden {compra.numero} está destinada a {compra.patio_destino.nombre}.")

    recibida = _a_decimal(cantidad_recibida, "cantidad recibida")
    if recibida > compra.cantidad:
        raise ErrorNegocio(
            f"La cantidad recibida ({recibida}) supera la solicitada ({compra.cantidad})."
        )
    compra.estado = OrdenCompra.Estado.RECEPCIONADA
    compra.cantidad_recibida = recibida
    compra.recibida_por = usuario
    compra.fecha_recepcion = timezone.now()
    if observacion:
        compra.observacion = f"{compra.observacion}\n[Recepción]: {observacion}".strip()
    compra.save(
        update_fields=["estado", "cantidad_recibida", "recibida_por", "fecha_recepcion", "observacion"]
    )

    _ajustar_stock(
        patio=compra.patio_destino,
        producto=compra.producto,
        delta=recibida,
        usuario=usuario,
        tipo=MovimientoInventario.Tipo.ENTRADA_COMPRA,
        compra=compra,
    )

    datos_auditoria = {"cantidad_recibida": recibida, "patio": compra.patio_destino.nombre}
    if recibida < compra.cantidad:
        datos_auditoria["diferencia"] = (compra.cantidad - recibida).quantize(Decimal("0.001"))

    registrar(
        Accion.RECEPCIONAR_COMPRA,
        f"Recepción de {compra.numero}: +{recibida} {compra.producto.unidad} de {compra.producto.nombre} en {compra.patio_destino}",
        usuario=usuario,
        entidad="OrdenCompra",
        entidad_id=compra.numero,
        datos=datos_auditoria,
        request=request,
    )
    return compra


@transaction.atomic
def crear_pedido_venta(
    *, usuario, cliente, patio_despacho, paquetes_ids, precio_m3_clp=185000, observacion="", request=None
):
    ids_unicos = list(dict.fromkeys(int(pid) for pid in paquetes_ids))
    if not ids_unicos:
        raise ErrorNegocio("Debe seleccionar al menos un paquete disponible para crear el pedido de venta.")

    paquetes = list(
        Paquete.objects.select_for_update()
        .select_related("ubicacion", "producto")
        .filter(pk__in=ids_unicos)
    )
    if len(paquetes) != len(ids_unicos):
        raise ErrorNegocio("Uno o más paquetes seleccionados no existen.")

    for p in paquetes:
        if p.estado not in (Paquete.Estado.ELABORADO, Paquete.Estado.PROCESADO):
            raise ErrorNegocio(f"El paquete {p.codigo_qr} no está disponible (estado actual: {p.get_estado_display()}).")
        if p.ubicacion.patio_id != patio_despacho.pk:
            raise ErrorNegocio(
                f"El paquete {p.codigo_qr} se encuentra en {p.ubicacion.patio.nombre} y no en {patio_despacho.nombre}."
            )

    volumen_total = sum((p.volumen_m3 for p in paquetes), Decimal("0")).quantize(Decimal("0.001"))
    monto_neto = int((volumen_total * Decimal(int(precio_m3_clp))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    pedido = PedidoVenta.objects.create(
        cliente=cliente,
        patio_despacho=patio_despacho,
        estado=PedidoVenta.Estado.PREPARACION,
        volumen_total_m3=volumen_total,
        monto_neto_clp=monto_neto,
        observacion=observacion,
        creado_por=usuario,
    )
    pedido.numero = f"PV-{pedido.pk:06d}"
    pedido.save(update_fields=["numero"])
    pedido.paquetes.set(paquetes)

    for p in paquetes:
        p.estado = Paquete.Estado.RESERVADO
        p.save(update_fields=["estado"])
        HistorialPaquete.objects.create(
            paquete=p,
            tipo_evento=HistorialPaquete.TipoEvento.RESERVA,
            ubicacion_origen=p.ubicacion,
            ubicacion_destino=p.ubicacion,
            observacion=f"Reservado para {pedido.numero} ({cliente.razon_social})",
            usuario=usuario,
        )

    registrar(
        Accion.CREAR_VENTA,
        f"Pedido {pedido.numero} para {cliente.razon_social}: {len(paquetes)} paquete(s), {volumen_total} m³",
        usuario=usuario,
        entidad="PedidoVenta",
        entidad_id=pedido.numero,
        datos={
            "cliente": cliente.razon_social,
            "paquetes": [p.codigo_qr for p in paquetes],
            "volumen_total_m3": volumen_total,
            "monto_neto_clp": monto_neto,
        },
        request=request,
    )
    return pedido


@transaction.atomic
def despachar_pedido_venta(*, usuario, pedido_id, patente_camion, conductor, observacion="", request=None):
    try:
        pedido = PedidoVenta.objects.select_for_update().select_related("cliente", "patio_despacho").get(pk=pedido_id)
    except PedidoVenta.DoesNotExist as exc:
        raise ErrorNegocio("El pedido de venta no existe.") from exc

    if pedido.estado != PedidoVenta.Estado.PREPARACION:
        raise ErrorNegocio(f"El pedido {pedido.numero} no se encuentra en preparación.")
    if (
        usuario.rol == Usuario.Rol.PATIO
        and usuario.patio_id
        and usuario.patio_id != pedido.patio_despacho_id
        and not usuario.is_superuser
    ):
        raise ErrorNegocio(f"El pedido {pedido.numero} debe despacharse desde {pedido.patio_despacho.nombre}.")

    paquetes = list(
        pedido.paquetes.select_for_update().select_related("ubicacion", "ubicacion__patio", "producto")
    )
    if not paquetes:
        raise ErrorNegocio("El pedido no tiene paquetes asignados.")

    for p in paquetes:
        if p.ubicacion.patio_id != pedido.patio_despacho_id:
            raise ErrorNegocio(
                f"El paquete {p.codigo_qr} se encuentra en {p.ubicacion.patio.nombre} "
                f"y no en {pedido.patio_despacho.nombre}."
            )

    documento_interno = f"GDC-INT-{pedido.pk:06d}"
    pedido.estado = PedidoVenta.Estado.DESPACHADO
    pedido.documento_interno = documento_interno
    pedido.patente_camion = patente_camion
    pedido.conductor = conductor
    pedido.despachado_por = usuario
    pedido.fecha_despacho = timezone.now()
    if observacion:
        pedido.observacion = f"{pedido.observacion}\n[Despacho]: {observacion}".strip()
    pedido.save(
        update_fields=[
            "estado",
            "documento_interno",
            "patente_camion",
            "conductor",
            "despachado_por",
            "fecha_despacho",
            "observacion",
        ]
    )

    for p in paquetes:
        p.estado = Paquete.Estado.DESPACHADO
        p.save(update_fields=["estado"])
        HistorialPaquete.objects.create(
            paquete=p,
            tipo_evento=HistorialPaquete.TipoEvento.DESPACHO,
            ubicacion_origen=p.ubicacion,
            observacion=f"Despachado en {pedido.numero} · Doc. interno {documento_interno} ({patente_camion})",
            usuario=usuario,
        )
        _ajustar_stock(
            patio=pedido.patio_despacho,
            producto=p.producto,
            delta=-p.volumen_m3,
            usuario=usuario,
            tipo=MovimientoInventario.Tipo.SALIDA_VENTA,
            venta=pedido,
            paquete=p,
        )

    registrar(
        Accion.DESPACHAR_VENTA,
        f"Despacho {pedido.numero} ({documento_interno}) a {pedido.cliente.razon_social} · {pedido.volumen_total_m3} m³",
        usuario=usuario,
        entidad="PedidoVenta",
        entidad_id=pedido.numero,
        datos={
            "documento_interno": documento_interno,
            "patente_camion": patente_camion,
            "conductor": conductor,
            "paquetes": [p.codigo_qr for p in paquetes],
        },
        request=request,
    )
    return pedido


@transaction.atomic
def anular_pedido_venta(usuario, pedido_id, motivo="", *, request=None):
    """Anula un pedido en PREPARACION y libera sus paquetes reservados sin alterar stock."""
    try:
        pedido = PedidoVenta.objects.select_for_update().select_related("cliente", "patio_despacho").get(pk=pedido_id)
    except PedidoVenta.DoesNotExist as exc:
        raise ErrorNegocio("El pedido de venta no existe.") from exc

    if pedido.estado != PedidoVenta.Estado.PREPARACION:
        raise ErrorNegocio(
            f"Solo se pueden anular pedidos en preparación (estado actual: {pedido.get_estado_display()})."
        )
    _validar_patio_operador(
        usuario,
        pedido.patio_despacho_id,
        f"El pedido {pedido.numero} corresponde a {pedido.patio_despacho.nombre}.",
    )

    paquetes = list(pedido.paquetes.select_for_update().select_related("ubicacion"))
    motivo_limpio = (motivo or "").strip() or "Anulación administrativa"

    pedido.estado = PedidoVenta.Estado.ANULADO
    pedido.observacion = f"{pedido.observacion}\n[Anulación]: {motivo_limpio}".strip()
    pedido.save(update_fields=["estado", "observacion"])

    codigos = []
    for p in paquetes:
        p.estado = (
            Paquete.Estado.PROCESADO
            if p.proceso_actual != Paquete.Proceso.NINGUNO
            else Paquete.Estado.ELABORADO
        )
        p.save(update_fields=["estado"])
        codigos.append(p.codigo_qr)
        HistorialPaquete.objects.create(
            paquete=p,
            tipo_evento=HistorialPaquete.TipoEvento.LIBERACION,
            ubicacion_origen=p.ubicacion,
            ubicacion_destino=p.ubicacion,
            observacion=f"Liberado por anulación de {pedido.numero}: {motivo_limpio}",
            usuario=usuario,
        )

    registrar(
        Accion.ANULAR_VENTA,
        f"Pedido {pedido.numero} anulado ({len(paquetes)} paquete(s) liberados): {motivo_limpio}",
        usuario=usuario,
        entidad="PedidoVenta",
        entidad_id=pedido.numero,
        datos={"motivo": motivo_limpio, "paquetes": codigos},
        request=request,
    )
    return pedido


def registrar_rechazo(*, usuario, operacion, motivo, request=None, datos=None):
    """Deja constancia de una operación rechazada (fuera de la transacción revertida)."""
    registrar(
        Accion.OPERACION_RECHAZADA,
        f"{operacion} rechazada: {motivo}",
        usuario=usuario,
        datos=datos,
        request=request,
    )
