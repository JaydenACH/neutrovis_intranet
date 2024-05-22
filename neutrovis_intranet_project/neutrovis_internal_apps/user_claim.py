# this .py file is to contain the functions to process data for UserClaim Model
import csv
import openpyxl
import os
from .models import UserClaim, Currency, UserClaimLine
from datetime import date, datetime, timedelta
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


def get_uc_number(rec_id: int) -> str:
    # current_count = UserClaim.objects.all().count() + 1
    year = date.today().year
    running_number = f"UC/{year}/{rec_id:05d}"
    return running_number


def convert_amount(curr_id: str, def_curr_id: int, amount: float) -> Decimal:
    target_currency = Currency.objects.get(id=int(curr_id))
    def_currency = Currency.objects.get(id=int(def_curr_id))
    amount = Decimal(amount)
    if target_currency and def_currency:
        rate = target_currency.exchange_rate
        def_rate = def_currency.exchange_rate
        act_amount = amount / rate * def_rate
        return Decimal(act_amount)
    return Decimal(amount)


def convert_custom_amount(rates: float, amount: float) -> Decimal:
    amount = Decimal(amount)
    rates = Decimal(rates)
    return Decimal(amount * rates)


def check_date(user_date: str) -> (bool, str):
    try:
        date_obj = datetime.strptime(user_date, '%Y-%m-%d')
        inv_date_obj = timezone.make_aware(date_obj, timezone.get_default_timezone())
        if inv_date_obj > timezone.now():
            return False, "Invoice date cannot be in the future!"
        return inv_date_obj, "OK"
    except ValueError:
        return False, "Invoice date format is wrong!"


def get_next_payment_date(today: date) -> date:
    if not isinstance(today, date):
        today = today.astimezone(timezone.get_current_timezone()).date()

    if today.day > 15:
        if today.month == 12:
            next_payment_date = date(today.year + 1, 1, 15)
        else:
            next_payment_date = date(today.year, today.month + 1, 15)
    else:
        temp_date = today.replace(day=28)
        next_month = temp_date + timedelta(days=4)
        next_payment_date = next_month - timedelta(days=next_month.day)
    return next_payment_date


def export_claim_to_excel(claim_ids: list) -> str:
    current_datetime = datetime.now()
    media_root = os.path.join(settings.MEDIA_ROOT, 'export_excel/')
    file_name = "claim_export_" + current_datetime.strftime("%Y%m%d_%H%M%S") + ".csv"
    file_path = media_root + file_name
    with open(file_path, mode="w", newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Reference', 'Requestor', 'Currency', 'Claim Amount', 'Analytic Code', 'Expense Code'])
        claims = UserClaim.objects.filter(id__in=claim_ids).prefetch_related('claim_lines')
        for claim in claims:
            claim_lines = claim.claim_lines.all()
            reference = claim.name
            requestor = claim.requestor
            for claim_line in claim_lines:
                currency = claim_line.currency
                claim_amount = claim_line.amount
                analytic_code = claim_line.analytic_code
                expense_type = claim_line.expense_type
                try:
                    writer.writerow([
                        reference, requestor,
                        currency, claim_amount,
                        analytic_code, expense_type,
                    ])
                except ValueError as e:
                    print(str(e))
    return file_name
