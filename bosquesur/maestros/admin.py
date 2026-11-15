from django.contrib import admin

from .models import Cliente, Faena, Patio, Producto, Proveedor, UbicacionBodega


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("rut", "razon_social", "tipo", "contacto", "activo")
    list_filter = ("tipo", "activo")
    search_fields = ("rut", "razon_social")


@admin.register(Faena)
class FaenaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo_predio", "proveedor", "contrato_vigente", "ubicacion", "activa")
    list_filter = ("activa", "proveedor")
    search_fields = ("nombre", "codigo_predio", "ubicacion", "contrato_vigente")


@admin.register(Patio)
class PatioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "ubicacion", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "ubicacion")


@admin.register(UbicacionBodega)
class UbicacionBodegaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "tipo", "patio", "activa")
    list_filter = ("tipo", "patio", "activa")
    search_fields = ("codigo", "nombre")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "tipo", "unidad", "activo")
    list_filter = ("tipo", "activo")
    search_fields = ("codigo", "nombre")


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("rut", "razon_social", "giro", "contacto", "activo")
    list_filter = ("activo",)
    search_fields = ("rut", "razon_social", "giro")
