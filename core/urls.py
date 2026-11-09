from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

urlpatterns = [
    path('', views.home, name='home'),
    path('privacy/', views.privacy, name='privacy'),
    path('terms/', views.terms, name='terms'),
    path('profile/', views.my_profile, name='my_profile'),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html',
            authentication_form=LoginForm,
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/adopter/', views.adopter_dashboard, name='adopter_dashboard'),
    path('dashboard/staff/', views.staff_dashboard, name='staff_dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('users/', views.user_list, name='user_list'),
    path('users/create-staff/', views.staff_create, name='staff_create'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/delete/', views.admin_user_delete, name='admin_user_delete'),
    path(
        'users/<int:pk>/anonymize/',
        views.admin_user_anonymize,
        name='admin_user_anonymize',
    ),
    path('users/<int:pk>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('dogs/', views.public_dog_list, name='public_dog_list'),
    path('dogs/<int:pk>/', views.public_dog_detail, name='public_dog_detail'),
    path('interviews/', views.interview_list, name='interview_list'),
    path('interviews/book/<int:dog_id>/', views.interview_book, name='interview_book'),
    path('interviews/<int:pk>/', views.interview_detail, name='interview_detail'),
    path('interviews/<int:pk>/cancel/', views.interview_cancel, name='interview_cancel'),
    path(
        'interviews/<int:pk>/confirm-attendance/',
        views.interview_confirm_attendance,
        name='interview_confirm_attendance',
    ),
    path('staff/interviews/', views.staff_interview_list, name='staff_interview_list'),
    path(
        'staff/interviews/<int:pk>/confirm/',
        views.staff_interview_confirm,
        name='staff_interview_confirm',
    ),
    path(
        'staff/interviews/<int:pk>/reject/',
        views.staff_interview_reject,
        name='staff_interview_reject',
    ),
    path(
        'staff/interviews/<int:pk>/result/',
        views.staff_interview_result,
        name='staff_interview_result',
    ),
    path(
        'staff/interviews/<int:interview_pk>/contract/create/',
        views.staff_contract_create,
        name='staff_contract_create',
    ),
    path('contracts/', views.contract_list, name='contract_list'),
    path('contracts/<int:pk>/', views.contract_detail, name='contract_detail'),
    path(
        'contracts/<int:pk>/acknowledge/',
        views.contract_acknowledge,
        name='contract_acknowledge',
    ),
    path('follow-ups/', views.followup_list, name='followup_list'),
    path('follow-ups/<int:pk>/', views.followup_detail, name='followup_detail'),
    path(
        'follow-ups/<int:pk>/submit/',
        views.followup_submit,
        name='followup_submit',
    ),
    path(
        'home-visits/<int:pk>/request-reschedule/',
        views.homevisit_request_reschedule,
        name='homevisit_request_reschedule',
    ),
    path('staff/contracts/', views.staff_contract_list, name='staff_contract_list'),
    path(
        'staff/contracts/<int:pk>/',
        views.staff_contract_detail,
        name='staff_contract_detail',
    ),
    path(
        'staff/contracts/<int:pk>/edit/',
        views.staff_contract_edit,
        name='staff_contract_edit',
    ),
    path(
        'staff/contracts/<int:pk>/activate/',
        views.staff_contract_activate,
        name='staff_contract_activate',
    ),
    path(
        'staff/contracts/<int:contract_pk>/home-visits/create/',
        views.homevisit_create,
        name='homevisit_create',
    ),
    path(
        'staff/home-visits/<int:pk>/edit/',
        views.homevisit_edit,
        name='homevisit_edit',
    ),
    path(
        'staff/home-visits/<int:pk>/approve/',
        views.homevisit_approve,
        name='homevisit_approve',
    ),
    path(
        'staff/home-visits/<int:pk>/deny/',
        views.homevisit_deny,
        name='homevisit_deny',
    ),
    path('staff/follow-ups/', views.staff_followup_list, name='staff_followup_list'),
    path(
        'staff/follow-ups/<int:pk>/',
        views.staff_followup_detail,
        name='staff_followup_detail',
    ),
    path(
        'staff/follow-ups/<int:pk>/evaluate/',
        views.staff_followup_evaluate,
        name='staff_followup_evaluate',
    ),
    path('staff/dogs/', views.dog_list, name='dog_list'),
    path('staff/dogs/create/', views.dog_create, name='dog_create'),
    path('staff/dogs/<int:pk>/', views.dog_detail, name='dog_detail'),
    path('staff/dogs/<int:pk>/edit/', views.dog_edit, name='dog_edit'),
    path('reports/adoption-stats/', views.adoption_stats, name='adoption_stats'),
    path(
        'reports/adoption-stats/csv/',
        views.adoption_stats_csv,
        name='adoption_stats_csv',
    ),
    path('reports/followup-stats/', views.followup_stats, name='followup_stats'),
    path(
        'reports/followup-stats/csv/',
        views.followup_stats_csv,
        name='followup_stats_csv',
    ),
    path('audit-log/', views.audit_log, name='audit_log'),
]
