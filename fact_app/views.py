from collections import defaultdict
import os
from decimal import Decimal
from django.shortcuts import redirect
from django.views import View
from django.contrib import messages
from django.db import transaction
from django.views.generic import TemplateView
from datetime import timedelta
from .forms import *
import json
from .models import *
from django.utils import timezone
from django.utils.timezone import datetime, now
from django.db.models import Count, Max, Q
from django.db.models import Sum, F
from django.db.models.functions import ExtractWeekDay
from django.http import JsonResponse
from django.utils.safestring import mark_safe
from django.db.models.functions import TruncMonth
from django.utils.dateparse import parse_datetime
from django.urls import reverse
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
import imgkit
import pywhatkit
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.templatetags.static import static
import logging

#page principale
class HomeView(LoginRequiredMixin, View):
    template_name = 'index.html'

    def get(self, request, *args, **kwargs):
        settings, created = GlobalSettings.objects.get_or_create(id=1)
        invoices = (Invoice.objects.select_related('save_by')
                    .prefetch_related('invoice_services__service', 'payments')).order_by('-reference')

        for invoice in invoices:
            last_payment = invoice.payments.order_by('-payment_date').first()
            invoice.last_payment_date = last_payment.payment_date if last_payment else None

        context = {
            'invoices': invoices,
            'use_delivery_confirmation': settings.use_delivery_confirmation,
            'use_partial_payment': settings.use_partial_payment,
            'use_antidate': settings.use_antidate,
        }

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        if request.POST.get('id_modified'):
            try:
                with transaction.atomic():
                    obj = Invoice.objects.get(id=request.POST.get('id_modified'))

                    paid = request.POST.get('modified', 'False')
                    delivered = request.POST.get('delivered', 'False')
                    mode_paiement = request.POST.get('mode_paiement') if paid == 'True' else None
                    amount_paid = Decimal(request.POST.get('amount_paid', 0))
                    if request.POST.get('payment_date'):
                        payment_date = timezone.make_aware(
                            datetime.strptime(request.POST.get('payment_date', ''), '%Y-%m-%d'))
                    else:
                        payment_date = timezone.now()

                    if paid == 'True' and amount_paid == 0:
                        amount_paid = obj.balance

                    # Si la case "Payé" est cochée et qu'un montant valide est saisi
                    if paid == 'True' and amount_paid > 0:
                        # Vérifiez si le montant total payé est inférieur au total de la facture
                        if obj.amount_paid + amount_paid <= obj.total:
                            Payment.objects.create(invoice=obj, amount=amount_paid, mode_paiement=mode_paiement, payment_date=payment_date)
                            obj.update_balance()  # Met à jour le solde après le paiement

                    # Mettez à jour l'état de la facture
                    obj.paid = obj.amount_paid >= obj.total

                    if obj.delivered != (delivered == 'True'):
                        obj.delivered = delivered == 'True'
                        if obj.delivered:
                            obj.delivered_date = timezone.now()

                    obj.save()

                    messages.success(request, 'La facture a été modifiée avec succès.', extra_tags='facture_modifier')

                    # Après la création des services liés à la facture
                    invoice_services_data = [
                        {
                            'service_name': invoice_service.service.designation,
                            'quantite': invoice_service.quantite,
                            'prix': invoice_service.prix,
                        }

                        for invoice_service in obj.invoice_services.all()
                    ]

                    # Déterminer l'état de paiement
                    if obj.balance == 0:
                        etat_paiement = 'Oui'  # Payé : Oui
                    elif obj.balance == obj.total:
                        etat_paiement = 'Non'  # Payé : Non
                    else:
                        etat_paiement = 'En cours'  # Payé : En cours

                    return JsonResponse({
                        'success': True,
                        'customer': obj.customer,
                        'paid': etat_paiement,
                        'id': obj.id,
                        'reference': obj.reference,
                        'total': obj.total,
                        'balance': obj.balance,
                        'delivered': 'Oui' if obj.delivered else 'Non',
                        'invoice_date_time': obj.invoice_date_time.strftime('%d/%m/%Y %H:%M'),
                        'invoice_services': invoice_services_data
                    })
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

