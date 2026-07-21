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


class OilBrandForm(forms.ModelForm):
    class Meta:
        model = OilBrand
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Castrol, Mobil 1, Shell, Total, Motul'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class OilGradeForm(forms.ModelForm):
    class Meta:
        model = OilGrade
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 5W-30, 10W-40, 15W-40, 0W-20, 20W-50'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class OilProductForm(forms.ModelForm):
    class Meta:
        model = OilProduct
        fields = ['oil_brand', 'oil_grade', 'name', 'vehicle_type', 'vehicle_make', 'price_per_litre', 'recommended_qty_litres', 'is_active']
        widgets = {
            'oil_brand': forms.Select(attrs={'class': 'form-control'}),
            'oil_grade': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product name (e.g. GTX, Edge, Helix)'}),
            'vehicle_type': forms.Select(attrs={'class': 'form-control'}),
            'vehicle_make': forms.Select(attrs={'class': 'form-control'}),
            'price_per_litre': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 450.00', 'step': '0.01', 'min': '0'}),
            'recommended_qty_litres': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 4.0 (optional)', 'step': '0.1', 'min': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['oil_brand'].queryset = OilBrand.objects.filter(is_active=True, is_deleted=False).order_by('name')
        self.fields['oil_grade'].queryset = OilGrade.objects.filter(is_active=True, is_deleted=False).order_by('name')
        self.fields['vehicle_type'].queryset = VehicleType.objects.filter(is_active=True, is_deleted=False).order_by('name')
        self.fields['vehicle_make'].queryset = VehicleMake.objects.filter(is_active=True, is_deleted=False).order_by('name')
        
        self.fields['oil_brand'].empty_label = '-- Select Oil Brand --'
        self.fields['oil_grade'].empty_label = '-- Select Oil Grade --'
        self.fields['vehicle_type'].empty_label = '-- All Vehicle Types --'
        self.fields['vehicle_make'].empty_label = '-- All Vehicle Makes --'
        
        self.fields['oil_brand'].required = True
        self.fields['oil_grade'].required = True
        self.fields['name'].required = False
        self.fields['vehicle_type'].required = False
        self.fields['vehicle_make'].required = False
        self.fields['recommended_qty_litres'].required = False


class TyreBrandForm(forms.ModelForm):
    class Meta:
        model = TyreBrand
        fields = ['brand', 'is_active']
        widgets = {
            'brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. MRF, Apollo, Bridgestone, CEAT'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class OilProductPriceForm(forms.ModelForm):
    class Meta:
        model = OilProductPrice
        fields = ['oil_product', 'vehicle_type', 'vehicle_make', 'price_per_litre', 'recommended_qty_litres', 'is_active']
        widgets = {
            'oil_product': forms.Select(attrs={'class': 'form-control'}),
            'vehicle_type': forms.Select(attrs={'class': 'form-control'}),
            'vehicle_make': forms.Select(attrs={'class': 'form-control'}),
            'price_per_litre': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 450.00', 'step': '0.01', 'min': '0'}),
            'recommended_qty_litres': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 4.0 (optional)', 'step': '0.1', 'min': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields['oil_product'].queryset = OilProduct.objects.filter(
                company=company, is_active=True, is_deleted=False
            ).order_by('brand', 'name')
        self.fields['vehicle_type'].queryset = VehicleType.objects.filter(
            is_active=True, is_deleted=False
        ).order_by('name')
        self.fields['vehicle_make'].queryset = VehicleMake.objects.filter(
            is_active=True, is_deleted=False
        ).order_by('name')
        self.fields['vehicle_type'].required = False
        self.fields['vehicle_make'].required = False
        self.fields['vehicle_type'].empty_label = '-- All Vehicle Types --'
        self.fields['vehicle_make'].empty_label = '-- All Makes --'
        self.fields['recommended_qty_litres'].required = False