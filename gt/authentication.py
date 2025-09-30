from rest_framework import authentication, exceptions

from .jwt import GtSignature
from gt_auth.models import User, Role, SourceChoice


class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            setattr(request, "role", None)
            setattr(request, "source", "web")
            setattr(request, "from_school", False)
            setattr(request, "is_server", False)
            return None

        try:
            prefix, tokens = auth_header.split(" ")
            # if prefix.lower() != "bearer":
            #     raise exceptions.AuthenticationFailed(
            #         "Authorization header must start with Bearer"
            #     )
        except ValueError:
            raise exceptions.AuthenticationFailed("认证信息格式错误")

        user = None
        for token in tokens.split("|"):
            payload = GtSignature.decode(token)

            source = payload.get("source", getattr(request, "source", "web"))
            if source and source not in [choice[0] for choice in SourceChoice.choices]:
                raise exceptions.AuthenticationFailed("非法来源")
            setattr(request, "source", source)

            from_school = payload.get(
                "from_school", getattr(request, "from_school", False)
            )
            setattr(request, "from_school", from_school)

            is_server = payload.get("is_server", getattr(request, "is_server", False))
            setattr(request, "is_server", is_server)

            _user = payload.get("user_id") and self.get_user(payload["user_id"])
            if isinstance(_user, User):
                if (
                    payload["user_version"] != -1
                    and payload["user_version"] < _user.version
                ):
                    raise exceptions.AuthenticationFailed("签名信息过期")
                elif not _user.is_active:
                    raise exceptions.AuthenticationFailed("用户已被封禁")
                user = _user

            role = getattr(request, "role", None)
            if "role_id" in payload and payload["role_id"]:
                role = self.get_role(payload["role_id"])
                if not role.is_active:
                    raise exceptions.AuthenticationFailed("角色已被封禁")
                elif role.deleted:
                    raise exceptions.AuthenticationFailed("角色已被删除")
                if not request.is_server:
                    if user is None:
                        raise exceptions.AuthenticationFailed("缺少用户信息")
                    elif not role.members.filter(user=user).exists():
                        raise exceptions.AuthenticationFailed("你没有访问该角色的权限")
            setattr(request, "role", role)

        return (user, None) if user else None

    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    def get_role(self, role_id):
        try:
            return Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return None
