from django import forms
from .models import Country


class CountryForm(forms.ModelForm):
    class Meta:
        model = Country
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country Name'}),
        }