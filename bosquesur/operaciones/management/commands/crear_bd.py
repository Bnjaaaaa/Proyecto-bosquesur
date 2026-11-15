"""
Crea la base de datos en el MariaDB/MySQL de XAMPP si aún no existe.

    python manage.py crear_bd

Equivale a ejecutar en phpMyAdmin:
    CREATE DATABASE bosquesur CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crea la base de datos MySQL/MariaDB (XAMPP) configurada en settings.py"
    requires_system_checks = []

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        if db["ENGINE"].endswith("sqlite3"):
            self.stdout.write("Modo SQLite activo (fallback automático sin XAMPP): no requiere CREATE DATABASE externo.")
            return
        if "mysql" not in db["ENGINE"]:
            self.stdout.write("El motor configurado no es MySQL/MariaDB; no hay nada que crear.")
            return
        try:
            import pymysql
        except ImportError as exc:
            raise CommandError("Falta PyMySQL: ejecute  pip install -r requirements.txt") from exc

        try:
            conexion = pymysql.connect(
                host=db["HOST"] or "127.0.0.1",
                port=int(db["PORT"] or 3306),
                user=db["USER"],
                password=db["PASSWORD"],
                charset="utf8mb4",
            )
        except pymysql.err.OperationalError as exc:
            raise CommandError(
                "No se pudo conectar a MySQL. ¿Está iniciado MySQL en el panel de XAMPP?\n"
                f"Detalle: {exc}"
            ) from exc

        nombre = db["NAME"]
        with conexion.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{nombre}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conexion.close()
        self.stdout.write(self.style.SUCCESS(f"Base de datos '{nombre}' lista en el servidor {version}."))
