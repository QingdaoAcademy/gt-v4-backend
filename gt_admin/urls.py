from django.urls import include, re_path
from rest_framework.routers import DefaultRouter

from gt_admin.views import (
    UserAdminViewset,
    RoleAdminViewset,
    PostAdminViewset,
    PostCommentAdminViewset,
)

router = DefaultRouter()
router.register(r"user", UserAdminViewset, basename="user_admin")
router.register(r"role", RoleAdminViewset, basename="role_admin")
router.register(r"post", PostAdminViewset, basename="post_admin")
router.register(r"comment", PostCommentAdminViewset, basename="comment_admin")

urlpatterns = [re_path(r"^", include(router.urls))]
