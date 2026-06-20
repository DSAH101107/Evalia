#!/usr/bin/env python
"""
Script para generar datos de prueba (seeds) para el sistema EVALIA.
Ejecutar con: python manage.py shell < apps/seeds.py
"""
from apps.usuarios.models import Usuario, Rol
from apps.evaluacion.models import (
    Fase, Trimestre, Ficha, GAES, Aprendiz, Checklist,
    Competencia, ChecklistItem, Invitacion
)

def crear_datos_prueba():
    print("Creando datos de prueba...")

    # Crear Fases
    for i in range(1, 8):
        Fase.objects.get_or_create(numero=i, defaults={'nombre': f'Fase {i}'})

    # Crear Trimestres
    for i in range(1, 5):
        Trimestre.objects.get_or_create(numero=i, anio=2024)

    # Crear GAES
    for i in range(1, 11):
        GAES.objects.get_or_create(nombre=f'GAES {i}', defaults={'descripcion': f'Grupo de Aprendices {i}'})

    # Crear Fichas
    for i in range(1, 6):
        Ficha.objects.get_or_create(numero=f'{2024}{i:03d}', defaults={'programa': f'Programa {i}'})

    # Crear competencias de ejemplo
    fases = list(Fase.objects.all()[:3])
    fichas = list(Ficha.objects.all()[:3])
    trimestres = list(Trimestre.objects.all()[:1])
    
    for i in range(1, 7):
        Competencia.objects.get_or_create(
            codigo=f'COMP{i:03d}',
            defaults={
                'nombre': f'Competencia {i}',
                'descripcion': f'Descripción de la competencia {i}',
                'fase_id': getattr(fases[(i-1) % len(fases)], 'id', None),
                'ficha_id': getattr(fichas[(i-1) % len(fichas)], 'id', None),
                'trimestre_id': getattr(trimestres[0], 'id', None) if trimestres else None,
                'activo': True
            }
        )
    
    # Crear Admin
    admin, _ = Usuario.objects.get_or_create(
        username='admin',
        defaults={'email': 'admin@evalia.com', 'rol': Rol.ADMINISTRADOR}
    )
    admin.set_password('admin123')
    admin.save()

    # Crear Instructores
    for i in range(1, 4):
        instructor, _ = Usuario.objects.get_or_create(
            username=f'instructor{i}',
            defaults={'email': f'instructor{i}@evalia.com', 'rol': Rol.INSTRUCTOR}
        )
        instructor.set_password(f'instructor{i}123')
        instructor.save()

    # Crear Aprendices
    fichas = list(Ficha.objects.all()[:5])
    gaes_list = list(GAES.objects.all()[:3])
    fases = list(Fase.objects.all()[:3])

    for i in range(1, 21):
        documento = f'100{i:04d}'
        aprendiz, _ = Aprendiz.objects.get_or_create(
            documento=documento,
            defaults={
                'nombres': f'Aprendiz{i}',
                'apellidos': 'Apellido',
                'email': f'aprendiz{i}@test.com',
                'ficha_id': getattr(fichas[(i-1) % len(fichas)], 'id', None),
                'gaes_id': getattr(gaes_list[(i-1) % len(gaes_list)], 'id', None),
                'fase_id': getattr(fases[(i-1) % len(fases)], 'id', None),
            }
        )

    # Crear Checklist de ejemplo
    checklist, _ = Checklist.objects.get_or_create(
        titulo='Checklist de Evaluación Estándar',
        defaults={'descripcion': 'Checklist para evaluación de aprendices'}
    )

    # Crear items de checklist
    competencias = list(Competencia.objects.all()[:3])
    for i in range(1, 6):
        ChecklistItem.objects.get_or_create(
            checklist=checklist,
            criterio=f'Criterio {i}',
            defaults={
                'descripcion': f'Descripción del criterio {i}',
                'puntaje_maximo': 10,
                'orden': i,
            }
        )

    print("Datos de prueba creados exitosamente.")
    return True

if __name__ == '__main__':
    crear_datos_prueba()