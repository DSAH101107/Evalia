from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps


@receiver(post_save, sender='evaluacion.Fase')
def crear_competencias_para_fase(sender, instance, created, **kwargs):
    """
    Cuando se crea una fase, crear competencias básicas asociadas a esa fase.
    """
    if created:
        # Obtener modelos de forma lazy para evitar importaciones circulares
        try:
            Competencia = apps.get_model('evaluacion', 'Competencia')
            GAES = apps.get_model('evaluacion', 'GAES')
            Ficha = apps.get_model('fichas', 'Ficha')
        except LookupError:
            # Si las apps no están listas, salir
            return

        # Crear una GAES por defecto si no existe ninguna
        gaes_default, _ = GAES.objects.get_or_create(
            nombre='GAES Default',
            defaults={'descripcion': 'Grupo de Aprendices por defecto'}
        )

        # Crear una ficha por defecto si no existe ninguna
        ficha_default, _ = Ficha.objects.get_or_create(
            numero='2024001',
            defaults={
                'programa': 'Programa por defecto',
                'gaes': gaes_default,
                'jornada': 'mañana',
                'estado': 'activo'
            }
        )

        # Crear competencias básicas para esta fase
        competencias_basicas = [
            {'codigo': f'F{instance.numero}C001', 'nombre': f'Competencia Fase {instance.numero} - 1', 'descripcion': f'Descripción de la competencia 1 para la fase {instance.numero}'},
            {'codigo': f'F{instance.numero}C002', 'nombre': f'Competencia Fase {instance.numero} - 2', 'descripcion': f'Descripción de la competencia 2 para la fase {instance.numero}'},
            {'codigo': f'F{instance.numero}C003', 'nombre': f'Competencia Fase {instance.numero} - 3', 'descripcion': f'Descripción de la competencia 3 para la fase {instance.numero}'},
        ]

        for comp_data in competencias_basicas:
            Competencia.objects.get_or_create(
                codigo=comp_data['codigo'],
                defaults={
                    'nombre': comp_data['nombre'],
                    'descripcion': comp_data['descripcion'],
                    'fase': instance,
                    'gaes': gaes_default,
                    'ficha': ficha_default,
                    'activo': True
                }
            )