from django import forms
from .models import Client, Subscription
from master.models import State, Area

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'company_name', 'owner_name', 'email', 'phone',
            'address', 'status', 'gst_number',
            'country', 'state', 'area',
            'logo_color', 'logo_bw' 
        ]
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initially show empty querysets for state/area (populated via JS)
        if not self.data.get('country'):
            self.fields['state'].queryset = State.objects.none()
        else:
            self.fields['state'].queryset = State.objects.filter(
                country_id=self.data.get('country'), is_deleted=False
            )
        if not self.data.get('state'):
            self.fields['area'].queryset = Area.objects.none()
        else:
            self.fields['area'].queryset = Area.objects.filter(
                district__state_id=self.data.get('state'), is_deleted=False
            )
        for field_name, field in self.fields.items():
            if field_name == 'status':
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'
                if not isinstance(field.widget, forms.Select):
                    field.widget.attrs['placeholder'] = f"Enter {field.label}"


class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = [
            'company', 'start_date', 'end_date', 'usage_fee', 'no_of_licenses',
            'whatsapp_integration', 'bulk_sms', 'email_integration',
            'bluetooth_printing', 'tally_integration',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['company'].queryset = Client.objects.filter(is_deleted=False).order_by('company_name')
        checkbox_fields = ['whatsapp_integration', 'bulk_sms', 'email_integration',
                           'bluetooth_printing', 'tally_integration']
        for field_name, field in self.fields.items():
            if field_name in checkbox_fields:
                field.widget.attrs['class'] = 'feature-checkbox'
            elif field_name not in ('start_date', 'end_date'):
                field.widget.attrs['class'] = 'form-control'
                if not isinstance(field.widget, forms.Select):
                    field.widget.attrs['placeholder'] = f"Enter {field.label}"

