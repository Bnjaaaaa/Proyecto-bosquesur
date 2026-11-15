"""Pruebas integrales de aceptación y consistencia transaccional del prototipo ES3."""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from auditoria.models import RegistroAuditoria
from auditoria.servicios import verificar_cadena
from cuentas.models import Usuario
from maestros.models import Cliente, Faena, Patio, Producto, Proveedor, UbicacionBodega

from . import servicios
from .consultas import trazabilidad_paquete
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

D = Decimal


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.proveedor_forestal = Proveedor.objects.create(
            rut="76.111.222-3", razon_social="Forestal Origen SpA", tipo=Proveedor.Tipo.FORESTAL
        )
        cls.proveedor_insumos = Proveedor.objects.create(
            rut="77.222.333-4", razon_social="Química Biobío Ltda.", tipo=Proveedor.Tipo.INSUMOS
        )
        cls.faena = Faena.objects.create(
            nombre="Predio Test",
            codigo_predio="PRED-01",
            proveedor=cls.proveedor_forestal,
            contrato_vigente="CM-TEST-01",
        )
        cls.otra_faena = Faena.objects.create(nombre="Predio Otro")
        cls.patio = Patio.objects.create(nombre="Patio Central")
        cls.otro_patio = Patio.objects.create(nombre="Patio Norte")
        cls.ub_bodega = UbicacionBodega.objects.create(
            codigo="PC-BOD-01", nombre="Bodega 1", tipo=UbicacionBodega.Tipo.BODEGA, patio=cls.patio
        )
        cls.ub_camara = UbicacionBodega.objects.create(
            codigo="PC-CAM-01", nombre="Cámara Secado", tipo=UbicacionBodega.Tipo.PROCESO, patio=cls.patio
        )
        cls.ub_norte = UbicacionBodega.objects.create(
            codigo="PN-BOD-01", nombre="Bodega Norte", tipo=UbicacionBodega.Tipo.BODEGA, patio=cls.otro_patio
        )
        cls.rollizo = Producto.objects.create(codigo="ROL", nombre="Rollizo pino", tipo=Producto.Tipo.ROLLIZO)
        cls.aserrado = Producto.objects.create(codigo="ASE", nombre="Aserrado 2x4", tipo=Producto.Tipo.ASERRADO)
        cls.insumo = Producto.objects.create(
            codigo="INS-CCA", nombre="Preservante CCA", tipo=Producto.Tipo.INSUMO, unidad="L"
        )
        cls.cliente = Cliente.objects.create(rut="96.999.888-7", razon_social="Constructora Demo S.A.")

        crear = Usuario.objects.create_user
        cls.gerente = crear("gerente", password="Clave-Segura-1", rol=Usuario.Rol.GERENTE)
        cls.administrativo = crear("adm", password="Clave-Segura-1", rol=Usuario.Rol.ADMINISTRATIVO)
        cls.encargado = crear("faena", password="Clave-Segura-1", rol=Usuario.Rol.FAENA, faena=cls.faena)
        cls.operador = crear("patio", password="Clave-Segura-1", rol=Usuario.Rol.PATIO, patio=cls.patio)

    def emitir(self, volumen="30.000", patio=None, lote_cosecha=None):
        return servicios.emitir_guia(
            usuario=self.encargado,
            faena=self.faena,
            patio_destino=patio or self.patio,
            producto=self.rollizo,
            volumen_enviado=D(volumen),
            patente_camion="ABCD12",
            conductor="Juan Pérez",
            lote_cosecha=lote_cosecha,
        )

    def stock(self, producto, patio=None):
        inv = Inventario.objects.filter(patio=patio or self.patio, producto=producto).first()
        return inv.cantidad if inv else D("0")


