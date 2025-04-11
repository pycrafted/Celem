from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import *
from django.db.models import Sum
from django.utils import timezone


@receiver(post_save, sender=Payment)
def update_daily_report(sender, instance, **kwargs):
    date_obj = instance.payment_date.date() if instance.payment_date else timezone.now().date()

    payments = Payment.objects.filter(payment_date__date=date_obj)
    total_entrees_cash = payments.filter(mode_paiement='cash').aggregate(total=Sum('amount'))['total'] or 0

    total_sorties = Exit.objects.filter(created_at__date=date_obj).aggregate(total=Sum('montant'))['total'] or 0

    total_report = total_entrees_cash - total_sorties

    report, created = DailyReport.objects.get_or_create(date=date_obj)
    report.reportage = total_report
    report.save()
