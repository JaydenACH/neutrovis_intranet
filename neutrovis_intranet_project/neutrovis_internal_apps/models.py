from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import datetime
from django.conf import settings


class Currency(models.Model):

    def __str__(self):
        return f'{self.symbol}: {self.exchange_rate}'

    id = models.AutoField(primary_key=True)
    create_date = models.DateTimeField(auto_now_add=True)
    write_date = models.DateTimeField(auto_now=True)
    symbol = models.CharField(max_length=3)
    default = models.BooleanField(default=False)
    exchange_rate = models.DecimalField(decimal_places=5, max_digits=20, null=True)
    active = models.BooleanField(default=True)


class Department(models.Model):

    def __str__(self):
        return f'{self.name}'

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50, null=True)


class Profile(models.Model):

    def save(self, *args, **kwargs):
        if not self.default_currency_id:
            self.default_currency_id = Currency.objects.get(symbol="MYR").id
        super(Profile, self).save(*args, **kwargs)

    def __str__(self):
        return f'{self.user.first_name} {self.user.last_name}'

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    reporting_user = models.ForeignKey(User, on_delete=models.CASCADE,
                                       related_name="approver", null=True, blank=True)
    employee_id = models.IntegerField(null=True, blank=True, unique=True)
    default_currency = models.ForeignKey(Currency, on_delete=models.SET_NULL,
                                         related_name="def_currency", null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


class UserClaim(models.Model):
    def __str__(self):
        return f"{self.requestor.profile} - {self.name}"

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=13, null=True, blank=True)
    create_date = models.DateTimeField(auto_now_add=True)
    write_date = models.DateTimeField(auto_now=True)
    submit_date = models.DateTimeField()
    requestor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="requestor")
    total_amount = models.DecimalField(decimal_places=2, max_digits=20)
    is_adv_payment = models.BooleanField(default=False)
    has_adv_payment = models.BooleanField(default=False)
    adv_claim = models.ForeignKey('self', on_delete=models.SET_NULL, null=True,
                                  blank=True, related_name='advance_claim')
    adv_balance = models.DecimalField(decimal_places=2, max_digits=20, null=True)
    approval_date = models.DateTimeField(null=True)
    payment_date = models.DateField(null=True)
    status = models.CharField(max_length=10, choices=[
        ('Draft', 'Draft'),
        ('Submitted', 'Submitted'),
        ('Approved', 'Approved'),
        ('Verified', 'Verified'),
        ('Paid', 'Paid'),
        ('Rejected', 'Rejected'),
        ('Cancelled', 'Cancelled'),
    ])


class Attachment(models.Model):
    def __str__(self):
        return self.file.name

    def delete(self, *args, **kwargs):
        self.file.delete(save=False)
        super().delete(*args, **kwargs)

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    create_date = models.DateTimeField(auto_now_add=True)
    write_date = models.DateTimeField(auto_now=True)
    file = models.FileField(blank=True, upload_to='attachments/')


class ExpenseType(models.Model):
    def __str__(self):
        return f'{self.e_type} {self.name}'

    id = models.AutoField(primary_key=True)
    e_type = models.CharField(max_length=50, null=True, unique=True)
    name = models.CharField(max_length=100, unique=True)
    create_date = models.DateTimeField(auto_now_add=True)
    write_date = models.DateTimeField(auto_now=True)


class AnalyticCode(models.Model):
    def __str__(self):
        return f'{self.name}'

    id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=30, null=True, unique=True)
    name = models.CharField(max_length=150, null=True, unique=True)
    create_date = models.DateTimeField(auto_now_add=True)
    write_date = models.DateTimeField(auto_now=True)


class TravelRequest(models.Model):
    name = models.CharField(max_length=13, null=True, blank=True)
    create_date = models.DateTimeField(auto_now_add=True)
    write_date = models.DateTimeField(auto_now=True)
    approval_date = models.DateTimeField(null=True, blank=True)
    ol_approval_date = models.DateTimeField(null=True, blank=True)
    requestor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tr_requestor")
    approval = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tr_approval", null=True, blank=True)
    total_flight_expense = models.DecimalField(decimal_places=2, max_digits=20, null=True, blank=True)
    total_accomodation_expense = models.DecimalField(decimal_places=2, max_digits=20, null=True, blank=True)
    total_flight_limit = models.DecimalField(decimal_places=2, max_digits=20, null=True, blank=True)
    total_accomodation_limit = models.DecimalField(decimal_places=2, max_digits=20, null=True, blank=True)
    total_flight_expense_usd = models.DecimalField(decimal_places=2, max_digits=20, null=True, blank=True)
    total_accomodation_expense_usd = models.DecimalField(decimal_places=2, max_digits=20, null=True, blank=True)
    total_flight_limit_usd = models.DecimalField(decimal_places=2, max_digits=20, null=True, blank=True)
    total_accomodation_limit_usd = models.DecimalField(decimal_places=2, max_digits=20, null=True, blank=True)
    remark = models.TextField(max_length=1000, null=True, blank=True)
    overlimit = models.BooleanField(default=False)
    status = models.CharField(max_length=15, choices=[
        ('Draft', 'Draft'),
        ('Submitted', 'Submitted'),
        ('Approved', 'Approved'),
        ('Sp. Approved', 'Sp. Approved'),
    ])

    def __str__(self):
        return f"{self.name} by {self.requestor}"


