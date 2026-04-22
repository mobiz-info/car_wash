from django import forms
from django.forms import TextInput, Select

from .models import *


class CountryForm(forms.ModelForm):
    class Meta:
        model = Country
        fields = ['name']
        widgets = {
            'name': TextInput(attrs={'class': 'form-control', 'placeholder': 'Country Name'}),
        }
        

class StateForm(forms.ModelForm):
    class Meta:
        model = State
        fields = ['country', 'name']
        widgets = {
            'country': Select(attrs={'class': 'form-control'}),
            'name': TextInput(attrs={'class': 'form-control'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        qs = Country.objects.filter(is_deleted=False)

        if self.instance and self.instance.pk:
            qs = Country.objects.filter(is_deleted=False) | Country.objects.filter(id=self.instance.country_id)

        self.fields['country'].queryset = qs
        
class DistrictForm(forms.ModelForm):
    class Meta:
        model = District
        fields = ['state', 'name']
        widgets = {
            'state': Select(attrs={'class': 'form-control'}),
            'name': TextInput(attrs={'class': 'form-control'}),
        }
        

class AreaForm(forms.ModelForm):
    class Meta:
        model = Area
        fields = ['district', 'name']
        widgets = {
            'district': Select(attrs={'class': 'form-control'}),
            'name': TextInput(attrs={'class': 'form-control'}),
        }