from django import forms
from .models import *


class ExitForm(forms.ModelForm):
    class Meta:
        model = Exit
        fields = ['titre', 'montant', 'created_at', 'type_depense']
        widgets = {
            'created_at': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['created_at'].required = False


# forms.py
class InputeForm(forms.ModelForm):
    class Meta:
        model = Inpute
        fields = ['titres', 'montants', 'mode_paiement', 'created_ats']
        widgets = {
            'created_ats': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['created_ats'].required = False


class DepenseForm(forms.ModelForm):
    class Meta:
        model = Depense
        fields = ['type', 'intitule', 'montant', 'quantite', 'date_depense']
        widgets = {
            'type': forms.Select(attrs={'class': 'form-control'}),
            'intitule': forms.TextInput(attrs={'class': 'form-control'}),
            'montant': forms.NumberInput(attrs={'class': 'form-control'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control'}),
            'date_depense': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
        }
