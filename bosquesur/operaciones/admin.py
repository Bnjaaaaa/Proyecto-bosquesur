"""
En el admin las operaciones son de solo lectura: documentos, paquetes, compras,
ventas e inventario solo se crean mediante los servicios transaccionales (web o API),
para que nunca se salten el kárdex ni la bitácora.
"""
from django.contrib import admin

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


class SoloLecturaAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LoteCosecha)
class LoteCosechaAdmin(SoloLecturaAdmin):
    list_display = ("codigo", "faena", "producto", "volumen_cosechado", "cuadrilla", "fecha_cosecha")
    list_filter = ("faena",)
    search_fields = ("codigo", "cuadrilla")


@admin.register(GuiaDespacho)
class GuiaDespachoAdmin(SoloLecturaAdmin):
    list_display = ("numero", "faena", "lote_cosecha", "patio_destino", "producto", "volumen_enviado", "estado", "fecha_emision")
    list_filter = ("estado", "faena", "patio_destino")
    search_fields = ("numero", "patente_camion", "conductor")


@admin.register(Recepcion)
class RecepcionAdmin(SoloLecturaAdmin):
    list_display = ("guia", "volumen_recibido", "discrepancia", "porcentaje_discrepancia", "requiere_revision", "fecha")
    list_filter = ("requiere_revision",)


@admin.register(OrdenProduccion)
class OrdenProduccionAdmin(SoloLecturaAdmin):
    list_display = ("numero", "patio", "guia_origen", "producto_entrada", "volumen_entrada", "producto_salida", "volumen_salida", "rendimiento", "fecha")


@admin.register(Paquete)
class PaqueteAdmin(SoloLecturaAdmin):
    list_display = ("codigo_qr", "producto", "volumen_m3", "piezas", "calidad", "proceso_actual", "estado", "ubicacion")
    list_filter = ("estado", "proceso_actual", "calidad", "ubicacion__patio")
    search_fields = ("codigo_qr", "producto__nombre")


@admin.register(HistorialPaquete)
class HistorialPaqueteAdmin(SoloLecturaAdmin):
    list_display = ("fecha", "paquete", "tipo_evento", "proceso_aplicado", "ubicacion_origen", "ubicacion_destino", "merma_m3")
    list_filter = ("tipo_evento",)


@admin.register(OrdenCompra)
class OrdenCompraAdmin(SoloLecturaAdmin):
    list_display = ("numero", "proveedor", "producto", "cantidad", "monto_total_clp", "estado", "fecha_solicitud")
    list_filter = ("estado", "patio_destino")
    search_fields = ("numero", "proveedor__razon_social")


@admin.register(PedidoVenta)
class PedidoVentaAdmin(SoloLecturaAdmin):
    list_display = ("numero", "cliente", "patio_despacho", "volumen_total_m3", "monto_neto_clp", "estado", "documento_interno")
    list_filter = ("estado", "patio_despacho")
    search_fields = ("numero", "documento_interno", "cliente__razon_social")


@admin.register(Inventario)
class InventarioAdmin(SoloLecturaAdmin):
    list_display = ("patio", "producto", "cantidad", "actualizado")
    list_filter = ("patio",)


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(SoloLecturaAdmin):
    list_display = ("fecha", "tipo", "patio", "producto", "cantidad", "saldo_resultante", "guia", "orden", "compra", "venta", "paquete", "usuario")
    list_filter = ("tipo", "patio")
