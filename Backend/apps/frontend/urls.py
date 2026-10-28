from django.urls import path
from .views import demo, login_page
urlpatterns = [
    path('', demo, name="demo"),
    path('login/', login_page, name="login_page"),
]