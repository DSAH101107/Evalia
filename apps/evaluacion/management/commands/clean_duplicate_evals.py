from django.core.management.base import BaseCommand
from django.db.models import Count, Max
from apps.evaluacion.models import Evaluacion
from django.db import transaction

