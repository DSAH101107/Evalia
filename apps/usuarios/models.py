
from django.contrib.auth.models import AbstractUser
from django.db import models


class Rol:
    """Constantes para los roles del sistema"""
    ADMINISTRADOR = 'administrador'
    INSTRUCTOR = 'instructor'
    JURADO = 'jurado'
    APRENDIZ = 'aprendiz'
    
    CHOICES = [
        (ADMINISTRADOR, 'Administrador'),
        (INSTRUCTOR, 'Instructor'),
        (JURADO, 'Jurado'),
        (APRENDIZ, 'Aprendiz'),
    ]


class Usuario(AbstractUser):
    rol = models.CharField(
        max_length=20,
        choices=Rol.CHOICES,
        default=Rol.INSTRUCTOR
    )

    def save(self, *args, **kwargs):
        """Si el usuario es superuser, forzar rol=administrador automaticamente."""
        if self.is_superuser:
            self.rol = Rol.ADMINISTRADOR
        super().save(*args, **kwargs)
    
    def is_admin(self):
        return self.rol == Rol.ADMINISTRADOR or self.is_superuser
    
    def is_instructor(self):
        return self.rol == Rol.INSTRUCTOR
    
    def is_jurado(self):
        return self.rol == Rol.JURADO
    
    def is_aprendiz(self):
        return self.rol == Rol.APRENDIZ
