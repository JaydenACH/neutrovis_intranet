import json
import os
import requests
import smtplib
from dotenv import load_dotenv
from stronghold.decorators import public
from neutrovis_internal_project.settings import EMAIL_HOST_USER
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, FileResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDictKeyError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from decimal import Decimal
from .email_template import (notification_reject_sc, notification_approval_sc,
                             notification_submission_sc, notification_verified_sc, password_reset_email)
from .models import (Attachment, UserClaim, UserClaimLine, Currency, ChatterBox,
                     AnalyticCode, ExpenseType, Profile, SystemParameter, Department, TravelRequest)
from .forms import (ExpenseTypeForm, AnalyticCodeForm, NewClaimForm, NewClaimLine,
                    CurrencyForm, AttachmentForm, ChatterForm, ProfileForm, SetPasswordForm,
                    PasswordResetForm, DepartmentForm)
from .user_claim import (get_uc_number, check_date, convert_amount,
                         get_next_payment_date, convert_custom_amount,
                         export_claim_to_excel)
from .tokens import account_activation_token


load_dotenv()
MAX_UPLOAD_SIZE = 5242880
DEBUG = os.environ.get("DEBUG", False)


def index(request):
    if request.method == "GET":
        # add a developer update log
        # add claims to approve / verify
        # add word of the day

        return render(request, "neutrovisinternal/index.html", {
            'today_date': timezone.now(),
        })


def mysubmission(request):
    if request.method == "GET":
        if request.user.is_authenticated:
            requestor = request.user
            claims = UserClaim.objects.filter(requestor=requestor).order_by('-id')
            context = {
                "claims": claims,
            }
            return render(request, "neutrovisinternal/mysubmission.html", context)
        return render(request, "neutrovisinternal/mysubmission.html")