class TrazabilidadTests(Base):
    """Criterio: toda entrada/salida queda asociada a su respaldo documental completo."""

    def test_emitir_guia_genera_numero_y_registro_de_auditoria(self):
        guia = self.emitir()
        self.assertEqual(guia.numero, f"GD-{guia.pk:06d}")
        self.assertEqual(guia.estado, GuiaDespacho.Estado.EMITIDA)
        self.assertTrue(RegistroAuditoria.objects.filter(accion="EMITIR_GUIA", entidad_id=guia.numero).exists())
        self.assertEqual(self.stock(self.rollizo), D("0"), "Emitir no debe mover stock: la madera va en tránsito")

    def test_recepcion_suma_inventario_y_calcula_discrepancia(self):
        guia = self.emitir("30.000")
        recepcion = servicios.recepcionar_guia(usuario=self.operador, guia_id=guia.pk, volumen_recibido=D("29.400"))
        self.assertEqual(recepcion.discrepancia, D("0.600"))
        self.assertEqual(recepcion.porcentaje_discrepancia, D("2.00"))
        self.assertFalse(recepcion.requiere_revision)
        self.assertEqual(self.stock(self.rollizo), D("29.400"))
        movimiento = MovimientoInventario.objects.get(guia=guia)
        self.assertEqual(movimiento.cantidad, D("29.400"))
        guia.refresh_from_db()
        self.assertEqual(guia.estado, GuiaDespacho.Estado.RECEPCIONADA)

    @override_settings(TOLERANCIA_DISCREPANCIA_PCT=3.0)
    def test_discrepancia_sobre_tolerancia_genera_alerta(self):
        guia = self.emitir("30.000")
        recepcion = servicios.recepcionar_guia(usuario=self.operador, guia_id=guia.pk, volumen_recibido=D("27.000"))
        self.assertTrue(recepcion.requiere_revision)
        self.assertTrue(RegistroAuditoria.objects.filter(accion="ALERTA_DISCREPANCIA", entidad_id=guia.numero).exists())

    def test_no_se_puede_recepcionar_dos_veces(self):
        guia = self.emitir()
        servicios.recepcionar_guia(usuario=self.operador, guia_id=guia.pk, volumen_recibido=D("30"))
        with self.assertRaises(servicios.ErrorNegocio):
            servicios.recepcionar_guia(usuario=self.operador, guia_id=guia.pk, volumen_recibido=D("30"))
        self.assertEqual(self.stock(self.rollizo), D("30"), "El stock no debe duplicarse")

    def test_operador_no_recepciona_guias_de_otro_patio(self):
        guia = self.emitir(patio=self.otro_patio)
        with self.assertRaises(servicios.ErrorNegocio):
            servicios.recepcionar_guia(usuario=self.operador, guia_id=guia.pk, volumen_recibido=D("30"))

    def test_encargado_no_emite_desde_otra_faena(self):
        with self.assertRaises(servicios.ErrorNegocio):
            servicios.emitir_guia(
                usuario=self.encargado,
                faena=self.otra_faena,
                patio_destino=self.patio,
                producto=self.rollizo,
                volumen_enviado=D("10"),
                patente_camion="ABCD12",
                conductor="X",
            )

    def test_bd_rechaza_movimiento_sin_documento_de_respaldo(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            MovimientoInventario.objects.create(
                tipo=MovimientoInventario.Tipo.ENTRADA_GUIA,
                patio=self.patio,
                producto=self.rollizo,
                cantidad=D("5"),
                saldo_resultante=D("5"),
                usuario=self.administrativo,
            )


class ConsistenciaTransaccionalTests(Base):
    """Criterio: las transacciones incompletas se revierten sin corromper la base de datos."""

    def test_produccion_descuenta_rollizo_y_suma_aserrado(self):
        guia = self.emitir("40")
        servicios.recepcionar_guia(usuario=self.operador, guia_id=guia.pk, volumen_recibido=D("40"))
        orden = servicios.registrar_produccion(
            usuario=self.operador,
            patio=self.patio,
            producto_entrada=self.rollizo,
            volumen_entrada=D("20"),
            producto_salida=self.aserrado,
            volumen_salida=D("10.5"),
        )
        self.assertEqual(orden.rendimiento, D("52.50"))
        self.assertEqual(self.stock(self.rollizo), D("20"))
        self.assertEqual(self.stock(self.aserrado), D("10.5"))
        self.assertEqual(orden.movimientos.count(), 2)

    def test_stock_insuficiente_revierte_toda_la_orden(self):
        guia = self.emitir("10")
        servicios.recepcionar_guia(usuario=self.operador, guia_id=guia.pk, volumen_recibido=D("10"))
        auditoria_antes = RegistroAuditoria.objects.count()
        with self.assertRaises(servicios.ErrorNegocio):
            servicios.registrar_produccion(
                usuario=self.operador,
                patio=self.patio,
                producto_entrada=self.rollizo,
                volumen_entrada=D("15"),
                producto_salida=self.aserrado,
                volumen_salida=D("7"),
            )
        self.assertEqual(OrdenProduccion.objects.count(), 0, "La orden no debe quedar guardada")
        self.assertEqual(self.stock(self.rollizo), D("10"))
        self.assertEqual(self.stock(self.aserrado), D("0"))
        self.assertEqual(RegistroAuditoria.objects.count(), auditoria_antes)

    def test_produccion_no_puede_superar_volumen_consumido(self):
        with self.assertRaises(servicios.ErrorNegocio):
            servicios.registrar_produccion(
                usuario=self.administrativo,
                patio=self.patio,
                producto_entrada=self.rollizo,
                volumen_entrada=D("5"),
                producto_salida=self.aserrado,
                volumen_salida=D("6"),
            )

    def test_bd_rechaza_inventario_negativo(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Inventario.objects.create(patio=self.patio, producto=self.rollizo, cantidad=D("-1"))

    def test_bitacora_queda_integra_despues_de_operar(self):
        guia = self.emitir()
        servicios.recepcionar_guia(usuario=self.operador, guia_id=guia.pk, volumen_recibido=D("29"))
        integra, total, _ = verificar_cadena()
        self.assertTrue(integra)
        self.assertGreaterEqual(total, 2)


class FlujosCompletosES3Tests(Base):
    """Pruebas de cosecha, paquetes QR, procesos posteriores, bodega, compras, ventas sin SII y trazabilidad."""

    def test_trazabilidad_completa_cosecha_qr_proceso_y_venta_sin_sii(self):
        lote = servicios.registrar_lote_cosecha(
            usuario=self.encargado,
            faena=self.faena,
            producto=self.rollizo,
            volumen_cosechado=D("80.000"),
            cuadrilla="Cuadrilla Sur",
        )
        self.assertTrue(lote.codigo.startswith("LC-"))

        guia = self.emitir("40.000", lote_cosecha=lote)
        servicios.recepcionar_guia(usuario=self.operador, guia_id=guia.pk, volumen_recibido=D("39.500"))
        orden = servicios.registrar_produccion(
            usuario=self.operador,
            patio=self.patio,
            producto_entrada=self.rollizo,
            volumen_entrada=D("20.000"),
            producto_salida=self.aserrado,
            volumen_salida=D("11.000"),
            guia_origen=guia,
        )

        # No permite empaquetar más volumen del producido en la orden
        with self.assertRaises(servicios.ErrorNegocio):
            servicios.crear_paquete(
                usuario=self.operador,
                orden_produccion=orden,
                ubicacion=self.ub_bodega,
                volumen_m3=D("12.000"),
            )

        paquete = servicios.crear_paquete(
            usuario=self.operador,
            orden_produccion=orden,
            ubicacion=self.ub_bodega,
            volumen_m3=D("5.000"),
            piezas=120,
            calidad=Paquete.Calidad.GRADO_B,
        )
        self.assertTrue(paquete.codigo_qr.startswith("BS-PKT-"))

        # Aplicar secado con merma 0.250 m³ y mover a cámara
        paquete = servicios.aplicar_proceso_paquete(
            usuario=self.operador,
            paquete_id=paquete.pk,
            proceso=Paquete.Proceso.SECADO,
            ubicacion_destino=self.ub_camara,
            calidad_resultante=Paquete.Calidad.GRADO_A,
            merma_m3=D("0.250"),
        )
        self.assertEqual(paquete.volumen_m3, D("4.750"))
        self.assertEqual(paquete.estado, Paquete.Estado.PROCESADO)
        self.assertEqual(paquete.calidad, Paquete.Calidad.GRADO_A)
        self.assertEqual(self.stock(self.aserrado), D("10.750"))

        # Transferir paquete a otro patio por movimiento entre bodegas y verificar stock cruzado
        paquete = servicios.mover_paquete(
            usuario=self.administrativo,
            paquete_id=paquete.pk,
            ubicacion_destino=self.ub_norte,
            observacion="Traslado a Bodega Norte",
        )
        self.assertEqual(self.stock(self.aserrado, self.patio), D("6.000"))
        self.assertEqual(self.stock(self.aserrado, self.otro_patio), D("4.750"))
        self.assertEqual(paquete.historial.count(), 3)

        # Devolver a patio central para despachar venta comercial
        paquete = servicios.mover_paquete(
            usuario=self.administrativo,
            paquete_id=paquete.pk,
            ubicacion_destino=self.ub_bodega,
        )
        pedido = servicios.crear_pedido_venta(
            usuario=self.administrativo,
            cliente=self.cliente,
            patio_despacho=self.patio,
            paquetes_ids=[paquete.pk],
            precio_m3_clp=200000,
        )
        self.assertEqual(pedido.estado, PedidoVenta.Estado.PREPARACION)
        self.assertEqual(pedido.monto_neto_clp, 950000)

        pedido = servicios.despachar_pedido_venta(
            usuario=self.operador,
            pedido_id=pedido.pk,
            patente_camion="HJKL23",
            conductor="Pedro Fuentealba",
        )
        self.assertEqual(pedido.estado, PedidoVenta.Estado.DESPACHADO)
        self.assertTrue(pedido.documento_interno.startswith("GDC-INT-"))
        self.assertEqual(self.stock(self.aserrado, self.patio), D("6.000"))
        paquete.refresh_from_db()
        self.assertEqual(paquete.estado, Paquete.Estado.DESPACHADO)
        self.assertEqual(HistorialPaquete.objects.filter(paquete=paquete).count(), 6)

        # Validar trazabilidad end-to-end
        traza = trazabilidad_paquete(paquete)
        self.assertTrue(traza["trazado_directo"])
        self.assertEqual(traza["proveedor"], self.proveedor_forestal)
        self.assertEqual(traza["lote"], lote)
        self.assertEqual(traza["guia"], guia)
        self.assertEqual(traza["orden"], orden)
        self.assertEqual(traza["pedido"], pedido)

        integra, _, _ = verificar_cadena()
        self.assertTrue(integra)

        # Renderización de vistas de detalle y documento simulado sin SII
        self.client.force_login(self.gerente)
        self.assertEqual(self.client.get(reverse("paquete_detalle", args=[paquete.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("venta_detalle", args=[pedido.pk])).status_code, 200)
        doc_resp = self.client.get(reverse("venta_documento", args=[pedido.pk]))
        self.assertEqual(doc_resp.status_code, 200)
        self.assertContains(doc_resp, "NO VÁLIDO COMO DTE")
        for ruta in ["compra_nueva", "venta_nueva"]:
            self.assertEqual(self.client.get(reverse(ruta)).status_code, 200, ruta)
        self.client.force_login(self.administrativo)
        for ruta in ["cosecha_nueva", "paquete_nuevo"]:
            self.assertEqual(self.client.get(reverse(ruta)).status_code, 200, ruta)

    def test_flujo_compras_externas_y_control_aprobacion_gerencial(self):
        compra = servicios.solicitar_compra(
            usuario=self.operador,
            proveedor=self.proveedor_insumos,
            patio_destino=self.patio,
            producto=self.insumo,
            cantidad=D("100.000"),
            precio_unitario_clp=4500,
        )
        self.assertEqual(compra.estado, OrdenCompra.Estado.SOLICITADA)
        self.assertEqual(compra.monto_total_clp, 450000)

        # No puede recepcionarse sin aprobación previa
        with self.assertRaises(servicios.ErrorNegocio):
            servicios.recepcionar_compra(
                usuario=self.operador, compra_id=compra.pk, cantidad_recibida=D("100.000")
            )

        # Operador de patio no puede aprobar
        with self.assertRaises(servicios.ErrorNegocio):
            servicios.resolver_aprobacion_compra(usuario=self.operador, compra_id=compra.pk, aprobar=True)

        compra = servicios.resolver_aprobacion_compra(usuario=self.gerente, compra_id=compra.pk, aprobar=True)
        self.assertEqual(compra.estado, OrdenCompra.Estado.APROBADA)

        compra = servicios.recepcionar_compra(
            usuario=self.operador, compra_id=compra.pk, cantidad_recibida=D("98.500")
        )
        self.assertEqual(compra.estado, OrdenCompra.Estado.RECEPCIONADA)
        self.assertEqual(self.stock(self.insumo), D("98.500"))

    def test_paquete_reservado_no_puede_moverse_a_otro_patio_pero_si_en_el_mismo(self):
        guia = self.emitir("20.000")
        servicios.recepcionar_guia(usuario=self.operador, guia_id=guia.pk, volumen_recibido=D("20.000"))
        orden = servicios.registrar_produccion(
            usuario=self.operador,
            patio=self.patio,
            producto_entrada=self.rollizo,
            volumen_entrada=D("10.000"),
            producto_salida=self.aserrado,
            volumen_salida=D("5.000"),
        )
        paquete = servicios.crear_paquete(
            usuario=self.operador,
            orden_produccion=orden,
            ubicacion=self.ub_bodega,
            volumen_m3=D("5.000"),
        )
        pedido = servicios.crear_pedido_venta(
            usuario=self.administrativo,
            cliente=self.cliente,
            patio_despacho=self.patio,
            paquetes_ids=[paquete.pk],
        )

        # No puede trasladarse a otro patio mientras está reservado
        with self.assertRaises(servicios.ErrorNegocio):
            servicios.mover_paquete(
                usuario=self.administrativo,
                paquete_id=paquete.pk,
                ubicacion_destino=self.ub_norte,
            )
        paquete.refresh_from_db()
        self.assertEqual(paquete.ubicacion_id, self.ub_bodega.pk)

        # Sí puede moverse dentro del mismo patio (por ejemplo a zona de despacho/cámara)
        servicios.mover_paquete(
            usuario=self.operador,
            paquete_id=paquete.pk,
            ubicacion_destino=self.ub_camara,
        )
        paquete.refresh_from_db()
        self.assertEqual(paquete.ubicacion_id, self.ub_camara.pk)

        # Defensa adicional en despacho: si un paquete estuviera en otro patio, el despacho falla sin descontar stock
        Paquete.objects.filter(pk=paquete.pk).update(ubicacion=self.ub_norte)
        with self.assertRaises(servicios.ErrorNegocio):
            servicios.despachar_pedido_venta(
                usuario=self.administrativo,
                pedido_id=pedido.pk,
                patente_camion="ABCD12",
                conductor="Pedro",
            )
        self.assertEqual(self.stock(self.aserrado, self.patio), D("5.000"))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidoVenta.Estado.PREPARACION)

    def test_recepcion_compra_rechaza_exceso_y_registra_diferencia_parcial(self):
        compra = servicios.solicitar_compra(
            usuario=self.operador,
            proveedor=self.proveedor_insumos,
            patio_destino=self.patio,
            producto=self.insumo,
            cantidad=D("10.000"),
            precio_unitario_clp=2000,
        )
        servicios.resolver_aprobacion_compra(usuario=self.gerente, compra_id=compra.pk, aprobar=True)

        with self.assertRaises(servicios.ErrorNegocio):
            servicios.recepcionar_compra(
                usuario=self.operador, compra_id=compra.pk, cantidad_recibida=D("12.000")
            )
        compra.refresh_from_db()
        self.assertEqual(compra.estado, OrdenCompra.Estado.APROBADA)
        self.assertEqual(self.stock(self.insumo), D("0"))

        compra = servicios.recepcionar_compra(
            usuario=self.operador, compra_id=compra.pk, cantidad_recibida=D("8.250")
        )
        self.assertEqual(compra.estado, OrdenCompra.Estado.RECEPCIONADA)
        self.assertEqual(self.stock(self.insumo), D("8.250"))
        reg = RegistroAuditoria.objects.filter(
            accion="RECEPCIONAR_COMPRA", entidad_id=compra.numero
        ).latest("id")
        self.assertEqual(reg.datos.get("diferencia"), "1.750")


class SeguridadWebTests(Base):
    """Criterio: RBAC restringe vistas administrativas frente a operativas y expone vistas ES3."""

    def test_requiere_iniciar_sesion(self):
        respuesta = self.client.get(reverse("dashboard"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login"), respuesta["Location"])

    def test_operador_de_patio_no_ve_dashboard_y_queda_registrado(self):
        self.client.force_login(self.operador)
        respuesta = self.client.get(reverse("dashboard"))
        self.assertEqual(respuesta.status_code, 403)
        self.assertTrue(RegistroAuditoria.objects.filter(accion="ACCESO_DENEGADO", usuario=self.operador).exists())

    def test_solo_gerente_ve_bitacora(self):
        self.client.force_login(self.administrativo)
        self.assertEqual(self.client.get(reverse("bitacora")).status_code, 403)
        self.client.force_login(self.gerente)
        self.assertEqual(self.client.get(reverse("bitacora")).status_code, 200)

    def test_flujo_web_completo_y_vistas_es3(self):
        self.client.force_login(self.encargado)
        respuesta = self.client.post(
            reverse("guia_nueva"),
            {
                "faena": self.faena.pk,
                "patio_destino": self.patio.pk,
                "producto": self.rollizo.pk,
                "volumen_enviado": "31.5",
                "patente_camion": "hj-kl 23",
                "conductor": "Pedro",
            },
        )
        guia = GuiaDespacho.objects.get()
        self.assertRedirects(respuesta, reverse("guia_detalle", args=[guia.pk]))
        self.assertEqual(guia.patente_camion, "HJKL23")

        self.client.force_login(self.operador)
        self.assertContains(self.client.get(reverse("recepciones_pendientes")), guia.numero)
        respuesta = self.client.post(reverse("recepcionar", args=[guia.pk]), {"volumen_recibido": "31.0"})
        self.assertRedirects(respuesta, reverse("recepciones_pendientes"))
        self.assertEqual(Recepcion.objects.get().volumen_recibido, D("31.000"))

        self.client.force_login(self.gerente)
        for nombre in [
            "dashboard",
            "cosecha_lista",
            "guias_lista",
            "inventario",
            "produccion_lista",
            "paquetes_lista",
            "compras_lista",
            "ventas_lista",
            "reportes",
            "bitacora",
            "app_movil",
        ]:
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200, nombre)
        self.assertEqual(self.client.get(reverse("guia_detalle", args=[guia.pk])).status_code, 200)
        csv_resp = self.client.get(reverse("reportes_csv"))
        self.assertEqual(csv_resp.status_code, 200)
        self.assertIn("text/csv", csv_resp["Content-Type"])

    def test_patente_invalida_es_rechazada(self):
        self.client.force_login(self.encargado)
        respuesta = self.client.post(
            reverse("guia_nueva"),
            {
                "faena": self.faena.pk,
                "patio_destino": self.patio.pk,
                "producto": self.rollizo.pk,
                "volumen_enviado": "10",
                "patente_camion": "123",
                "conductor": "Pedro",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(GuiaDespacho.objects.exists())

    def test_encargado_solo_ve_guias_de_su_faena(self):
        servicios.emitir_guia(
            usuario=self.administrativo,
            faena=self.otra_faena,
            patio_destino=self.patio,
            producto=self.rollizo,
            volumen_enviado=D("10"),
            patente_camion="ABCD12",
            conductor="X",
        )
        propia = self.emitir()
        self.client.force_login(self.encargado)
        respuesta = self.client.get(reverse("guias_lista"))
        self.assertEqual(list(respuesta.context["pagina"]), [propia])