class UserClaimLine(models.Model):
    def __str__(self):
        return f"{self.claim.requestor} / {self.claim.name} / {self.invoice_id}"

    id = models.AutoField(primary_key=True)
    create_date = models.DateTimeField(auto_now_add=True)
    write_date = models.DateTimeField(auto_now=True)
    claim = models.ForeignKey(UserClaim, on_delete=models.CASCADE, related_name="claim_lines")
    invoice_date = models.DateField()
    invoice_id = models.CharField(max_length=100, null=True)
    invoice_description = models.CharField(max_length=100)
    attachment = models.ForeignKey(Attachment, on_delete=models.CASCADE, related_name="attachment")
    expense_type = models.ForeignKey(ExpenseType, on_delete=models.PROTECT, related_name="expense_type", null=True)
    analytic_code = models.ForeignKey(AnalyticCode, on_delete=models.PROTECT, related_name="analytic_code", null=True)
    amount = models.DecimalField(decimal_places=2, max_digits=20)
    # amount_myr is being used as user's default currency amount
    amount_myr = models.DecimalField(decimal_places=2, max_digits=20, default=0)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="currency", null=True)
    use_own_rate = models.BooleanField(default=False)
    own_rate = models.DecimalField(decimal_places=5, max_digits=20, null=True)
    remark = models.TextField(max_length=1000, null=True, blank=True,
                              help_text="Add remarks like the beneficiary of the expense")
    travel_request = models.ForeignKey(TravelRequest, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name="ucl_travel_request")


class SystemParameter(models.Model):

    def __str__(self):
        return f'{self.key}: {self.value}'

    id = models.AutoField(primary_key=True)
    create_date = models.DateTimeField(auto_now_add=True)
    write_date = models.DateTimeField(auto_now=True)
    last_modified = models.ForeignKey(User, on_delete=models.CASCADE, related_name="modified_by", null=True)
    key = models.CharField(max_length=100, null=True)
    value = models.CharField(max_length=100, null=True)


class ChatterBox(models.Model):
    def __str__(self):
        return f"{self.claim_id.name} by {self.chat_user}"

    id = models.AutoField(primary_key=True)
    create_date = models.DateTimeField(auto_now_add=True)
    claim_id = models.ForeignKey(UserClaim, on_delete=models.CASCADE, related_name="claims_chat")
    chat_user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name="chatter")
    message = models.TextField(max_length=350)

#
# class ExpenseBeneficiary(models.Model):
#     def __str__(self):
#         return f"{self.claim_line_id.claim.name} / {self.claim_line_id.invoice_id}"
#
#     create_date = models.DateTimeField(auto_now_add=True)
#     write_date = models.DateTimeField(auto_now=True)
#     claim_line_id = models.ForeignKey(UserClaimLine, on_delete=models.CASCADE, related_name="claim_line_beneficiary")
#     beneficiary = models.CharField(max_length=100)
#     title = models.CharField(max_length=10)
#     designation = models.CharField(max_length=150)
#     company = models.CharField(max_length=150)


'''
Below are the models declaration for travel request
'''



class Destination(models.Model):
    def __str__(self):
        return f"{self.destination} ({self.currency.symbol})"

    destination = models.CharField(max_length=100)
    grouping = models.CharField(max_length=100)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name="destination_currency", null=True)


class AllowanceLimit(models.Model):
    def __str__(self):
        return f"{self.destination}: {self.currency.symbol} ({self.flight_allowance}, {self.accomodation_allowance})"

    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name="tr_destination")
    flight_allowance = models.IntegerField()
    accomodation_allowance = models.IntegerField()
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name="allowance_currency")


class TravelRequestLine(models.Model):
    def __str__(self):
        return f"{self.travel_request} by {self.travel_request.requestor} to {self.destination}"

    travel_request = models.ForeignKey(TravelRequest, on_delete=models.CASCADE, related_name="travel_request")
    travel_start_date = models.DateField()
    travel_end_date = models.DateField()
    departure = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name="trl_departure", null=True)
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name="trl_destination")
    flight_currency = models.ForeignKey(Currency, on_delete=models.CASCADE,
                                        related_name="trl_flight_currency", null=True)
    accomodation_currency = models.ForeignKey(Currency, on_delete=models.CASCADE,
                                              related_name="trl_accomodation_currency", null=True)
    flight_limit = models.DecimalField(decimal_places=2, max_digits=20, null=True, blank=True)
    accomodation_limit = models.DecimalField(decimal_places=2, max_digits=20, null=True, blank=True)
    estimated_flight_expense = models.DecimalField(decimal_places=2, max_digits=20, null=True, blank=True)
    estimated_accomodation_expense = models.DecimalField(decimal_places=2, max_digits=20, null=True, blank=True)
    overlimit = models.BooleanField(default=False)


class SupportingDocument(models.Model):
    def __str__(self):
        return self.file.name

    def delete(self, *args, **kwargs):
        self.file.delete(save=False)
        super().delete(*args, **kwargs)

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    create_date = models.DateTimeField(auto_now_add=True)
    write_date = models.DateTimeField(auto_now=True)
    file = models.FileField(blank=True, upload_to='tr_attachments/')