def newsubmission(request):
    if request.method == "GET":
        additional_data = {}
        if 'form_data' in request.session:
            saved_data = request.session.pop('form_data')
            claim_form = NewClaimForm(initial=saved_data, request_user=request.user)
            additional_data['invoice_id'] = saved_data.get('invoice_id', '')
            additional_data['invoice_date'] = saved_data.get('invoice_date', '')
            additional_data['invoice_description'] = saved_data.get('invoice_description', '')
            additional_data['currency'] = saved_data.get('currency', '')
            additional_data['amount'] = saved_data.get('amount', '')
            additional_data['expense_type'] = saved_data.get('expense_type', '')
            additional_data['analytic_code'] = saved_data.get('analytic_code', '')
            additional_data['remarks'] = saved_data.get('claim_form_remarks', '')
        else:
            claim_form = NewClaimForm(initial={
                'name': "New",
                'requestor': request.user.username,
                'status': "Draft"
            }, request_user=request.user)
        context = {
            'claim_form': claim_form,
            'attachment': AttachmentForm(),
            'prev_data': additional_data,
        }
        return render(request, "neutrovisinternal/newsubmission.html", context)
    elif request.method == "POST":
        claim_form = NewClaimForm(request.POST, request_user=request.user)
        if claim_form:
            claim_form_name = request.POST.get("claim_form_name", "new")
            status = request.POST["status"]
            remark = request.POST.get("claim_form_remarks", False)
            invoice_id = request.POST.get("invoice_id", False)
            invoice_date = request.POST["invoice_date"]
            invoice_description = request.POST["invoice_description"]
            expense_type = request.POST["expense_type"]
            travel_request = request.POST["travel_request"]
            analytic_code = request.POST["analytic_code"]
            currency_id = request.POST["currency"]
            amount = request.POST["amount"]
            use_own_rate = request.POST.get("use_own_rate", False)
            own_rate = request.POST.get("own_rate", False)
            try:
                attachment_id = request.POST["attachment_id"]
            except MultiValueDictKeyError:
                request.session['form_data'] = request.POST.dict()
                messages.error(request, "No file uploaded")
                return redirect(request.META.get('HTTP_REFERER'))

            if status != "Draft":
                messages.error(request, "Record not in draft status!")
                return redirect(request.META.get('HTTP_REFERER'))
            try:
                currency = Currency.objects.get(id=int(currency_id))
            except ValueError:
                request.session['form_data'] = request.POST.dict()
                messages.error(request, "No currency selected!")
                return redirect(request.META.get('HTTP_REFERER'))

            conversion_rate = 0
            if use_own_rate:
                amount_myr = convert_custom_amount(own_rate, amount)
            else:
                amount_myr = convert_amount(currency_id, request.user.profile.default_currency.id, amount)
                my_curr = request.user.profile.default_currency
                conversion_rate = round(my_curr.exchange_rate / currency.exchange_rate, 5)

            if invoice_id:
                existing_inv_id = UserClaimLine.objects.filter(invoice_id=invoice_id)
                if existing_inv_id.exists():
                    request.session['form_data'] = request.POST.dict()
                    messages.error(request, "Invoice existed in system")
                    return redirect(request.META.get('HTTP_REFERER'))

            existing_claim = UserClaim.objects.filter(name=claim_form_name)
            if existing_claim.exists():
                claim = existing_claim.first()
                claim.total_amount += amount_myr
                claim.save()
            else:
                claim = UserClaim(
                    submit_date=timezone.now(),
                    requestor=request.user,
                    total_amount=amount_myr,
                    status="Draft",
                )
                claim.save()
                claim.name = get_uc_number(claim.id)
                claim.save()
                chatter = ChatterBox(
                    claim_id=claim,
                    chat_user=request.user,
                    message=f"created record {claim.name}",
                )
                chatter.save()

            attachment = Attachment.objects.get(id=int(attachment_id))

            invoice_date_obj, msg = check_date(invoice_date)

            if not invoice_date_obj:
                request.session['form_data'] = request.POST.dict()
                messages.error(request, message=msg)
                return redirect(request.META.get('HTTP_REFERER'))

            claim_line = UserClaimLine(
                claim=claim,
                invoice_date=invoice_date_obj,
                invoice_id=invoice_id,
                invoice_description=invoice_description,
                attachment=attachment,
                currency=currency,
                remark=remark,
                amount=Decimal(amount),
                amount_myr=amount_myr,
                use_own_rate=True if use_own_rate == "on" else False,
                own_rate=own_rate if use_own_rate else conversion_rate,
            )
            if expense_type:
                expense_type = ExpenseType.objects.get(id=int(expense_type))
                claim_line.expense_type = expense_type
            if analytic_code:
                analytic_code = AnalyticCode.objects.get(id=int(analytic_code))
                claim_line.analytic_code = analytic_code
            if travel_request:
                travel_request = TravelRequest.objects.get(id=int(travel_request))
                claim_line.travel_request = travel_request
            claim_line.save()
            if claim.has_adv_payment:
                claim.adv_balance = claim.adv_claim.total_amount - claim.total_amount
                claim.save()
            chatter = ChatterBox(
                claim_id=claim,
                chat_user=request.user,
                message=f"updated total amount to {request.user.profile.default_currency.symbol} "
                        f"{round(claim.total_amount,2)}",
            )
            chatter.save()
            messages.success(request, "Claim line added")
            if claim_form_name == "new":
                return HttpResponseRedirect(reverse('viewsubmission', args=(claim.id,)))
            else:
                return redirect(request.META.get('HTTP_REFERER'))
        return redirect('newsubmission')


