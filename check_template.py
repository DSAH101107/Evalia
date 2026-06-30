import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()
from django.template import engines
engine = engines['django']
template_string = open('templates/evaluacion/lista_evaluaciones.html', encoding='utf-8').read()
try:
    template = engine.from_string(template_string)
    print('Template syntax OK')
except Exception as e:
    print('Template error:', e)
