from django.contrib import admin
from .models.customuser import CustomUser
from .models.profiles import UserProfile, DealerProfile
from .models.audit import AuditLog
from .models.device import Devices

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(UserProfile)
admin.site.register(DealerProfile)
admin.site.register(AuditLog)
admin.site.register(Devices)