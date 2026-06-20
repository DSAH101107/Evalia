from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from .models import Evaluacion, Invitacion

User = get_user_model()


@receiver(post_save, sender=Evaluacion)
def revert_role_after_evaluation(sender, instance, created, **kwargs):
    """
    When an evaluation is completed, check if the juror has completed all
    evaluations for all accepted invitations. If yes, revert the juror's role
    back to instructor.
    """
    # Only act on completed evaluations
    if instance.estado != Evaluacion.ESTADO_COMPLETADA:
        return

    juror = instance.juror
    if not juror:
        return

    # Get all accepted invitations for this juror (where juror is either the invited instructor
    # or is in the list of jurados) and that have a ficha.
    invitaciones = Invitacion.objects.filter(
        estado=Invitacion.ESTADO_ACEPTADA
    ).filter(
        Q(instructor_invitado=juror) | Q(instructores_jurados=juror),
        ficha__isnull=False
    ).annotate(
        total_aprendices=Count('ficha__aprendices'),
        evaluated_count=Count(
            'ficha__aprendices__evaluaciones',
            filter=Q(ficha__aprendices__evaluaciones__juror=juror) &
                   Q(ficha__aprendices__evaluaciones__estado=Evaluacion.ESTADO_COMPLETADA)
        )
    )

    # If there are no accepted invitations, do nothing.
    if not invitaciones.exists():
        return

    # Check if for every invitation, the evaluated count is at least the total aprendices
    # and there is at least one aprendiz.
    all_complete = all(
        inv.evaluated_count >= inv.total_aprendices and inv.total_aprendices > 0
        for inv in invitaciones
    )

    if all_complete and juror.rol == 'jurado':
        juror.rol = 'instructor'
        juror.save(update_fields=['rol'])