from django import forms
from django.forms import TextInput, Select, Textarea, NumberInput, CheckboxInput
from .models import ServiceType, Service
from client_management.models import Client

class ServiceTypeForm(forms.ModelForm):
    class Meta:
        model = ServiceType
        fields = ['company', 'name', 'description']
        widgets = {
            'company': Select(attrs={'class': 'form-control'}),
            'name': TextInput(attrs={'class': 'form-control', 'placeholder': 'Service type name (e.g. Basic Wash)'}),
            'description': Textarea(attrs={'class': 'form-control', 'placeholder': 'Optional description...', 'rows': 3}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['company'].queryset = Client.objects.filter(is_deleted=False)

class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['company', 'service_type', 'name', 'description', 'price', 'duration', 'is_active']
        widgets = {
            'company': Select(attrs={'class': 'form-control'}),
            'service_type': Select(attrs={'class': 'form-control'}),
            'name': TextInput(attrs={'class': 'form-control', 'placeholder': 'Service Name (e.g. Foam Wash)'}),
            'description': Textarea(attrs={'class': 'form-control', 'placeholder': 'Operation details...', 'rows': 3}),
            'price': NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'duration': NumberInput(attrs={'class': 'form-control', 'placeholder': 'Minutes'}),
            'is_active': CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['company'].queryset = Client.objects.filter(is_deleted=False)
        self.fields['service_type'].queryset = ServiceType.objects.filter(is_deleted=False)
