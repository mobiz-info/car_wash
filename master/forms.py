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


class VehicleMakeForm(forms.ModelForm):
    class Meta:
        model = VehicleMake
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Make Name (e.g. Honda, Toyota)'}),
        }


class VehicleBrandModelForm(forms.ModelForm):
    class Meta:
        model = VehicleBrandModel
        fields = ['vehicle_type_model', 'make', 'name', 'is_active']
        widgets = {
            'vehicle_type_model': forms.Select(attrs={'class': 'form-control'}),
            'make': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Model Name (e.g. City, Virtus)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vehicle_type_model'].queryset = VehicleTypeModel.objects.filter(is_deleted=False).order_by('vehicle_type__name', 'name')
        self.fields['make'].queryset = VehicleMake.objects.filter(is_deleted=False, is_active=True).order_by('name')
        self.fields['make'].required = True
        self.fields['make'].empty_label = '-- Select Make --'


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'address', 'gst_no', 'phone_no', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Supplier Name'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Supplier Address', 'rows': 3}),
            'gst_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'GST No. (Optional)'}),
            'phone_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
        }


class OilProductForm(forms.ModelForm):
    class Meta:
        model = OilProduct
        fields = ['brand', 'name', 'grade', 'is_active']
        widgets = {
            'brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Castrol, Mobil 1, Shell'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. GTX, Edge, Helix'}),
            'grade': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 5W-30, 10W-40'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TyreBrandForm(forms.ModelForm):
    class Meta:
        model = TyreBrand
        fields = ['brand', 'is_active']
        widgets = {
            'brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. MRF, Apollo, Bridgestone, CEAT'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }