from django.contrib import admin

from .models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    """Solo lectura: nadie, ni siquiera el superusuario, puede editar o borrar la bitácora."""

    list_display = ("fecha", "usuario_nombre", "accion", "entidad", "entidad_id", "descripcion", "ip")
    list_filter = ("accion", "entidad")
    search_fields = ("usuario_nombre", "descripcion", "entidad_id")
    readonly_fields = [f.name for f in RegistroAuditoria._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
