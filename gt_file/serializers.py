from rest_framework import serializers
from .models import Image, Drop, File, Video
from gt_auth.serializers import RoleBriefSerializer, UserBriefSerializer
from .doge_api import generate_playtoken


class ImageViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = read_only_fields = ("id", "key")


class ImageSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)

    class Meta:
        model = Image
        fields = "__all__"
        read_only_fields = ("id", "key", "create_time", "is_banned", "user")


class FileUploadSerializer(serializers.ModelSerializer):
    expire_days = serializers.IntegerField(default=0)

    class Meta:
        model = File
        fields = ("id", "name", "content_type", "storage", "size", "expire_days")
        read_only_fields = ("id",)


class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        fields = read_only_fields = (
            "id",
            "name",
            "content_type",
            "storage",
            "size",
            "create_time",
            "verified",
        )


class DropDetailSerializer(serializers.ModelSerializer):
    role = RoleBriefSerializer()
    files = FileSerializer(many=True)

    class Meta:
        model = Drop
        fields = "__all__"


class DropSerializer(serializers.ModelSerializer):
    role = RoleBriefSerializer()

    class Meta:
        model = Drop
        exclude = ("files",)


class DropCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Drop
        fields = (
            "id",
            "code",
            "expire_days",
            "require_login",
            "pay_by_download",
            "max_download",
            "storage",
        )
        read_only_fields = ("id", "code")


class VideoSerializer(serializers.ModelSerializer):

    class Meta:
        model = Video
        fields = (
            "id",
            "name",
            "size",
            "create_time",
            "did",
            "vcode",
            "is_active",
        )
        read_only_fields = ("id", "did", "vcode", "is_active", "create_time")


class VideoDetailSerializer(serializers.ModelSerializer):
    playtoken = serializers.SerializerMethodField()

    def get_playtoken(self, obj):
        if not all([obj.did, obj.vcode, obj.is_active]):
            return None
        return generate_playtoken(obj.vcode)

    class Meta:
        model = Video
        fields = (
            "id",
            "name",
            "size",
            "create_time",
            "did",
            "vcode",
            "is_active",
            "playtoken",
        )
        read_only_fields = (
            "id",
            "did",
            "vcode",
            "is_active",
            "create_time",
            "playtoken",
        )
