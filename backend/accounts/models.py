from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.utils import timezone

class AccountManager(BaseUserManager):
    def create_user(self, telegram_id, first_name, password=None):
        user = self.model(
            telegram_id=telegram_id,
            first_name=first_name,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, telegram_id, first_name, password):
        user = self.create_user(telegram_id, first_name, password)
        user.is_admin = True
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class Account(AbstractBaseUser):
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    username = models.CharField(max_length=150, blank=True, null=True, unique=True)
    bio = models.TextField(blank=True, null=True)
    is_online = models.BooleanField(default=False)
    is_banned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    objects = AccountManager()

    USERNAME_FIELD = 'telegram_id'
    REQUIRED_FIELDS = ['first_name']

    def __str__(self):
        return f"{self.first_name} ({self.telegram_id})"

    def has_module_perms(self, app_label):
        return True
    def has_perm(self, perm, obj=None):
        return True

    class Meta:
        ordering = ['-created_at']


class Contact(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='contacts_sent')
    contact = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='contacts_received')
    custom_name = models.CharField(max_length=150, blank=True, null=True)
    is_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('user', 'contact')

    def __str__(self):
        return f"{self.user} -> {self.contact}"


class Message(models.Model):
    MESSAGE_TYPES = (
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
    )
    
    sender = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='received_messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    text = models.TextField(blank=True, null=True)
    
    # Media fields
    media_file = models.FileField(upload_to='chat_media/%Y/%m/%d/', blank=True, null=True)
    media_thumbnail = models.ImageField(upload_to='chat_thumbnails/%Y/%m/%d/', blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.BigIntegerField(blank=True, null=True)
    
    is_read = models.BooleanField(default=False)
    is_deleted_by_sender = models.BooleanField(default=False)
    is_deleted_by_receiver = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}: {self.message_type}"