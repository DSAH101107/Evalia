"""
apps/gaes/models.py

GAES is defined in apps.evaluacion.models (canonical).
This module re-exports it so other code can do:
    from apps.gaes.models import GAES
"""
# Late import to prevent circular import during app registry population
def get_gaes_model():
    from apps.evaluacion.models import GAES
    return GAES


# Re-export for convenience
from apps.evaluacion.models import GAES as GAES  # noqa: E402, F401