#page principale
class DeleteInvoiceView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        invoice = get_object_or_404(Invoice, pk=pk)
        invoice.delete()
        messages.success(request, "La facture a été supprimée avec succès.", extra_tags='facture_supprimer')
        return redirect('home')


class AddInvoiceView(LoginRequiredMixin, View):
    template_name = 'add_invoice.html'

    def get(self, request, *args, **kwargs):
        services = Service.objects.exclude(proposition="invisible").order_by('proposition')
        settings, created = GlobalSettings.objects.get_or_create(id=1)

        last_reference = Invoice.objects.aggregate(Max('reference'))['reference__max']
        next_reference = (last_reference or 7999) + 1

        context = {
            'services': services,
            'next_reference': next_reference,
            'use_delivery_confirmation': settings.use_delivery_confirmation,
            'use_partial_payment': settings.use_partial_payment,
            'use_antidate': settings.use_antidate,
        }
        return render(request, self.template_name, context)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        try:
            customer_name = request.POST.get('customer')
            telephone = request.POST.get('telephone')
            delivered = request.POST.get('delivered') == 'on'
            mode_paiement = request.POST.get('mode_paiement')
            reference = request.POST.get('reference')

            invoice_date_time_str = request.POST.get('invoice_date_time')
            if invoice_date_time_str:
                invoice_date_time = parse_datetime(invoice_date_time_str)
            else:
                invoice_date_time = timezone.now()

            if not reference:
                last_reference = Invoice.objects.aggregate(Max('reference'))['reference__max']
                reference = (last_reference or 7999) + 1

            invoice = Invoice.objects.create(
                customer=customer_name,
                telephone=telephone,
                reference=reference,
                save_by=request.user,
                delivered=delivered,
                delivered_date=timezone.now() if delivered else None,
                invoice_date_time=invoice_date_time,
            )

            # Ajout des services associés à la facture
            service_ids = request.POST.getlist('service')
            quantites = request.POST.getlist('quantite')
            prixs = request.POST.getlist('prix')
            total_facture = Decimal(0)

            for service_id, quantite, prix in zip(service_ids, quantites, prixs):
                service = get_object_or_404(Service, pk=service_id)
                quantite = int(quantite)
                prix = Decimal(prix)

                InvoiceService.objects.create(
                    invoice=invoice,
                    service=service,
                    quantite=quantite,
                    prix=prix
                )

                total_facture += quantite * prix

            invoice.total = total_facture
            invoice.update_balance()

            amount_paid = request.POST.get('amount_paid')
            payment_date_str = request.POST.get('payment_date')
            if mode_paiement:
                if not amount_paid or Decimal(amount_paid) == 0:
                    amount_paid = invoice.total

                payment_date = parse_datetime(payment_date_str) if payment_date_str else timezone.now()

                Payment.objects.create(
                    invoice=invoice,
                    amount=Decimal(amount_paid),
                    mode_paiement=mode_paiement,
                    payment_date=payment_date
                )

            invoice.update_balance()

            invoice_services_data = [
                {
                    'service_name': invoice_service.service.designation,
                    'quantite': invoice_service.quantite,
                    'prix': invoice_service.prix,
                }
                for invoice_service in invoice.invoice_services.all()
            ]

            # Déterminer l'état de paiement
            etat_paiement = 'Oui' if invoice.balance == 0 else 'Non' if invoice.balance == invoice.total else 'En cours'

            # Réponse JSON pour confirmer le succès
            return JsonResponse({'success': True,
                                 'total': str(invoice.total),
                                 'balance': str(invoice.balance),
                                 'customer': invoice.customer,
                                 'id': invoice.id,
                                 'reference': invoice.reference,
                                 'paid': etat_paiement,
                                 'delivered': 'Oui' if invoice.delivered else 'Non',
                                 'invoice_date_time': invoice.invoice_date_time.strftime('%d/%m/%Y %H:%M'),
                                 'invoice_services': invoice_services_data
                                 })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class ReceiptView(LoginRequiredMixin, View):
    template_name = 'receipt.html'

    def get(self, request, *args, **kwargs):
        date_filter = request.GET.get('date', None)
        today = timezone.now().date()
        settings, created = GlobalSettings.objects.get_or_create(id=1)

        # Filtrer les données pour la date choisie
        if date_filter:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
        else:
            date_obj = today

        payments = Payment.objects.filter(payment_date__date=date_obj)  # erreur
        if not payments.exists():
            print("Aucun paiement trouvé pour la date spécifiée.")
        exits = Exit.objects.filter(created_at__date=date_obj)
        inputes = Inpute.objects.filter(created_ats__date=date_obj)

        inputes_wave = Inpute.objects.filter(created_ats__date=date_obj, mode_paiement='wave')
        inputes_orange = Inpute.objects.filter(created_ats__date=date_obj, mode_paiement='om')
        inputes_cash = Inpute.objects.filter(created_ats__date=date_obj, mode_paiement='cash')

        # Calcul du total de la caisse pour le jour précédent
        previous_day = date_obj - timedelta(days=1)
        previous_day_report = DailyReport.objects.filter(date=previous_day).first()
        previous_day_total = previous_day_report.reportage if previous_day_report else 0

        # Calcul des totaux
        total_inputes = inputes_cash.aggregate(total=Sum('montants'))['total'] or 0
        total_inputes_wave = inputes_wave.aggregate(total=Sum('montants'))['total'] or 0
        total_inputes_orange = inputes_orange.aggregate(total=Sum('montants'))['total'] or 0

        total_entrees_cash = ((payments.filter(mode_paiement='cash').aggregate(total=Sum('amount'))['total'] or 0)
                              + previous_day_total + total_inputes)
        total_entrees_wave = ((payments.filter(mode_paiement='wave').aggregate(total=Sum('amount'))['total'] or 0)
                              + total_inputes_wave)
        total_payments_om = (payments.filter(mode_paiement='om').aggregate(total=Sum('amount'))['total'] or 0)

        total_entrees_om = total_payments_om + total_inputes_orange
        total_sorties = exits.aggregate(total=Sum('montant'))['total'] or 0
        total_entrees = total_entrees_cash + total_entrees_wave + total_entrees_om
        total_caisse = total_entrees - total_sorties
        total_report = total_entrees_cash - total_sorties
        # Enregistrement du rapport pour le jour actuel
        report, created = DailyReport.objects.get_or_create(date=date_obj)
        report.reportage = total_report
        report.save()

        context = {
            'payments': payments,
            'exits': exits,
            'inputes': inputes,
            'inputes_wave': inputes_wave,
            'inputes_orange': inputes_orange,
            'inputes_cash': inputes_cash,
            'exit_form': ExitForm(),
            'inpute_form': InputeForm(),
            'total_entrees_cash': total_entrees_cash,
            'total_entrees_wave': total_entrees_wave,
            'total_entrees_om': total_entrees_om,
            'total_sorties': total_sorties,
            'total_entrees': total_entrees,
            'total_caisse': total_caisse,
            'total_report': total_report,
            'total_inputes': total_inputes,
            'total_inputes_wave': total_inputes_wave,
            'total_inputes_orange': total_inputes_orange,
            'date_filter': date_filter,
            'previous_day_total': previous_day_total,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        exit_form = ExitForm(request.POST)
        if exit_form.is_valid():
            exit_form.save()
            messages.success(request, "Nouvelle sortie efféctuée.", extra_tags='sortie')
        else:
            messages.error(request, "Erreur lors de l'ajout de la sortie.")

        inpute_form = InputeForm(request.POST)
        if inpute_form.is_valid():
            inpute_form.save()
            messages.success(request, "Nouvelle entrée efféctuée.", extra_tags='entrer')
        else:
            messages.error(request, "Erreur lors de l'ajout de l'entrée.")

        return redirect('receipt')


class JournalView(LoginRequiredMixin, View):
    template_name = 'journal.html'

    def get(self, request, *args, **kwargs):
        settings, created = GlobalSettings.objects.get_or_create(id=1)
        date_filter = request.GET.get('date', None)

        if date_filter:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d')
            invoices = Invoice.objects.filter(invoice_date_time__date=date_obj).order_by('-invoice_date_time')
        else:
            invoices = Invoice.objects.filter(invoice_date_time__date=timezone.now().date()).order_by(
                '-invoice_date_time')

            # Ajouter la date du dernier paiement pour chaque facture
        for invoice in invoices:
            latest_payment = invoice.payments.order_by('-payment_date').first()
            invoice.latest_payment_date = latest_payment.payment_date if latest_payment else None

        total_sales = invoices.aggregate(total=Sum('total'))['total'] or 0

        context = {
            'invoices': invoices,
            'total_sales': total_sales,
            'date_filter': date_filter,
            'use_delivery_confirmation': settings.use_delivery_confirmation,
        }
        return render(request, self.template_name, context)


class DepenseView(LoginRequiredMixin, TemplateView):
    template_name = 'depense.html'

    def get(self, request, *args, **kwargs):
        # Récupération des filtres depuis le GET request
        month_filter = request.GET.get('month', None)
        search_query = request.GET.get('search', '').lower()
        form = DepenseForm()  # Formulaire vide pour l'ajout de dépense

        # Filtrer par mois si un filtre est fourni
        if month_filter:
            date_obj = datetime.strptime(month_filter, '%Y-%m')
            depenses = Depense.objects.filter(date_depense__year=date_obj.year, date_depense__month=date_obj.month)
        else:
            # Afficher les dépenses pour le mois courant par défaut
            today = now()
            depenses = Depense.objects.filter(date_depense__year=today.year, date_depense__month=today.month)

        # Trier les dépenses du plus récent au plus ancien
        depenses = depenses

        # Appliquer le filtre de recherche si une recherche est effectuée
        if search_query:
            depenses = depenses.filter(
                models.Q(type__icontains=search_query) |
                models.Q(intitule__icontains=search_query) |
                models.Q(date_depense__icontains=search_query)
            )

        context = {
            'depenses': depenses,
            'month_filter': month_filter,
            'form': form,
            'search_query': search_query,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = DepenseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Nouvelle charge ajoutée avec succès.', extra_tags='nouvelle_charge')
        else:
            messages.error(request, 'Erreur lors de l\'ajout de la dépense.')
        return redirect('depense')


class BilanView(LoginRequiredMixin, TemplateView):
    template_name = 'bilan.html'

    def get(self, request, *args, **kwargs):
        current_date = datetime.now()
        month_filters = request.GET.get('month', None)
        if not month_filters:
            month_filters = current_date.strftime('%Y-%m')

        # Récupérer toutes les factures, paiements et inputes
        invoices = Invoice.objects.all()
        depenses = Depense.objects.all()
        payments = Payment.objects.all()
        inputes = Inpute.objects.all()

        if month_filters:
            month_obj = datetime.strptime(month_filters, '%Y-%m')
            invoices = invoices.filter(invoice_date_time__year=month_obj.year, invoice_date_time__month=month_obj.month)
            depenses = depenses.filter(date_depense__year=month_obj.year, date_depense__month=month_obj.month)
            payments = payments.filter(payment_date__year=month_obj.year, payment_date__month=month_obj.month)
            inputes = inputes.filter(created_ats__year=month_obj.year, created_ats__month=month_obj.month)

        # Calcul des totaux journaliers
        daily_sales = invoices.values('invoice_date_time__date').annotate(total=Sum('total')).order_by(
            'invoice_date_time__date')
        daily_depenses = depenses.values('date_depense__date').annotate(
            total=Sum(F('montant') * F('quantite'))).order_by('date_depense__date')

        # Ajouter les totaux journaliers pour les paiements et les inputes
        daily_payments = payments.values('payment_date__date').annotate(total=Sum('amount')).order_by(
            'payment_date__date')
        daily_inputes = inputes.values('created_ats__date').annotate(total=Sum('montants')).order_by(
            'created_ats__date')

        combined_daily_data = defaultdict(lambda: {'payment_total': 0, 'inpute_total': 0})

        for payment in daily_payments:
            date = payment['payment_date__date']
            combined_daily_data[date]['payment_total'] = payment['total']

        for inpute in daily_inputes:
            date = inpute['created_ats__date']
            combined_daily_data[date]['inpute_total'] = inpute['total']

        # Ajouter la somme des paiements et inputes dans combined_daily_data
        daily_combined_totals = []
        for date, totals in combined_daily_data.items():
            combined_total = totals['payment_total'] + totals['inpute_total']
            daily_combined_totals.append({'date': date, 'total': combined_total})

        total_inputes = inputes.aggregate(total=Sum('montants'))['total'] or 0

        total_benefit = (payments.aggregate(total=Sum('amount'))['total'] or 0) + total_inputes

        context = {
            'daily_sales': daily_sales,
            'total_sales': invoices.aggregate(total=Sum('total'))['total'] or 0,
            'daily_depenses': daily_depenses,
            'total_depenses': depenses.aggregate(total=Sum(F('montant') * F('quantite')))['total'] or 0,
            'daily_payments': daily_payments,
            'daily_inputes': daily_inputes,
            'total_benefit': total_benefit,
            'total_inputes': total_inputes,
            'month_filter': month_filters,
            'daily_combined_totals': daily_combined_totals,
        }
        return render(request, self.template_name, context)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Obtenir le mois sélectionné depuis la requête GET
        selected_month = self.request.GET.get('month')
        if selected_month:
            year, month = map(int, selected_month.split('-'))
            start_date = timezone.make_aware(datetime(year, month, 1))
            if month == 12:
                end_date = timezone.make_aware(datetime(year + 1, 1, 1))
            else:
                end_date = timezone.make_aware(datetime(year, month + 1, 1))

            depenses = Depense.objects.filter(date_depense__range=(start_date, end_date))
        else:
            depenses = Depense.objects.all()

        # Calculer la somme des dépenses par type
        depenses = depenses.values('type').annotate(total=Sum(F('montant') * F('quantite')))

        # Calculer le total général
        total_general = sum(dep['total'] for dep in depenses)

        # Préparer les données pour le graphique
        context['labels'] = json.dumps([dep['type'] for dep in depenses])
        context['data'] = json.dumps([
            float(dep['total']) / float(total_general) * 100
            for dep in depenses
        ])

        # Calculer l'année actuelle et les 4 années précédentes
        current_year = now().year
        last_year = current_year - 1

        years = [current_year, last_year]

        # Obtenir les chiffres d'affaires mensuels des 5 dernières années
        invoices = Invoice.objects.filter()

        # Créer un dictionnaire pour stocker les chiffres d'affaires par année et par mois
        sales_data = [0] * 24

        # Calculer le chiffre d'affaires mensuel
        for invoice in invoices:
            date_facture = invoice.invoice_date_time#look
            if date_facture.year in years:
                index = (date_facture.year - last_year) * 12 + date_facture.month - 1
                sales_data[index] += float(invoice.total)

        # Calculer les dépenses mensuelles pour les 5 dernières années
        depensons = Depense.objects.filter(date_depense__year__in=years)

        # Initialiser un dictionnaire pour les dépenses
        depense_data = [0] * (12 * 2)

        # Créer les labels de mois/année pour l'axe des x
        labelo = []
        index_map = {}

        for year in sorted(years):
            for month in range(1, 13):
                labelo.append(f"{month:02d}-{year}")
                index_map[(year, month)] = len(labelo) - 1

        # Calculer les dépenses mensuelles
        for depensier in depensons:
            year = depensier.date_depense.year
            month = depensier.date_depense.month
            index = index_map[(year, month)]
            depense_data[index] += float(depensier.montant) * depensier.quantite

        # Calculer la somme des montants des factures payées et le nombre de factures payées
        paid_invoices = Invoice.objects.filter()
        total_amount = paid_invoices.aggregate(Sum('total'))['total__sum'] or 0
        total_count = paid_invoices.aggregate(Count('id'))['id__count'] or 1  # Éviter la division par zéro

        # Calculer le montant moyen dépensé par client
        montant_moyen = total_amount / total_count if total_count > 0 else 0

        # Calculer le nombre total de factures
        total_invoices = Invoice.objects.count()

        if total_invoices > 0:
            # Extraire les mois distincts où il y a des factures
            months_with_invoices = (
                Invoice.objects
                .annotate(month=TruncMonth('invoice_date_time'))
                .values('month')
                .distinct()
            )

            # Calculer le nombre de mois distincts
            months_difference = months_with_invoices.count()

            # Éviter la division par zéro
            months_difference = max(months_difference, 1)

            # Calculer la moyenne mensuelle de factures
            print(months_difference)
            print(total_invoices)
            average_monthly_invoices = total_invoices / months_difference
        else:
            average_monthly_invoices = 0

        # Filtrer uniquement les factures payées
        invoices_paid = Invoice.objects.filter()

        # Grouper par mois et calculer le chiffre d'affaires total pour chaque mois
        paid_invoices_per_month = (
            invoices_paid
            .annotate(month=TruncMonth('invoice_date_time'))
            .values('month')
            .annotate(monthly_total=Sum('total'))
        )

        # Nombre de mois avec des factures payées
        num_months = paid_invoices_per_month.count()

        # Somme totale du chiffre d'affaires
        total_revenue = invoices_paid.aggregate(Sum('total'))['total__sum'] or 0

        # Calculer le chiffre d'affaires mensuel moyen
        average_monthly_revenue = total_revenue / num_months if num_months > 0 else 0

        # Regrouper par mois et calculer la somme des dépenses pour chaque mois
        depenses_par_mois = (
            Depense.objects
            .annotate(month=TruncMonth('date_depense'))
            .values('month')
            .annotate(total_mois=Sum(F('montant') * F('quantite')))
            .order_by('month')
        )

        # Calculer la somme des dépenses mensuelles et le nombre de mois
        total_depenses = sum(item['total_mois'] for item in depenses_par_mois)
        nombre_de_mois = depenses_par_mois.count()

        # Calculer la dépense mensuelle moyenne
        if nombre_de_mois > 0:
            depense_mensuelle_moyenne = total_depenses / nombre_de_mois
        else:
            depense_mensuelle_moyenne = 0

            # Obtenir les chiffres d'affaires mensuels pour l'année en cours
        monthly_revenue = (
            Invoice.objects
            .filter(invoice_date_time__year=current_year)#look
            .annotate(month=TruncMonth('invoice_date_time'))
            .values('month')
            .annotate(monthly_total=Sum('total'))
            .order_by('month')
        )

        # Créer une liste pour les chiffres d'affaires mensuels
        revenue_data = [0] * 12  # Pour 12 mois

        # Remplir revenue_data avec les montants mensuels
        for item in monthly_revenue:
            month_index = item['month'].month - 1  # Index 0 pour janvier
            revenue_data[month_index] = float(item['monthly_total'])

        depenses_mensuelles = (
            Depense.objects
            .filter(date_depense__year=current_year)
            .annotate(month=TruncMonth('date_depense'))
            .values('month')
            .annotate(total_mensuel=Sum(F('montant') * F('quantite')))
            .order_by('month')
        )

        depense_datas = [0] * 12

        # Remplir la liste avec les montants des dépenses mensuelles
        for depensey in depenses_mensuelles:
            month_index = depensey['month'].month - 1  # Index 0 pour janvier
            depense_datas[month_index] = float(depensey['total_mensuel'])

        context['depense_mensuelle_moyenne'] = depense_mensuelle_moyenne
        context['average_monthly_revenue'] = average_monthly_revenue
        context['sales_data'] = mark_safe(json.dumps(sales_data))
        context['total_values'] = json.dumps([float(dep['total']) for dep in depenses])
        context['selected_month'] = selected_month
        context['depense_data'] = json.dumps(depense_data)
        context['labelo'] = json.dumps(labelo)
        context['montant_moyen'] = montant_moyen
        context['average_monthly_invoices'] = average_monthly_invoices
        context['revenue_data'] = revenue_data
        context['depense_datas'] = depense_datas

        return context


def weekly_visits_data(request):
    # Extraire le jour de la semaine (1 pour Lundi, 7 pour Dimanche)
    weekly_data = Invoice.objects.annotate(day_of_week=ExtractWeekDay('invoice_date_time')) \
        .values('day_of_week') \
        .annotate(total=Count('id')) \
        .order_by('day_of_week')

    # Organiser les données pour correspondre aux jours de la semaine (Lundi à Dimanche)
    days_mapping = {1: 'Dimanche', 2: 'Lundi', 3: 'Mardi', 4: 'Mercredi', 5: 'Jeudi', 6: 'Vendredi', 7: 'Samedi'}
    data = {days_mapping[i]: 0 for i in range(1, 8)}
    for item in weekly_data:
        day = days_mapping[item['day_of_week']]
        data[day] = item['total']

    return JsonResponse({
        'labels': list(data.keys()),
        'data': list(data.values())
    })


from django.urls import reverse_lazy  # Ajoute cette importation

class CustomLoginView(LoginView):
    template_name = 'connexion.html'

    def get_success_url(self):
        return reverse_lazy('add-invoice')  # Change 'home' par 'add-invoice'

    def form_invalid(self, form):
        messages.error(self.request, 'Nom d’utilisateur ou mot de passe incorrect.')
        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    next_page = 'login'


class ServicePriceView(LoginRequiredMixin, View):
    def get(self, request, service_id):
        try:
            service = Service.objects.get(id=service_id)
            print(f"Service trouvé : {service}, Prix : {service.prix}")
            return JsonResponse({'prix': service.prix})
        except Service.DoesNotExist:
            print("Service non trouvé")
            return JsonResponse({'prix': 0}, status=404)


class ParametreView(LoginRequiredMixin, TemplateView):
    template_name = 'parametre.html'

    def get(self, request, *args, **kwargs):
        page = kwargs.get('page', 'default')

        settings, created = GlobalSettings.objects.get_or_create(id=1)
        services = Service.objects.all().order_by('proposition')  # Récupérer tous les services existants
        users = User.objects.all()  # Récupérer tous les utilisateurs
        inputes = Inpute.objects.all().order_by('-created_ats')
        exits = Exit.objects.all().order_by('-created_at')
        depenses = Depense.objects.all().order_by('-date_depense')
        return render(request, self.template_name, {
            'settings': settings,
            'services': services,
            'users': users,
            'inputes': inputes,
            'exits': exits,
            'depenses': depenses,
            'current_page': page,
        })

    def post(self, request, *args, **kwargs):
        settings, created = GlobalSettings.objects.get_or_create(id=1)

        if 'toggle_superuser' in request.POST:
            user_id = request.POST.get('user_id')
            user = User.objects.get(id=user_id)

            # Vérifier si la case est cochée ou décochée
            is_superuser = 'toggle_superuser' in request.POST

            # Empêcher la modification des droits de l'utilisateur courant
            if user == request.user:
                messages.error(request, "Vous ne pouvez pas modifier votre propre statut d'administrateur.",
                               extra_tags='error_admin')
            else:
                # Mettre à jour le statut d'administrateur
                user.is_superuser = is_superuser
                user.is_staff = is_superuser  # Mettre à jour le statut 'is_staff' selon les besoins
                user.save()
                messages.success(request, f"Le statut d'administrateur de {user.username} a été mis à jour.",
                                 extra_tags='modif_admin_succes')
                return redirect(reverse('parametre_page', kwargs={'page': 'utilisateur'}))

        # Gestion du formulaire de réglages
        if 'save_settings' in request.POST:
            settings.use_delivery_confirmation = request.POST.get('use_delivery_confirmation') == 'on'
            settings.use_partial_payment = request.POST.get('use_partial_payment') == 'on'
            settings.use_antidate = request.POST.get('use_antidate') == 'on'
            settings.save()
            messages.success(request, "Les réglages ont été enregistrés avec succes.", extra_tags='reglage_succes')
            return redirect(reverse('parametre_page', kwargs={'page': 'settings'}))

        # Gestion du formulaire d'ajout d'utilisateur
        elif 'add_user' in request.POST:
            username = request.POST.get('username')
            password = request.POST.get('password')
            is_superuser = request.POST.get('is_superuser') == 'on'

            if username and password:
                if User.objects.filter(username=username).exists():
                    messages.error(request, "Le nom d'utilisateur existe déjà.", extra_tags='utilisateur_existant')
                else:
                    user = User.objects.create_user(username=username, password=password)
                    user.is_superuser = is_superuser
                    user.is_staff = is_superuser
                    user.save()
                    messages.success(request, "L'utilisateur a été ajouté avec succès.",
                                     extra_tags='succes_user_creation')
                    return redirect(reverse('parametre_page', kwargs={'page': 'utilisateur'}))

        # Gestion du formulaire d'ajout de service
        elif 'add_service' in request.POST:
            proposition = request.POST.get('proposition')
            designation = request.POST.get('designation')
            prix = request.POST.get('prix')

            if proposition and designation and prix:
                service = Service(proposition=proposition, designation=designation, prix=prix)
                service.save()
                messages.success(request, "Le service a été ajouté avec succès.", extra_tags='succes_service')
                return redirect(reverse('parametre_page', kwargs={'page': 'service'}))
            else:
                messages.error(request, "Tous les champs du service sont requis.", )

        return redirect(reverse('parametre_page', kwargs={'page': 'service'}))


class DeleteUserView(LoginRequiredMixin, View):
    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        user.delete()
        messages.success(request, "L'utilisateur a été supprimé avec succès.", extra_tags='success')
        return redirect(reverse('parametre_page', kwargs={'page': 'utilisateur'}))


class DeleteServiceView(LoginRequiredMixin, View):
    def post(self, request, service_id):
        service = get_object_or_404(Service, id=service_id)
        service.delete()
        messages.success(request, "Le service a été supprimé avec succès.", extra_tags='success')
        return redirect(reverse('parametre_page', kwargs={'page': 'service'}))


class DeleteInputeView(LoginRequiredMixin, View):
    def post(self, request, inpute_id):
        inpute = get_object_or_404(Inpute, id=inpute_id)
        inpute.delete()
        messages.success(request, "L'entrée a été supprimée avec succès.", extra_tags='success')
        return redirect(reverse('parametre_page', kwargs={'page': 'caisse'}))


class DeleteExitView(LoginRequiredMixin, View):
    def post(self, request, exit_id):
        exit_item = get_object_or_404(Exit, id=exit_id)
        exit_item.delete()
        messages.success(request, "La sortie a été supprimé avec succès.", extra_tags='success')
        return redirect(reverse('parametre_page', kwargs={'page': 'caisse'}))


class DeleteDepenseView(LoginRequiredMixin, View):
    def post(self, request, depense_id):
        depense = get_object_or_404(Depense, id=depense_id)
        depense.delete()
        messages.success(request, "La dépense a été supprimée avec succès.", extra_tags='success')
        return redirect(reverse('parametre_page', kwargs={'page': 'charge'}))


logging.basicConfig(level=logging.INFO)


def absolute_static_url(file_path):
    return f"{settings.BASE_URL}{static(file_path)}"


class SendInvoiceView(View):
    def get(self, request, invoice_id):
        # Obtenir la facture
        invoice = get_object_or_404(Invoice, id=invoice_id)
        services = invoice.invoice_services.all()

        # Rendu du template HTML en une image
        context = {'invoice': invoice, 'services': services}
        rendered_html = render(request, 'invoice_image.html', context).content.decode('utf-8')

        # Chemin de sortie pour l'image dans le dossier 'media'
        invoice_reference = invoice.reference
        output_image_path = os.path.join(settings.MEDIA_ROOT, f'{invoice_reference}_{invoice.customer}.png')

        css_path = os.path.join(settings.BASE_DIR, 'static', 'facture_image.css')
        try:
            imgkit.from_string(rendered_html, output_image_path, options={'--user-style-sheet': css_path})
            logging.info(f"Image générée à l'emplacement : {output_image_path}")
        except OSError as e:
            return HttpResponse(f"Erreur lors de la conversion de la facture en image : {str(e)}", status=500)

        # Envoi de l'image via WhatsApp
        try:
            # Vérification du format du numéro de téléphone
            telephone = f'+221{invoice.telephone}'
            logging.info(f"Envoi de la facture à : {telephone}")

            if telephone:
                # Log de l'emplacement de l'image
                logging.info(f"Chemin de l'image à envoyer : {output_image_path}")
                caption = f"Veuillez recevoir ci_joint votre facture, {invoice.customer}"
                # Ajout d'un délai avant l'envoi pour s'assurer que WhatsApp Web est prêt
                pywhatkit.sendwhats_image(telephone, output_image_path, caption)  # délai de 10 secondes

                return redirect('home')
            else:
                return HttpResponse("Numéro de téléphone manquant pour ce client.", status=400)
        except Exception as e:
            return HttpResponse(f"Erreur lors de l'envoi de la facture : {str(e)}", status=500)



