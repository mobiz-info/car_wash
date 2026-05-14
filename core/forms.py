from django import forms
from django.forms import TextInput, Select
from django.contrib.auth.models import User
from .models import UserProfile, Role
from client_management.models import Client

class UserCreationAdminForm(forms.ModelForm):
    """Custom form to handle User creation specifically for the super admin portal"""
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'}),
        label="Confirm Password"
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'password': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create password'})
        }

    def __init__(self, *args, **kwargs):
        self.role = kwargs.pop('role', None)
        super().__init__(*args, **kwargs)

        if self.role and self.role.name.upper() == "COMPANY_ADMIN":
            self.fields['email'].required = False
            self.fields['first_name'].required = False
            self.fields['last_name'].required = False
            
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Passwords do not match.")
        
        if self.role and self.role.name.upper() == "COMPANY_ADMIN":
            company_id = self.data.get('company')
            
            if company_id:
                from client_management.models import Client
                try:
                    company = Client.objects.get(id=company_id)
                except Client.DoesNotExist:
                    self.add_error('company', "Invalid company selected.")
            else:
                self.add_error('company', "Company is required.")
            
            # Allow custom username, clear out other non-required fields
            cleaned_data['email'] = ''
            cleaned_data['first_name'] = ''
            cleaned_data['last_name'] = ''

        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'role', 'company']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'company': forms.Select(attrs={'class': 'form-control'})
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['company'].queryset = Client.objects.filter(
            is_deleted=False
        )
        
class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Role Name'})
        }


class UserEditForm(forms.ModelForm):
    """Form for editing an existing user (no password required)"""
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New password (leave blank to keep)'}),
        required=False,
        label='New Password'
    )
    role = forms.ModelChoiceField(
        queryset=Role.objects.filter(is_deleted=False),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False
    )
    company = forms.ModelChoiceField(
        queryset=Client.objects.filter(is_deleted=False),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            try:
                profile = self.instance.profile
                self.fields['role'].initial = profile.role
                self.fields['company'].initial = profile.company
            except Exception:
                pass

    def save(self, commit=True):
        user = super().save(commit=False)
        new_password = self.cleaned_data.get('new_password')
        if new_password:
            user.set_password(new_password)
        if commit:
            user.save()
            try:
                profile = user.profile
            except Exception:
                from .models import UserProfile
                profile = UserProfile(user=user)
            profile.role = self.cleaned_data.get('role')
            profile.company = self.cleaned_data.get('company')
            if new_password:
                profile.raw_password = new_password
            profile.save()
        return user
