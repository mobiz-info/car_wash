from django import forms
from .models import *
from master.models import State, Area, SchemeType, VehicleType
from service_management.models import Service

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
            'country', 'state', 'district', 'area',

            'licenses_count', 'max_branches',
            'monthly_tariff', 
            'scheme_types',

            'status', 'logo_color', 'logo_bw'
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
            
        # Restrict scheme_types to the company's allowed schemes
        if self.request and hasattr(self.request.user, 'profile') and self.request.user.profile.company:
            self.fields['scheme_types'].queryset = self.request.user.profile.company.scheme_types.filter(is_deleted=False)
        else:
            self.fields['scheme_types'].queryset = SchemeType.objects.none()

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
                creator=self.request.user,
                raw_password=password
            )
            branch.branch_admin = user
        else:
            # Updating existing branch
            if branch.branch_admin:
                user = branch.branch_admin
                user.username = username
                if password:
                    user.set_password(password)
                    if hasattr(user, 'profile'):
                        user.profile.raw_password = password
                        user.profile.save()
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
        fields = ['branch', 'designation', 'name', 'phone', 'salary_mode', 'monthly_salary', 'daily_wage']

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
        
        # Widget overrides for salary fields
        self.fields['salary_mode'].widget.attrs['class'] = 'form-control'
        self.fields['monthly_salary'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Enter monthly salary'})
        self.fields['daily_wage'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Enter daily wage'})
        self.fields['monthly_salary'].required = False
        self.fields['daily_wage'].required = False
        if self.instance and not self.instance._state.adding:
            if self.instance.user:
                self.fields['username'].initial = self.instance.user.username
            self.fields['password'].required = False
            # Remove salary fields on edit to prevent overwriting
            for f in ['salary_mode', 'monthly_salary', 'daily_wage']:
                if f in self.fields:
                    del self.fields[f]
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
            import re
            max_num = 0
            manager = getattr(Staff, 'all_objects', Staff._base_manager)
            for s in manager.filter(employee_id__startswith='EMP-'):
                match = re.match(r'^EMP-(\d+)$', s.employee_id)
                if match:
                    try:
                        num = int(match.group(1))
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        pass
            
            staff.employee_id = f"EMP-{max_num + 1:04d}"

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

    def save_commissions(self, staff, commission_data):
        """
        Save commission records.
        commission_data: list of dicts with keys:
            service_id, vehicle_type_id, commission_type, amount
        """
        # Remove old commissions for this staff
        StaffCommission.objects.filter(staff=staff).delete()
        for row in commission_data:
            service_id = row.get('service_id')
            vehicle_type_id = row.get('vehicle_type_id')
            commission_type = row.get('commission_type', 'PERCENTAGE')
            amount = row.get('amount', 0)
            if service_id and vehicle_type_id and amount:
                try:
                    StaffCommission.objects.create(
                        staff=staff,
                        service_id=service_id,
                        vehicle_type_id=vehicle_type_id,
                        commission_type=commission_type,
                        amount=amount,
                        auto_id=get_auto_id(StaffCommission),
                        creator=self.request.user,
                    )
                except Exception:
                    pass

class StaffSalaryForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = ['salary_mode', 'monthly_salary', 'daily_wage']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.fields['salary_mode'].widget.attrs['class'] = 'form-control'
        self.fields['monthly_salary'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Enter monthly salary'})
        self.fields['daily_wage'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Enter daily wage'})
        self.fields['monthly_salary'].required = False
        self.fields['daily_wage'].required = False

    def save_commissions(self, staff, commission_data):
        StaffCommission.objects.filter(staff=staff).delete()
        for row in commission_data:
            service_id = row.get('service_id')
            vehicle_type_id = row.get('vehicle_type_id')
            commission_type = row.get('commission_type', 'PERCENTAGE')
            amount = row.get('amount', 0)
            if service_id and vehicle_type_id and amount:
                try:
                    StaffCommission.objects.create(
                        staff=staff,
                        service_id=service_id,
                        vehicle_type_id=vehicle_type_id,
                        commission_type=commission_type,
                        amount=amount,
                        auto_id=get_auto_id(StaffCommission),
                        creator=self.request.user,
                    )
                except Exception:
                    pass

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

class RenewalForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    usage_fee = forms.DecimalField(max_digits=10, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    no_of_licenses = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs={'class': 'form-control'}))

    # Feature flags
    whatsapp_integration = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'feature-checkbox'}))
    bulk_sms = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'feature-checkbox'}))
    email_integration = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'feature-checkbox'}))
    bluetooth_printing = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'feature-checkbox'}))
    tally_integration = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'feature-checkbox'}))

    # Payment/Transaction Details
    payment_method = forms.ChoiceField(
        choices=[
            ('Cash', 'Cash'),
            ('UPI', 'UPI'),
            ('Card', 'Card'),
            ('Bank Transfer', 'Bank Transfer'),
            ('Online', 'Online Payment'),
            ('Other', 'Other')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    amount_paid = forms.DecimalField(max_digits=10, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    transaction_id = forms.CharField(required=False, max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional reference/TXN ID'}))
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional notes'}))


from .models import Customer, CustomerVehicle
from master.models import VehicleType, VehicleTypeModel, VehicleBrandModel

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
        queryset=VehicleType.objects.filter(is_active=True, is_deleted=False),
        required=True,
        empty_label="---------",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = CustomerVehicle
        fields = ['vehicle_type', 'vehicle_type_model', 'vehicle_number', 'color', 'brand_model']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            # Disable HTML5 validation so the browser doesn't block hidden inputs
            if field.required:
                field.widget.attrs['required'] = False
            if not isinstance(field.widget, forms.Select):
                field.widget.attrs['placeholder'] = f"Enter {field.label}"
                
        if 'vehicle_type' in self.data:
            try:
                vehicle_type_id = int(self.data.get('vehicle_type'))
                self.fields['vehicle_type_model'].queryset = VehicleTypeModel.objects.filter(vehicle_type_id=vehicle_type_id, is_active=True, is_deleted=False).order_by('name')
            except (ValueError, TypeError):
                pass
        elif not self.instance._state.adding and getattr(self.instance, 'vehicle_type_model_id', None):
            self.fields['vehicle_type'].initial = self.instance.vehicle_type_model.vehicle_type.id
            self.fields['vehicle_type_model'].queryset = self.instance.vehicle_type_model.vehicle_type.models.filter(is_active=True, is_deleted=False).order_by('name')
        else:
            self.fields['vehicle_type_model'].queryset = VehicleTypeModel.objects.none()

        if 'vehicle_type_model' in self.data:
            try:
                vehicle_type_model_id = int(self.data.get('vehicle_type_model'))
                self.fields['brand_model'].queryset = VehicleBrandModel.objects.filter(vehicle_type_model_id=vehicle_type_model_id, is_active=True, is_deleted=False).order_by('name')
            except (ValueError, TypeError):
                pass
        elif not self.instance._state.adding and getattr(self.instance, 'vehicle_type_model_id', None):
            self.fields['brand_model'].queryset = self.instance.vehicle_type_model.brand_models.filter(is_active=True, is_deleted=False).order_by('name')
        else:
            self.fields['brand_model'].queryset = VehicleBrandModel.objects.none()


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
        fields = ['customer', 'vehicle_type', 'vehicle_type_model', 'make', 'vehicle_number', 'color', 'brand_model']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

        if self.request:
            try:
                user_profile = self.request.user.profile
                user_role = user_profile.role.name

                # default branch
                branch = None

                if user_role == 'BRANCH_ADMIN' and hasattr(self.request.user, 'managed_branch'):
                    branch = self.request.user.managed_branch
                else:
                    branch = user_profile.branch  # adjust if your profile has branch FK

                self.fields['customer'].queryset = Customer.objects.filter(
                    is_deleted=False,
                    branch=branch
                ).order_by('name')

            except AttributeError:
                self.fields['customer'].queryset = Customer.objects.none()

        # 🚨 IMPORTANT: Always set queryset based on POST or instance
        if self.data:
            vehicle_type_id = self.data.get('vehicle_type')

            if vehicle_type_id:
                self.fields['vehicle_type_model'].queryset = VehicleTypeModel.objects.filter(
                    vehicle_type_id=vehicle_type_id,
                    is_active=True,
                    is_deleted=False
                )
            else:
                self.fields['vehicle_type_model'].queryset = VehicleTypeModel.objects.none()

        elif self.instance.pk and self.instance.vehicle_type:
            self.fields['vehicle_type_model'].queryset = VehicleTypeModel.objects.filter(
                vehicle_type=self.instance.vehicle_type,
                is_active=True,
                is_deleted=False
            )
        else:
            self.fields['vehicle_type_model'].queryset = VehicleTypeModel.objects.none()

        from master.models import VehicleMake
        # make queryset
        if self.data:
            vehicle_type_model_id = self.data.get('vehicle_type_model')
            if vehicle_type_model_id:
                self.fields['make'].queryset = VehicleMake.objects.filter(
                    models__vehicle_type_model_id=vehicle_type_model_id,
                    is_active=True,
                    is_deleted=False
                ).distinct().order_by('name')
            else:
                self.fields['make'].queryset = VehicleMake.objects.none()
        elif self.instance.pk and self.instance.vehicle_type_model:
            self.fields['make'].queryset = VehicleMake.objects.filter(
                models__vehicle_type_model=self.instance.vehicle_type_model,
                is_active=True,
                is_deleted=False
            ).distinct().order_by('name')
        else:
            self.fields['make'].queryset = VehicleMake.objects.none()

        self.fields['make'].required = False
        self.fields['make'].empty_label = '---------'

        # brand model queryset
        if self.data:
            vehicle_type_model_id = self.data.get('vehicle_type_model')
            make_id = self.data.get('make')
            if vehicle_type_model_id:
                qs = VehicleBrandModel.objects.filter(
                    vehicle_type_model_id=vehicle_type_model_id,
                    is_active=True,
                    is_deleted=False
                )
                if make_id:
                    qs = qs.filter(make_id=make_id)
                self.fields['brand_model'].queryset = qs.order_by('name')
            else:
                self.fields['brand_model'].queryset = VehicleBrandModel.objects.none()
        elif self.instance.pk and self.instance.vehicle_type_model:
            qs = VehicleBrandModel.objects.filter(
                vehicle_type_model=self.instance.vehicle_type_model,
                is_active=True,
                is_deleted=False
            )
            if self.instance.make:
                qs = qs.filter(make=self.instance.make)
            self.fields['brand_model'].queryset = qs.order_by('name')
        else:
            self.fields['brand_model'].queryset = VehicleBrandModel.objects.none()



class WhatsAppSettingForm(forms.ModelForm):
    class Meta:
        model = WhatsAppSetting
        fields = ['url', 'username', 'password', 'sender_id', 'whatsapp_number', 'is_official_api']
        widgets = {
            'url': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter WhatsApp API Url'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter WhatsApp username'}),
            'password': forms.PasswordInput(render_value=True, attrs={'class': 'form-control', 'placeholder': 'Enter WhatsApp password'}),
            'sender_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter WhatsApp Sender ID'}),
            'whatsapp_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter WhatsApp Sender Number (with country code)'}),
            'is_official_api': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'is_official_api': 'Is Official Cloud API (Requires Templates)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'is_official_api':
                continue
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class WhatsAppTypeForm(forms.ModelForm):
    class Meta:
        model = WhatsAppType
        fields = ['name', 'account', 'message_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Type/Category Name'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Populate account choices dynamically from WhatsAppSetting
        account_choices = [("", "Select A/c")]
        if self.request and hasattr(self.request.user, 'profile') and self.request.user.profile.company:
            company = self.request.user.profile.company
            settings = WhatsAppSetting.objects.filter(company=company)
            for s in settings:
                if s.username:
                    account_choices.append((s.username, f"{s.username} ({s.sender_id or 'No Sender ID'})"))
        self.fields['account'] = forms.ChoiceField(
            choices=account_choices,
            required=False,
            widget=forms.Select(attrs={'class': 'form-control'})
        )
        
        # Populate message type choices
        message_type_choices = [
            ("", "Select Message Type"),
            ("Text", "Text"),
            ("Media", "Media"),
            ("Template", "Template"),
            ("Utility", "Utility"),
            ("Marketing", "Marketing"),
            ("Authentication", "Authentication")
        ]
        self.fields['message_type'] = forms.ChoiceField(
            choices=message_type_choices,
            required=True,
            widget=forms.Select(attrs={'class': 'form-control'})
        )
        
        for field_name, field in self.fields.items():
            if field_name not in ['account', 'message_type']:
                if 'class' not in field.widget.attrs:
                    field.widget.attrs['class'] = 'form-control'


class WhatsAppTemplateForm(forms.ModelForm):
    class Meta:
        model = WhatsAppTemplate
        fields = ['whatsapp_type', 'template_name', 'content']
        widgets = {
            'whatsapp_type': forms.Select(attrs={'class': 'form-control'}),
            'template_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter template name'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter template content', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if self.request and hasattr(self.request.user, 'profile') and self.request.user.profile.company:
            company = self.request.user.profile.company
            self.fields['whatsapp_type'].queryset = WhatsAppType.objects.filter(company=company)
        else:
            self.fields['whatsapp_type'].queryset = WhatsAppType.objects.none()
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class WhatsAppComposeForm(forms.ModelForm):
    class Meta:
        model = WhatsAppMessage
        fields = ['whatsapp_type', 'message', 'attachment']
        widgets = {
            'whatsapp_type': forms.Select(attrs={'class': 'form-control'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter message content', 'rows': 4}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if self.request and hasattr(self.request.user, 'profile') and self.request.user.profile.company:
            company = self.request.user.profile.company
            self.fields['whatsapp_type'].queryset = WhatsAppType.objects.filter(company=company)
        else:
            self.fields['whatsapp_type'].queryset = WhatsAppType.objects.none()
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'



class StockForm(forms.ModelForm):
    class Meta:
        model = Stock
        fields = ['item_name', 'unit', 'expense_head']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filter expense head queryset by company
        from master.models import ExpenseHead
        from django.db.models import Q
        if self.request and hasattr(self.request.user, 'profile') and self.request.user.profile.company:
            company = self.request.user.profile.company
            self.fields['expense_head'].queryset = ExpenseHead.objects.filter(
                Q(company=company) | Q(company__isnull=True),
                is_deleted=False
            ).order_by('name')
        else:
            self.fields['expense_head'].queryset = ExpenseHead.objects.filter(is_deleted=False).order_by('name')

        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            if field_name != 'expense_head':
                field.widget.attrs['placeholder'] = f"Enter {field.label}"


from .models import StaffLeave

class StaffLeaveForm(forms.ModelForm):
    class Meta:
        model = StaffLeave
        fields = ['staff', 'start_date', 'end_date', 'reason', 'remarks', 'status']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Enter reason for leave'}),
            'remarks': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Enter remarks'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Restrict staffs based on the user's company and branch
        if self.request and hasattr(self.request.user, 'profile') and self.request.user.profile.company:
            company = self.request.user.profile.company
            staff_qs = Staff.objects.filter(company=company, is_deleted=False)
            if self.request.user.profile.role.name == 'BRANCH_ADMIN' and hasattr(self.request.user, 'managed_branch'):
                staff_qs = staff_qs.filter(branch=self.request.user.managed_branch)
            self.fields['staff'].queryset = staff_qs.order_by('name')
        
        for field_name, field in self.fields.items():
            if field_name not in ['start_date', 'end_date', 'reason', 'remarks', 'status']:
                field.widget.attrs['class'] = 'form-control'


class PurchaseRequestForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        fields = ['date', 'material', 'qty', 'status', 'remarks']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'material': forms.Select(attrs={'class': 'form-control'}),
            'qty': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Enter remarks'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        
        if self.request and hasattr(self.request.user, 'profile') and self.request.user.profile.company:
            company = self.request.user.profile.company
            stock_qs = Stock.objects.filter(
                Q(company=company) | Q(company__isnull=True),
                is_deleted=False
            )
            self.fields['material'].queryset = stock_qs.order_by('item_name')
        
        for field_name, field in self.fields.items():
            if field_name not in ['date', 'material', 'qty', 'status', 'remarks']:
                field.widget.attrs['class'] = 'form-control'


class FirebaseSettingForm(forms.ModelForm):
    class Meta:
        model = FirebaseSetting
        fields = ['api_key', 'project_id', 'messaging_sender_id', 'app_id', 'server_key']
        widgets = {
            'api_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Firebase API Key'}),
            'project_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Project ID'}),
            'messaging_sender_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Messaging Sender ID'}),
            'app_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter App ID'}),
            'server_key': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter Server Key / Service Account JSON', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class BulkSmsSettingForm(forms.ModelForm):
    class Meta:
        model = BulkSmsSetting
        fields = ['api_key', 'sender_id', 'sms_url']
        widgets = {
            'api_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Bulk SMS API Key'}),
            'sender_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Sender ID'}),
            'sms_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Enter Gateway SMS URL'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class GmailCredentialForm(forms.ModelForm):
    class Meta:
        model = GmailCredential
        fields = ['email_address', 'app_password', 'smtp_server', 'smtp_port']
        widgets = {
            'email_address': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter Gmail Address'}),
            'app_password': forms.PasswordInput(render_value=True, attrs={'class': 'form-control', 'placeholder': 'Enter Gmail App Password'}),
            'smtp_server': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter SMTP Server (default: smtp.gmail.com)'}),
            'smtp_port': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter SMTP Port (default: 587)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'