from datetime import datetime, timezone, timedelta
from random import choice
from string import digits
from time import time

from django.db.models import Q
from django.core.mail import send_mail
from django.core.cache import caches, cache

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet, ReadOnlyModelViewSet

from .models import (
    User,
    Role,
    RoleMember,
    IdentityChoice,
    TrustedUser,
    Quota,
    SourceChoice,
    Permission,
    Privacy,
    Notification,
    Follow,
    SchoolChoice,
)
from .serializers import (
    UserDetailReadSerializer,
    UserBriefSerializer,
    QuotaSerializer,
    PermissionSerializer,
    PrivacySerializer,
    RoleBriefSerializer,
    RoleBriefSelfSerializer,
    UserCreateSerializer,
    RoleDetailSerializer,
    RoleFullSerializer,
    RoleSerializer,
    NotificationSerializer,
)
from .yunxiao import login as yunxiao_login
from gt.permissions import Hccaptcha
from gt.jwt import GtSignature
from gt_coin.models import Coin, CoinRecordType
import gt_coin.amount as coin_amount

email_verify_code = caches["default"]


def random_verify_code(length=6):
    return "".join([choice(digits) for _ in range(length)])


def get_authorization(user, remember_me):
    payload = {
        "user_id":
        user.id,
        "user_version":
        user.version,
        "source":
        SourceChoice.WEB,
        "exp":
        (datetime.now(timezone.utc) +
         timedelta(days=30) if remember_me else datetime.now(timezone.utc) +
         timedelta(minutes=15)).timestamp(),
    }
    signature = GtSignature.calculate_signature(payload)
    return {"payload": payload, "signature": signature}


def make_user_response(user, login=False, remember_me=False):
    roles = Role.objects.filter(members__user=user,
                                deleted=False).order_by("id")
    captcha_expire_time = cache.get(f"captcha_valid:{user.id}") or 0
    signed = bool(user.coin.record_today.sign)
    return Response({
        "msg":
        "ok",
        "authorization":
        get_authorization(user, remember_me) if login else None,
        "user":
        UserDetailReadSerializer(user).data,
        "quota":
        QuotaSerializer(user.quota).data,
        "permission":
        PermissionSerializer(user.permission).data,
        "coin":
        user.coin.total,
        "signed":
        signed,
        "roles":
        RoleBriefSelfSerializer(roles, many=True, context={
            "safe": True
        }).data,
        "captcha_expire_time":
        captcha_expire_time,
    })


