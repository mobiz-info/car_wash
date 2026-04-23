from django import forms
from django.forms import TextInput, Select
from .models import Client

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'company_name', 'owner_name', 'email', 'phone', 
            'address', 'status', 'gst_number', 'city', 
            'state', 'country'
        ]
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'status':
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'
                field.widget.attrs['placeholder'] = f"Enter {field.label}"
