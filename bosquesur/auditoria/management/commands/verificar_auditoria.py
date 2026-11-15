from django.core.management.base import BaseCommand

from auditoria.servicios import verificar_cadena


class Command(BaseCommand):
    help = "Recalcula la cadena de hashes de la bitácora y reporta si fue alterada."

    def handle(self, *args, **options):
        integra, total, alterado = verificar_cadena()
        if integra:
            self.stdout.write(self.style.SUCCESS(f"Bitácora íntegra: {total} registros verificados."))
        elif alterado:
            self.stdout.write(self.style.ERROR(f"Bitácora ALTERADA a partir del registro #{alterado}."))
        else:
            self.stdout.write(self.style.ERROR("Bitácora ALTERADA: faltan registros al final de la cadena."))
