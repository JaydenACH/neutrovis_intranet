import os
from datetime import datetime
from decimal import Decimal
import requests
import smtplib
from dotenv import load_dotenv
from neutrovis_internal_project.settings import EMAIL_HOST_USER
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, FileResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from .models import (TravelRequest, TravelRequestLine, Destination,
                     AllowanceLimit, SupportingDocument, Profile)
from .forms import NewTravelRequestForm
from .email_template import (notification_reject_tr, notification_approval_tr, notification_submission_tr)
from .travel_request import get_tr_number, calculate_date_delta, check_date, compute_travel_request_amount


load_dotenv()
DEBUG = os.environ.get("DEBUG", False)


def view_travel_request(request, travel_id):
    if request.method == "GET":
        travel_req = TravelRequest.objects.get(id=int(travel_id))
        travel_req_line = TravelRequestLine.objects.filter(travel_request=travel_req)
        additional_data = {}
        if 'form_data' in request.session:
            saved_data = request.session.pop('form_data')
            new_travel_request_line = NewTravelRequestForm(initial=saved_data)
            additional_data['start_date'] = saved_data.get('start_date', '')
            additional_data['end_date'] = saved_data.get('end_date', '')
            additional_data['est_flight'] = saved_data.get('est_flight', '')
            additional_data['est_accomodation'] = saved_data.get('est_accomodation', '')
            additional_data['departure'] = saved_data.get('departure', '')
            additional_data['destination'] = saved_data.get('destination', '')
        else:
            new_travel_request_line = NewTravelRequestForm()
        context = {
            "travel_request": travel_req,
            "travel_req_line": travel_req_line,
            "new_travel_req_line": NewTravelRequestForm(),
            "travel_request_form": new_travel_request_line,
            "prev_data": additional_data,
        }
        return render(request, "neutrovistravelrequest/viewtravelrequest.html", context)


def new_travel_request(request):
    if request.method == "GET":
        travel_request_form = NewTravelRequestForm()
        context = {
            "travel_request_form": travel_request_form,
        }
        return render(request, "neutrovistravelrequest/newtravelrequest.html", context)
    elif request.method == "POST":
        travel_request_form = NewTravelRequestForm(request.POST)
        if travel_request_form.is_valid():
            travel_request = request.POST.get("travel_request", "new")
            start_date = request.POST["start_date"]
            end_date = request.POST["end_date"]
            departure = request.POST["departure"]
            destination = request.POST["destination"]
            if not check_date(start_date, end_date):
                request.session['form_data'] = request.POST.dict()
                request.session['form_data']['start_date'] = start_date
                request.session['form_data']['end_date'] = end_date
                request.session['form_data']['departure'] = departure
                request.session['form_data']['destination'] = destination
                request.session['form_data']['est_accomodation'] = request.POST.get("est_accomodation", 0)
                request.session['form_data']['est_flight'] = request.POST["est_flight"]
                messages.error(request, "Wrong date!")
                return redirect(request.META.get('HTTP_REFERER'))
            est_accomodation = request.POST.get("est_accomodation", 0)
            est_flight = request.POST["est_flight"]
            overnight = calculate_date_delta(start_date, end_date)
            departure_limit = AllowanceLimit.objects.get(destination=int(departure))
            destination_limit = AllowanceLimit.objects.get(destination=int(destination))
            limits = destination_limit
            if departure_limit.currency.symbol == "USD" and destination_limit.currency.symbol == "MYR":
                limits = departure_limit
            accomodation_allowance = destination_limit.accomodation_allowance * overnight
            flight_allowance = limits.flight_allowance
            if travel_request == "new":
                travel_req = TravelRequest(
                    requestor=request.user,
                    status="Draft",
                )
                travel_req.save()
                travel_req.name = get_tr_number(travel_req.id)
                travel_req.save()
            else:
                travel_req = TravelRequest.objects.get(id=int(travel_request))
            travel_req_line = TravelRequestLine(
                travel_request=travel_req,
                travel_start_date=datetime.strptime(start_date, '%Y-%m-%d'),
                travel_end_date=datetime.strptime(end_date, '%Y-%m-%d'),
                departure=departure_limit.destination,
                destination=destination_limit.destination,
                flight_currency=limits.currency,
                accomodation_currency=destination_limit.currency,
                flight_limit=Decimal(flight_allowance),
                accomodation_limit=Decimal(accomodation_allowance),
                estimated_flight_expense=est_flight,
                estimated_accomodation_expense=est_accomodation,
                overlimit=any([
                    Decimal(est_flight) > Decimal(flight_allowance),
                    Decimal(est_accomodation) > Decimal(accomodation_allowance),
                    ])
            )
            travel_req_line.save()
            compute_travel_request_amount(travel_req.id)
            return HttpResponseRedirect(reverse('view_travel_request', args=(travel_req.id,)))
        return redirect('new_travel_request')


