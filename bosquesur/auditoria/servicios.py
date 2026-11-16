"""API interna para escribir y verificar la bitácora de auditoría."""
import json

from django.db import transaction
from django.utils import timezone

from .models import EslabonCadena, RegistroAuditoria

HASH_INICIAL = "0" * 64


class Accion:
    LOGIN = "LOGIN"
    LOGIN_API = "LOGIN_API"
    LOGIN_FALLIDO = "LOGIN_FALLIDO"
    LOGOUT = "LOGOUT"
    ACCESO_DENEGADO = "ACCESO_DENEGADO"
    REGISTRAR_COSECHA = "REGISTRAR_COSECHA"
    EMITIR_GUIA = "EMITIR_GUIA"
    RECEPCIONAR_GUIA = "RECEPCIONAR_GUIA"
    ALERTA_DISCREPANCIA = "ALERTA_DISCREPANCIA"
    RESOLVER_DISCREPANCIA = "RESOLVER_DISCREPANCIA"
    ORDEN_PRODUCCION = "ORDEN_PRODUCCION"
    CREAR_PAQUETE_QR = "CREAR_PAQUETE_QR"
    PROCESAR_PAQUETE = "PROCESAR_PAQUETE"
    MOVER_PAQUETE = "MOVER_PAQUETE"
    SOLICITAR_COMPRA = "SOLICITAR_COMPRA"
    APROBAR_COMPRA = "APROBAR_COMPRA"
    RECEPCIONAR_COMPRA = "RECEPCIONAR_COMPRA"
    CREAR_VENTA = "CREAR_VENTA"
    DESPACHAR_VENTA = "DESPACHAR_VENTA"
    ANULAR_VENTA = "ANULAR_VENTA"
    OPERACION_RECHAZADA = "OPERACION_RECHAZADA"


def _ip_cliente(request):
    if request is None:
        return None
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _normalizar(datos):
    """Convierte Decimal, fechas, etc. a tipos JSON para que el hash sea reproducible."""
    return json.loads(json.dumps(datos or {}, default=str, ensure_ascii=False))


def registrar(accion, descripcion, usuario=None, entidad="", entidad_id="", datos=None, request=None):
    """Agrega un registro encadenado a la bitácora. Si está dentro de una
    transacción y esta se revierte, el registro también se revierte."""
    if usuario is not None and not getattr(usuario, "is_authenticated", False):
        usuario = None
    with transaction.atomic():
        eslabon, _ = EslabonCadena.objects.select_for_update().get_or_create(pk=1)
        registro = RegistroAuditoria(
            fecha=timezone.now(),
            usuario=usuario,
            usuario_nombre=usuario.username if usuario else "",
            accion=accion,
            entidad=entidad,
            entidad_id=str(entidad_id or ""),
            descripcion=descripcion[:255],
            datos=_normalizar(datos),
            ip=_ip_cliente(request),
            hash_anterior=eslabon.ultimo_hash,
        )
        registro.hash = registro.calcular_hash()
        registro.save()
        eslabon.ultimo_hash = registro.hash
        eslabon.save(update_fields=["ultimo_hash"])
    return registro


def verificar_cadena():
    """Recalcula la cadena completa. Devuelve (es_integra, total, id_del_primer_registro_alterado)."""
    anterior = HASH_INICIAL
    total = 0
    for registro in RegistroAuditoria.objects.order_by("id").iterator():
        total += 1
        if registro.hash_anterior != anterior or registro.calcular_hash() != registro.hash:
            return False, total, registro.pk
        anterior = registro.hash
    eslabon = EslabonCadena.objects.filter(pk=1).first()
    if eslabon and total and eslabon.ultimo_hash != anterior:
        # Se borraron registros al final de la cadena.
        return False, total, None
    return True, total, None
