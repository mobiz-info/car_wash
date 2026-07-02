from django import forms
from django.forms import TextInput, Select
from .models import *
class CountryForm(forms.ModelForm):
    class Meta:
        model = Country
        fields = ['name', 'currency_code', 'currency_symbol']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country Name'}),
            'currency_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. INR, AED'}),
            'currency_symbol': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ₹, د.إ'})
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
                
                
class VehicleTypeModelForm(forms.ModelForm):
    class Meta:
        model = VehicleTypeModel
        fields = ['vehicle_type', 'name', 'description', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['vehicle_type'].queryset = VehicleType.objects.filter(
            is_deleted=False
        )

class SchemeTypeForm(forms.ModelForm):
    class Meta:
        model = SchemeType
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Scheme Type Name'})
        }
        

class ExpenseHeadForm(forms.ModelForm):
    class Meta:
        model = ExpenseHead
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Expense Head Name'})
        }


class VehicleColorForm(forms.ModelForm):
    class Meta:
        model = VehicleColor
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Color Name'})
        }


class VehicleCompanyForm(forms.ModelForm):
    class Meta:
        model = VehicleCompany
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company/Brand Name'})
        }