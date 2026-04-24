from django import forms
from django.forms import TextInput, Select
from .models import *
class CountryForm(forms.ModelForm):
    class Meta:
        model = Country
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country Name'})
        }

class StateForm(forms.ModelForm):
    class Meta:
        model = State
        fields = ['country', 'name']
        widgets = {
            'country': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State Name'})
        }

class DistrictForm(forms.ModelForm):
    class Meta:
        model = District
        fields = ['state', 'name']
        widgets = {
            'state': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'District Name'})
        }

class AreaForm(forms.ModelForm):
    class Meta:
        model = Area
        fields = ['district', 'name']
        widgets = {
            'district': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Area Name'})
        }


class VehicleTypeForm(forms.ModelForm):
    class Meta:
        model = VehicleType
        fields = ['name', 'description', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            if field_name == 'is_active':
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'