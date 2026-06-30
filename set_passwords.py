import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()
from apps.usuarios.models import Usuario
from django.contrib.auth import get_user_model
User = get_user_model()
aprendices = User.objects.filter(rol='aprendiz')
count = 0
for u in aprendices:
    u.set_password('aprendizsena')
    u.save()
    count += 1
print(f'Contraseña establecida para {count} aprendices: aprendizsena')
