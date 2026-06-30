import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()
from apps.evaluacion.models import Resultado, Evaluacion
from django.db import transaction

with transaction.atomic():
    # Archive all evaluations first
    actualizados = Evaluacion.objects.all().update(estado=Evaluacion.ESTADO_CANCELADA)
    # Delete all results
    borrados, _ = Resultado.objects.all().delete()
    print(f'Evaluaciones archivadas: {actualizados}')
    print(f'Resultados eliminados: {borrados}')