def my_travel_request(request):
    if request.method == "GET":
        if request.user.is_authenticated:
            travel_request = TravelRequest.objects.filter(requestor=request.user).order_by("-id")
            context = {
                "travel_request": travel_request
            }
            return render(request, "neutrovistravelrequest/mytravelrequest.html", context)
        return render(request, "neutrovisinternal/index.html")


def edit_tr_line(request):
    if request.method == "POST":
        treq_line = request.POST["travel_request_line"]
        travel_req_line = TravelRequestLine.objects.get(id=int(treq_line))
        request.session['form_data'] = request.POST.dict()
        request.session['form_data']['start_date'] = travel_req_line.travel_start_date.strftime("%Y-%m-%d")
        request.session['form_data']['end_date'] = travel_req_line.travel_end_date.strftime("%Y-%m-%d")
        request.session['form_data']['departure'] = travel_req_line.departure.id
        request.session['form_data']['destination'] = travel_req_line.destination.id
        request.session['form_data']['est_accomodation'] = str(travel_req_line.estimated_accomodation_expense)
        request.session['form_data']['est_flight'] = str(travel_req_line.estimated_flight_expense)
        travel_req_line.delete()
        compute_travel_request_amount(travel_req_line.travel_request.id)
        return redirect(request.META.get('HTTP_REFERER'))


def delete_travel_request(request):
    if request.method == "POST":
        treq_id = request.POST["travel_request"]
        travel_request = TravelRequest.objects.get(id=int(treq_id))
        if travel_request.status == "Draft":
            travel_request.delete()
            messages.success(request, "Travel request deleted")
            return redirect(request.META.get('HTTP_REFERER'))
        else:
            messages.error(request, "The request is not in draft state")
            return redirect(request.META.get('HTTP_REFERER'))


def delete_tr_line(request):
    if request.method == "POST":
        treq_line = request.POST["travel_request_line"]
        travel_request_line = TravelRequestLine.objects.get(id=int(treq_line))
        travel_request_line.delete()
        compute_travel_request_amount(travel_request_line.travel_request.id)
        messages.success(request, "Request line deleted")
        return redirect("view_travel_request", travel_id=travel_request_line.travel_request.id)


def view_tr_approval(request):
    if request.method == "GET":
        members = Profile.objects.filter(reporting_user=request.user)
        user_ids = members.values_list("user__id", flat=True)
        travel_request = TravelRequest.objects.filter(requestor__in=user_ids).filter(status="Submitted").order_by("-id")
        ol_travel_request = (TravelRequest.objects
                             .filter(requestor__in=user_ids)
                             .filter(status="Approved").filter(overlimit=True)
                             .order_by("-id"))
        context = {
            "travel_request": travel_request,
            "ol_travel_request": ol_travel_request,
        }
        return render(request, "neutrovistravelrequest/viewtrapproval.html", context)


def submit_travel_request(request):
    if request.method == "POST":
        treq_id = request.POST["treq_id"]
        travel_request = TravelRequest.objects.get(id=int(treq_id))
        if travel_request.status == "Draft":
            try:
                link = settings.BASE_URL + f"view_travel_request/{treq_id}"
                send_mail(
                    subject="Travel Request Submitted",
                    message=notification_submission_tr(travel_request.name, request.user, link),
                    from_email=EMAIL_HOST_USER,
                    recipient_list=[travel_request.requestor.profile.reporting_user.email],
                    fail_silently=not DEBUG,
                )
                travel_request.status = "Submitted"
                travel_request.save()
                messages.success(request, "Travel Request submitted for approval.")
            except smtplib.SMTPAuthenticationError:
                messages.error(request, "Email server not working.")
                return redirect("view_travel_request", travel_id=treq_id)
        else:
            messages.error(request, "Travel Request not submitted for approval.")
        return redirect("view_travel_request", travel_id=treq_id)


