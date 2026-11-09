from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/adopter/', views.adopter_dashboard, name='adopter_dashboard'),
    path('dashboard/staff/', views.staff_dashboard, name='staff_dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('users/', views.user_list, name='user_list'),
    path('users/create-staff/', views.staff_create, name='staff_create'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('dogs/', views.public_dog_list, name='public_dog_list'),
    path('dogs/<int:pk>/', views.public_dog_detail, name='public_dog_detail'),
    path('interviews/book/<int:dog_id>/', views.interview_book, name='interview_book'),
    path('staff/dogs/', views.dog_list, name='dog_list'),
    path('staff/dogs/create/', views.dog_create, name='dog_create'),
    path('staff/dogs/<int:pk>/', views.dog_detail, name='dog_detail'),
    path('staff/dogs/<int:pk>/edit/', views.dog_edit, name='dog_edit'),
]
