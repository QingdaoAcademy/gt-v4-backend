from random import randint, choice
from string import ascii_letters, digits
from datetime import timedelta
from django.db import models
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin

from . import doge_api
from .models import Image, Drop, File, ExpireDaysChoice, Video
from .serializers import (
    ImageSerializer,
    DropCreateSerializer,
    DropSerializer,
    DropDetailSerializer,
    FileUploadSerializer,
    FileSerializer,
    VideoSerializer,
    VideoDetailSerializer,
)
from .ali_oss_sign import sign_upload
from gt.permissions import HaveRoleOrReadOnly
from gt_auth.models import User


def random_string(length: int = 4) -> str:
    return "".join([choice(ascii_letters + digits) for _ in range(length)])


class ImageViewset(GenericViewSet, ListModelMixin):
    permission_classes = [IsAuthenticated]
    serializer_class = ImageSerializer
    filterset_fields = ["scene"]
    search_fields = ["^user__username", "user__real_name"]

    def get_queryset(self):
        user = self.request.user
        if User.has_permission(user, "admin_file"):
            queryset = Image.objects.all()
        else:
            queryset = Image.objects.filter(user=user)
        return queryset.order_by("-id")

    def create(self, request, *args, **kwargs):
        if type(request.data) == dict:
            _data = [request.data]
        else:
            _data = request.data

        user = request.user
        scene = None
        quota = {
            "image_max_size": user.quota.image_max_size,
            "image_24h_count_limit": user.quota.image_24h_count_limit,
            "image_24h_size_limit": user.quota.image_24h_size_limit,
        }

        count = len(_data)
        data = []
        total_size = 0
        for item in _data:
            serializer = ImageSerializer(data=item)
            md5 = serializer.initial_data["md5"]
            if Image.objects.filter(md5=md5).exists():
                image = Image.objects.get(md5=md5)
                data.append(image)
                continue
            serializer.is_valid(raise_exception=True)
            if not serializer.validated_data["content_type"].startswith("image/"):
                raise ValidationError("不支持的文件类型")
            elif serializer.validated_data["size"] > quota["image_max_size"]:
                raise ValidationError(
                    f"文件大小超过限制({int(quota['image_max_size'] / 1024 / 1024)}MB)"
                )
            if scene:
                serializer.validated_data["scene"] = scene
            data.append(serializer)
            total_size += serializer.validated_data["size"]

        time = timezone.now()
        recent_images = Image.objects.filter(
            user=user,
            create_time__gte=time - timedelta(days=1),
        )
        if recent_images.count() + count > quota["image_24h_count_limit"]:
            raise ValidationError(
                f"24小时内上传图片数量已达上限({quota['image_24h_count_limit']}张)"
            )
        elif (
            recent_images.aggregate(total_size=models.Sum("size"))["total_size"] or 0
        ) + total_size > quota["image_24h_size_limit"]:
            raise ValidationError(
                f"24小时内上传图片累计大小已达上限({quota['image_24h_size_limit']}MB)"
            )

        response_data = []
        for serializer in data:
            if type(serializer) == Image:
                response_data.append(
                    {"data": ImageSerializer(serializer).data, "upload_data": None}
                )
                continue
            key = (
                serializer.validated_data["scene"]
                + "/"
                + time.strftime("%Y-%m")
                + "/"
                + serializer.validated_data["md5"]
                + "."
                + serializer.validated_data["content_type"].split("/")[-1]
            )
            upload_data = sign_upload(
                key,
                serializer.validated_data["md5"],
                serializer.validated_data["size"],
                serializer.validated_data["content_type"],
                time,
            )
            serializer.save(user=user, key=key, create_time=time)
            response_data.append(
                {
                    "data": serializer.data,
                    "upload_data": upload_data,
                }
            )

        return Response({"msg": "ok", "data": response_data})


class FileViewset(GenericViewSet, ListModelMixin):
    permission_classes = [IsAuthenticated]
    serializer_class = FileSerializer

    def get_queryset(self):
        user = self.request.user
        if User.has_permission(user, "admin_file"):
            queryset = File.objects.all()
        else:
            queryset = File.objects.filter(user=user)
        return queryset.order_by("-id")

    def create(self, request, *args, **kwargs):
        if type(request.data) == dict:
            _data = [request.data]
        else:
            _data = request.data

        user = request.user
        data = []

        for item in _data:
            serializer = FileUploadSerializer(data=item)
            serializer.is_valid(raise_exception=True)
            data.append(serializer)

        response_data = []
        file_items = []
        for serializer in data:
            if serializer.validated_data["expire_days"] not in [
                choice[0] for choice in ExpireDaysChoice.choices
            ]:
                raise ValidationError("过期时间不是合法选项")
            expire_days = serializer.validated_data["expire_days"]
            serializer.validated_data.pop("expire_days")
            serializer.save(user=user)
            key = (
                f"expire_{expire_days}"
                + "/"
                + str(serializer.instance.id)
                + "/"
                + serializer.validated_data["name"]
            )
            serializer.instance.key = key
            serializer.instance.save(update_fields=["key"])
            _data = serializer.data
            _data["key"] = key
            response_data.append(_data)
            file_items.append(serializer.instance)

        upload_data = doge_api.get_upload_data(file_items)

        return Response(
            {"msg": "ok", "data": response_data, "upload_data": upload_data}
        )


