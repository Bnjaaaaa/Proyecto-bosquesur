"""
PyMySQL se registra como reemplazo de mysqlclient (MySQLdb).

Así el proyecto funciona con la base MariaDB de XAMPP en Windows sin
instalar compiladores de C ni librerías de MySQL.
"""
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # pragma: no cover - solo si se usa otro motor
    pass
