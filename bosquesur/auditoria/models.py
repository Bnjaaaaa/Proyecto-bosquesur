"""
Bitácora de auditoría inmutable.

Cada registro guarda el hash SHA-256 del registro anterior más su propio
contenido (cadena de hashes). Si alguien modifica o borra una fila directamente
en la base de datos, la verificación de la cadena lo detecta.
"""
import hashlib
import json

from django.conf import settings
from django.db import models


class RegistroInmutableError(Exception):
    pass


class RegistroQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise RegistroInmutableError("La bitácora de auditoría no admite modificaciones.")

    def delete(self):
        raise RegistroInmutableError("La bitácora de auditoría no admite eliminaciones.")


class RegistroAuditoria(models.Model):
    fecha = models.DateTimeField(db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="registros_auditoria",
    )
    usuario_nombre = models.CharField(max_length=150, blank=True)
    accion = models.CharField(max_length=30, db_index=True)
    entidad = models.CharField(max_length=50, blank=True, db_index=True)
    entidad_id = models.CharField(max_length=50, blank=True)
    descripcion = models.CharField("descripción", max_length=255)
    datos = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    hash_anterior = models.CharField(max_length=64)
    hash = models.CharField(max_length=64, unique=True)

    objects = RegistroQuerySet.as_manager()

    class Meta:
        ordering = ["-id"]
        verbose_name = "registro de auditoría"
        verbose_name_plural = "bitácora de auditoría"
        indexes = [models.Index(fields=["entidad", "entidad_id"])]

    def __str__(self):
        return f"[{self.fecha:%d-%m-%Y %H:%M}] {self.accion} · {self.descripcion}"

    def calcular_hash(self):
        contenido = "|".join(
            [
                self.hash_anterior,
                self.fecha.isoformat(),
                self.usuario_nombre,
                self.accion,
                self.entidad,
                self.entidad_id,
                self.descripcion,
                json.dumps(self.datos, sort_keys=True, ensure_ascii=False),
            ]
        )
        return hashlib.sha256(contenido.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RegistroInmutableError("Un registro de auditoría no puede modificarse.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroInmutableError("Un registro de auditoría no puede eliminarse.")


class EslabonCadena(models.Model):
    """
    Fila única que guarda el último hash de la cadena. Se bloquea con
    SELECT ... FOR UPDATE para que dos registros simultáneos no tomen el
    mismo "hash anterior".
    """

    ultimo_hash = models.CharField(max_length=64, default="0" * 64)

    class Meta:
        verbose_name = "eslabón de la cadena"
