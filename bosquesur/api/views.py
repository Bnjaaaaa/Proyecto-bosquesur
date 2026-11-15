"""
API REST (JSON) protegida con JWT, pensada para la app móvil Flutter, cliente /app-movil/
y futuras integraciones. Usa los mismos servicios transaccionales que la web.
"""
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from auditoria.models import RegistroAuditoria
from auditoria.servicios import Accion, registrar
from cuentas.models import Usuario
from maestros.models import Cliente, Faena, Patio, Producto, Proveedor, UbicacionBodega
from operaciones import servicios
from operaciones.consultas import guias_visibles, resumen_dashboard, trazabilidad_paquete
from operaciones.models import (
    GuiaDespacho,
    Inventario,
    LoteCosecha,
    OrdenCompra,
    OrdenProduccion,
    Paquete,
    PedidoVenta,
)

from .permisos import requiere
from .serializers import (
    AprobarCompraEntradaSerializer,
    ClienteSerializer,
    DespacharVentaEntradaSerializer,
    FaenaSerializer,
    GuiaDespachoSerializer,
    InventarioSerializer,
    LoteCosechaSerializer,
    MoverPaqueteEntradaSerializer,
    OrdenCompraSerializer,
    OrdenProduccionSerializer,
    PaqueteSerializer,
    PatioSerializer,
    PedidoVentaSerializer,
    ProcesoPaqueteEntradaSerializer,
    ProductoSerializer,
    ProveedorSerializer,
    RecepcionarCompraEntradaSerializer,
    RecepcionEntradaSerializer,
    RegistroAuditoriaSerializer,
    TokenConRolSerializer,
    UbicacionBodegaSerializer,
    UsuarioSerializer,
)


def _ejecutar(request, operacion, funcion, **kwargs):
    """Ejecuta un servicio y traduce ErrorNegocio en HTTP 400 dejando constancia en la bitácora."""
    try:
        return funcion(usuario=request.user, request=request, **kwargs)
    except servicios.ErrorNegocio as error:
        servicios.registrar_rechazo(usuario=request.user, operacion=operacion, motivo=str(error), request=request)
        raise ValidationError({"detalle": str(error)}) from error


class LoginJWTView(TokenObtainPairView):
    serializer_class = TokenConRolSerializer

    def post(self, request, *args, **kwargs):
        respuesta = super().post(request, *args, **kwargs)
        if respuesta.status_code == status.HTTP_200_OK:
            usuario = Usuario.objects.get(username=request.data.get("username"))
            registrar(Accion.LOGIN_API, "Inicio de sesión en la API (JWT)", usuario=usuario, request=request)
        return respuesta


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def yo(request):
    return Response(UsuarioSerializer(request.user).data)


class LoteCosechaViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = LoteCosechaSerializer

    def get_permissions(self):
        permiso = "registrar_cosecha" if self.action == "create" else "ver_cosecha"
        return [IsAuthenticated(), requiere(permiso)()]

    def get_queryset(self):
        qs = LoteCosecha.objects.select_related("faena", "producto", "registrado_por")
        u = self.request.user
        if u.rol == Usuario.Rol.FAENA and u.faena_id and not u.is_superuser:
            qs = qs.filter(faena_id=u.faena_id)
        return qs

    def create(self, request, *args, **kwargs):
        entrada = self.get_serializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        lote = _ejecutar(
            request,
            "Registro de cosecha (API)",
            servicios.registrar_lote_cosecha,
            faena=d["faena"],
            producto=d["producto"],
            volumen_cosechado=d["volumen_cosechado"],
            cuadrilla=d.get("cuadrilla", "Cuadrilla Forestal 1"),
            observacion=d.get("observacion", ""),
        )
        return Response(self.get_serializer(lote).data, status=status.HTTP_201_CREATED)


class GuiaDespachoViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = GuiaDespachoSerializer

    def get_permissions(self):
        permiso = {"create": "emitir_guia", "recepcionar": "recepcionar"}.get(self.action, "ver_guias")
        return [IsAuthenticated(), requiere(permiso)()]

    def get_queryset(self):
        guias = guias_visibles(self.request.user)
        estado = self.request.query_params.get("estado")
        return guias.filter(estado=estado) if estado else guias

    def create(self, request, *args, **kwargs):
        entrada = self.get_serializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        guia = _ejecutar(
            request,
            "Emisión de guía (API)",
            servicios.emitir_guia,
            faena=d["faena"],
            patio_destino=d["patio_destino"],
            producto=d["producto"],
            volumen_enviado=d["volumen_enviado"],
            patente_camion=d["patente_camion"],
            conductor=d["conductor"],
            lote_cosecha=d.get("lote_cosecha"),
        )
        return Response(self.get_serializer(guia).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def recepcionar(self, request, pk=None):
        guia = self.get_object()
        entrada = RecepcionEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        _ejecutar(
            request,
            f"Recepción de {guia.numero} (API)",
            servicios.recepcionar_guia,
            guia_id=guia.pk,
            **entrada.validated_data,
        )
        guia.refresh_from_db()
        return Response(self.get_serializer(guia).data, status=status.HTTP_201_CREATED)


class OrdenProduccionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = OrdenProduccionSerializer

    def get_permissions(self):
        permiso = "registrar_produccion" if self.action == "create" else "ver_produccion"
        return [IsAuthenticated(), requiere(permiso)()]

    def get_queryset(self):
        ordenes = OrdenProduccion.objects.select_related(
            "patio", "guia_origen", "producto_entrada", "producto_salida", "creada_por"
        )
        u = self.request.user
        if u.rol == Usuario.Rol.PATIO and u.patio_id and not u.is_superuser:
            ordenes = ordenes.filter(patio_id=u.patio_id)
        return ordenes

    def create(self, request, *args, **kwargs):
        entrada = self.get_serializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        orden = _ejecutar(
            request,
            "Orden de producción (API)",
            servicios.registrar_produccion,
            patio=d["patio"],
            producto_entrada=d["producto_entrada"],
            volumen_entrada=d["volumen_entrada"],
            producto_salida=d["producto_salida"],
            volumen_salida=d["volumen_salida"],
            observacion=d.get("observacion", ""),
            guia_origen=d.get("guia_origen"),
        )
        return Response(self.get_serializer(orden).data, status=status.HTTP_201_CREATED)


class PaqueteViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = PaqueteSerializer

    def get_permissions(self):
        permiso = (
            "gestionar_paquetes" if self.action in ("create", "procesar", "mover") else "ver_paquetes"
        )
        return [IsAuthenticated(), requiere(permiso)()]

    def get_queryset(self):
        qs = Paquete.objects.select_related(
            "orden_produccion", "producto", "ubicacion", "ubicacion__patio", "creado_por"
        ).prefetch_related("historial__ubicacion_origen", "historial__ubicacion_destino", "historial__usuario")
        u = self.request.user
        if u.rol == Usuario.Rol.PATIO and u.patio_id and not u.is_superuser:
            qs = qs.filter(ubicacion__patio_id=u.patio_id)
        codigo_qr = self.request.query_params.get("codigo_qr")
        estado = self.request.query_params.get("estado")
        if codigo_qr:
            qs = qs.filter(codigo_qr__iexact=codigo_qr.strip())
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    def create(self, request, *args, **kwargs):
        entrada = self.get_serializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        paquete = _ejecutar(
            request,
            "Creación de paquete QR (API)",
            servicios.crear_paquete,
            orden_produccion=d["orden_produccion"],
            ubicacion=d["ubicacion"],
            volumen_m3=d["volumen_m3"],
            piezas=d.get("piezas", 100),
            calidad=d.get("calidad", Paquete.Calidad.GRADO_A),
            observacion=d.get("observacion", ""),
        )
        return Response(self.get_serializer(paquete).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def trazabilidad(self, request, pk=None):
        paquete = self.get_object()
        t = trazabilidad_paquete(paquete)
        return Response(
            {
                "trazado_directo": t["trazado_directo"],
                "proveedor": (
                    {"razon_social": t["proveedor"].razon_social, "rut": t["proveedor"].rut}
                    if t["proveedor"]
                    else None
                ),
                "faena": (
                    {
                        "id": t["faena"].pk,
                        "nombre": t["faena"].nombre,
                        "codigo_predio": t["faena"].codigo_predio,
                        "contrato": t["faena"].contrato_vigente,
                    }
                    if t["faena"]
                    else None
                ),
                "lote": (
                    {
                        "codigo": t["lote"].codigo,
                        "volumen_cosechado": str(t["lote"].volumen_cosechado),
                        "cuadrilla": t["lote"].cuadrilla,
                    }
                    if t["lote"]
                    else None
                ),
                "guia": (
                    {
                        "numero": t["guia"].numero,
                        "volumen_enviado": str(t["guia"].volumen_enviado),
                        "patente_camion": t["guia"].patente_camion,
                    }
                    if t["guia"]
                    else None
                ),
                "recepcion": (
                    {
                        "volumen_recibido": str(t["recepcion"].volumen_recibido),
                        "porcentaje_discrepancia": str(t["recepcion"].porcentaje_discrepancia),
                        "requiere_revision": t["recepcion"].requiere_revision,
                    }
                    if t["recepcion"]
                    else None
                ),
                "orden": {
                    "numero": t["orden"].numero,
                    "patio": t["orden"].patio.nombre,
                    "rendimiento": str(t["orden"].rendimiento),
                },
                "paquete": self.get_serializer(paquete).data,
                "pedido": (
                    {
                        "numero": t["pedido"].numero,
                        "cliente": t["pedido"].cliente.razon_social,
                        "estado": t["pedido"].estado,
                        "documento_interno": t["pedido"].documento_interno,
                    }
                    if t["pedido"]
                    else None
                ),
                "auditoria": [
                    {
                        "fecha": e.fecha.isoformat(),
                        "accion": e.accion,
                        "descripcion": e.descripcion,
                        "hash": e.hash,
                    }
                    for e in t["auditoria"]
                ],
            }
        )

    @action(detail=True, methods=["post"])
    def procesar(self, request, pk=None):
        paquete = self.get_object()
        entrada = ProcesoPaqueteEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        paquete = _ejecutar(
            request,
            f"Proceso posterior {paquete.codigo_qr} (API)",
            servicios.aplicar_proceso_paquete,
            paquete_id=paquete.pk,
            proceso=d["proceso"],
            ubicacion_destino=d.get("ubicacion_destino"),
            calidad_resultante=d.get("calidad_resultante") or None,
            merma_m3=d.get("merma_m3", 0),
            observacion=d.get("observacion", ""),
        )
        return Response(self.get_serializer(paquete).data)

    @action(detail=True, methods=["post"])
    def mover(self, request, pk=None):
        paquete = self.get_object()
        entrada = MoverPaqueteEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        paquete = _ejecutar(
            request,
            f"Traslado {paquete.codigo_qr} (API)",
            servicios.mover_paquete,
            paquete_id=paquete.pk,
            ubicacion_destino=d["ubicacion_destino"],
            observacion=d.get("observacion", ""),
        )
        return Response(self.get_serializer(paquete).data)


class OrdenCompraViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = OrdenCompraSerializer

    def get_permissions(self):
        permiso = {
            "create": "solicitar_compra",
            "aprobar": "aprobar_compra",
            "recepcionar": "recepcionar_compra",
        }.get(self.action, "ver_compras")
        return [IsAuthenticated(), requiere(permiso)()]

    def get_queryset(self):
        qs = OrdenCompra.objects.select_related(
            "proveedor", "patio_destino", "producto", "solicitada_por", "aprobada_por", "recibida_por"
        )
        u = self.request.user
        if u.rol == Usuario.Rol.PATIO and u.patio_id and not u.is_superuser:
            qs = qs.filter(patio_destino_id=u.patio_id)
        return qs

    def create(self, request, *args, **kwargs):
        entrada = self.get_serializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        compra = _ejecutar(
            request,
            "Solicitud de compra (API)",
            servicios.solicitar_compra,
            proveedor=d["proveedor"],
            patio_destino=d["patio_destino"],
            producto=d["producto"],
            cantidad=d["cantidad"],
            precio_unitario_clp=d["precio_unitario_clp"],
            observacion=d.get("observacion", ""),
        )
        return Response(self.get_serializer(compra).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def aprobar(self, request, pk=None):
        compra = self.get_object()
        entrada = AprobarCompraEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        compra = _ejecutar(
            request,
            f"Resolución compra {compra.numero} (API)",
            servicios.resolver_aprobacion_compra,
            compra_id=compra.pk,
            aprobar=d["aprobar"],
            observacion=d.get("observacion", ""),
        )
        return Response(self.get_serializer(compra).data)

    @action(detail=True, methods=["post"])
    def recepcionar(self, request, pk=None):
        compra = self.get_object()
        entrada = RecepcionarCompraEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        compra = _ejecutar(
            request,
            f"Recepción compra {compra.numero} (API)",
            servicios.recepcionar_compra,
            compra_id=compra.pk,
            cantidad_recibida=d["cantidad_recibida"],
            observacion=d.get("observacion", ""),
        )
        return Response(self.get_serializer(compra).data)


class PedidoVentaViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = PedidoVentaSerializer

    def get_permissions(self):
        permiso = {
            "create": "gestionar_ventas",
            "despachar": "despachar_venta",
        }.get(self.action, "ver_ventas")
        return [IsAuthenticated(), requiere(permiso)()]

    def get_queryset(self):
        qs = PedidoVenta.objects.select_related("cliente", "patio_despacho", "creado_por", "despachado_por")
        u = self.request.user
        if u.rol == Usuario.Rol.PATIO and u.patio_id and not u.is_superuser:
            qs = qs.filter(patio_despacho_id=u.patio_id)
        return qs

    def create(self, request, *args, **kwargs):
        entrada = self.get_serializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        paquetes_ids = [p.pk for p in d["paquetes"]]
        pedido = _ejecutar(
            request,
            "Pedido de venta (API)",
            servicios.crear_pedido_venta,
            cliente=d["cliente"],
            patio_despacho=d["patio_despacho"],
            paquetes_ids=paquetes_ids,
            precio_m3_clp=d.get("precio_m3_clp", 185000),
            observacion=d.get("observacion", ""),
        )
        return Response(self.get_serializer(pedido).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def despachar(self, request, pk=None):
        pedido = self.get_object()
        entrada = DespacharVentaEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        pedido = _ejecutar(
            request,
            f"Despacho comercial {pedido.numero} (API)",
            servicios.despachar_pedido_venta,
            pedido_id=pedido.pk,
            patente_camion=d["patente_camion"],
            conductor=d["conductor"],
            observacion=d.get("observacion", ""),
        )
        return Response(self.get_serializer(pedido).data)


class InventarioViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InventarioSerializer
    permission_classes = [IsAuthenticated, requiere("ver_inventario")]

    def get_queryset(self):
        saldos = Inventario.objects.select_related("patio", "producto")
        u = self.request.user
        if u.rol == Usuario.Rol.PATIO and u.patio_id and not u.is_superuser:
            return saldos.filter(patio_id=u.patio_id)
        patio = self.request.query_params.get("patio")
        return saldos.filter(patio_id=patio) if patio else saldos


class AuditoriaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RegistroAuditoriaSerializer
    permission_classes = [IsAuthenticated, requiere("ver_auditoria")]
    queryset = RegistroAuditoria.objects.all()


class FaenaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FaenaSerializer
    queryset = Faena.objects.filter(activa=True).select_related("proveedor")
    pagination_class = None


class PatioViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PatioSerializer
    queryset = Patio.objects.filter(activo=True)
    pagination_class = None


class UbicacionBodegaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UbicacionBodegaSerializer
    queryset = UbicacionBodega.objects.filter(activa=True).select_related("patio")
    pagination_class = None


class ProductoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductoSerializer
    queryset = Producto.objects.filter(activo=True)
    pagination_class = None


class ProveedorViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProveedorSerializer
    queryset = Proveedor.objects.filter(activo=True)
    pagination_class = None


class ClienteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ClienteSerializer
    queryset = Cliente.objects.filter(activo=True)
    pagination_class = None


@api_view(["GET"])
@permission_classes([IsAuthenticated, requiere("ver_dashboard")])
def dashboard(request):
    try:
        dias = int(request.query_params.get("dias", 14))
    except ValueError:
        dias = 14
    return Response(resumen_dashboard(dias if dias in (7, 14, 30) else 14))
