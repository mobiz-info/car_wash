from django import forms
from .models import *
from master.models import State, Area,SchemeType

class ClientForm(forms.ModelForm):
    scheme_types = forms.ModelMultipleChoiceField(
        queryset=SchemeType.objects.filter(is_deleted=False),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Client
        fields = [
            'company_name', 'business_name', 'owner_name',
            'email', 'phone', 'address',
            'gst_number',
            'country', 'state', 'area',

            'licenses_count', 'max_branches',
            'monthly_tariff', 'next_renewal_date',

            'scheme_types',

            'status', 'logo_color', 'logo_bw'
        ]
        widgets = {
            'next_renewal_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
        }
            
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

from django.contrib.auth.models import User
from core.models import UserProfile, Role
from core.functions import get_auto_id

class BranchForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150, 
        required=True, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter branch username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create password'}),
        required=False  # Required only on creation, not edit
    )
    scheme_types = forms.ModelMultipleChoiceField(
        queryset=SchemeType.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    class Meta:
        model = Branch
        fields = ['name', 'address', 'phone', 'email', 'gst_number', 'website', 'logo','scheme_types']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ['logo', 'username', 'password', 'scheme_types']:
                field.widget.attrs['class'] = 'form-control'
                if not isinstance(field.widget, forms.Select) and not isinstance(field.widget, forms.Textarea):
                    field.widget.attrs['placeholder'] = f"Enter {field.label}"
        self.fields['scheme_types'].widget.attrs.update({'class': 'form-check-input'})
        if self.instance and not self.instance._state.adding:
            if self.instance.branch_admin:
                self.fields['username'].initial = self.instance.branch_admin.username
            self.fields['password'].required = False
        else:
            self.fields['password'].required = True

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if self.instance._state.adding or (self.instance.branch_admin and self.instance.branch_admin.username != username):
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError("Username already exists.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        if self.instance._state.adding:
            try:
                company = self.request.user.profile.company
                if company and company.max_branches is not None:
                    current_count = Branch.objects.filter(company=company, is_deleted=False).count()
                    if current_count >= company.max_branches:
                        raise forms.ValidationError(f"Your company has reached the maximum limit of {company.max_branches} branches.")
            except AttributeError:
                pass
        return cleaned_data

    def save(self, commit=True):
        branch = super().save(commit=False)
        company = self.request.user.profile.company
        branch.company = company
        
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if branch._state.adding:
            # Creating new branch & user
            user = User.objects.create_user(username=username, password=password)
            role, _ = Role.objects.get_or_create(
                name='BRANCH_ADMIN', 
                defaults={'auto_id': get_auto_id(Role)}
            )
            
            # Create user profile
            UserProfile.objects.create(
                user=user,
                role=role,
                company=company,
                auto_id=get_auto_id(UserProfile),
                creator=self.request.user
            )
            branch.branch_admin = user
        else:
            # Updating existing branch
            if branch.branch_admin:
                user = branch.branch_admin
                user.username = username
                if password:
                    user.set_password(password)
                user.save()

        if commit:
            branch.save()
            self.save_m2m()
            
        return branch

class StaffForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150, 
        required=True, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create password'}),
        required=False
    )

    class Meta:
        model = Staff
        fields = ['branch', 'designation', 'name', 'phone']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Restrict branches
        if self.request and hasattr(self.request.user, 'profile') and self.request.user.profile.company:
            if self.request.user.profile.role.name == 'BRANCH_ADMIN' and hasattr(self.request.user, 'managed_branch'):
                self.fields['branch'].queryset = Branch.objects.filter(
                    id=self.request.user.managed_branch.id,
                    is_deleted=False
                )
                self.fields['branch'].initial = self.request.user.managed_branch.id
                self.fields['branch'].widget = forms.HiddenInput()
            else:
                self.fields['branch'].queryset = Branch.objects.filter(
                    company=self.request.user.profile.company, 
                    is_deleted=False
                )
            
        for field_name, field in self.fields.items():
            if field_name not in ['username', 'password']:
                field.widget.attrs['class'] = 'form-control'
                if not isinstance(field.widget, forms.Select):
                    field.widget.attrs['placeholder'] = f"Enter {field.label}"
        
        if self.instance and not self.instance._state.adding:
            if self.instance.user:
                self.fields['username'].initial = self.instance.user.username
            self.fields['password'].required = False
        else:
            self.fields['password'].required = True

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if self.instance._state.adding or (self.instance.user and self.instance.user.username != username):
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError("Username already exists.")
        return username

    def save(self, commit=True):
        staff = super().save(commit=False)
        company = self.request.user.profile.company
        staff.company = company
        
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if staff._state.adding:
            # Generate employee_id
            last_staff = Staff.objects.all().order_by('-id').first()
            if last_staff and last_staff.employee_id and last_staff.employee_id.startswith('EMP-'):
                try:
                    last_id = int(last_staff.employee_id.split('-')[1])
                    staff.employee_id = f"EMP-{last_id + 1:04d}"
                except ValueError:
                    staff.employee_id = f"EMP-{Staff.objects.count() + 1:04d}"
            else:
                staff.employee_id = f"EMP-{Staff.objects.count() + 1:04d}"

            # Create User
            user = User.objects.create_user(username=username, password=password)
            
            # Map designation to a role name
            designation_to_role = {
                'BRANCH_MANAGER': 'BRANCH_MANAGER',
                'MARKETING': 'MARKETING',
                'CLERICAL': 'CLERICAL',
                'SERVICE': 'SERVICE'
            }
            role_name = designation_to_role.get(staff.designation, staff.designation)
            role, _ = Role.objects.get_or_create(
                name=role_name,
                defaults={'auto_id': get_auto_id(Role)}
            )
            
            UserProfile.objects.create(
                user=user,
                role=role,
                company=company,
                auto_id=get_auto_id(UserProfile),
                creator=self.request.user
            )
            staff.user = user
        else:
            if staff.user:
                user = staff.user
                user.username = username
                if password:
                    user.set_password(password)
                user.save()
                
                # Update role if designation changed
                designation_to_role = {
                    'BRANCH_MANAGER': 'BRANCH_MANAGER',
                    'MARKETING': 'MARKETING',
                    'CLERICAL': 'CLERICAL',
                    'SERVICE': 'SERVICE'
                }
                role_name = designation_to_role.get(staff.designation, staff.designation)
                role, _ = Role.objects.get_or_create(
                    name=role_name,
                    defaults={'auto_id': get_auto_id(Role)}
                )
                
                profile = user.profile
                if profile.role != role:
                    profile.role = role
                    profile.save()

        if commit:
            staff.save()
            
        return staff

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

from .models import Customer, CustomerVehicle
from master.models import VehicleTypeModel

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['branch', 'name', 'phone', 'customer_type', 'whatsapp_number', 'email', 'address', 'pincode']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
        
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Restrict branches based on role
        if self.request and hasattr(self.request.user, 'profile') and self.request.user.profile.company:
            if self.request.user.profile.role.name == 'BRANCH_ADMIN' and hasattr(self.request.user, 'managed_branch'):
                self.fields['branch'].queryset = Branch.objects.filter(
                    id=self.request.user.managed_branch.id,
                    is_deleted=False
                )
                self.fields['branch'].initial = self.request.user.managed_branch.id
                self.fields['branch'].widget = forms.HiddenInput()
            else:
                self.fields['branch'].queryset = Branch.objects.filter(
                    company=self.request.user.profile.company, 
                    is_deleted=False
                )
                
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            if not isinstance(field.widget, forms.Select) and not isinstance(field.widget, forms.Textarea):
                field.widget.attrs['placeholder'] = f"Enter {field.label}"

from master.models import VehicleType, VehicleTypeModel

class CustomerVehicleForm(forms.ModelForm):
    vehicle_type = forms.ModelChoiceField(
        queryset=VehicleType.objects.filter(is_active=True),
        required=True,
        empty_label="---------",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = CustomerVehicle
        fields = ['vehicle_type', 'vehicle_type_model', 'vehicle_number']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            # Disable HTML5 validation so the browser doesn't block hidden inputs
            if field.required:
                field.widget.attrs['required'] = False
            if not isinstance(field.widget, forms.Select):
                field.widget.attrs['placeholder'] = f"Enter {field.label}"
                
        # Handle dynamic vehicle model selection
        if 'vehicle_type' in self.data:
            try:
                vehicle_type_id = int(self.data.get('vehicle_type'))
                self.fields['vehicle_type_model'].queryset = VehicleTypeModel.objects.filter(vehicle_type_id=vehicle_type_id, is_active=True).order_by('name')
            except (ValueError, TypeError):
                pass
        elif not self.instance._state.adding and getattr(self.instance, 'vehicle_type_model_id', None):
            self.fields['vehicle_type'].initial = self.instance.vehicle_type_model.vehicle_type.id
            self.fields['vehicle_type_model'].queryset = self.instance.vehicle_type_model.vehicle_type.models.filter(is_active=True).order_by('name')
        else:
            self.fields['vehicle_type_model'].queryset = VehicleTypeModel.objects.none()


class CustomerTypeForm(forms.ModelForm):
    class Meta:
        model = CustomerType
        fields = ['name']


from .models import Scheme
from master.models import SchemeType
from service_management.models import Service

class SchemeForm(forms.ModelForm):
    class Meta:
        model = Scheme
        fields = ['scheme_type', 'name', 'start_date', 'end_date',
                  'services', 'customer_types', 'vehicle_types',
                  'paid_visits', 'free_visits', 'discount_percentage']
        widgets = {
            'scheme_type': forms.Select(attrs={'class': 'form-control', 'id': 'id_scheme_type'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Scheme Name'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'paid_visits': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'No. of Paid Visits', 'min': 1}),
            'free_visits': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'No. of Free Visits', 'min': 1}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Discount %', 'min': 0, 'max': 100, 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make benefit and selection fields optional — view handles validation
        for f in ['paid_visits', 'free_visits', 'discount_percentage', 'services', 'customer_types', 'vehicle_types']:
            self.fields[f].required = False
            
class CustomersVehicleForm(forms.ModelForm):
    class Meta:
        model = CustomerVehicle
        fields = ['customer', 'vehicle_type', 'vehicle_type_model', 'vehicle_number']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 🚨 IMPORTANT: Always set queryset based on POST or instance
        if self.data:
            vehicle_type_id = self.data.get('vehicle_type')

            if vehicle_type_id:
                self.fields['vehicle_type_model'].queryset = VehicleTypeModel.objects.filter(
                    vehicle_type_id=vehicle_type_id
                )
            else:
                self.fields['vehicle_type_model'].queryset = VehicleTypeModel.objects.none()

        elif self.instance.pk and self.instance.vehicle_type:
            self.fields['vehicle_type_model'].queryset = VehicleTypeModel.objects.filter(
                vehicle_type=self.instance.vehicle_type
            )
        else:
            self.fields['vehicle_type_model'].queryset = VehicleTypeModel.objects.none()