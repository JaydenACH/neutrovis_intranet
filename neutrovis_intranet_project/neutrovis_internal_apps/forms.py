from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.forms import SetPasswordForm, PasswordResetForm
from .models import (Currency, Attachment, ExpenseType, AnalyticCode, UserClaim,
                     Destination, Department, TravelRequest)
from django.db.models import Q
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox


class ExpenseTypeForm(forms.Form):
    expense_type = forms.CharField(required=True)
    name = forms.CharField(required=True)


class AnalyticCodeForm(forms.Form):
    code = forms.CharField(required=True)
    name = forms.CharField(required=True)


class DepartmentForm(forms.Form):
    name = forms.CharField(required=True)


class NewClaimLine(forms.Form):
    invoice_id = forms.CharField()
    invoice_date = forms.DateTimeField()
    invoice_description = forms.CharField()
    expense_type = forms.Select()
    analytic_code = forms.Select()
    amount = forms.DecimalField()
    currency = forms.Select()


class NewClaimForm(forms.Form):
    requestor = forms.CharField()
    status = forms.CharField()
    remarks = forms.Textarea()
    currency = forms.ModelChoiceField(queryset=Currency.objects.filter(active=True).order_by("symbol"),
                                      empty_label="Select Currency", required=False)
    expense_type = forms.ModelChoiceField(queryset=ExpenseType.objects.all(),
                                          empty_label="Select Expense Type")
    analytic_code = forms.ModelChoiceField(queryset=AnalyticCode.objects.all(),
                                           empty_label="Select Analytic Code")
    use_own_rate = forms.BooleanField(required=False, label='Use Own Rate')
    own_rate = forms.DecimalField(required=False)
    is_adv_payment = forms.BooleanField(required=False, label='Is this an advance payment?')
    has_adv_payment = forms.BooleanField(required=False, label='Has advance payment?')
    adv_claim = forms.ModelChoiceField(queryset=UserClaim.objects.filter(is_adv_payment=True).order_by("id"),
                                       required=False, empty_label="Select Previous Claims")
    travel_request = forms.ModelChoiceField(queryset=TravelRequest.objects.none(), required=False,
                                            empty_label="Select Travel Request")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("request_user", None)
        super(NewClaimForm, self).__init__(*args, **kwargs)
        self.fields['requestor'].widget.attrs.update({'hidden': True})
        self.fields['status'].widget.attrs.update({'hidden': True})
        def_currency = self.user.profile.default_currency
        if def_currency:
            self.fields['currency'].initial = def_currency.id
        self.fields['travel_request'].queryset = TravelRequest.objects.filter(
            Q(overlimit=False, status='Approved') | Q(overlimit=True, status='Sp. Approved'),
            requestor=self.user
        ).order_by('id')


class CurrencyForm(forms.Form):
    symbol = forms.CharField()
    symbol.widget.attrs.update({'class': 'newsymbol'})


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ('file',)


class ChatterForm(forms.Form):
    chat_message = forms.Textarea()

#
# class ExpenseBeneficiaryForm(forms.Form):
#     beneficiary = forms.CharField()
#     designation = forms.CharField()
#     title = forms.CharField()
#     company = forms.CharField()


class NewTravelRequestForm(forms.Form):
    departure = forms.ModelChoiceField(queryset=Destination.objects.all().order_by('destination'),
                                       empty_label="Select Departure")
    destination = forms.ModelChoiceField(queryset=Destination.objects.all().order_by('destination'),
                                         empty_label="Select Destination")


class ProfileForm(forms.Form):
    username = forms.CharField(label='Username')
    first_name = forms.CharField(label='First Name', required=False)
    last_name = forms.CharField(label='Last Name', required=False)
    email = forms.EmailField(label='Email Address', required=True)
    employee_id = forms.IntegerField(label='Employee ID', required=True)
    reporting_user = forms.ModelChoiceField(label='Reporting User', queryset=User.objects.all(), required=False)
    profile_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    default_currency = forms.ModelChoiceField(label='Default Currency',
                                              empty_label='Select Currency',
                                              queryset=Currency.objects.filter(active=True),
                                              required=False
                                              )
    department = forms.ModelChoiceField(label='Department',
                                        empty_label='Select Department',
                                        queryset=Department.objects.all(),
                                        required=False
                                        )
    is_active = forms.BooleanField(required=False)


class SetPasswordForm(SetPasswordForm):
    class Meta:
        model = get_user_model()
        fields = ["new_password1", "new_password2"]


class PasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super(PasswordResetForm, self).__init__(*args, **kwargs)

    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)
