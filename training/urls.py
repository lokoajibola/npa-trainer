from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('create-training/', views.create_training_program, name='create_training'),
    path('set-criteria/<int:training_id>/', views.set_selection_criteria, name='set_selection_criteria'),
    path('review-nomination/<int:nomination_id>/', views.review_nomination, name='review_nomination'),
    path('admin-review-nomination/<int:nomination_id>/', views.admin_review_nomination, name='admin_review_nomination'),
    path('approvals/', views.approval_list, name='approval_list'),
    path('approve-nomination/<int:nomination_id>/', views.approve_nomination, name='approve_nomination'),
    path('print-nomination/<int:nomination_id>/', views.print_nomination, name='print_nomination'),
    path('upload-nominal-roll/', views.upload_nominal_roll, name='upload_nominal_roll'),
    path('search-staff-trainings/', views.search_staff_trainings, name='search_staff_trainings'),
    # API endpoints
    path('api/search-staff/', views.search_staff, name='search_staff'),
    path('api/add-staff-to-nomination/', views.add_staff_to_nomination, name='add_staff_to_nomination'),
    path('api/remove-staff-from-nomination/', views.remove_staff_from_nomination, name='remove_staff_from_nomination'),
    path('verify-nomination/<int:nomination_id>/', views.verify_nomination, name='verify_nomination'),
    path('reset-nominal-roll/', views.reset_nominal_roll, name='reset_nominal_roll'),
    # Authentication URLs
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    
]