def save_claim_advance_info(request):
    if request.method == "POST":
        claim_id = request.POST["claim_id"]
        is_adv_payment = request.POST.get("is_adv_payment", False)
        has_adv_payment = request.POST.get("has_adv_payment", False)
        adv_claim_select = request.POST.get("adv_claim_select", False)

        claim = UserClaim.objects.get(id=int(claim_id))
        if claim.status != "Draft":
            messages.error(request, "Cannot edit non-draft record!")
            return redirect(request.META.get("HTTP_REFERER"))
        if is_adv_payment and has_adv_payment:
            messages.error(request, "Cannot be an advance payment that has an advance payment!")
            return redirect(request.META.get('HTTP_REFERER'))
        if is_adv_payment:
            claim.is_adv_payment = True
            claim.has_adv_payment = False
            claim.adv_claim = None
            claim.save()
            chatter = ChatterBox(
                claim_id=claim,
                chat_user=request.user,
                message=f"set this claim to be advance claim.",
            )
            chatter.save()
        elif has_adv_payment:
            claim.is_adv_payment = False
            claim.has_adv_payment = True
            adv_claim = UserClaim.objects.get(id=int(adv_claim_select))
            claim.adv_claim = adv_claim
            claim.adv_balance = claim.adv_claim.total_amount - claim.total_amount
            claim.save()
            chatter = ChatterBox(
                claim_id=claim,
                chat_user=request.user,
                message=f"set {claim.adv_claim.name} to be advance claim.",
            )
            chatter.save()
        else:
            claim.is_adv_payment = False
            claim.has_adv_payment = False
            claim.adv_claim = None
            claim.save()
            chatter = ChatterBox(
                claim_id=claim,
                chat_user=request.user,
                message=f"cleared all advance claim fields.",
            )
            chatter.save()
        messages.success(request, "Saved")
        return redirect("viewsubmission", claim_id=claim_id)


def delete_claim(request):
    if request.method == "POST":
        claim_id = request.POST["claim_id"]
        claim = UserClaim.objects.get(id=int(claim_id))
        claim.delete()
        messages.success(request, "Claim deleted")
        return redirect(request.META.get('HTTP_REFERER'))


