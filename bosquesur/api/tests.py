"""Pruebas de la API REST completa protegida con autenticación JWT."""
from decimal import Decimal

from rest_framework.test import APITestCase

from cuentas.models import Usuario
from maestros.models import Cliente, Faena, Patio, Producto, Proveedor, UbicacionBodega
from operaciones.models import Inventario, Paquete


class ApiJwtTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.proveedor = Proveedor.objects.create(
            rut="76.000.111-2", razon_social="Forestal Proveedora SpA", tipo=Proveedor.Tipo.FORESTAL
        )
        cls.faena = Faena.objects.create(nombre="Predio API", codigo_predio="API-01", proveedor=cls.proveedor)
        cls.patio = Patio.objects.create(nombre="Patio API")
        cls.ub1 = UbicacionBodega.objects.create(
            codigo="API-BOD-1", nombre="Bodega 1", tipo=UbicacionBodega.Tipo.BODEGA, patio=cls.patio
        )
        cls.ub2 = UbicacionBodega.objects.create(
            codigo="API-CAM-1", nombre="Cámara Secado", tipo=UbicacionBodega.Tipo.PROCESO, patio=cls.patio
        )
        cls.rollizo = Producto.objects.create(codigo="R1", nombre="Rollizo", tipo=Producto.Tipo.ROLLIZO)
        cls.aserrado = Producto.objects.create(codigo="A1", nombre="Aserrado 2x4", tipo=Producto.Tipo.ASERRADO)
        cls.insumo = Producto.objects.create(codigo="I1", nombre="Sellador", tipo=Producto.Tipo.INSUMO, unidad="L")
        cls.cliente = Cliente.objects.create(rut="99.111.222-3", razon_social="Cliente API S.A.")

        crear = Usuario.objects.create_user
        crear("faena", password="Clave-Segura-1", rol=Usuario.Rol.FAENA, faena=cls.faena)
        crear("patio", password="Clave-Segura-1", rol=Usuario.Rol.PATIO, patio=cls.patio)
        crear("administrativo", password="Clave-Segura-1", rol=Usuario.Rol.ADMINISTRATIVO)
        crear("gerente", password="Clave-Segura-1", rol=Usuario.Rol.GERENTE)

    def login(self, usuario):
        respuesta = self.client.post("/api/token/", {"username": usuario, "password": "Clave-Segura-1"}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.data["usuario"]["username"], usuario)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {respuesta.data['access']}")

    def test_sin_token_responde_401(self):
        self.assertEqual(self.client.get("/api/guias/").status_code, 401)
        self.assertEqual(self.client.get("/api/paquetes/").status_code, 401)

    def test_credenciales_invalidas(self):
        respuesta = self.client.post("/api/token/", {"username": "faena", "password": "mala"}, format="json")
        self.assertEqual(respuesta.status_code, 401)

    def test_flujo_movil_completo_cosecha_guia_recepcion_qr_y_trazabilidad(self):
        # 1. Encargado de faena registra cosecha y emite guía asociada
        self.login("faena")
        r_lote = self.client.post(
            "/api/lotes-cosecha/",
            {
                "faena": self.faena.pk,
                "producto": self.rollizo.pk,
                "volumen_cosechado": "50.000",
                "cuadrilla": "Cuadrilla API",
            },
            format="json",
        )
        self.assertEqual(r_lote.status_code, 201, r_lote.content)
        lote_id = r_lote.data["id"]

        r_guia = self.client.post(
            "/api/guias/",
            {
                "faena": self.faena.pk,
                "lote_cosecha": lote_id,
                "patio_destino": self.patio.pk,
                "producto": self.rollizo.pk,
                "volumen_enviado": "28.75",
                "patente_camion": "GTRS45",
                "conductor": "Luis",
            },
            format="json",
        )
        self.assertEqual(r_guia.status_code, 201, r_guia.content)
        guia_id = r_guia.data["id"]
        self.assertTrue(r_guia.data["numero"].startswith("GD-"))

        # El encargado de faena no puede recepcionar.
        self.assertEqual(
            self.client.post(f"/api/guias/{guia_id}/recepcionar/", {"volumen_recibido": "28"}, format="json").status_code,
            403,
        )

        # 2. Operador de patio recepciona guía, produce aserrado, crea paquete QR y procesa
        self.login("patio")
        r_rec = self.client.post(f"/api/guias/{guia_id}/recepcionar/", {"volumen_recibido": "28.5"}, format="json")
        self.assertEqual(r_rec.status_code, 201, r_rec.content)
        self.assertEqual(r_rec.data["estado"], "RECEPCIONADA")
        self.assertEqual(Inventario.objects.get(producto=self.rollizo).cantidad, Decimal("28.500"))

        # Segunda recepción: error de negocio -> 400
        self.assertEqual(
            self.client.post(f"/api/guias/{guia_id}/recepcionar/", {"volumen_recibido": "28.5"}, format="json").status_code,
            400,
        )

        r_orden = self.client.post(
            "/api/ordenes-produccion/",
            {
                "patio": self.patio.pk,
                "guia_origen": guia_id,
                "producto_entrada": self.rollizo.pk,
                "volumen_entrada": "20.000",
                "producto_salida": self.aserrado.pk,
                "volumen_salida": "11.000",
            },
            format="json",
        )
        self.assertEqual(r_orden.status_code, 201, r_orden.content)
        orden_id = r_orden.data["id"]

        r_pkt = self.client.post(
            "/api/paquetes/",
            {
                "orden_produccion": orden_id,
                "ubicacion": self.ub1.pk,
                "volumen_m3": "5.500",
                "piezas": 110,
                "calidad": Paquete.Calidad.GRADO_A,
            },
            format="json",
        )
        self.assertEqual(r_pkt.status_code, 201, r_pkt.content)
        pkt_id = r_pkt.data["id"]
        qr = r_pkt.data["codigo_qr"]

        # Consulta por filtro QR desde lector móvil
        r_busca = self.client.get(f"/api/paquetes/?codigo_qr={qr}")
        self.assertEqual(r_busca.status_code, 200)
        lista = r_busca.data["results"] if isinstance(r_busca.data, dict) else r_busca.data
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["codigo_qr"], qr)

        # Aplicar proceso posterior (secado con merma) y verificar trazabilidad completa
        r_proc = self.client.post(
            f"/api/paquetes/{pkt_id}/procesar/",
            {"proceso": "SECADO", "ubicacion_destino": self.ub2.pk, "merma_m3": "0.100"},
            format="json",
        )
        self.assertEqual(r_proc.status_code, 200, r_proc.content)
        self.assertEqual(r_proc.data["proceso_actual"], "SECADO")

        r_traza = self.client.get(f"/api/paquetes/{pkt_id}/trazabilidad/")
        self.assertEqual(r_traza.status_code, 200)
        self.assertTrue(r_traza.data["trazado_directo"])
        self.assertEqual(r_traza.data["faena"]["nombre"], "Predio API")
        self.assertEqual(r_traza.data["lote"]["codigo"], r_lote.data["codigo"])

        # 3. Administrativo crea pedido de venta reservando el paquete -> Patio despacha
        self.login("administrativo")
        r_vta = self.client.post(
            "/api/ventas/",
            {
                "cliente": self.cliente.pk,
                "patio_despacho": self.patio.pk,
                "paquetes": [pkt_id],
                "precio_m3_clp": 200000,
            },
            format="json",
        )
        self.assertEqual(r_vta.status_code, 201, r_vta.content)
        vta_id = r_vta.data["id"]

        self.login("patio")
        r_desp = self.client.post(
            f"/api/ventas/{vta_id}/despachar/",
            {"patente_camion": "HJKL23", "conductor": "Pedro"},
            format="json",
        )
        self.assertEqual(r_desp.status_code, 200, r_desp.content)
        self.assertEqual(r_desp.data["estado"], "DESPACHADO")
        self.assertTrue(r_desp.data["documento_interno"].startswith("GDC-INT-"))

    def test_api_compras_y_ventas(self):
        # Operador de patio no puede solicitar compra ni aprobarla
        self.login("patio")
        payload_compra = {
            "proveedor": self.proveedor.pk,
            "patio_destino": self.patio.pk,
            "producto": self.insumo.pk,
            "cantidad": "40.000",
            "precio_unitario_clp": 5000,
        }
        self.assertEqual(self.client.post("/api/compras/", payload_compra, format="json").status_code, 403)

        # Administrativo solicita compra -> Gerente aprueba -> Patio recepciona
        self.login("administrativo")
        r_comp = self.client.post("/api/compras/", payload_compra, format="json")
        self.assertEqual(r_comp.status_code, 201, r_comp.content)
        comp_id = r_comp.data["id"]

        self.login("patio")
        self.assertEqual(self.client.post(f"/api/compras/{comp_id}/aprobar/", {"aprobar": True}, format="json").status_code, 403)

        self.login("gerente")
        r_apr = self.client.post(f"/api/compras/{comp_id}/aprobar/", {"aprobar": True}, format="json")
        self.assertEqual(r_apr.status_code, 200)
        self.assertEqual(r_apr.data["estado"], "APROBADA")

        self.login("patio")
        r_rec = self.client.post(f"/api/compras/{comp_id}/recepcionar/", {"cantidad_recibida": "40.000"}, format="json")
        self.assertEqual(r_rec.status_code, 200)
        self.assertEqual(r_rec.data["estado"], "RECEPCIONADA")

    def test_dashboard_y_auditoria_solo_para_gerente(self):
        self.login("patio")
        self.assertEqual(self.client.get("/api/dashboard/").status_code, 403)
        self.assertEqual(self.client.get("/api/auditoria/").status_code, 403)
        self.login("gerente")
        respuesta = self.client.get("/api/dashboard/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("kpis", respuesta.data)
        self.assertIn("paquetes_activos", respuesta.data["kpis"])
        self.assertEqual(self.client.get("/api/auditoria/").status_code, 200)
