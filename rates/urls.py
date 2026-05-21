from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('update/', views.update_rates, name='update'),
    path('settings/', views.user_settings, name='settings'),
    path('converter/', views.converter, name='converter'),
    path('history/', views.history_view, name='history'),
    path('delete/<int:rate_id>/', views.delete_rate, name='delete_rate'),
    path('delete-all/', views.delete_all_rates, name='delete_all'),

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),

    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),

    path('admin-panel/', views.admin_panel_view, name='admin_panel'),
    path('admin-panel/role/<int:user_id>/', views.admin_change_role_view, name='change_role'),
    path('admin-panel/delete/<int:user_id>/', views.admin_delete_user_view, name='delete_user'),
]