def finance_edit(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            for claim_line_obj in data:
                for claim_line_id, claim_line_contents in claim_line_obj.items():
                    claim_line = UserClaimLine.objects.get(id=int(claim_line_id))
                    for content, value in claim_line_contents.items():
                        if content == "expense_type":
                            expense_type = ExpenseType.objects.get(id=int(value))
                            claim_line.expense_type = expense_type
                        if content == "analytic_code":
                            analytic_code = AnalyticCode.objects.get(id=int(value))
                            claim_line.analytic_code = analytic_code
                    claim_line.save()
                    chatter = ChatterBox(
                        claim_id=claim_line.claim,
                        chat_user=request.user,
                        message=f"changed expense type and/or analytic code for {claim_line.invoice_id}.",
                    )
                    chatter.save()
            return redirect(request.META.get('HTTP_REFERER'))
        except KeyError:
            return JsonResponse({"error": f"Missing data, {str(e)}"}, status=400)


def edit_claim_line(request):
    if request.method == "POST":
        claim_line_id = request.POST["claim_line_id"]
        claim_line = UserClaimLine.objects.get(id=int(claim_line_id))
        request.session['form_data'] = request.POST.dict()
        request.session['form_data']['invoice_id'] = claim_line.invoice_id
        request.session['form_data']['invoice_date'] = claim_line.invoice_date.strftime("%Y-%m-%d")
        request.session['form_data']['invoice_description'] = claim_line.invoice_description
        request.session['form_data']['remarks'] = claim_line.remark
        request.session['form_data']['expense_type'] = claim_line.expense_type.id if claim_line.expense_type else ""
        request.session['form_data']['analytic_code'] = claim_line.analytic_code.id if claim_line.analytic_code else ""
        request.session['form_data']['currency'] = claim_line.currency.id
        request.session['form_data']['amount'] = str(claim_line.amount)
        claim_line.claim.total_amount -= claim_line.amount_myr
        claim_line.claim.save()
        claim_line.delete()
        return redirect(request.META.get('HTTP_REFERER'))


def deleteclaimline(request):
    if request.method == "POST":
        claim_line_id = request.POST["claim_line_id"]
        claim_line = UserClaimLine.objects.get(id=claim_line_id)
        claim = claim_line.claim
        if claim_line.attachment:
            claim_line.attachment.file.delete()
            claim_line.attachment.delete()

        claim.total_amount -= claim_line.amount_myr
        if claim.has_adv_payment:
            claim.adv_balance += claim_line.amount_myr
        claim.save()
        claim_line.delete()
        chatter = ChatterBox(
            claim_id=claim,
            chat_user=request.user,
            message=f"changed total amount to {request.user.profile.default_currency} {claim.total_amount}.",
        )
        chatter.save()
        messages.success(request, "Claim line deleted")
        return redirect(request.META.get('HTTP_REFERER'))


def viewsubmission(request, claim_id):
    if request.method == "GET":
        additional_data = {}
        claim = UserClaim.objects.get(id=claim_id)
        claim_lines = UserClaimLine.objects.filter(claim=claim)
        chatterbox = ChatterBox.objects.filter(claim_id=claim.id)
        adv_claims = (UserClaim.objects.filter(requestor=request.user).
                      filter(status__in=["Approved", "Verified", "Paid"]).
                      filter(is_adv_payment=True))
        if 'form_data' in request.session:
            saved_data = request.session.pop('form_data')
            claim_form = NewClaimForm(initial=saved_data, request_user=request.user)
            claim_form.status = saved_data.get('claim_status', '')
            additional_data['invoice_id'] = saved_data.get('invoice_id', '')
            additional_data['invoice_date'] = saved_data.get('invoice_date', '')
            additional_data['invoice_description'] = saved_data.get('invoice_description', '')
            additional_data['expense_type'] = saved_data.get('expense_type', '')
            additional_data['analytic_code'] = saved_data.get('analytic_code', '')
            additional_data['remarks'] = saved_data.get('remarks', '')
            additional_data['currency'] = saved_data.get('currency', '')
            additional_data['amount'] = saved_data.get('amount', '')
            additional_data['remarks'] = saved_data.get('claim_form_remarks', '')
        else:
            claim_form = NewClaimForm(initial={
                'name': "New",
                'requestor': request.user.username,
                'status': claim.status,
                'is_adv_payment': claim.is_adv_payment,
                'has_adv_payment': claim.has_adv_payment,
            }, request_user=request.user)
        context = {
            "claim": claim,
            "records": claim_lines,
            "claim_form": claim_form,
            "additional_data": additional_data,
            "chatters": chatterbox,
            "adv_claims": adv_claims,
        }
        return render(request,
                      "neutrovisinternal/viewsubmission.html",
                      context)


def viewapproval(request):
    if request.method == "GET":
        members = Profile.objects.filter(reporting_user=request.user)
        user_ids = members.values_list('user__id', flat=True)
        claims = UserClaim.objects.filter(requestor__in=user_ids).filter(status="Submitted").order_by('-id')
        context = {
            "claims": claims,
        }
        return render(request, "neutrovisinternal/viewapproval.html", context)


def viewverify(request):
    if request.method == "GET":
        if not request.user.groups.filter(name="Finance").exists():
            referer_url = request.META.get('HTTP_REFERER')
            if referer_url:
                return HttpResponseRedirect(referer_url)
            else:
                return HttpResponseRedirect(reverse('index'))
        claims = UserClaim.objects.filter(status="Approved").order_by('-id')
        context = {
            "claims": claims,
        }
        return render(request, "neutrovisinternal/viewverify.html", context)


def viewexport(request):
    if request.method == "GET":
        if not request.user.groups.filter(name="Finance").exists():
            referer_url = request.META.get('HTTP_REFERER')
            if referer_url:
                return HttpResponseRedirect(referer_url)
            else:
                return HttpResponseRedirect(reverse('index'))
        verified_claims = UserClaim.objects.filter(status="Verified").order_by('-id')
        context = {
            "verified_claims": verified_claims,
        }
        return render(request, "neutrovisinternal/viewexport.html", context)


def submitapproval(request):
    if request.method == "POST":
        claim_id = request.POST["claim_id"]
        claim = UserClaim.objects.get(id=claim_id)
        if claim.status == "Draft":
            try:
                if claim.has_adv_payment:
                    claim.adv_balance = claim.adv_claim.total_amount - claim.total_amount
                    claim.save()
                link = settings.BASE_URL + f"viewsubmission/{claim_id}"
                send_mail(
                    subject="Claim Submitted",
                    message=notification_submission_sc(claim.name, request.user.profile, link),
                    from_email=EMAIL_HOST_USER,
                    recipient_list=[claim.requestor.profile.reporting_user.email],
                    fail_silently=not DEBUG,
                )
                claim.status = "Submitted"
                claim.save()
                chatter = ChatterBox(
                    claim_id=claim,
                    chat_user=request.user,
                    message=f"submitted for approval.",
                )
                chatter.save()
                messages.success(request, "Claim submitted for approval.")
            except smtplib.SMTPAuthenticationError:
                messages.error(request, "Email server not working.")
                return redirect("viewsubmission", claim_id=claim_id)
        else:
            messages.error(request, "Claim not submitted for approval.")
        return redirect('viewsubmission', claim_id=claim_id)


def approve_claim(request):
    if request.method == "POST":
        claim_id = request.POST["claim_id"]
        claim = UserClaim.objects.get(id=claim_id)
        if claim.status == "Submitted":
            try:
                link = settings.BASE_URL + f"viewsubmission/{claim_id}"
                send_mail(
                    subject="Claim Approved",
                    message=notification_approval_sc(claim.name, request.user.profile, link),
                    from_email=EMAIL_HOST_USER,
                    recipient_list=[claim.requestor.email],
                    fail_silently=not DEBUG,
                )
                claim.status = "Approved"
                claim.approval_date = timezone.now()
                claim.save()
                chatter = ChatterBox(
                    claim_id=claim,
                    chat_user=request.user,
                    message=f"approved the claim.",
                )
                chatter.save()
                messages.success(request, f"Approved claim: {claim.name}.")
            except smtplib.SMTPAuthenticationError:
                messages.error(request, "Email server not working.")
                return redirect("viewapproval")
        return redirect("viewapproval")


def reject_claim(request):
    if request.method == "POST":
        claim_id = request.POST["claim_id"]
        reject_reason = request.POST["reject_reason"]
        claim = UserClaim.objects.get(id=claim_id)
        if claim.status == "Submitted":
            try:
                link = settings.BASE_URL + f"viewsubmission/{claim_id}"
                send_mail(
                    subject="Claim Rejected",
                    message=notification_reject_sc(claim.name, request.user.profile, reject_reason, link),
                    from_email=EMAIL_HOST_USER,
                    recipient_list=[claim.requestor.email],
                    fail_silently=not DEBUG,
                )
                claim.status = "Draft"
                claim.save()
                chatter = ChatterBox(
                    claim_id=claim,
                    chat_user=request.user,
                    message=f"rejected due to {reject_reason}.",
                )
                chatter.save()
                messages.success(request, f"Rejected with reason: {reject_reason}.")
            except smtplib.SMTPAuthenticationError:
                messages.error(request, "Email server not working.")
                return redirect("viewapproval")
        return redirect("viewapproval")


def verify_claim(request):
    if request.method == "POST":
        claim_id = request.POST["claim_id"]
        claim = UserClaim.objects.get(id=claim_id)
        if claim.status == "Approved":
            try:
                link = settings.BASE_URL + f"viewsubmission/{claim_id}"
                send_mail(
                    subject="Claim Verified",
                    message=notification_verified_sc(claim.name, request.user.profile, link),
                    from_email=EMAIL_HOST_USER,
                    recipient_list=[claim.requestor.email],
                    fail_silently=not DEBUG,
                )
                claim.status = "Verified"
                claim.payment_date = get_next_payment_date(timezone.now())
                claim.save()
                chatter = ChatterBox(
                    claim_id=claim,
                    chat_user=request.user,
                    message=f"verified this claim.",
                )
                chatter.save()
                messages.success(request, f"Verified claim: {claim.name}.")
            except smtplib.SMTPAuthenticationError:
                messages.error(request, "Email server not working.")
                return redirect("viewverify")
        return redirect("viewverify")


def reject_aclaim(request):
    if request.method == "POST":
        claim_id = request.POST["claim_id"]
        reject_reason = request.POST["reject_reason"]
        claim = UserClaim.objects.get(id=claim_id)
        if claim.status == "Approved":
            try:
                link = settings.BASE_URL + f"viewsubmission/{claim_id}"
                send_mail(
                    subject="Claim Rejected",
                    message=notification_reject_sc(claim.name, request.user.profile, reject_reason, link),
                    from_email=EMAIL_HOST_USER,
                    recipient_list=[claim.requestor.email],
                    fail_silently=not DEBUG,
                )
                claim.status = "Draft"
                claim.save()
                chatter = ChatterBox(
                    claim_id=claim,
                    chat_user=request.user,
                    message=f"rejected due to {reject_reason}.",
                )
                chatter.save()
                messages.success(request, f"Rejected with reason: {reject_reason}.")
            except smtplib.SMTPAuthenticationError:
                messages.error(request, "Email server not working.")
                return redirect("viewverify")
        return redirect("viewverify")


def upload_attachment(request):
    if request.method == "POST" and request.FILES.get('file', False):
        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            if attachment.file.size > MAX_UPLOAD_SIZE:
                data = {'is_valid': False, 'message': "File Too Big (> 5MB)"}
                return JsonResponse(data)
            _, _, filename = attachment.file.name.rpartition('/')
            attachment.name = filename
            attachment.save()
            full_url = request.build_absolute_uri(attachment.file.url)
            data = {'is_valid': True,
                    'name': filename,
                    'url': full_url,
                    'att_id': attachment.id}
        else:
            data = {'is_valid': False, 'message': "File invalid"}
        return JsonResponse(data)


def setting_currency(request):
    results = Currency.objects.all().order_by("-active", "symbol").values()
    if request.method == "GET":
        updated_on = SystemParameter.objects.filter(key="Query BNM API").first()
        return render(request, "neutrovisinternal/settingcurrency.html", {
            "results": results,
            "updated_on": updated_on,
        })
    elif request.method == "POST":
        api_url = SystemParameter.objects.get(key="BNM_API").value
        header = {'Accept': 'application/vnd.BNM.API.v1+json'}
        try:
            response = requests.get(api_url, headers=header)
            response.raise_for_status()
            all_rates = response.json()['data']
            for rate in all_rates:
                symbol = rate['currency_code']
                unit_rate = rate['rate']['middle_rate']
                unit = rate['unit']
                exchange_rate = round(unit / unit_rate, 5)
                curr = Currency.objects.filter(symbol=symbol)
                if curr.exists():
                    curr.exchange_rate = exchange_rate
                else:
                    currency = Currency(
                        symbol=symbol,
                        exchange_rate=exchange_rate,
                        active=True
                    )
                    currency.save()
            sys_param = SystemParameter.objects.get(key="Query BNM API")
            sys_param.value = response.json()["meta"]["last_updated"]
            sys_param.save()
            messages.success(request, "Rates updated successfully.")
        except requests.RequestException as e:
            return render(request, "neutrovisinternal/settingcurrency.html", {
                "message": str(e),
            })
        return redirect("setting_currency")


def setting_analyticcode(request):
    results = AnalyticCode.objects.all()
    if request.method == "GET":
        return render(request, "neutrovisinternal/settinganalyticcode.html", {
            "results": results,
            "analytic_code_form": AnalyticCodeForm()

        })
    elif request.method == "POST":
        ana_code = AnalyticCodeForm(request.POST)
        if ana_code.is_valid():
            code = ana_code.cleaned_data['code']
            name = ana_code.cleaned_data['name']
            try:
                analytic_code = AnalyticCode(
                    code=code,
                    name=name,
                )
                analytic_code.save()
            except IntegrityError:
                messages.error(request, "Record existed in database.")
                return redirect("setting_analyticcode")
            messages.success(request, "Record added successfully.")
        return redirect("setting_analyticcode")


def delete_analyticcode(request):
    if request.method == "POST":
        analytic_code_id = request.POST["analytic_code"]
        analytic_code = AnalyticCode.objects.get(id=analytic_code_id)
        try:
            analytic_code.delete()
        except ProtectedError:
            messages.error(request, "Cannot delete due to used in claim lines")
            return redirect("setting_analyticcode")
        messages.success(request, "Record deleted successfully.")
        return redirect("setting_analyticcode")


def setting_expensetype(request):
    results = ExpenseType.objects.all()
    if request.method == "GET":
        return render(request, "neutrovisinternal/settingexpensetype.html", {
            "expense_type_form": ExpenseTypeForm(),
            "results": results,
        })
    elif request.method == "POST":
        exp_type = ExpenseTypeForm(request.POST)
        if exp_type.is_valid():
            e_type = exp_type.cleaned_data['expense_type']
            name = exp_type.cleaned_data['name']
            try:
                expense_type = ExpenseType(
                    e_type=e_type,
                    name=name,
                )
                expense_type.save()
            except IntegrityError:
                messages.error(request, "Record existed in database.")
                return redirect("setting_expensetype")
            messages.success(request, "Record added successfully.")
        return redirect("setting_expensetype")


def delete_expensetype(request):
    if request.method == "POST":
        expense_type_id = request.POST["expense_type"]
        expense_type = ExpenseType.objects.get(id=expense_type_id)
        try:
            expense_type.delete()
        except ProtectedError:
            messages.error(request, "Cannot delete due to used in claim lines")
            return redirect("setting_expensetype")
        messages.success(request, "Record deleted successfully.")
        return redirect("setting_expensetype")


def setting_department(request):
    if request.method == "GET":
        context = {
            "results": Department.objects.all().order_by('id'),
            "department_form": DepartmentForm()
        }
        return render(request, "neutrovisinternal/setting_department.html", context)
    elif request.method == "POST":
        dept = DepartmentForm(request)
        if dept.is_valid():
            dept_name = dept.cleaned_data('name').strip().title()
            exist_dept = Department.objects.get(name=dept_name)
            if exist_dept.exists():
                messages.error(request, "Record existed in the database.")
                return redirect("setting_department")
            department = Department(
                name=dept_name
            )
            department.save()
            messages.success(request, "Record added successfully.")
            return redirect("setting_department")


def delete_department(request):
    if request.method == "POST":
        dept_id = request.POST["department_id"]
        department = Department.objects.get(id=dept_id)
        department.delete()
        messages.success(request, "Record deleted successfully.")
        return redirect("setting_department")


def export_claims(request):
    if request.method == "POST":
        claim_ids_list = request.POST.getlist("export_claims[]")
        claim_ids = [int(ids) for ids in claim_ids_list]
        file_name = export_claim_to_excel(claim_ids)
        file_abs_path = os.path.join(settings.MEDIA_ROOT, "export_excel", file_name)
        return FileResponse(open(file_abs_path, 'rb'), as_attachment=True)


def send_message(request):
    if request.method == "POST":
        chat_msg = request.POST["chat_message"]
        claim_id = request.POST["claim_id"]
        claim = UserClaim.objects.get(id=int(claim_id))
        chat = ChatterBox(
            claim_id=claim,
            chat_user=request.user,
            message="says " + chat_msg,
        )
        chat.save()
        messages.success(request, "Added message")
        return redirect("viewsubmission", claim_id=claim_id)


def setting_profile(request):
    if request.method == "POST":
        profile_form = ProfileForm(request.POST)
        if profile_form.is_valid():
            profile_id = profile_form.cleaned_data.get('profile_id')
            if not profile_id:
                username = profile_form.cleaned_data['username']
                email = profile_form.cleaned_data['email']
                first_name = profile_form.cleaned_data['first_name'].title()
                last_name = profile_form.cleaned_data['last_name'].title()
                is_active = profile_form.cleaned_data.get('is_active')
                default_password = SystemParameter.objects.get(key="DEFAULT_PASSWORD").value
                username_validator = UnicodeUsernameValidator()
                try:
                    username_validator(username)
                    try:
                        user = User.objects.create_user(
                            username=username,
                            email=email,
                            first_name=first_name,
                            last_name=last_name,
                            is_active=is_active,
                            password=default_password,
                        )
                        profile = user.profile
                        messages.success(request, "New user created successfully")
                    except IntegrityError:
                        messages.error(request, "A user with this username or email already exists.")
                        return redirect('setting_profile')
                except ValidationError as e:
                    messages.error(request, str(e))
                    return redirect('setting_profile')
            else:
                profile = Profile.objects.get(id=profile_id)
                user = profile.user
                user.first_name = profile_form.cleaned_data['first_name'].title()
                user.last_name = profile_form.cleaned_data['last_name'].title()
                user.email = profile_form.cleaned_data['email']
                user.is_active = profile_form.cleaned_data.get('is_active')
                user.save()
                messages.success(request, "Changes have been saved")

            employee_id = profile_form.cleaned_data['employee_id']
            reporting_user_id = profile_form.cleaned_data.get('reporting_user')
            default_currency_id = profile_form.cleaned_data.get('default_currency')
            department_id = profile_form.cleaned_data.get('department')
            if employee_id and Profile.objects.filter(employee_id=employee_id).exclude(id=profile_id).exists():
                messages.error(request, "This Employee ID is already in use")
            else:
                profile.employee_id = employee_id
            if reporting_user_id:
                profile.reporting_user = User.objects.get(id=reporting_user_id.id)
            else:
                profile.reporting_user = None
            if default_currency_id:
                profile.default_currency = Currency.objects.get(id=default_currency_id.id)
            if department_id:
                profile.department = Department.objects.get(id=department_id.id)
            else:
                profile.department = None
            profile.save()

            return redirect('setting_profile')
        else:
            for error in profile_form.errors.items():
                messages.error(request, f"{error}")

    return render(request, "neutrovisinternal/settingprofile.html", {
        "results": Profile.objects.all().order_by('employee_id'),
        "users": User.objects.all().order_by('first_name', 'last_name'),
        "currencies": Currency.objects.all().order_by('symbol'),
        "departments": Department.objects.all().order_by('name'),
    })


def password_change(request):
    form = SetPasswordForm(request.user)
    context = {
        "form": form,
    }
    if request.method == "POST":
        form = SetPasswordForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Your password has been changed.")
            return redirect("index")
        else:
            for error in list(form.errors.values()):
                messages.error(request, error)
    return render(request, "neutrovisinternal/password_reset_confirm.html", context)


@public
def password_reset_request(request):
    if request.method == "GET":
        form = PasswordResetForm()
        context = {
            "form": form,
        }
        return render(request, "neutrovisinternal/password_reset.html", context)
    elif request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            user_email = form.cleaned_data['email']
            associated_user = get_user_model().objects.filter(email=user_email).first()
            if associated_user:
                uid = urlsafe_base64_encode(force_bytes(associated_user.pk))
                token = account_activation_token.make_token(associated_user)
                link = settings.BASE_URL + "reset/" + uid + "/" + token
                try:
                    send_mail(
                        subject="Password Reset request",
                        message=password_reset_email(link, associated_user.username),
                        from_email=EMAIL_HOST_USER,
                        recipient_list=[associated_user.email],
                        fail_silently=not DEBUG,
                    )
                    messages.success(request, "The reset instructions had been sent to your mailbox.")
                except smtplib.SMTPAuthenticationError:
                    messages.error(request, "Problem sending reset password email, <b>SERVER PROBLEM</b>")
                    return redirect('index')
            return redirect('login')

        for key, error in list(form.errors.items()):
            if key == 'captcha' and error[0] == 'This field is required.':
                messages.error(request, "You must pass the reCAPTCHA test")
                continue

        return redirect(request.META.get('HTTP_REFERER'))


@public
def password_reset_confirm(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except TypeError:
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        if request.method == "POST":
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Your password has been reseted, You may now login.")
                return redirect("index")
            else:
                for error in list(form.errors.values()):
                    messages.error(request, error)
        elif request.method == "GET":
            form = SetPasswordForm(user)
            return render(request, 'neutrovisinternal/password_reset_confirm.html', {'form': form})
    else:
        messages.error(request, "Link is expired")
        return redirect("index")
