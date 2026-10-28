from django.urls import path
from . import views as vw

urlpatterns = [
    path('login/', vw.login_page, name="login_page"),
    path('dashboard/', vw.dashboard, name="dashboard"),
]