class UserViewset(ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    search_fields = ["real_name", "^username"]

    def get_serializer_class(self):
        return UserBriefSerializer

    def get_queryset(self):
        if User.has_permission(self.request.user, "admin_user"):
            return User.objects.order_by("id")
        else:
            queryset = (User.objects.filter(
                Q(privacy__allow_show_in_list=True)
                | Q(trusted_users__trusted_user=self.request.user)).exclude(
                    id=self.request.user.id).distinct())
        return queryset.order_by("id")

    def get_object(self):
        pk = self.kwargs.get("pk")
        queryset = self.get_queryset()
        if pk.isdigit():
            return queryset.get(id=pk)
        return queryset.get(username=pk)

    @action(detail=False,
            methods=["post"],
            url_path="login",
            permission_classes=[Hccaptcha])
    def login(self, request):
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "").strip()
        remember_me = request.data.get("remember_me") == True

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise AuthenticationFailed("用户不存在")
        if not user.is_active:
            raise AuthenticationFailed("用户已被封禁")

        if user.check_password(password):
            user.last_login = datetime.now(timezone.utc)
            user.add_captcha_expire_seconds(600, update=False)
            user.save()
            cache.set(
                f"captcha_valid:{user.id}",
                int(time()) + user.captcha_expire_seconds - 1,
                timeout=user.captcha_expire_seconds,
            )
            return make_user_response(user, True, remember_me)
        else:
            raise AuthenticationFailed("用户名或密码错误")

    @action(
        detail=False,
        methods=["post"],
        url_path="register-with-yunxiao",
        permission_classes=[Hccaptcha],
    )
    def register_with_yunxiao(self, request):
        username = request.data.get("username").strip()
        yunxiao_username = request.data.get("yunxiao_username").strip()
        password = request.data.get("password").strip()
        school = request.data.get("school")
        invite_username = request.data.get("invite_username")
        invite_user = None

        if school not in [i.value for i in SchoolChoice]:
            raise ValidationError("学校不存在")
        if invite_username:
            invite_user = User.objects.filter(username=invite_username).first()
            if not invite_user:
                raise ValidationError("邀请用户不存在")
        if User.objects.filter(username=username).exists():
            raise ValidationError("该用户名已被使用")

        yunxiao_data = yunxiao_login(yunxiao_username, password, school)
        if yunxiao_data["status"] != "success":
            raise ValidationError(f"云校验证出错：{yunxiao_data['msg']}")

        yunxiao_data = yunxiao_data["data"]
        if User.objects.filter(student_id=yunxiao_data["account"],
                               school=school).exists():
            raise ValidationError("该云校账号已被其他用户绑定")

        quota = Quota.objects.create()
        permission = Permission.objects.create()
        privacy = Privacy.objects.create()
        coin = Coin.objects.create()

        user = User.objects.create_user(
            username=username,
            password=password,
            mobile=yunxiao_data["mobile"],
            real_name=yunxiao_data['name'],
            school=school,
            identity=(yunxiao_data['roles'][0]["roleName"] if len(
                yunxiao_data['roles']) > 0 else IdentityChoice.OTHER),
            quota=quota,
            permission=permission,
            privacy=privacy,
            coin=coin,
        )
        user.last_login = datetime.now(timezone.utc)
        user.save()
        role = Role.generate_default_role(user)

        coin.add_record(
            coin_amount.REGISTER,
            CoinRecordType.REGISTER,
            detail=f"注册奖励",
        )
        if invite_user:
            coin.add_record(
                coin_amount.INVITE_BY,
                CoinRecordType.INVITE,
                detail=f"邀请用户ID={invite_user.id}",
            )
            invite_user.coin.add_record(
                coin_amount.INVITE,
                CoinRecordType.INVITE,
                detail=f"注册用户ID={user.id}",
            )

        # try:
        #     role_name = chatgpt_get_response(
        #         f"我叫{user.real_name}，性别{user.gender}，请为我生成论坛用户名。用户名应为4或5个字，好听、有诗意，不泄露姓名，使用名字中姓氏之外的一个字，具有一定本意，可以使用拆字、谐音梗的方式，符合青少年。仅输出生成的一个用户名"
        #     )
        #     role.name = role_name
        #     role.save()
        # except Exception as e:
        #     print("生成角色名失败", e)

        return make_user_response(user, login=True, remember_me=False)

    @action(
        detail=False,
        methods=["post"],
        url_path="email_verifycode",
        permission_classes=[IsAuthenticated],
    )
    def email_verifycode(self, request):
        code_tmp = request.data.get("code").strip()
        code = email_verify_code.get(code_tmp)
        email_verify_code.delete(code_tmp)
        if (not code) or (code["user_id"] != request.user.id):
            raise ValidationError("验证码错误或过期")
        user = request.user
        user.email = code["email"]
        user.save()
        return make_user_response(user, True)

    @action(
        detail=False,
        methods=["post"],
        url_path="email_sendcode",
        permission_classes=[IsAuthenticated],
    )
    def email_sendcode(self, request):
        email = request.data.get("email").strip()
        verify_code = random_verify_code()
        email_verify_code.set(verify_code, {
            "email": email,
            "user_id": request.user.id
        }, 60 * 5)
        send_mail(
            "瓜田 - 邮箱绑定",
            "您在瓜田上提交了绑定邮箱的请求，您的验证码为 {} ， 有效期为五分钟 ，如不是您本人操作请忽略。".format(
                verify_code),
            "gt-noreply@qdzx.icu",
            [email],
            fail_silently=False,
        )
        return Response({"msg": "ok"})

    def create(self, request, *args, **kwargs):
        User.has_permission(request.user, "admin_user", raise_exception=True)
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if User.objects.filter(
                username=serializer.validated_data["username"]).exists():
            raise ValidationError("该用户名已存在")

        quota = Quota.objects.create()
        permission = Permission.objects.create()
        privacy = Privacy.objects.create()
        coin = Coin.objects.create()
        user = User.objects.create_user(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
            real_name=serializer.validated_data["real_name"],
            student_id=serializer.validated_data["student_id"],
            identity=serializer.validated_data["identity"],
            school=serializer.validated_data["school"],
            quota=quota,
            permission=permission,
            privacy=privacy,
            coin=coin,
        )

        Role.generate_default_role(user)

        return make_user_response(user, False)

    @action(
        detail=False,
        methods=["get"],
        url_path="info",
        permission_classes=[IsAuthenticated],
    )
    def info(self, request):
        return make_user_response(request.user, True,
                                  request.GET.get("remember_me") == "true")

    @action(
        detail=False,
        methods=["post", "get"],
        url_path="captcha",
        permission_classes=[IsAuthenticated, Hccaptcha],
    )
    def captcha(self, request):
        user = request.user
        captcha_expire_time = cache.get(f"captcha_valid:{user.id}") or 0
        return Response({
            "msg": "ok",
            "captcha_expire_time": captcha_expire_time
        })


