# accounts/urls.py
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # 📄 Pages
    path('', views.index, name='index'),
    path('chat/', views.chat, name='chat'),
    
    # 🔐 Authentication
    path('api/auth/telegram/', views.telegram_auth_api, name='telegram_auth_api'),
    path('api/logout/', views.logout_api, name='logout_api'),
    
    # 🔍 Search
    path('api/search/users/', views.search_users, name='search_users'),
    
    # 👥 Contacts
    path('api/contacts/add/', views.add_contact, name='add_contact'),
    path('api/contacts/accept/', views.accept_contact, name='accept_contact'),
    path('api/contacts/reject/', views.reject_contact, name='reject_contact'),  # ✅ NEW
    path('api/contacts/', views.get_contacts, name='get_contacts'),
    
    # 💬 Messages
    path('api/messages/<int:contact_id>/', views.get_messages, name='get_messages'),
    path('api/messages/send/', views.send_message, name='send_message'),  # ✅ NEW
]