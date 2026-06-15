from django import forms
from django.forms import TextInput, Select, Textarea, NumberInput, CheckboxInput
from .models import *


class HolidayCalendarForm(forms.ModelForm):

    class Meta:
        model = HolidayCalendar
        fields = [
            'branch',
            'holiday_date',
            'repeat_yearly'
        ]

        widgets = {
            'branch': forms.Select(
                attrs={'class': 'form-control'}
            ),
            'holiday_date': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date'
                }
            ),
            'repeat_yearly': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)

        super().__init__(*args, **kwargs)

        if user:
            role = getattr(
                getattr(user, 'profile', None),
                'role',
                None
            )

            role_name = role.name if role else None

            if role_name == 'COMPANY_ADMIN':

                company = getattr(
                    user.profile,
                    'company',
                    None
                )

                self.fields['branch'].queryset = Branch.objects.filter(
                    company=company,
                    is_deleted=False
                )

            else:

                branch = getattr(
                    user,
                    'managed_branch',
                    None
                )

                self.fields['branch'].queryset = Branch.objects.filter(
                    id=branch.id,
                    is_deleted=False
                ) if branch else Branch.objects.none()