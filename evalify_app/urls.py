from django.urls import path
from . import views

urlpatterns = [
    path('', views.home),
    path('signup/', views.sign_up_html, name='sign_up_html'),
    path('signin/', views.sign_in_html, name='sign_in_html'),
]