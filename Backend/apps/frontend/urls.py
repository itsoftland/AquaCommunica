from django.urls import path
from . import views as vw

urlpatterns = [
    path('login/', vw.login_page, name="login_page"),
    path('dashboard/', vw.dashboard, name="dashboard"),
    path('audit-logs/', vw.audit_log_page, name="audit_log_page"),
    path('customers/', vw.customer_page, name="customer_page"),
]