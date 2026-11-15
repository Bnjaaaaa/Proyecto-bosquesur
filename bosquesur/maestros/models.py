"""Datos maestros: proveedores, faenas forestales, patios, ubicaciones de bodega, productos y clientes."""
from django.db import models


class Proveedor(models.Model):
    """Proveedor forestal (propietario de predio) o proveedor de insumos y materiales."""

    class Tipo(models.TextChoices):
        FORESTAL = "FORESTAL", "Proveedor / Propietario Forestal"
        INSUMOS = "INSUMOS", "Proveedor de Insumos y Materiales"

    rut = models.CharField("RUT", max_length=15, unique=True)
    razon_social = models.CharField("razón social", max_length=120)
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.FORESTAL, db_index=True)
    contacto = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["razon_social"]
        verbose_name = "proveedor"
        verbose_name_plural = "proveedores"

    def __str__(self):
        return f"{self.razon_social} ({self.rut})"


class Faena(models.Model):
    """Predio o frente de cosecha forestal donde se emiten guías de despacho."""

    nombre = models.CharField(max_length=100, unique=True)
    ubicacion = models.CharField("ubicación", max_length=150, blank=True)
    codigo_predio = models.CharField("código predio/rol", max_length=30, blank=True, default="PRED-BS-01")
    proveedor = models.ForeignKey(
        Proveedor,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="faenas",
        verbose_name="propietario / proveedor",
    )
    contrato_vigente = models.CharField(
        "contrato/plan de manejo", max_length=60, blank=True, default="CM-CONAF-2026"
    )
    especie = models.CharField("especie forestal", max_length=60, blank=True, default="Pino Radiata")
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "faena"
        verbose_name_plural = "faenas"

    def __str__(self):
        return self.nombre


class Patio(models.Model):
    """Patio de acopio del aserradero donde se recepciona y procesa la madera."""

    nombre = models.CharField(max_length=100, unique=True)
    ubicacion = models.CharField("ubicación", max_length=150, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "patio"
        verbose_name_plural = "patios"

    def __str__(self):
        return self.nombre


class UbicacionBodega(models.Model):
    """Ubicación física interna dentro de un patio/planta para almacenar o procesar paquetes."""

    class Tipo(models.TextChoices):
        ACOPIO = "ACOPIO", "Patio Acopio"
        PROCESO = "PROCESO", "Planta de Proceso (Secado/Impregnado)"
        BODEGA = "BODEGA", "Bodega Producto Terminado"
        DESPACHO = "DESPACHO", "Zona de Pre-Despacho"

    codigo = models.CharField("código ubicación", max_length=25, unique=True)
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.ACOPIO, db_index=True)
    patio = models.ForeignKey(Patio, on_delete=models.PROTECT, related_name="ubicaciones")
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["patio__nombre", "codigo"]
        verbose_name = "ubicación de bodega"
        verbose_name_plural = "ubicaciones de bodega"

    def __str__(self):
        return f"{self.codigo} · {self.nombre} ({self.patio.nombre})"


class Producto(models.Model):
    """Producto forestal o insumo. Rollizos entran por guía; aserrados salen de producción; insumos por compra."""

    class Tipo(models.TextChoices):
        ROLLIZO = "ROLLIZO", "Rollizo (materia prima)"
        ASERRADO = "ASERRADO", "Madera aserrada (producto terminado)"
        INSUMO = "INSUMO", "Insumo / Material externo"

    codigo = models.CharField("código", max_length=20, unique=True)
    nombre = models.CharField(max_length=120)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, db_index=True)
    unidad = models.CharField(max_length=10, default="m³")
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["tipo", "nombre"]
        verbose_name = "producto"
        verbose_name_plural = "productos"

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class Cliente(models.Model):
    """Cliente comercial comprador de paquetes de madera elaborada."""

    rut = models.CharField("RUT", max_length=15, unique=True)
    razon_social = models.CharField("razón social", max_length=120)
    giro = models.CharField(max_length=120, blank=True, default="Constructora y Comercializadora Maderera")
    direccion = models.CharField("dirección", max_length=150, blank=True)
    contacto = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["razon_social"]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"

    def __str__(self):
        return f"{self.razon_social} ({self.rut})"
