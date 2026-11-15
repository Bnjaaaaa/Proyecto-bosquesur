"""
Modelo operacional completo de BosqueSur Maderas SpA:
- Lotes de cosecha (origen forestal)
- Guías de despacho forestal y recepciones en patio
- Órdenes de producción (transformación rollizo -> madera aserrada)
- Paquetes con identificación QR única, procesos posteriores y movimientos entre ubicaciones
- Órdenes de compra externa con flujo de aprobación y recepción
- Pedidos de venta comercial, reserva de paquetes y guía comercial interna simulada (sin SII)
- Inventario por patio y kárdex inmutable con documento de respaldo obligatorio (CHECK en BD)
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from maestros.models import Cliente, Faena, Patio, Producto, Proveedor, UbicacionBodega

VOLUMEN_MINIMO = [MinValueValidator(Decimal("0.001"))]


class LoteCosecha(models.Model):
    """Registro de materia prima cosechada en predio forestal antes de su despacho a planta."""

    codigo = models.CharField("código de lote", max_length=20, unique=True, null=True, editable=False)
    faena = models.ForeignKey(Faena, on_delete=models.PROTECT, related_name="lotes")
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="lotes_cosecha",
        limit_choices_to={"tipo": Producto.Tipo.ROLLIZO, "activo": True},
    )
    volumen_cosechado = models.DecimalField(
        "volumen cosechado (m³)", max_digits=10, decimal_places=3, validators=VOLUMEN_MINIMO
    )
    cuadrilla = models.CharField(max_length=100, default="Cuadrilla Forestal 1")
    fecha_cosecha = models.DateTimeField(auto_now_add=True, db_index=True)
    observacion = models.TextField("observación", blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lotes_registrados"
    )

    class Meta:
        ordering = ["-fecha_cosecha", "-id"]
        verbose_name = "lote de cosecha"
        verbose_name_plural = "lotes de cosecha"

    def __str__(self):
        return f"{self.codigo or f'Lote #{self.pk}'} · {self.faena.nombre}"


class GuiaDespacho(models.Model):
    class Estado(models.TextChoices):
        EMITIDA = "EMITIDA", "En tránsito"
        RECEPCIONADA = "RECEPCIONADA", "Recepcionada"

    numero = models.CharField("número", max_length=20, unique=True, null=True, editable=False)
    faena = models.ForeignKey(Faena, on_delete=models.PROTECT, related_name="guias")
    lote_cosecha = models.ForeignKey(
        LoteCosecha,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="guias",
        verbose_name="lote de cosecha origen",
    )
    patio_destino = models.ForeignKey(Patio, on_delete=models.PROTECT, related_name="guias")
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="guias",
        limit_choices_to={"tipo": Producto.Tipo.ROLLIZO, "activo": True},
    )
    volumen_enviado = models.DecimalField("volumen enviado (m³)", max_digits=10, decimal_places=3, validators=VOLUMEN_MINIMO)
    patente_camion = models.CharField("patente del camión", max_length=10)
    conductor = models.CharField(max_length=100)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.EMITIDA, db_index=True)
    emitida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="guias_emitidas")
    fecha_emision = models.DateTimeField("fecha de emisión", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-fecha_emision", "-id"]
        verbose_name = "guía de despacho"
        verbose_name_plural = "guías de despacho"

    def __str__(self):
        return self.numero or f"Guía #{self.pk}"


class Recepcion(models.Model):
    guia = models.OneToOneField(GuiaDespacho, on_delete=models.PROTECT, related_name="recepcion")
    volumen_recibido = models.DecimalField("volumen recibido (m³)", max_digits=10, decimal_places=3, validators=VOLUMEN_MINIMO)
    # Positiva = merma (llegó menos de lo enviado); negativa = sobrante.
    discrepancia = models.DecimalField(max_digits=10, decimal_places=3)
    porcentaje_discrepancia = models.DecimalField(max_digits=7, decimal_places=2)
    requiere_revision = models.BooleanField(default=False, db_index=True)
    observacion = models.TextField("observación", blank=True)
    recibida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recepciones")
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "recepción"
        verbose_name_plural = "recepciones"

    def __str__(self):
        return f"Recepción de {self.guia}"


class OrdenProduccion(models.Model):
    numero = models.CharField("número", max_length=20, unique=True, null=True, editable=False)
    patio = models.ForeignKey(Patio, on_delete=models.PROTECT, related_name="ordenes")
    guia_origen = models.ForeignKey(
        GuiaDespacho,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ordenes_derivadas",
        verbose_name="guía de rollizo asociada",
    )
    producto_entrada = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="ordenes_como_entrada",
        limit_choices_to={"tipo": Producto.Tipo.ROLLIZO, "activo": True},
        verbose_name="rollizo consumido",
    )
    volumen_entrada = models.DecimalField("volumen consumido (m³)", max_digits=10, decimal_places=3, validators=VOLUMEN_MINIMO)
    producto_salida = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="ordenes_como_salida",
        limit_choices_to={"tipo": Producto.Tipo.ASERRADO, "activo": True},
        verbose_name="madera producida",
    )
    volumen_salida = models.DecimalField("volumen producido (m³)", max_digits=10, decimal_places=3, validators=VOLUMEN_MINIMO)
    rendimiento = models.DecimalField("rendimiento (%)", max_digits=6, decimal_places=2)
    observacion = models.TextField("observación", blank=True)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ordenes_creadas")
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "orden de producción"
        verbose_name_plural = "órdenes de producción"
        constraints = [
            models.CheckConstraint(
                check=Q(volumen_salida__lte=models.F("volumen_entrada")),
                name="produccion_no_supera_entrada",
            )
        ]

    def __str__(self):
        return self.numero or f"Orden #{self.pk}"


class Paquete(models.Model):
    """Unidad logística de madera elaborada con identificación única por código QR."""

    class Calidad(models.TextChoices):
        GRADO_A = "GRADO_A", "Grado A (Estructural / Exportación)"
        GRADO_B = "GRADO_B", "Grado B (Construcción)"
        REPROCESO = "REPROCESO", "Grado C / Reproceso"

    class Estado(models.TextChoices):
        ELABORADO = "ELABORADO", "Elaborado (Aserrado Verde)"
        PROCESADO = "PROCESADO", "Procesado / Terminado"
        RESERVADO = "RESERVADO", "Reservado en Venta"
        DESPACHADO = "DESPACHADO", "Despachado a Cliente"

    class Proceso(models.TextChoices):
        NINGUNO = "NINGUNO", "Aserrado Primario"
        SECADO = "SECADO", "Secado en Cámara (KD 12%)"
        IMPREGNADO = "IMPREGNADO", "Impregnado IPV (CCA)"
        CEPILLADO = "CEPILLADO", "Cepillado Dimensionado"
        REPROCESO = "REPROCESO", "Reproceso / Cambio Calidad"

    codigo_qr = models.CharField("código QR único", max_length=30, unique=True, null=True, editable=False, db_index=True)
    orden_produccion = models.ForeignKey(OrdenProduccion, on_delete=models.PROTECT, related_name="paquetes")
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="paquetes",
        limit_choices_to={"tipo": Producto.Tipo.ASERRADO, "activo": True},
    )
    volumen_m3 = models.DecimalField("volumen del paquete (m³)", max_digits=10, decimal_places=3, validators=VOLUMEN_MINIMO)
    piezas = models.PositiveIntegerField("unidades/piezas", default=100)
    calidad = models.CharField(max_length=15, choices=Calidad.choices, default=Calidad.GRADO_A)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.ELABORADO, db_index=True)
    proceso_actual = models.CharField(max_length=15, choices=Proceso.choices, default=Proceso.NINGUNO)
    ubicacion = models.ForeignKey(UbicacionBodega, on_delete=models.PROTECT, related_name="paquetes")
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="paquetes_creados")
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-fecha_creacion", "-id"]
        verbose_name = "paquete"
        verbose_name_plural = "paquetes"

    def __str__(self):
        return f"{self.codigo_qr or f'PKT #{self.pk}'} · {self.producto.nombre}"


class HistorialPaquete(models.Model):
    """Registro histórico de procesos, traslados, reservas y despachos de un paquete."""

    class TipoEvento(models.TextChoices):
        CREACION = "CREACION", "Generación de paquete y código QR"
        PROCESO = "PROCESO", "Aplicación de proceso posterior"
        MOVIMIENTO = "MOVIMIENTO", "Cambio de ubicación en bodega"
        RESERVA = "RESERVA", "Asignación a pedido de venta"
        DESPACHO = "DESPACHO", "Despacho comercial a cliente"

    paquete = models.ForeignKey(Paquete, on_delete=models.PROTECT, related_name="historial")
    tipo_evento = models.CharField(max_length=15, choices=TipoEvento.choices)
    proceso_aplicado = models.CharField(max_length=20, blank=True, default="")
    ubicacion_origen = models.ForeignKey(
        UbicacionBodega, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    ubicacion_destino = models.ForeignKey(
        UbicacionBodega, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    calidad_resultante = models.CharField(max_length=20, blank=True, default="")
    merma_m3 = models.DecimalField("merma del proceso (m³)", max_digits=10, decimal_places=3, default=Decimal("0"))
    observacion = models.TextField("observación", blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["fecha", "id"]
        verbose_name = "historial de paquete"
        verbose_name_plural = "historiales de paquetes"

    def __str__(self):
        return f"{self.paquete.codigo_qr} · {self.get_tipo_evento_display()}"


class OrdenCompra(models.Model):
    """Compra externa a terceros: solicitud, aprobación gerencial y recepción en inventario."""

    class Estado(models.TextChoices):
        SOLICITADA = "SOLICITADA", "Solicitada (Pendiente Aprobación)"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"
        RECEPCIONADA = "RECEPCIONADA", "Recepcionada en Inventario"

    numero = models.CharField(max_length=20, unique=True, null=True, editable=False)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="ordenes_compra")
    patio_destino = models.ForeignKey(Patio, on_delete=models.PROTECT, related_name="ordenes_compra")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="ordenes_compra")
    cantidad = models.DecimalField("cantidad solicitada", max_digits=10, decimal_places=3, validators=VOLUMEN_MINIMO)
    cantidad_recibida = models.DecimalField("cantidad recepcionada", max_digits=10, decimal_places=3, default=Decimal("0"))
    precio_unitario_clp = models.PositiveIntegerField("costo unitario ($ CLP)", default=50000)
    monto_total_clp = models.PositiveBigIntegerField("monto total ($ CLP)", default=0)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.SOLICITADA, db_index=True)
    solicitada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="compras_solicitadas"
    )
    aprobada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="compras_aprobadas"
    )
    recibida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="compras_recibidas"
    )
    observacion = models.TextField("observación", blank=True)
    fecha_solicitud = models.DateTimeField(auto_now_add=True, db_index=True)
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    fecha_recepcion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_solicitud", "-id"]
        verbose_name = "orden de compra externa"
        verbose_name_plural = "órdenes de compra externa"

    def __str__(self):
        return self.numero or f"OC #{self.pk}"


class PedidoVenta(models.Model):
    """Flujo comercial de venta, reserva de paquetes, despacho y documento interno simulado (sin SII)."""

    class Estado(models.TextChoices):
        PREPARACION = "PREPARACION", "En Preparación (Paquetes Reservados)"
        DESPACHADO = "DESPACHADO", "Despachado a Cliente"
        ANULADO = "ANULADO", "Anulado"

    numero = models.CharField(max_length=20, unique=True, null=True, editable=False)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="pedidos")
    patio_despacho = models.ForeignKey(Patio, on_delete=models.PROTECT, related_name="pedidos_venta")
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PREPARACION, db_index=True)
    paquetes = models.ManyToManyField(Paquete, related_name="pedidos_venta", blank=True)
    volumen_total_m3 = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal("0"))
    monto_neto_clp = models.PositiveBigIntegerField("monto neto ($ CLP)", default=0)
    documento_interno = models.CharField(
        "guía comercial interna (Simulada - Sin SII)", max_length=30, blank=True, default=""
    )
    patente_camion = models.CharField(max_length=10, blank=True, default="")
    conductor = models.CharField(max_length=100, blank=True, default="")
    observacion = models.TextField("observación", blank=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pedidos_creados"
    )
    despachado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="pedidos_despachados"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_index=True)
    fecha_despacho = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_creacion", "-id"]
        verbose_name = "pedido de venta"
        verbose_name_plural = "pedidos de venta"

    def __str__(self):
        return self.numero or f"PV #{self.pk}"


class Inventario(models.Model):
    """Saldo actual de un producto en un patio."""

    patio = models.ForeignKey(Patio, on_delete=models.PROTECT, related_name="inventario")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="inventario")
    cantidad = models.DecimalField("cantidad (m³)", max_digits=12, decimal_places=3, default=Decimal("0"))
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["patio__nombre", "producto__tipo", "producto__nombre"]
        verbose_name = "inventario"
        verbose_name_plural = "inventario"
        constraints = [
            models.UniqueConstraint(fields=["patio", "producto"], name="inventario_unico_por_patio_producto"),
            models.CheckConstraint(check=Q(cantidad__gte=0), name="inventario_no_negativo"),
        ]

    def __str__(self):
        return f"{self.producto} en {self.patio}: {self.cantidad}"


class MovimientoInventario(models.Model):
    """Kárdex: historial inmutable de cada cambio de stock y su documento de respaldo."""

    class Tipo(models.TextChoices):
        ENTRADA_GUIA = "ENTRADA_GUIA", "Entrada por guía de despacho"
        SALIDA_PRODUCCION = "SALIDA_PRODUCCION", "Consumo en producción"
        ENTRADA_PRODUCCION = "ENTRADA_PRODUCCION", "Ingreso desde producción"
        ENTRADA_COMPRA = "ENTRADA_COMPRA", "Entrada por compra externa"
        SALIDA_VENTA = "SALIDA_VENTA", "Salida por despacho comercial"
        MERMA_PROCESO = "MERMA_PROCESO", "Merma por proceso posterior"
        TRANSFERENCIA_SALIDA = "TRANSFERENCIA_SALIDA", "Traslado salida entre patios"
        TRANSFERENCIA_ENTRADA = "TRANSFERENCIA_ENTRADA", "Traslado entrada entre patios"

    tipo = models.CharField(max_length=25, choices=Tipo.choices)
    patio = models.ForeignKey(Patio, on_delete=models.PROTECT, related_name="movimientos")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="movimientos")
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, help_text="Positiva = entrada, negativa = salida")
    saldo_resultante = models.DecimalField(max_digits=12, decimal_places=3)
    guia = models.ForeignKey(GuiaDespacho, null=True, blank=True, on_delete=models.PROTECT, related_name="movimientos")
    orden = models.ForeignKey(OrdenProduccion, null=True, blank=True, on_delete=models.PROTECT, related_name="movimientos")
    compra = models.ForeignKey(OrdenCompra, null=True, blank=True, on_delete=models.PROTECT, related_name="movimientos")
    venta = models.ForeignKey(PedidoVenta, null=True, blank=True, on_delete=models.PROTECT, related_name="movimientos")
    paquete = models.ForeignKey(Paquete, null=True, blank=True, on_delete=models.PROTECT, related_name="movimientos")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="movimientos")
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "movimiento de inventario"
        verbose_name_plural = "movimientos de inventario"
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(guia__isnull=False)
                    | Q(orden__isnull=False)
                    | Q(compra__isnull=False)
                    | Q(venta__isnull=False)
                    | Q(paquete__isnull=False)
                ),
                name="movimiento_con_documento_respaldo",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Los movimientos de inventario no se modifican; se registra un nuevo movimiento.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tipo_display()} {self.cantidad} {self.producto.codigo}"
