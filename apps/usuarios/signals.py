from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps
from .models import Rol


@receiver(post_save, sender='usuarios.Usuario')
def crear_datos_basicos_admin(sender, instance, created, **kwargs):
    """
    Cuando se crea un usuario con rol administrador,
    crear fases y competencias básicas si no existen.
    """
    # Solo actuar al crear el usuario y si el rol es administrador (o superuser, que ya se fuerza a administrador)
    if not created:
        return
    if instance.rol != Rol.ADMINISTRADOR:
        return

    # Obtener modelos de forma lazy para evitar importaciones circulares
    try:
        Fase = apps.get_model('competencias', 'Fase')
        GAES = apps.get_model('evaluacion', 'GAES')
        Ficha = apps.get_model('fichas', 'Ficha')
        Competencia = apps.get_model('competencias', 'Competencia')
    except LookupError:
        # Si las apps no están listas, salir
        return

    # Crear fases 1-7 si no existen
    for numero in range(1, 8):
        Fase.objects.get_or_create(
            numero=numero,
            defaults={'nombre': f'Fase {numero}'}
        )

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

    # Crear algunas competencias básicas si no existen
    competencias_basicas = [
        {'codigo': 'COM001', 'nombre': 'Competencia Básica 1', 'descripcion': 'Descripción de la competencia básica 1'},
        {'codigo': 'COM002', 'nombre': 'Competencia Básica 2', 'descripcion': 'Descripción de la competencia básica 2'},
        {'codigo': 'COM003', 'nombre': 'Competencia Básica 3', 'descripcion': 'Descripción de la competencia básica 3'},
    ]

    for comp_data in competencias_basicas:
        Competencia.objects.get_or_create(
            codigo=comp_data['codigo'],
            defaults={
                'nombre': comp_data['nombre'],
                'descripcion': comp_data['descripcion'],
                'fase': Fase.objects.filter(numero=1).first(),  # Asociar a fase 1
                'gaes': gaes_default,
                'ficha': ficha_default,
                'activo': True
            }
        )