from django.urls import path

from . import views
from .plugin_settings import MANAGER_URL

urlpatterns = [
    path("manager/", views.Manager.as_view(), name=MANAGER_URL),
]
