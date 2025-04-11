from django.contrib import admin
from .models import *


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ['amount', 'payment_date', 'mode_paiement']


class InvoiceServiceInline(admin.TabularInline):
    model = InvoiceService
    extra = 0
    fields = ['service', 'quantite', 'prix']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'reference', 'customer', 'invoice_date_time', 'delivered_date')
    search_fields = ('reference', 'customer', 'invoice_date_time')
    list_editable = (
        'customer', 'invoice_date_time', 'delivered_date')
    inlines = [InvoiceServiceInline, PaymentInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.total = obj.get_total()
        obj.save()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.total = form.instance.get_total()
        form.instance.save()


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('proposition', 'designation', 'prix',)
    search_fields = ('proposition', 'prix')
    list_editable = ('designation', 'prix',)


@admin.register(Exit)
class ExitAdmin(admin.ModelAdmin):
    list_display = ('titre', 'type_depense', 'montant', 'created_at',)
    search_fields = ('titre',)
    list_editable = ('montant', 'type_depense', 'created_at',)


@admin.register(Inpute)
class InputeAdmin(admin.ModelAdmin):
    list_display = ('titres', 'montants', 'created_ats',)
    search_fields = ('titres',)
    list_editable = ('montants', 'created_ats',)


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ('date', 'reportage',)


@admin.register(Depense)
class DepenseAdmin(admin.ModelAdmin):
    list_display = ('intitule', 'type', 'montant', 'quantite', 'date_depense')
    search_fields = ('intitule',)
    list_editable = ('type', 'montant', 'quantite', 'date_depense')


admin.site.site_title = "Administration"
admin.site.site_header = "Cortex Administration"
admin.site.index_title = "Cortex"
