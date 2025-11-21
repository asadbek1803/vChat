from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Account, Contact, Message


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    # Admin panelda ko'rinadigan ustunlar
    list_display = (
        'telegram_id',
        'first_name',
        'last_name',
        'username',
        'is_online',
        'is_banned',
        'created_at',
    )

    # Qidirish maydonlari
    search_fields = (
        'first_name',
        'last_name',
        'telegram_id',
        'username',
    )

    readonly_fields = (
        'created_at',
        'updated_at',
        'last_seen',
        'telegram_id',
    )

    # Formada maydonlarni guruhlash (chiroyli ko'rinish uchun)
    fieldsets = (
        ('Asosiy maʼlumotlar', {
            'fields': ('telegram_id', 'first_name', 'last_name', 'username', 'bio')
        }),
        ('Holat', {
            'fields': ('is_online', 'is_banned')
        }),
        ('Tizim maʼlumotlari', {
            'fields': ('created_at', 'updated_at', 'last_seen'),
        }),
    )

    # Yangi foydalanuvchi qo'shishda ko'rinadigan maydonlar
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('telegram_id', 'first_name', 'last_name', 'username'),
        }),
    )

    ordering = ('-created_at',)
    list_filter = ('is_online', 'is_banned', 'created_at')


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['user', 'contact', 'custom_name', 'is_accepted', 'created_at']
    list_filter = ['is_accepted', 'created_at']
    search_fields = ['user__username', 'contact__username', 'custom_name']
    readonly_fields = ['created_at', 'accepted_at']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'receiver', 'created_at']
    list_filter = ['created_at']
    search_fields = ['sender__username', 'receiver__username', 'text']
    readonly_fields = ['created_at']