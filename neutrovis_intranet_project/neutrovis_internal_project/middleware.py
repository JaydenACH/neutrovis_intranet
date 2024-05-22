from django.conf import settings
from django.shortcuts import redirect


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        whitelist = [
            '/admin',
            settings.LOGIN_URL,
        ]

        if not request.user.is_authenticated:
            if not any(request.path.startswith(url) for url in whitelist):
                return redirect(f'{settings.LOGIN_URL}?next={request.path}')

        response = self.get_response(request)
        return response
