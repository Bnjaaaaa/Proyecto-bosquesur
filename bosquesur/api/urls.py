from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register("lotes-cosecha", views.LoteCosechaViewSet, basename="lote-cosecha")
router.register("guias", views.GuiaDespachoViewSet, basename="guia")
router.register("ordenes-produccion", views.OrdenProduccionViewSet, basename="orden")
router.register("paquetes", views.PaqueteViewSet, basename="paquete")
router.register("compras", views.OrdenCompraViewSet, basename="compra")
router.register("ventas", views.PedidoVentaViewSet, basename="venta")
router.register("inventario", views.InventarioViewSet, basename="inventario")
router.register("auditoria", views.AuditoriaViewSet, basename="auditoria")
router.register("faenas", views.FaenaViewSet, basename="faena")
router.register("patios", views.PatioViewSet, basename="patio")
router.register("ubicaciones", views.UbicacionBodegaViewSet, basename="ubicacion")
router.register("productos", views.ProductoViewSet, basename="producto")
router.register("proveedores", views.ProveedorViewSet, basename="proveedor")
router.register("clientes", views.ClienteViewSet, basename="cliente")

urlpatterns = [
    path("token/", views.LoginJWTView.as_view(), name="token_obtener"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refrescar"),
    path("yo/", views.yo, name="api_yo"),
    path("dashboard/", views.dashboard, name="api_dashboard"),
    path("", include(router.urls)),
]