class DropViewset(ModelViewSet):
    permission_classes = [HaveRoleOrReadOnly]

    def get_queryset(self):
        if self.action in ["list", "destroy"]:
            return Drop.objects.filter(role=self.request.role).order_by("-id")
        return Drop.objects.filter(expired=False)

    def get_serializer_class(self):
        if self.action == "create":
            return DropCreateSerializer
        elif self.action == "list":
            return DropSerializer

    def destroy(self, request, *args, **kwargs):
        drop = self.get_object()
        drop.expired = True
        drop.save(update_fields=["expired"])
        return Response({"msg": "ok"})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = "".join([str(randint(0, 9)) for _ in range(6)])
        while Drop.objects.filter(code=code, expired=False).exists():
            code = "".join([str(randint(0, 9)) for _ in range(6)])

        if serializer.validated_data["pay_by_download"]:
            serializer.validated_data["require_login"] = True

        serializer.save(
            role=self.request.role,
            code=code,
            expire_time=timezone.now()
            + timedelta(days=serializer.validated_data["expire_days"]),
        )
        return Response({"msg": "ok", "data": serializer.data})

    @action(detail=False, methods=["get"], url_path=r"get/(?P<code>\d+)")
    def get_drop(self, request, code, *args, **kwargs):
        drop = self.get_queryset().filter(code=code)
        if not drop:
            return Response(
                {"msg": "分享不存在或已过期"}, status=status.HTTP_404_NOT_FOUND
            )
        drop = drop.prefetch_related("files", "role").first()
        if drop.require_login and not request.user.is_authenticated:
            return Response({"msg": "需要登录"}, status=status.HTTP_403_FORBIDDEN)
        if drop.expire_time < timezone.now():
            drop.expired = True
            drop.save(update_fields=["expired"])
            return Response({"msg": "分享已过期"}, status=status.HTTP_400_BAD_REQUEST)
        data = DropDetailSerializer(drop).data
        # data["files"].sort(key=lambda x: x["id"])
        return Response({"msg": "ok", "data": data})

    @action(
        detail=False,
        methods=["get"],
        url_path=r"download/(?P<code>\d+)/(?P<file_id>\d+)",
    )
    def download_drop_file(self, request, code, file_id, *args, **kwargs):
        drop = self.get_queryset().get(code=code)
        file = drop.files.get(id=file_id)
        drop.download_count += 1
        if drop.max_download and drop.download_count >= drop.max_download:
            drop.expired = True
            drop.save(update_fields=["expired", "download_count"])
        else:
            drop.save(update_fields=["download_count"])
        url = f"https://file.qaguatian.com/{file.key}"
        user = request.user
        if user.is_authenticated:
            auth_key = doge_api.get_cdn_authkey(url, 30, user.username, user.id)
        else:
            auth_key = doge_api.get_cdn_authkey(url, 30, "0", 0)
        return Response({"msg": "ok", "url": f"{url}?auth_key={auth_key}"})

    @action(
        methods=["post"],
        detail=True,
        url_path="add_file",
        permission_classes=[IsAuthenticated],
    )
    def add_file(self, request, *args, **kwargs):
        file_drop = self.get_object()
        role = request.role
        if role != file_drop.role:
            return Response(
                {"msg": "当前身份不是创建者"}, status=status.HTTP_403_FORBIDDEN
            )
        file_id = request.data["file_id"]
        file = File.objects.get(id=file_id)
        if file.user != request.user:
            return Response(
                {"msg": "文件不属于当前用户"}, status=status.HTTP_403_FORBIDDEN
            )
        file_drop.files.add(file)
        return Response({"msg": "ok"}, status=status.HTTP_200_OK)


class VideoViewset(GenericViewSet, ListModelMixin, RetrieveModelMixin):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return VideoDetailSerializer
        return VideoSerializer

    def get_queryset(self):
        user = self.request.user
        if self.action == "retrieve":
            queryset = Video.objects.filter(is_active=True)
        elif User.has_permission(user, "admin_file"):
            queryset = Video.objects.all()
        else:
            queryset = Video.objects.filter(user=user)
        return queryset.order_by("-id")

    def create(self, request, *args, **kwargs):
        user = request.user

        if not request.data["content_type"].startswith("video/"):
            raise ValidationError("不支持的文件类型")
        else:
            request.data.pop("content_type")

        serializer = VideoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quota = {
            "video_max_size": user.quota.video_max_size,
            "video_24h_count_limit": user.quota.video_24h_count_limit,
            "video_24h_size_limit": user.quota.video_24h_size_limit,
        }

        start_time = timezone.now() - timedelta(days=1)
        videos_24h = Video.objects.filter(user=user, create_time__gte=start_time)
        if videos_24h.count() >= quota["video_24h_count_limit"]:
            raise ValidationError("24小时内上传视频数量超出限制")
        if serializer.validated_data["size"] > quota["video_max_size"]:
            raise ValidationError("单个视频大小超出限制")
        total_size = sum(v.size for v in videos_24h)
        total_size += serializer.validated_data["size"]
        if total_size > quota["video_24h_size_limit"]:
            raise ValidationError("24小时内上传视频总大小超出限制")

        time = timezone.now()
        serializer.save(user=user, create_time=time)

        upload_data = doge_api.get_video_upload_data(serializer.instance)

        serializer.instance.did = upload_data["VodUploadInfo"]["did"]
        serializer.instance.save(update_fields=["did"])

        response_data = {
            "data": serializer.data,
            "upload_data": upload_data,
        }

        return Response({"msg": "ok", "data": response_data})

    @action(
        detail=False,
        methods=["get"],
        url_path="dogecloud_callback",
        permission_classes=[],
    )
    def dogecloud_callback(self, request, *args, **kwargs):
        msg = request.query_params.get("msg")
        vcode = request.query_params.get("vcode")
        callback_string = request.query_params.get("callbackString")

        try:
            video = Video.objects.get(uuid=callback_string)
            if vcode:
                video.vcode = vcode
            if msg == "transcode":
                video.is_active = True
            video.save(update_fields=["vcode", "is_active"])
        except Video.DoesNotExist:
            ...

        return Response("DogeCloud Callback Success")
