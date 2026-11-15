import re
from decimal import Decimal

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from auditoria.models import RegistroAuditoria
from cuentas.models import Usuario
from maestros.models import Cliente, Faena, Patio, Producto, Proveedor, UbicacionBodega
from operaciones.forms import PATENTE_CHILENA
from operaciones.models import (
    GuiaDespacho,
    HistorialPaquete,
    Inventario,
    LoteCosecha,
    OrdenCompra,
    OrdenProduccion,
    Paquete,
    PedidoVenta,
    Recepcion,
)


def _limpiar_patente(valor):
    patente = re.sub(r"[\s\-·.]", "", valor.upper())
    if not PATENTE_CHILENA.match(patente):
        raise serializers.ValidationError("Formato de patente no válido (ej.: ABCD12 o AB1234).")
    return patente


class TokenConRolSerializer(TokenObtainPairSerializer):
    """Agrega el rol al JWT para que la app móvil adapte sus pantallas."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["rol"] = user.rol
        return token

    def validate(self, attrs):
        datos = super().validate(attrs)
        datos["usuario"] = UsuarioSerializer(self.user).data
        return datos


class UsuarioSerializer(serializers.ModelSerializer):
    faena = serializers.StringRelatedField()
    patio = serializers.StringRelatedField()

    class Meta:
        model = Usuario
        fields = ["id", "username", "first_name", "last_name", "rol", "faena", "patio"]


class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = ["id", "rut", "razon_social", "tipo", "contacto", "activo"]


class FaenaSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.CharField(source="proveedor.razon_social", read_only=True, allow_null=True)

    class Meta:
        model = Faena
        fields = ["id", "nombre", "ubicacion", "codigo_predio", "contrato_vigente", "especie", "proveedor", "proveedor_nombre"]


class PatioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patio
        fields = ["id", "nombre", "ubicacion"]


class UbicacionBodegaSerializer(serializers.ModelSerializer):
    patio_nombre = serializers.CharField(source="patio.nombre", read_only=True)

    class Meta:
        model = UbicacionBodega
        fields = ["id", "codigo", "nombre", "tipo", "patio", "patio_nombre"]


class ProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = ["id", "codigo", "nombre", "tipo", "unidad"]


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ["id", "rut", "razon_social", "giro", "direccion", "contacto"]


class LoteCosechaSerializer(serializers.ModelSerializer):
    faena_nombre = serializers.CharField(source="faena.nombre", read_only=True)
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    registrado_por = serializers.StringRelatedField()

    class Meta:
        model = LoteCosecha
        fields = [
            "id",
            "codigo",
            "faena",
            "faena_nombre",
            "producto",
            "producto_nombre",
            "volumen_cosechado",
            "cuadrilla",
            "observacion",
            "registrado_por",
            "fecha_cosecha",
        ]
        read_only_fields = ["codigo", "registrado_por", "fecha_cosecha"]


class RecepcionSerializer(serializers.ModelSerializer):
    recibida_por = serializers.StringRelatedField()

    class Meta:
        model = Recepcion
        fields = [
            "volumen_recibido",
            "discrepancia",
            "porcentaje_discrepancia",
            "requiere_revision",
            "observacion",
            "recibida_por",
            "fecha",
        ]


class GuiaDespachoSerializer(serializers.ModelSerializer):
    faena_nombre = serializers.CharField(source="faena.nombre", read_only=True)
    lote_codigo = serializers.CharField(source="lote_cosecha.codigo", read_only=True, allow_null=True)
    patio_destino_nombre = serializers.CharField(source="patio_destino.nombre", read_only=True)
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    emitida_por = serializers.StringRelatedField()
    recepcion = RecepcionSerializer(read_only=True)

    class Meta:
        model = GuiaDespacho
        fields = [
            "id",
            "numero",
            "estado",
            "faena",
            "faena_nombre",
            "lote_cosecha",
            "lote_codigo",
            "patio_destino",
            "patio_destino_nombre",
            "producto",
            "producto_nombre",
            "volumen_enviado",
            "patente_camion",
            "conductor",
            "emitida_por",
            "fecha_emision",
            "recepcion",
        ]
        read_only_fields = ["numero", "estado", "emitida_por", "fecha_emision"]

    def validate_patente_camion(self, valor):
        return _limpiar_patente(valor)


class RecepcionEntradaSerializer(serializers.Serializer):
    volumen_recibido = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal("0.001"))
    observacion = serializers.CharField(required=False, allow_blank=True, default="")


class OrdenProduccionSerializer(serializers.ModelSerializer):
    patio_nombre = serializers.CharField(source="patio.nombre", read_only=True)
    guia_origen_numero = serializers.CharField(source="guia_origen.numero", read_only=True, allow_null=True)
    producto_entrada_nombre = serializers.CharField(source="producto_entrada.nombre", read_only=True)
    producto_salida_nombre = serializers.CharField(source="producto_salida.nombre", read_only=True)
    creada_por = serializers.StringRelatedField()

    class Meta:
        model = OrdenProduccion
        fields = [
            "id",
            "numero",
            "patio",
            "patio_nombre",
            "guia_origen",
            "guia_origen_numero",
            "producto_entrada",
            "producto_entrada_nombre",
            "volumen_entrada",
            "producto_salida",
            "producto_salida_nombre",
            "volumen_salida",
            "rendimiento",
            "observacion",
            "creada_por",
            "fecha",
        ]
        read_only_fields = ["numero", "rendimiento", "creada_por", "fecha"]


class HistorialPaqueteSerializer(serializers.ModelSerializer):
    ubicacion_origen = serializers.StringRelatedField()
    ubicacion_destino = serializers.StringRelatedField()
    usuario = serializers.StringRelatedField()

    class Meta:
        model = HistorialPaquete
        fields = [
            "id",
            "tipo_evento",
            "proceso_aplicado",
            "ubicacion_origen",
            "ubicacion_destino",
            "calidad_resultante",
            "merma_m3",
            "observacion",
            "usuario",
            "fecha",
        ]


class PaqueteSerializer(serializers.ModelSerializer):
    orden_numero = serializers.CharField(source="orden_produccion.numero", read_only=True)
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    ubicacion_codigo = serializers.CharField(source="ubicacion.codigo", read_only=True)
    ubicacion_nombre = serializers.CharField(source="ubicacion.nombre", read_only=True)
    patio_nombre = serializers.CharField(source="ubicacion.patio.nombre", read_only=True)
    creado_por = serializers.StringRelatedField()
    historial = HistorialPaqueteSerializer(many=True, read_only=True)
    observacion = serializers.CharField(write_only=True, required=False, allow_blank=True, default="")

    class Meta:
        model = Paquete
        fields = [
            "id",
            "codigo_qr",
            "orden_produccion",
            "orden_numero",
            "producto",
            "producto_nombre",
            "volumen_m3",
            "piezas",
            "calidad",
            "estado",
            "proceso_actual",
            "ubicacion",
            "ubicacion_codigo",
            "ubicacion_nombre",
            "patio_nombre",
            "creado_por",
            "fecha_creacion",
            "observacion",
            "historial",
        ]
        read_only_fields = ["codigo_qr", "producto", "estado", "proceso_actual", "creado_por", "fecha_creacion"]


class ProcesoPaqueteEntradaSerializer(serializers.Serializer):
    proceso = serializers.ChoiceField(choices=Paquete.Proceso.choices)
    ubicacion_destino = serializers.PrimaryKeyRelatedField(
        queryset=UbicacionBodega.objects.filter(activa=True), required=False, allow_null=True
    )
    calidad_resultante = serializers.ChoiceField(
        choices=Paquete.Calidad.choices, required=False, allow_null=True, allow_blank=True
    )
    merma_m3 = serializers.DecimalField(
        max_digits=10, decimal_places=3, min_value=Decimal("0"), required=False, default=Decimal("0")
    )
    observacion = serializers.CharField(required=False, allow_blank=True, default="")


class MoverPaqueteEntradaSerializer(serializers.Serializer):
    ubicacion_destino = serializers.PrimaryKeyRelatedField(queryset=UbicacionBodega.objects.filter(activa=True))
    observacion = serializers.CharField(required=False, allow_blank=True, default="")


class OrdenCompraSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.CharField(source="proveedor.razon_social", read_only=True)
    patio_nombre = serializers.CharField(source="patio_destino.nombre", read_only=True)
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    solicitada_por = serializers.StringRelatedField()
    aprobada_por = serializers.StringRelatedField()
    recibida_por = serializers.StringRelatedField()

    class Meta:
        model = OrdenCompra
        fields = [
            "id",
            "numero",
            "proveedor",
            "proveedor_nombre",
            "patio_destino",
            "patio_nombre",
            "producto",
            "producto_nombre",
            "cantidad",
            "cantidad_recibida",
            "precio_unitario_clp",
            "monto_total_clp",
            "estado",
            "observacion",
            "solicitada_por",
            "aprobada_por",
            "recibida_por",
            "fecha_solicitud",
            "fecha_aprobacion",
            "fecha_recepcion",
        ]
        read_only_fields = [
            "numero",
            "cantidad_recibida",
            "monto_total_clp",
            "estado",
            "solicitada_por",
            "aprobada_por",
            "recibida_por",
            "fecha_solicitud",
            "fecha_aprobacion",
            "fecha_recepcion",
        ]


class AprobarCompraEntradaSerializer(serializers.Serializer):
    aprobar = serializers.BooleanField(default=True)
    observacion = serializers.CharField(required=False, allow_blank=True, default="")


class RecepcionarCompraEntradaSerializer(serializers.Serializer):
    cantidad_recibida = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal("0.001"))
    observacion = serializers.CharField(required=False, allow_blank=True, default="")


class PedidoVentaSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source="cliente.razon_social", read_only=True)
    patio_nombre = serializers.CharField(source="patio_despacho.nombre", read_only=True)
    paquetes = serializers.PrimaryKeyRelatedField(queryset=Paquete.objects.all(), many=True)
    precio_m3_clp = serializers.IntegerField(write_only=True, min_value=1000, required=False, default=185000)
    creado_por = serializers.StringRelatedField()
    despachado_por = serializers.StringRelatedField()

    class Meta:
        model = PedidoVenta
        fields = [
            "id",
            "numero",
            "cliente",
            "cliente_nombre",
            "patio_despacho",
            "patio_nombre",
            "estado",
            "paquetes",
            "volumen_total_m3",
            "monto_neto_clp",
            "precio_m3_clp",
            "documento_interno",
            "patente_camion",
            "conductor",
            "observacion",
            "creado_por",
            "despachado_por",
            "fecha_creacion",
            "fecha_despacho",
        ]
        read_only_fields = [
            "numero",
            "estado",
            "volumen_total_m3",
            "monto_neto_clp",
            "documento_interno",
            "patente_camion",
            "conductor",
            "creado_por",
            "despachado_por",
            "fecha_creacion",
            "fecha_despacho",
        ]


class DespacharVentaEntradaSerializer(serializers.Serializer):
    patente_camion = serializers.CharField(max_length=10)
    conductor = serializers.CharField(max_length=100)
    observacion = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_patente_camion(self, valor):
        return _limpiar_patente(valor)


class InventarioSerializer(serializers.ModelSerializer):
    patio = serializers.StringRelatedField()
    producto = ProductoSerializer()

    class Meta:
        model = Inventario
        fields = ["id", "patio", "producto", "cantidad", "actualizado"]


class RegistroAuditoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroAuditoria
        fields = [
            "id",
            "fecha",
            "usuario_nombre",
            "accion",
            "entidad",
            "entidad_id",
            "descripcion",
            "datos",
            "ip",
            "hash_anterior",
            "hash",
        ]
