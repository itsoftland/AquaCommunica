from django.urls import path
from .views import demo
urlpatterns = [
    path('', demo, name="demo"),
]