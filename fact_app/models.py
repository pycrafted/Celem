from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Service(models.Model):
    proposition = models.CharField(max_length=132, null=True)
    designation = models.CharField(max_length=132, null=True)
    prix = models.DecimalField(max_digits=10, decimal_places=0, default=0)

    def __str__(self):
        return self.proposition


class Invoice(models.Model):
    reference = models.PositiveIntegerField(null=True, unique=True)
    customer = models.CharField(max_length=132, null=True)
    telephone = models.CharField(max_length=132, blank=True, default="")
    save_by = models.ForeignKey(User, on_delete=models.PROTECT)
    invoice_date_time = models.DateTimeField(default=timezone.now)
    total = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    delivered = models.BooleanField(default=False)
    delivered_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"

    def __str__(self):
        return f"{self.customer}_{self.invoice_date_time}"

    def save(self, *args, **kwargs):
        if self.reference is None:
            last_reference = Invoice.objects.aggregate(models.Max('reference'))['reference__max']
            self.reference = (last_reference or 7999) + 1
        super().save(*args, **kwargs)

    def get_total(self):
        return sum(item.prix * item.quantite for item in self.invoice_services.all())

    def update_balance(self, payment_date=None):
        self.balance = self.total - self.amount_paid
        self.save()

    def is_fully_paid(self):
        return self.balance == 0


class InvoiceService(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='invoice_services')
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField(default=1)
    prix = models.DecimalField(max_digits=10, decimal_places=0, default=0)

    def save(self, *args, **kwargs):
        if self.prix == 0:
            self.prix = self.service.prix
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.service.proposition} x {self.quantite} - Prix: {self.prix}"


class Payment(models.Model):
    MODE_PAIEMENT_CHOICES = [
        ('wave', 'Wave'),
        ('om', 'Orange Money'),
        ('cash', 'Espèces'),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=0)
    payment_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    mode_paiement = models.CharField(max_length=10, choices=MODE_PAIEMENT_CHOICES, null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.amount_paid += self.amount
        self.invoice.update_balance()

    def __str__(self):
        return f"Paiement de {self.amount} pour la facture {self.invoice}"



class Exit(models.Model):
    titre = models.CharField(max_length=132, null=True)
    montant = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    created_at = models.DateTimeField(default=timezone.now, null=True, blank=True)
    save_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True)

    TYPES_DEPENSES = [
        ('', 'Retrait'),
        ('reparation', 'Réparation'),
        ('salaire', 'Salaire'),
        ('facture eau', 'Facture eau'),
        ('electricite', 'Électricité'),
        ('produit repassage', 'Produit repassage'),
        ('produit lavage', 'Produit lavage'),
        ('frais divers', 'Frais divers'),
    ]

    type_depense = models.CharField(max_length=20, choices=TYPES_DEPENSES, blank=True, null=True)

    def __str__(self):
        return self.titre

    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)

        if self.type_depense:
            Depense.objects.create(
                type=self.type_depense,
                intitule=self.titre,
                montant=self.montant,
                quantite=1,
                date_depense=self.created_at
            )


class Inpute(models.Model):
    MODE_PAIEMENT_CHOICES = [
        ('wave', 'Wave'),
        ('om', 'Orange Money'),
        ('cash', 'Espèces'),
    ]

    titres = models.CharField(max_length=132, null=True)
    montants = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    mode_paiement = models.CharField(max_length=10, choices=MODE_PAIEMENT_CHOICES, null=True, blank=True)
    created_ats = models.DateTimeField(default=timezone.now, null=True, blank=True)
    save_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True)

    def __str__(self):
        return self.titres

    def save(self, *args, **kwargs):
        if not self.created_ats:
            self.created_ats = timezone.now()
        super().save(*args, **kwargs)


class DailyReport(models.Model):
    date = models.DateField(default=timezone.now, unique=True)
    reportage = models.DecimalField(max_digits=10, decimal_places=0, default=0)

    class Meta:
        verbose_name = "Daily Report"
        verbose_name_plural = "Daily Reports"

    def __str__(self):
        return f"Report for {self.date}: {self.reportage}"


class Depense(models.Model):
    TYPES_DEPENSES = [
        ('reparation', 'reparation'),
        ('salaire', 'Salaire'),
        ('facture eau', 'facture eau'),
        ('electricite', 'electricite'),
        ('produit repassage', 'Produit repassage'),
        ('produit lavage', 'Produit lavage'),
        ('frais divers', 'frais divers'),
    ]

    type = models.CharField(max_length=20, choices=TYPES_DEPENSES)
    intitule = models.CharField(max_length=132, null=True)
    montant = models.DecimalField(max_digits=10, decimal_places=0)
    quantite = models.IntegerField(default=1)
    date_depense = models.DateTimeField(default=timezone.now, null=True, blank=True)

    def __str__(self):
        return f"{self.intitule} - {self.montant} x {self.quantite}F.FCFA"


class GlobalSettings(models.Model):
    use_delivery_confirmation = models.BooleanField(default=True)
    use_partial_payment = models.BooleanField(default=True)
    use_antidate = models.BooleanField(default=True)

    def __str__(self):
        return "Paramètres globaux"
