from django.db import models

from gt_auth.models import User

class GenderChoice(models.TextChoices):
    MALE = "男"
    FEMALE = "女"
    NO = ""


class Alumni(models.Model):
    name = models.CharField(max_length=100)
    avatar = models.URLField(null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, blank=True, choices=GenderChoice.choices)
    year = models.IntegerField()
    description = models.CharField(max_length=100, null=True, blank=True)

    academic_background = models.JSONField(default=list)
    work_experience = models.JSONField(default=list)

    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    contact = models.CharField(max_length=50, null=True, blank=True)

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alumni",
    )
