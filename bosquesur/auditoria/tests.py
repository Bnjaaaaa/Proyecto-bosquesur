from django.test import TestCase

from .models import RegistroAuditoria, RegistroInmutableError
from .servicios import registrar, verificar_cadena


class BitacoraInmutableTests(TestCase):
    def test_no_se_puede_modificar_ni_borrar(self):
        registro = registrar("PRUEBA", "Registro de prueba")
        registro.descripcion = "alterado"
        with self.assertRaises(RegistroInmutableError):
            registro.save()
        with self.assertRaises(RegistroInmutableError):
            registro.delete()
        with self.assertRaises(RegistroInmutableError):
            RegistroAuditoria.objects.all().update(descripcion="x")
        with self.assertRaises(RegistroInmutableError):
            RegistroAuditoria.objects.all().delete()

    def test_cadena_detecta_alteracion_directa_en_bd(self):
        registrar("PRUEBA", "uno")
        segundo = registrar("PRUEBA", "dos")
        registrar("PRUEBA", "tres")
        self.assertTrue(verificar_cadena()[0])
        # Simula a alguien editando la tabla con SQL directo (p. ej. desde phpMyAdmin).
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {RegistroAuditoria._meta.db_table} SET descripcion = %s WHERE id = %s",
                ["manipulado", segundo.pk],
            )
        integra, _, alterado = verificar_cadena()
        self.assertFalse(integra)
        self.assertEqual(alterado, segundo.pk)

    def test_login_fallido_queda_registrado(self):
        self.client.post("/login/", {"username": "nadie", "password": "x"})
        self.assertTrue(RegistroAuditoria.objects.filter(accion="LOGIN_FALLIDO").exists())
