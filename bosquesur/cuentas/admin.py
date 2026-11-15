from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "get_full_name", "rol", "faena", "patio", "is_active")
    list_filter = ("rol", "is_active", "faena", "patio")
    fieldsets = UserAdmin.fieldsets + (
        ("Rol en BosqueSur", {"fields": ("rol", "faena", "patio")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Rol en BosqueSur", {"fields": ("first_name", "last_name", "rol", "faena", "patio")}),
    )

    def has_delete_permission(self, request, obj=None):
        # Los usuarios no se borran (romperían la trazabilidad): se desactivan.
        return False
