"""Usuarios del sistema con control de acceso basado en roles (RBAC)."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        GERENTE = "GERENTE", "Gerente"
        ADMINISTRATIVO = "ADMINISTRATIVO", "Administrativo"
        FAENA = "FAENA", "Encargado de faena"
        PATIO = "PATIO", "Operador de patio"

    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.ADMINISTRATIVO)
    faena = models.ForeignKey(
        "maestros.Faena",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="encargados",
        help_text="Solo para encargados de faena: la faena desde la que emite guías.",
    )
    patio = models.ForeignKey(
        "maestros.Patio",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="operadores",
        help_text="Solo para operadores de patio: el patio donde recepciona.",
    )

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def tiene_rol(self, *roles):
        """El superusuario tiene acceso total; el resto solo a sus roles."""
        return self.is_active and (self.is_superuser or self.rol in roles)

    @property
    def nombre_visible(self):
        return self.get_full_name() or self.username
