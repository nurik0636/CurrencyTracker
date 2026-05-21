from django.db import models
from django.contrib.auth.models import User


class Currency(models.Model):
    name = models.CharField(max_length=10)
    value = models.FloatField()
    date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        null=True, blank=True, related_name="rates"
    )

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.name} - {self.value}"


class UserProfile(models.Model):
    ROLE_CHOICES = [("user", "Пользователь"), ("admin", "Администратор")]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="user")

    def is_admin(self):
        return self.role == "admin"

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class AlertSetting(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="alerts")
    currency = models.CharField(max_length=10, default="KZT")
    threshold = models.FloatField()
    direction = models.CharField(
        max_length=5,
        choices=[("above", "Выше"), ("below", "Ниже")]
    )
    telegram_chat_id = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} | USD/{self.currency} {self.direction} {self.threshold}"