from .models import TravelRequest, TravelRequestLine
from datetime import datetime, date
from decimal import Decimal


def get_tr_number(rec_id: int) -> str:
    year = date.today().year
    running_number = f"TR/{year}/{rec_id:05d}"
    return running_number


def calculate_date_delta(start_date: str, end_date: str) -> int:
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
    date_delta = end_date_obj - start_date_obj
    return date_delta.days


def check_date(start_date: str, end_date: str) -> bool:
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
    if end_date_obj < start_date_obj:
        return False
    return True


def compute_travel_request_amount(treq_id: int) -> None:
    travel_request = TravelRequest.objects.get(id=int(treq_id))
    travel_request_lines = TravelRequestLine.objects.filter(travel_request=travel_request)
    total_flight_expense = Decimal(0)
    total_accomodation_expense = Decimal(0)
    total_flight_limit = Decimal(0)
    total_accomodation_limit = Decimal(0)
    total_flight_expense_usd = Decimal(0)
    total_accomodation_expense_usd = Decimal(0)
    total_flight_limit_usd = Decimal(0)
    total_accomodation_limit_usd = Decimal(0)
    for treq_line in travel_request_lines:
        if treq_line.flight_currency.symbol == "USD":
            total_flight_expense_usd += treq_line.estimated_flight_expense
            total_flight_limit_usd += treq_line.flight_limit
        else:
            total_flight_expense += treq_line.estimated_flight_expense
            total_flight_limit += treq_line.flight_limit
        if treq_line.accomodation_currency.symbol == "USD":
            total_accomodation_expense_usd += treq_line.estimated_accomodation_expense
            total_accomodation_limit_usd += treq_line.accomodation_limit
        else:
            total_accomodation_expense += treq_line.estimated_accomodation_expense
            total_accomodation_limit += treq_line.accomodation_limit
    travel_request.overlimit = any(line.overlimit for line in travel_request_lines)
    travel_request.total_flight_expense = total_flight_expense
    travel_request.total_accomodation_expense = total_accomodation_expense
    travel_request.total_flight_limit = total_flight_limit
    travel_request.total_accomodation_limit = total_accomodation_limit
    travel_request.total_flight_expense_usd = total_flight_expense_usd
    travel_request.total_accomodation_expense_usd = total_accomodation_expense_usd
    travel_request.total_flight_limit_usd = total_flight_limit_usd
    travel_request.total_accomodation_limit_usd = total_accomodation_limit_usd
    travel_request.save()
