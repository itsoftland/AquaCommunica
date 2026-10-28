from django.shortcuts import render


def login_page(request):
    return render(request, "Authentication/login.html")

def dashboard(request):
    return render(request, "Dashboard/dashboard.html")

def audit_log_page(request):
    return render(request, "AuditLog/audit_log.html")
