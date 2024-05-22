from neutrovis_internal_apps.models import Currency, SystemParameter
import requests
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Fetches exchange rates from BNM API and updates the database'

    def handle(self, *args, **options):
        myr_currency = Currency.objects.get(symbol="MYR")
        if not myr_currency:
            myr = Currency(
                symbol="MYR",
                exchange_rate=1.0,
                active=True,
            )
            myr.save()
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
        except requests.RequestException as e:
            print(str(e))
