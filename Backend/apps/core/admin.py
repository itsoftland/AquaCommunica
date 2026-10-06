from django.contrib import admin
from .models.customuser import CustomUser
from .models.profiles import UserProfile


# Register your models here.
admin.site.register(CustomUser)
admin.site.register(UserProfile)