class UserSettingViewset(GenericViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"], url_path="password")
    def change_password(self, request):
        user: User = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        remember_me = request.data.get("remember_me") == True

        if not user.check_password(old_password):
            raise ValidationError("原密码错误")

        user.set_password(new_password)
        user.version += 1
        user.add_captcha_expire_seconds(1800, update=False)
        user.save()

        return make_user_response(user, True, remember_me)

    @action(detail=False, methods=["get", "put"], url_path="privacy")
    def privacy(self, request):
        user = request.user
        trusted_users = User.objects.filter(trusted_by_users__user=user)
        if request.method == "PUT":
            serializer = PrivacySerializer(user.privacy,
                                           data=request.data,
                                           partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            new_trusted_users = serializer.validated_data.get("trusted_users")

            if new_trusted_users is not None:
                old_trusted_users = user.trusted_users.values_list(
                    "trusted_user_id", flat=True)
                to_add, to_remove = [], []
                for new_trusted_user in new_trusted_users:
                    if new_trusted_user not in old_trusted_users:
                        to_add.append(new_trusted_user)
                for old_trusted_user in old_trusted_users:
                    if old_trusted_user not in new_trusted_users:
                        to_remove.append(old_trusted_user)
                TrustedUser.objects.filter(
                    user=user, trusted_user_id__in=to_remove).delete()
                for trusted_user_id in to_add:
                    TrustedUser.objects.create(user=user,
                                               trusted_user_id=trusted_user_id)

        return Response({
            "msg":
            "ok",
            "privacy":
            PrivacySerializer(user.privacy).data,
            "trusted_users":
            UserBriefSerializer(trusted_users, many=True).data,
        })


class RoleViewset(ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = RoleBriefSerializer
    search_fields = ["name"]
    filterset_fields = [
        "followers__follower",
        "followings__following",
    ]

    def get_queryset(self):
        _queryset = Role.objects.exclude(is_private=True).exclude(deleted=True)
        queryset_my = Role.objects.none()
        if self.request.user.is_authenticated:
            queryset_my = Role.objects.filter(members__user=self.request.user)
        queryset = (_queryset | queryset_my).exclude(deleted=True).distinct()
        return queryset.order_by("id")

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if (request.user.is_authenticated
                and instance.members.filter(user=request.user).exists()):
            serializer = RoleFullSerializer(
                instance, context=self.get_serializer_context())
        else:
            serializer = RoleDetailSerializer(
                instance, context=self.get_serializer_context())
        return Response({"msg": "ok", "data": serializer.data})

    def check_editable(self, request):
        role = self.get_object()
        if not role.editable:
            raise ValidationError("当前角色不允许编辑")
        elif not RoleMember.objects.filter(
                user=request.user, role=role, is_owner=True).exists():
            raise ValidationError("仅所有者可编辑角色")

    def update(self, request, *args, **kwargs):
        role = self.get_object()
        self.check_editable(request)

        serializer = RoleFullSerializer(role,
                                        data=request.data,
                                        partial=True,
                                        context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        new_members = serializer.validated_data.get("members_id")

        if new_members is not None:
            old_members = role.members.values_list("user_id", flat=True)
            to_add, to_remove = [], []
            for new_member in new_members:
                if new_member not in old_members:
                    to_add.append(new_member)
            for old_member in old_members:
                if old_member not in new_members:
                    to_remove.append(old_member)
            RoleMember.objects.filter(role=role,
                                      is_owner=False,
                                      user_id__in=to_remove).delete()
            for user_id in to_add:
                RoleMember.objects.create(role=role, user_id=user_id)

        if getattr(role, "_prefetched_objects_cache", None):
            role._prefetched_objects_cache = {}

        return Response({"msg": "ok", "data": serializer.data})

    def create(self, request, *args, **kwargs):
        user = request.user
        if user.roles.count() >= user.quota.role_count_limit:
            raise ValidationError(f"你的角色数超过限制{user.quota.role_count_limit}")
        serializer = RoleFullSerializer(data=request.data,
                                        context={"user": user})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        RoleMember.objects.create(user=user,
                                  role=serializer.instance,
                                  is_owner=True)

        user.add_captcha_expire_seconds(600)

        return Response(
            {
                "msg": "ok",
                "data": RoleBriefSerializer(serializer.instance).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def perform_destroy(self, instance):
        self.check_editable(self.request)
        instance.deleted = True
        instance.save(update_fields=["deleted"])

    @action(
        detail=True,
        methods=["post"],
        url_path="follow",
        permission_classes=[IsAuthenticated],
    )
    def follow(self, request, pk):
        role = request.role
        instance = self.get_object()
        follow_item, created = Follow.objects.get_or_create(follower=role,
                                                            following=instance)
        if not created:
            follow_item.delete()
            instance.follower_count -= 1
            instance.save(update_fields=["follower_count"])
            role.following_count -= 1
            role.save(update_fields=["following_count"])
        else:
            instance.follower_count += 1
            instance.save(update_fields=["follower_count"])
            role.following_count += 1
            role.save(update_fields=["following_count"])
        return Response({
            "msg": "ok",
            "followed": created,
            "follower_count": instance.follower_count,
        })


class NotificationViewset(GenericViewSet, ListModelMixin):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    filterset_fields = ["is_read"]

    def get_queryset(self):
        return Notification.objects.filter(
            role=self.request.role).order_by("-id")

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        unread_count = self.get_queryset().filter(is_read=False).count()
        response.data.update({"unread_count": unread_count})
        return response

    def delete(self, request, *args, **kwargs):
        self.get_queryset().delete()
        return Response({"msg": "ok"})

    @action(methods=["post"], detail=False, url_path="read_all")
    def read_all(self, request):
        self.get_queryset().update(is_read=True)
        return Response({"msg": "ok"})

    @action(methods=["post"], detail=True, url_path="read")
    def read(self, request, pk):
        instance = self.get_object()
        instance.is_read = True
        instance.save(update_fields=["is_read"])
        return Response({"msg": "ok"})