def approve_travel_request(request):
    if request.method == "POST":
        treq_id = request.POST["treq_id"]
        travel_request = TravelRequest.objects.get(id=int(treq_id))
        if travel_request.status == "Submitted":
            try:
                link = settings.BASE_URL + f"view_travel_request/{treq_id}"
                send_mail(
                    subject="Travel Request Approved",
                    message=notification_approval_tr(travel_request.name, request.user.profile, link),
                    from_email=EMAIL_HOST_USER,
                    recipient_list=[travel_request.requestor.email],
                    fail_silently=not DEBUG,
                )
                travel_request.status = "Approved"
                travel_request.approval_date = timezone.now()
                travel_request.save()
                messages.success(request, f"Approved travel request: {travel_request.name}")
            except smtplib.SMTPAuthenticationError:
                messages.error(request, "Email server not working.")
                return redirect("view_tr_approval")
        return redirect("view_tr_approval")


def reject_travel_request(request):
    if request.method == "POST":
        treq_id = request.POST["treq_id"]
        reject_reason = request.POST["reject_reason"]
        travel_request = TravelRequest.objects.get(id=int(treq_id))
        if travel_request.status == "Submitted":
            try:
                link = settings.BASE_URL + f"view_travel_request/{treq_id}"
                send_mail(
                    subject="Travel Request Rejected",
                    message=notification_reject_tr(travel_request.name, request.user.profile, reject_reason, link),
                    from_email=EMAIL_HOST_USER,
                    recipient_list=[travel_request.requestor.email],
                    fail_silently=not DEBUG,
                )
                travel_request.status = "Draft"
                travel_request.save()
                messages.success(request, f"Rejected with reason: {reject_reason}.")
            except smtplib.SMTPAuthenticationError:
                messages.error(request, "Email server not working.")
                return redirect("view_tr_approval")
        return redirect("view_tr_approval")


def ol_approval_traval_request(request):
    if request.method == "POST":
        treq_id = request.POST["treq_id"]
        travel_request = TravelRequest.objects.get(id=int(treq_id))
        if travel_request.status == "Approved":
            try:
                link = settings.BASE_URL + f"view_travel_request/{treq_id}"
                send_mail(
                    subject="Travel Request Special Approved",
                    message=notification_approval_tr(travel_request.name, request.user.profile, link),
                    from_email=EMAIL_HOST_USER,
                    recipient_list=[travel_request.requestor.email],
                    fail_silently=not DEBUG,
                )
                travel_request.status = "Sp. Approved"
                travel_request.save()
                messages.success(request, f"Special approved travel request: {travel_request.name}.")
            except smtplib.SMTPAuthenticationError:
                messages.error(request, "Email server not working.")
                return redirect("view_tr_approval")
        return redirect("view_tr_approval")


def ol_reject_traval_request(request):
    if request.method == "POST":
        treq_id = request.POST["treq_id"]
        reject_reason = request.POST["reject_reason"]
        travel_request = TravelRequest.objects.get(id=int(treq_id))
        if travel_request.status == "Approved":
            try:
                link = settings.BASE_URL + f"view_travel_request/{treq_id}"
                send_mail(
                    subject="Travel Request Rejected",
                    message=notification_reject_tr(travel_request.name, request.user.profile, reject_reason, link),
                    from_email=EMAIL_HOST_USER,
                    recipient_list=[travel_request.requestor.email],
                    fail_silently=not DEBUG,
                )
                travel_request.status = "Draft"
                travel_request.save()
                messages.success(request, f"Rejected with reason: {reject_reason}.")
            except smtplib.SMTPAuthenticationError:
                messages.error(request, "Email server not working.")
                return redirect("view_tr_approval")
        return redirect("view_tr_approval")
