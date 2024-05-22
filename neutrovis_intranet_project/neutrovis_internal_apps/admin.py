from django.contrib import admin
from .models import (UserClaim, Attachment,
                     ExpenseType, AnalyticCode, UserClaimLine,
                     Profile, Currency, SystemParameter, ChatterBox,
                     TravelRequest, TravelRequestLine, Destination, AllowanceLimit,
                     SupportingDocument, Department)


admin.site.register(AnalyticCode)
admin.site.register(Attachment)
admin.site.register(ChatterBox)
admin.site.register(Currency)
admin.site.register(ExpenseType)
admin.site.register(Profile)
admin.site.register(SystemParameter)
admin.site.register(UserClaim)
admin.site.register(UserClaimLine)

admin.site.register(TravelRequest)
admin.site.register(TravelRequestLine)
admin.site.register(Destination)
admin.site.register(AllowanceLimit)
admin.site.register(SupportingDocument)
admin.site.register(Department)