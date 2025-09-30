from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from .models import User, Role, Quota, Permission, Privacy, Notification, Follow
from gt_forum.tasks import review_with_aliyun
from gt_admin._models import ReviewStatusChoice
from gt_coin.models import CoinRecordType
import gt_coin.amount as coin_amount


class UserDetailReadSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = read_only_fields = (
            "id",
            "username",
            "real_name",
            "student_id",
            "school",
            "date_joined",
            "identity",
            "is_active",
            "email",
        )


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = read_only_fields = ("id", "username", "real_name", "student_id")


class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "real_name", "password", "identity", "school", "student_id"]


class IsRoleOwnerField(serializers.ReadOnlyField):
    def to_representation(self, value):
        user = self.context.get("user")
        if not user:
            return None
        return value.members.get(user=user).is_owner


class QuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quota
        exclude = ("id",)


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        exclude = ("id",)


class PrivacySerializer(serializers.ModelSerializer):
    trusted_users = serializers.JSONField(write_only=True, required=False)

    class Meta:
        model = Privacy
        exclude = ("id",)

    def validate_trusted_users(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("trusted_users应为列表")
        for user_id in value:
            if not isinstance(user_id, int):
                raise serializers.ValidationError("trusted_users的项应为整数")
        return value


class RoleIdField(serializers.ReadOnlyField):
    def to_representation(self, obj):
        if obj.is_private and not self.context.get("safe"):
            user = None
            if self.context.get("user"):
                user = self.context.get("user")
            elif self.context.get("request"):
                user = self.context.get("request").user
            if not user or not obj.is_member(user):
                return None
        return obj.id


class RoleBriefSelfSerializer(serializers.ModelSerializer):
    unread_notification_count = serializers.SerializerMethodField()

    def get_unread_notification_count(self, obj):
        return Notification.objects.filter(role=obj, is_read=False).count()

    class Meta:
        model = Role
        fields = read_only_fields = (
            "id",
            "name",
            "avatar",
            "verify",
            "is_private",
            "is_active",
            "unread_notification_count",
        )


class RoleBriefSerializer(serializers.ModelSerializer):
    id = RoleIdField(source="*")

    class Meta:
        model = Role
        fields = read_only_fields = ("id", "name", "avatar", "verify")


class RoleSerializer(serializers.ModelSerializer):
    id = RoleIdField(source="*")
    user_info = serializers.SerializerMethodField()

    def get_user_info(self, obj):
        if obj.show_user_info:
            return UserBriefSerializer(obj.members.get(is_owner=True).user).data

    class Meta:
        model = Role
        fields = read_only_fields = (
            "id",
            "name",
            "avatar",
            "verify",
            "user_info",
            "description",
            "following_count",
            "follower_count",
        )


class RoleAdminSerializer(serializers.ModelSerializer):
    user_info = serializers.SerializerMethodField()

    def get_user_info(self, obj):
        return UserBriefSerializer(obj.members.get(is_owner=True).user).data

    class Meta:
        model = Role
        fields = (
            "id",
            "name",
            "avatar",
            "verify",
            "user_info",
            "description",
            "show_like",
            "is_active",
            "editable",
            "following_count",
            "follower_count",
        )
        read_only_fields = (
            "id",
            "name",
            "avatar",
            "description",
            "following_count",
            "follower_count",
        )


class RoleDetailSerializer(serializers.ModelSerializer):
    id = RoleIdField(source="*")
    user_info = serializers.SerializerMethodField()
    is_owner = IsRoleOwnerField(source="*")
    followed = serializers.SerializerMethodField()

    def get_followed(self, obj):
        request = self.context.get("request")
        if request is None:
            return False
        role = getattr(request, "role", None)
        if role is None:
            return False
        return Follow.objects.filter(follower=role, following=obj).exists()

    def get_user_info(self, obj):
        if obj.show_user_info:
            return UserBriefSerializer(obj.members.get(is_owner=True).user).data

    class Meta:
        model = Role
        fields = (
            "id",
            "name",
            "avatar",
            "description",
            "is_private",
            "is_shared",
            "show_user_info",
            "user_info",
            "show_like",
            "editable",
            "verify",
            "is_owner",
            "followed",
            "following_count",
            "follower_count",
        )


class RoleFullSerializer(serializers.ModelSerializer):
    # 包含敏感信息，只应展示给角色成员；唯一可能用于编辑的Role Serializer

    user_info = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    followed = serializers.SerializerMethodField()

    def get_followed(self, obj):
        request = self.context.get("request")
        if request is None:
            return False
        role = getattr(request, "role", None)
        if role is None:
            return False
        return Follow.objects.filter(follower=role, following=obj).exists()

    def get_user_info(self, obj):
        return UserBriefSerializer(obj.members.get(is_owner=True).user).data

    def get_members(self, obj):
        members_id = (
            obj.members.exclude(is_owner=True)
            .order_by("-is_owner", "id")
            .values_list("user_id", flat=True)
        )
        members = User.objects.filter(id__in=members_id)
        data = UserBriefSerializer(members, many=True).data
        return data

    members_id = serializers.JSONField(write_only=True, required=False)

    def validate_members_id(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("members_id应为列表")
        for user_id in value:
            if not isinstance(user_id, int):
                raise serializers.ValidationError("members_id的项应为整数")
        role_max_members = self.context["user"].quota.role_max_members
        if len(value) > role_max_members:
            raise serializers.ValidationError(
                f"角色成员数不能超过{role_max_members}，请联系管理员提高配额"
            )
        return value

    def is_valid(self, raise_exception=False):
        res = super().is_valid(raise_exception=raise_exception)
        user = self.context["user"]

        if User.has_permission(user, "no_review"):
            return res

        instance = getattr(self, "instance", None)

        _name = self.validated_data.get("name", "")
        _description = self.validated_data.get("description", "")

        queryset = Role.objects.filter(name=_name)
        if instance:
            queryset = queryset.exclude(id=instance.id)
        if queryset.exists():
            raise ValidationError("角色名已被使用")

        need_review = instance is None
        if _name and (instance is None or _name != instance.name):
            need_review = True
        if _description and (instance is None or _description != instance.description):
            need_review = True

        if need_review:
            review_text = _name + "\n" + _description

            if instance is None or _name != instance.name:
                user.coin.add_record(
                    coin_amount.ROLE_REVIEW,
                    CoinRecordType.ROLE,
                    "修改角色名称" if instance else "创建角色",
                    allow_negative=bool(
                        not instance and not user.coin.role_create_reward
                    ),
                )
            review_res = review_with_aliyun(review_text, "nickname_detection")
            if review_res["status"] != ReviewStatusChoice.ACCEPTED:
                user.coin.add_record(
                    coin_amount.ROLE_VIOLATION,
                    CoinRecordType.PUNISH,
                    "角色信息违规",
                )
                raise ValidationError(f"角色信息违规：{review_res['message']}")

        _avatar = self.validated_data.get("avatar", "")
        if instance and instance.avatar and _avatar and _avatar != instance.avatar:
            user.coin.add_record(
                coin_amount.ROLE_AVATAR, CoinRecordType.ROLE, "修改角色头像"
            )

        return res

    def create(self, validated_data):
        res = super().create(validated_data)
        user = self.context["user"]
        coin = user.coin
        if not coin.role_create_reward:
            coin.add_record(
                coin_amount.ROLE_CREATE_REWARD,
                CoinRecordType.ONE_TIME,
                "首次创建角色奖励",
            )
            coin.role_create_reward = True
            coin.save(update_fields=["role_create_reward"])
        return res

    def save(self, **kwargs):
        user = self.context["user"]
        coin = user.coin
        if not coin.role_change_reward:
            coin.add_record(
                coin_amount.ROLE_CHANGE_REWARD,
                CoinRecordType.ONE_TIME,
                "首次修改角色补偿",
            )
            coin.role_change_reward = True
            coin.save(update_fields=["role_change_reward"])
        return super().save(**kwargs)

    class Meta:
        model = Role
        exclude = ("deleted",)
        read_only_fields = (
            "verify",
            "is_active",
            "editable",
            "following_count",
            "follower_count",
        )


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = "__all__"
