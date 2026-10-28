from django.shortcuts import render

# Create your views here.

def demo(request):

    return render(request, "base.html")

def login_page(request):
    return render(request, "Authentication/login.html")
