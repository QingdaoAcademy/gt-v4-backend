from time import time
from django.db import models
from django.contrib.auth.models import AbstractUser
from rest_framework.exceptions import PermissionDenied
from gt.validators import validate_no_invisible_characters


class IdentityChoice(models.TextChoices):
    STUDENT = "学生"
    TEACHER = "教师"
    PARENT = "家长"
    OTHER = "其他"


class SchoolChoice(models.TextChoices):
    QDZX = "qa", "青岛中学"
    JJLXX = "jjl", "金家岭学校"


class SourceChoice(models.TextChoices):
    WEB = "web"
    WECHAT = "wechat"


class Quota(models.Model):
    role_count_limit = models.IntegerField(default=10, verbose_name="角色数量限制")
    role_max_members = models.IntegerField(default=5, verbose_name="角色最大成员数")
    image_max_size = models.IntegerField(
        default=1024 * 1024 * 10, verbose_name="图片最大尺寸"
    )
    image_24h_count_limit = models.IntegerField(
        default=100, verbose_name="图片24小时上传数量限制"
    )
    image_24h_size_limit = models.IntegerField(
        default=1024 * 1024 * 300, verbose_name="图片24小时上传尺寸限制"
    )
    video_max_size = models.IntegerField(
        default=1024 * 1024 * 512, verbose_name="视频最大尺寸"
    )
    video_24h_count_limit = models.IntegerField(
        default=5, verbose_name="视频24小时上传数量限制"
    )
    video_24h_size_limit = models.IntegerField(
        default=1024 * 1024 * 1024, verbose_name="视频24小时上传尺寸限制"
    )
    post_24h_count_limit = models.IntegerField(
        default=15, verbose_name="帖子24小时发布数量限制"
    )
    comment_24h_count_limit = models.IntegerField(
        default=50, verbose_name="评论24小时发布数量限制"
    )

    class Meta:
        verbose_name = verbose_name_plural = "配额"


class Permission(models.Model):
    base_admin = models.BooleanField(default=False)
    admin_user = models.BooleanField(default=False)
    admin_role = models.BooleanField(default=False)
    admin_forum = models.BooleanField(default=False)
    admin_report = models.BooleanField(default=False)
    admin_file = models.BooleanField(default=False)
    no_review = models.BooleanField(default=False)
    admin_alumni = models.BooleanField(default=False)


class Privacy(models.Model):
    allow_show_in_list = models.BooleanField(default=False)
    accept_join_role = models.BooleanField(default=False)


class User(AbstractUser):
    real_name = models.CharField(max_length=40, verbose_name="真实姓名")
    mobile = models.CharField(
        max_length=16, null=True, blank=True, verbose_name="手机号码"
    )
    identity = models.CharField(
        choices=IdentityChoice.choices, max_length=10, verbose_name="身份"
    )
    school = models.CharField(
        choices=SchoolChoice.choices,
        default=SchoolChoice.QDZX,
        max_length=10,
        verbose_name="学校",
    )
    student_id = models.CharField(
        max_length=20, null=True, blank=True, verbose_name="学号"
    )
    version = models.IntegerField(default=1, verbose_name="版本号")

    quota = models.OneToOneField(Quota, on_delete=models.PROTECT, verbose_name="配额")
    permission = models.OneToOneField(
        Permission, on_delete=models.PROTECT, verbose_name="权限"
    )
    privacy = models.OneToOneField(
        Privacy, on_delete=models.PROTECT, verbose_name="隐私设置"
    )
    coin = models.OneToOneField(
        "gt_coin.Coin", on_delete=models.PROTECT, verbose_name="金币"
    )

    captcha_expire_seconds = models.IntegerField(
        default=60, verbose_name="验证码过期时间（秒）"
    )  # seconds

    first_name = None
    last_name = None

    @property
    def role_ids(self):
        if not hasattr(self, "_role_ids"):
            self._role_ids = RoleMember.objects.filter(user=self).values_list(
                "role_id", flat=True
            )
        return self._role_ids

    @classmethod
    def has_permission(cls, user, permission: str, raise_exception=False):
        res = user and user.is_authenticated and getattr(user.permission, permission)
        if raise_exception and not res:
            raise PermissionDenied
        return res

    def add_captcha_expire_seconds(self, seconds: int = 120, update: bool = True):
        self.captcha_expire_seconds += seconds
        if update:
            self.save(update_fields=["captcha_expire_seconds"])


class TrustedUser(models.Model):
    user = models.ForeignKey(User, models.CASCADE, related_name="trusted_users")
    trusted_user = models.ForeignKey(
        User, models.CASCADE, related_name="trusted_by_users"
    )


def external_links_default():
    return {
        "github": "",
        "wechat": "",
        "qq": "",
        "twitter": "",
        "weibo": "",
        "douyin": "",
        "other": "",
    }


class Role(models.Model):
    name = models.CharField(
        max_length=20, validators=[validate_no_invisible_characters]
    )
    avatar = models.URLField(null=True)
    description = models.CharField(
        default="",
        max_length=50,
        validators=[validate_no_invisible_characters],
        blank=True,
    )
    external_links = models.JSONField(default=external_links_default)

    is_private = models.BooleanField(default=False)
    is_shared = models.BooleanField(default=False)
    show_user_info = models.BooleanField(default=False)
    show_like = models.BooleanField(default=True)
    editable = models.BooleanField(default=True)

    verify = models.CharField(max_length=64, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    deleted = models.BooleanField(default=False)

    following_count = models.IntegerField(default=0)
    follower_count = models.IntegerField(default=0)

    @classmethod
    def generate_default_role(cls, user: User):
        role1 = Role.objects.create(
            name=f"角色{int(time()) % 10000}",
            editable=True,
            show_user_info=False,
        )
        role2 = Role.objects.create(
            name="匿名角色",
            editable=False,
            is_private=True,
            avatar="https://image.qaguatian.com/anonymous.jpg/avatar",
        )
        RoleMember.objects.create(user=user, role=role1, is_owner=True)
        RoleMember.objects.create(user=user, role=role2, is_owner=True)
        return role1

    def is_member(self, user: User):
        if not user.is_authenticated:
            return False
        return self.id in user.role_ids

    def is_owner(self, user: User):
        return RoleMember.objects.filter(role=self, user=user, is_owner=True).exists()

    @property
    def owner(self) -> User:
        return self.members.filter(is_owner=True).first().user


class RoleMember(models.Model):
    user = models.ForeignKey(User, models.CASCADE, related_name="roles")
    role = models.ForeignKey(Role, models.CASCADE, related_name="members")

    is_owner = models.BooleanField(default=False)


class Follow(models.Model):
    follower = models.ForeignKey(Role, models.CASCADE, related_name="followings")
    following = models.ForeignKey(Role, models.CASCADE, related_name="followers")

    create_time = models.DateTimeField(auto_now_add=True)


class NotificationType(models.TextChoices):
    SYSTEM = "system"
    POST_COMMENT = "post_comment"
    COMMENT_REPLY = "comment_reply"
    POST_LIKE = "post_like"
    COMMENT_LIKE = "comment_like"


class Notification(models.Model):
    role = models.ForeignKey(Role, models.CASCADE, related_name="notifications")
    type = models.CharField(choices=NotificationType.choices, max_length=31)
    content = models.JSONField(default=dict)
    time = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
