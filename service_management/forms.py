from django import forms
from django.forms import TextInput, Select, Textarea, NumberInput, CheckboxInput
from .models import ServiceType, Service
from client_management.models import Client

class ServiceTypeForm(forms.ModelForm):
    class Meta:
        model = ServiceType
        fields = [ 'name']
        widgets = {
            'name': TextInput(attrs={'class': 'form-control', 'placeholder': 'Service category name (e.g. Wash, Oil Change)'}),
        }
        
class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['service_type', 'name', 'sac_code', 'description', 'is_active']
        widgets = {
            'service_type': Select(attrs={'class': 'form-control'}),
            'name': TextInput(attrs={'class': 'form-control', 'placeholder': 'Service Name (e.g. Foam Wash)'}),
            'sac_code': TextInput(attrs={'class': 'form-control', 'placeholder': 'SAC Code (e.g. 998714)'}),
            'description': Textarea(attrs={'class': 'form-control', 'placeholder': 'Operation details...', 'rows': 3}),
            # 'duration': NumberInput(attrs={'class': 'form-control', 'placeholder': 'Minutes'}),
            'is_active': CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service_type'].queryset = ServiceType.objects.filter(is_deleted=False)
        self.fields['service_type'].label = "Service Category"
        self.fields['service_type'].empty_label = "-- Select Service Category --"
        self.fields['sac_code'].required = False
        self.fields['sac_code'].label = "SAC Code"
