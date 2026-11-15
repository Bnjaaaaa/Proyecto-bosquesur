"""
Carga datos de demostración realistas para presentar el prototipo completo ES3.

    python manage.py cargar_demo

Crea proveedores, faenas con predios/contratos, patios, ubicaciones de bodega,
productos (rollizos, aserrados, insumos), clientes, usuarios por rol y ~3 semanas
de operación completa trazable (lotes de cosecha, guías, recepciones, producción,
paquetes QR, procesos posteriores, compras externas y ventas comerciales con
documento interno simulado sin SII).
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from cuentas.models import Usuario
from maestros.models import Cliente, Faena, Patio, Producto, Proveedor, UbicacionBodega
from operaciones import servicios
from operaciones.models import (
    GuiaDespacho,
    LoteCosecha,
    MovimientoInventario,
    OrdenCompra,
    OrdenProduccion,
    Paquete,
    PedidoVenta,
    Recepcion,
)

CLAVE_DEMO = "Bosque2026!"

PROVEEDORES = [
    ("76.120.450-3", "Forestal Río Claro SpA", Proveedor.Tipo.FORESTAL, "gerencia@rioclaroforestal.cl"),
    ("77.340.810-9", "Agrícola y Maderera Los Robles Ltda.", Proveedor.Tipo.FORESTAL, "abastecimiento@losrobles.cl"),
    ("96.880.120-5", "Química Industrial Biobío S.A.", Proveedor.Tipo.INSUMOS, "ventas@quibiobio.cl"),
    ("78.510.220-1", "Ferretería y Repuestos Industriales Sur", Proveedor.Tipo.INSUMOS, "contacto@repuestossur.cl"),
]

FAENAS = [
    ("Predio Los Coigües", "Comuna de Mulchén, Biobío", "ROL-MUL-104", 0, "CM-CONAF-2026-01", "Pino Radiata"),
    ("Predio El Manzano", "Comuna de Nacimiento, Biobío", "ROL-NAC-218", 0, "CM-CONAF-2026-02", "Pino Radiata"),
    ("Fundo Santa Elena", "Comuna de Collipulli, Araucanía", "ROL-COL-309", 1, "CONV-TERC-2026-08", "Eucalipto Nitens"),
]

PATIOS = [
    ("Patio Central Aserradero", "Planta Los Ángeles"),
    ("Patio Norte", "Planta Los Ángeles, sector norte"),
]

UBICACIONES = [
    ("PC-ACOP-01", "Cancha de Acopio Rollizo 1", UbicacionBodega.Tipo.ACOPIO, 0),
    ("PC-CAM-01", "Cámara de Secado Térmico 1", UbicacionBodega.Tipo.PROCESO, 0),
    ("PC-IMP-01", "Planta de Impregnado CCA", UbicacionBodega.Tipo.PROCESO, 0),
    ("PC-BOD-01", "Bodega Producto Terminado A", UbicacionBodega.Tipo.BODEGA, 0),
    ("PC-DESP-01", "Andén Pre-Despacho Central", UbicacionBodega.Tipo.DESPACHO, 0),
    ("PN-BOD-01", "Bodega Patio Norte", UbicacionBodega.Tipo.BODEGA, 1),
]

PRODUCTOS = [
    ("ROL-PR-24", "Rollizo pino radiata 2,44 m", Producto.Tipo.ROLLIZO, "m³"),
    ("ROL-PR-32", "Rollizo pino radiata 3,20 m", Producto.Tipo.ROLLIZO, "m³"),
    ("ROL-EU-24", "Rollizo eucalipto 2,44 m", Producto.Tipo.ROLLIZO, "m³"),
    ("ASE-2X4", "Madera aserrada 2x4\" pino", Producto.Tipo.ASERRADO, "m³"),
    ("ASE-1X6", "Tabla 1x6\" pino cepillada", Producto.Tipo.ASERRADO, "m³"),
    ("ASE-2X6", "Madera aserrada 2x6\" pino", Producto.Tipo.ASERRADO, "m³"),
    ("INS-CCA", "Preservante CCA Osmose (L)", Producto.Tipo.INSUMO, "L"),
    ("INS-SIE", "Hoja sierra cinta bi-metal 14\"", Producto.Tipo.INSUMO, "u"),
]

CLIENTES = [
    ("96.550.210-4", "Constructora del Sur S.A.", "Construcción Habitacional", "Av. Alemania 1240, Los Ángeles", "compras@constructorasur.cl"),
    ("76.912.330-8", "Comercializadora Maderera Maule Ltda.", "Distribución de Materiales", "Panamericana Sur Km 255, Talca", "logistica@maderamaule.cl"),
    ("77.105.640-2", "Barraca Los Ángeles SpA", "Comercio Minorista de Madera", "Camino a Antuco Km 3, Los Ángeles", "pedidos@barracalosangeles.cl"),
]

CONDUCTORES = ["Juan Sepúlveda", "Pedro Fuentealba", "Luis Riquelme", "Marco Carrasco", "Rodrigo Muñoz"]
PATENTES = ["HJKL23", "GTRS45", "FKPB12", "KLMN67", "BCDF89", "PZ4512"]


class Command(BaseCommand):
    help = "Carga datos de demostración completos ES3 (maestros, usuarios y operaciones trazables)."

    def add_arguments(self, parser):
        parser.add_argument("--sin-operaciones", action="store_true", help="Solo maestros y usuarios.")

    def handle(self, *args, **options):
        random.seed(2026)

        proveedores = [
            Proveedor.objects.get_or_create(
                rut=rut, defaults={"razon_social": rs, "tipo": tipo, "contacto": cont}
            )[0]
            for rut, rs, tipo, cont in PROVEEDORES
        ]

        faenas = []
        for nombre, ubicacion, cod_predio, idx_prov, contrato, especie in FAENAS:
            faena, creado = Faena.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "ubicacion": ubicacion,
                    "codigo_predio": cod_predio,
                    "proveedor": proveedores[idx_prov],
                    "contrato_vigente": contrato,
                    "especie": especie,
                },
            )
            if not creado and faena.proveedor is None:
                faena.codigo_predio = cod_predio
                faena.proveedor = proveedores[idx_prov]
                faena.contrato_vigente = contrato
                faena.especie = especie
                faena.save()
            faenas.append(faena)

        patios = [Patio.objects.get_or_create(nombre=n, defaults={"ubicacion": u})[0] for n, u in PATIOS]

        ubicaciones = []
        for codigo, nombre, tipo, idx_patio in UBICACIONES:
            ub, _ = UbicacionBodega.objects.get_or_create(
                codigo=codigo,
                defaults={"nombre": nombre, "tipo": tipo, "patio": patios[idx_patio]},
            )
            ubicaciones.append(ub)

        for codigo, nombre, tipo, unidad in PRODUCTOS:
            Producto.objects.get_or_create(
                codigo=codigo, defaults={"nombre": nombre, "tipo": tipo, "unidad": unidad}
            )

        clientes = [
            Cliente.objects.get_or_create(
                rut=rut, defaults={"razon_social": rs, "giro": giro, "direccion": dir_, "contacto": cont}
            )[0]
            for rut, rs, giro, dir_, cont in CLIENTES
        ]

        usuarios = {
            "admin": dict(
                first_name="Administrador",
                last_name="Sistema",
                rol=Usuario.Rol.GERENTE,
                is_staff=True,
                is_superuser=True,
            ),
            "gerente": dict(first_name="Carolina", last_name="Vergara", rol=Usuario.Rol.GERENTE),
            "administrativo": dict(
                first_name="Andrés", last_name="Toledo", rol=Usuario.Rol.ADMINISTRATIVO, is_staff=True
            ),
            "faena": dict(first_name="Héctor", last_name="Inostroza", rol=Usuario.Rol.FAENA, faena=faenas[0]),
            "faena2": dict(first_name="Ximena", last_name="Paredes", rol=Usuario.Rol.FAENA, faena=faenas[1]),
            "patio": dict(first_name="Daniel", last_name="Saavedra", rol=Usuario.Rol.PATIO, patio=patios[0]),
        }
        for username, datos in usuarios.items():
            usuario, creado = Usuario.objects.get_or_create(username=username, defaults=datos)
            if creado:
                usuario.set_password(CLAVE_DEMO)
                usuario.save()
        self._permisos_admin_maestros()

        self.stdout.write(self.style.SUCCESS("Maestros y usuarios ES3 listos."))
        if options["sin_operaciones"]:
            return
        if GuiaDespacho.objects.exists():
            self.stdout.write("Ya existen operaciones; no se generan nuevas.")
            return
        self._generar_operaciones(faenas, patios, ubicaciones, proveedores, clientes)

    def _permisos_admin_maestros(self):
        """El administrativo puede mantener los datos maestros desde /admin/."""
        from django.contrib.auth.models import Permission

        admin = Usuario.objects.get(username="administrativo")
        permisos = Permission.objects.filter(
            content_type__app_label="maestros", codename__regex=r"^(add|change|view)_"
        )
        admin.user_permissions.add(*permisos)

    @transaction.atomic
    def _generar_operaciones(self, faenas, patios, ubicaciones, proveedores, clientes):
        rollizos = list(Producto.objects.filter(tipo=Producto.Tipo.ROLLIZO))
        aserrados = list(Producto.objects.filter(tipo=Producto.Tipo.ASERRADO))
        insumos = list(Producto.objects.filter(tipo=Producto.Tipo.INSUMO))
        encargados = {u.faena_id: u for u in Usuario.objects.filter(rol=Usuario.Rol.FAENA)}
        operador = Usuario.objects.get(username="patio")
        administrativo = Usuario.objects.get(username="administrativo")
        gerente = Usuario.objects.get(username="gerente")

        ahora = timezone.now()
        guias_count = 0
        recepcionadas_patio_central = []
        paquetes_patio_central = []

        # Ubicaciones de patio central: [1]=Camara Secado, [2]=Planta Impregnado, [3]=Bodega A, [4]=Pre-Despacho
        ub_camara, ub_impreg, ub_bodega, ub_despacho = ubicaciones[1], ubicaciones[2], ubicaciones[3], ubicaciones[4]

        for dias_atras in range(18, -1, -1):
            base = ahora - timedelta(days=dias_atras)
            faena_lote = random.choice(faenas)
            encargado_lote = encargados.get(faena_lote.pk, administrativo)
            lote_hoy = servicios.registrar_lote_cosecha(
                usuario=encargado_lote,
                faena=faena_lote,
                producto=rollizos[0],
                volumen_cosechado=Decimal(random.randint(90000, 140000)) / 1000,
                cuadrilla=f"Cuadrilla {faena_lote.codigo_predio}",
                observacion="Cosecha planificada Plan de Manejo",
            )
            self._fechar(LoteCosecha, lote_hoy.pk, "fecha_cosecha", base - timedelta(hours=10))

            for idx_g in range(4 if dias_atras == 0 else random.randint(2, 3)):
                faena = faena_lote if idx_g == 0 else random.choice(faenas)
                emisor = encargados.get(faena.pk, administrativo)
                patio = patios[0] if random.random() < 0.78 else patios[1]
                prod = rollizos[0] if idx_g == 0 else random.choice(rollizos)
                enviado = Decimal(random.randint(25000, 35000)) / 1000
                guia = servicios.emitir_guia(
                    usuario=emisor,
                    faena=faena,
                    patio_destino=patio,
                    producto=prod,
                    volumen_enviado=enviado,
                    patente_camion=random.choice(PATENTES),
                    conductor=random.choice(CONDUCTORES),
                    lote_cosecha=lote_hoy if faena == faena_lote else None,
                )
                guias_count += 1
                self._fechar(GuiaDespacho, guia.pk, "fecha_emision", base - timedelta(hours=random.randint(4, 9)))

                if dias_atras == 0:
                    continue
                merma = random.choice([0.005, 0.010, 0.014, 0.020, 0.048])
                if faena == faenas[2]:
                    merma += 0.018
                recibido = (enviado * Decimal(str(1 - merma))).quantize(Decimal("0.001"))
                receptor = operador if patio == patios[0] else administrativo
                recepcion = servicios.recepcionar_guia(
                    usuario=receptor,
                    guia_id=guia.pk,
                    volumen_recibido=recibido,
                    observacion="Carga con rollizos quebrados" if merma > 0.04 else "",
                )
                fecha_rec = base - timedelta(hours=random.randint(0, 3))
                self._fechar(Recepcion, recepcion.pk, "fecha", fecha_rec)
                MovimientoInventario.objects.filter(guia=guia).update(fecha=fecha_rec)
                if patio == patios[0]:
                    recepcionadas_patio_central.append(guia)

            if dias_atras % 2 == 0 and dias_atras > 0 and recepcionadas_patio_central:
                guia_orig = recepcionadas_patio_central[-1]
                entrada = Decimal("22.000")
                rend = Decimal("0.55")
                salida = (entrada * rend).quantize(Decimal("0.001"))
                prod_sal = random.choice(aserrados)
                try:
                    orden = servicios.registrar_produccion(
                        usuario=operador,
                        patio=patios[0],
                        producto_entrada=guia_orig.producto,
                        volumen_entrada=entrada,
                        producto_salida=prod_sal,
                        volumen_salida=salida,
                        guia_origen=guia_orig,
                        observacion=f"Aserrío trazado a {guia_orig.numero}",
                    )
                except servicios.ErrorNegocio:
                    continue
                self._fechar(OrdenProduccion, orden.pk, "fecha", base)
                MovimientoInventario.objects.filter(orden=orden).update(fecha=base)

                # Crear 2 paquetes QR por orden para contar con paquetes trazables
                vol_pkt = (salida * Decimal("0.45")).quantize(Decimal("0.001"))
                for sub_idx in range(2):
                    pkt = servicios.crear_paquete(
                        usuario=operador,
                        orden_produccion=orden,
                        ubicacion=ub_bodega,
                        volumen_m3=vol_pkt,
                        piezas=140,
                        calidad=Paquete.Calidad.GRADO_A if sub_idx == 0 else Paquete.Calidad.GRADO_B,
                        observacion=f"Lote empaquetado de {orden.numero}",
                    )
                    if sub_idx == 0:
                        proc = Paquete.Proceso.SECADO if len(paquetes_patio_central) % 2 == 0 else Paquete.Proceso.IMPREGNADO
                        ub_proc = ub_camara if proc == Paquete.Proceso.SECADO else ub_impreg
                        servicios.aplicar_proceso_paquete(
                            usuario=operador,
                            paquete_id=pkt.pk,
                            proceso=proc,
                            ubicacion_destino=ub_proc,
                            merma_m3=Decimal("0.120"),
                            observacion="Tratamiento industrial de calidad",
                        )
                        servicios.mover_paquete(
                            usuario=operador,
                            paquete_id=pkt.pk,
                            ubicacion_destino=ub_despacho,
                            observacion="Listo en andén pre-despacho",
                        )
                        pkt.refresh_from_db()
                    paquetes_patio_central.append(pkt)

        # Compras externas (en todos sus estados)
        oc1 = servicios.solicitar_compra(
            usuario=operador,
            proveedor=proveedores[2],
            patio_destino=patios[0],
            producto=insumos[0],
            cantidad=Decimal("500.000"),
            precio_unitario_clp=4800,
            observacion="Reposición trimestral sales impregnación",
        )
        servicios.resolver_aprobacion_compra(
            usuario=gerente, compra_id=oc1.pk, aprobar=True, observacion="Autorizado Gerencia"
        )
        servicios.recepcionar_compra(
            usuario=operador,
            compra_id=oc1.pk,
            cantidad_recibida=Decimal("500.000"),
            observacion="Tambores sellados conformes",
        )

        oc2 = servicios.solicitar_compra(
            usuario=administrativo,
            proveedor=proveedores[3],
            patio_destino=patios[0],
            producto=insumos[1],
            cantidad=Decimal("20.000"),
            precio_unitario_clp=65000,
            observacion="Sierras cinta de repuesto",
        )
        servicios.resolver_aprobacion_compra(usuario=gerente, compra_id=oc2.pk, aprobar=True)
        servicios.recepcionar_compra(usuario=operador, compra_id=oc2.pk, cantidad_recibida=Decimal("20.000"))

        oc3 = servicios.solicitar_compra(
            usuario=operador,
            proveedor=proveedores[2],
            patio_destino=patios[0],
            producto=insumos[0],
            cantidad=Decimal("250.000"),
            precio_unitario_clp=4950,
            observacion="Reserva proyectada mes próximo",
        )
        servicios.resolver_aprobacion_compra(usuario=gerente, compra_id=oc3.pk, aprobar=True)

        # Solicitud pendiente de aprobación
        servicios.solicitar_compra(
            usuario=operador,
            proveedor=proveedores[3],
            patio_destino=patios[1],
            producto=insumos[1],
            cantidad=Decimal("10.000"),
            precio_unitario_clp=68000,
            observacion="Requerimiento Patio Norte pendiente de V°B°",
        )

        # Ventas comerciales y despacho simulado sin SII
        if len(paquetes_patio_central) >= 6:
            pv1 = servicios.crear_pedido_venta(
                usuario=administrativo,
                cliente=clientes[0],
                patio_despacho=patios[0],
                paquetes_ids=[paquetes_patio_central[0].pk, paquetes_patio_central[1].pk],
                precio_m3_clp=215000,
                observacion="Despacho constructora Los Ángeles",
            )
            servicios.despachar_pedido_venta(
                usuario=operador,
                pedido_id=pv1.pk,
                patente_camion="GTRS45",
                conductor="Pedro Fuentealba",
                observacion="Salida verificada con QR en portería",
            )

            pv2 = servicios.crear_pedido_venta(
                usuario=administrativo,
                cliente=clientes[1],
                patio_despacho=patios[0],
                paquetes_ids=[paquetes_patio_central[2].pk, paquetes_patio_central[3].pk],
                precio_m3_clp=198000,
                observacion="Pedido Maule despachado",
            )
            servicios.despachar_pedido_venta(
                usuario=operador,
                pedido_id=pv2.pk,
                patente_camion="HJKL23",
                conductor="Juan Sepúlveda",
            )

            # Pedido en preparación (reservado)
            servicios.crear_pedido_venta(
                usuario=administrativo,
                cliente=clientes[2],
                patio_despacho=patios[0],
                paquetes_ids=[paquetes_patio_central[4].pk, paquetes_patio_central[5].pk],
                precio_m3_clp=192000,
                observacion="Programado para retiro de mañana",
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Operaciones ES3 generadas: {LoteCosecha.objects.count()} lotes cosecha, {guias_count} guías, "
                f"{Recepcion.objects.count()} recepciones, {OrdenProduccion.objects.count()} órdenes producción, "
                f"{Paquete.objects.count()} paquetes QR, {OrdenCompra.objects.count()} compras, "
                f"{PedidoVenta.objects.count()} pedidos venta."
            )
        )
        self.stdout.write(
            f"Usuarios: admin, gerente, administrativo, faena, faena2, patio · Clave: {CLAVE_DEMO}"
        )

    @staticmethod
    def _fechar(modelo, pk, campo, fecha):
        """Retrocede la fecha de un documento demo (auto_now_add no permite fijarla al crear)."""
        modelo.objects.filter(pk=pk).update(**{campo: fecha})
