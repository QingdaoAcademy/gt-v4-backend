from django.contrib import admin  # 导入 admin 模块
from django.urls import include, re_path
from rest_framework.routers import DefaultRouter

from gt_auth.views import (
    UserViewset,
    UserSettingViewset,
    RoleViewset,
    NotificationViewset,
)
from gt_forum.views import PostViewset, CommentViewset
from gt_file.views import ImageViewset, FileViewset, DropViewset, VideoViewset
from gt_admin.views import ReportViewset
from gt_coin.views import CoinViewset
from gt_alumni.views import AlumniViewset

from gt_admin.urls import urlpatterns as admin_urls

router = DefaultRouter()
router.register(r"user", UserViewset, basename="user")
router.register(r"user/setting", UserSettingViewset, basename="user_setting")
router.register(r"role", RoleViewset, basename="role")
router.register(r"post", PostViewset, basename="post")
router.register(r"comment", CommentViewset, basename="comment")
router.register(r"drop", DropViewset, basename="drop")
router.register(r"image", ImageViewset, basename="image")
router.register(r"file", FileViewset, basename="file")
router.register(r"video", VideoViewset, basename="video")
router.register(r"report", ReportViewset, basename="report")
router.register(r"notification", NotificationViewset, basename="notification")
router.register(r"coin", CoinViewset, basename="coin")
router.register(r"alumni", AlumniViewset, basename="alumni")

urlpatterns = [
    re_path(r"^django-admin/", admin.site.urls),  # 添加 Django 内置管理界面路由
    re_path(r"^", include(router.urls)),
    re_path(r"^admin/", include(admin_urls)),
]
