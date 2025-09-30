from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import (
    IdentityChoice,
    SchoolChoice,
    SourceChoice,
    Quota,
    Permission,
    Privacy,
    User,
    TrustedUser,
    Role,
    RoleMember,
    Follow,
    NotificationType,
    Notification
)

# 注册其他模型
admin.site.register(Quota)
admin.site.register(Permission)
admin.site.register(Privacy)

# 自定义 User 的 admin
class UserAdmin(DjangoUserAdmin):
    readonly_fields = ('last_login', 'date_joined', 'permission', 'privacy', 'quota', 'coin', 'version')
    search_fields = ('username', 'student_id', 'real_name')
    list_display = ('username', 'student_id', 'real_name')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {'fields': ('student_id', 'real_name', 'school', 'identity')}),
        ('权限信息', {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
        }),
        ('重要日期', {'fields': ('last_login', 'date_joined')}),
        ('其他信息', {'fields': ('permission', 'privacy', 'quota', 'coin', 'version')}),
    )

# 使用自定义的 UserAdmin 注册 User 模型
admin.site.register(User, UserAdmin)

admin.site.register(TrustedUser)
admin.site.register(Role)
admin.site.register(RoleMember)
admin.site.register(Follow)
admin.site.register(Notification)

# 枚举类通常不需要注册到 admin，这里注释掉
# admin.site.register(IdentityChoice)
# admin.site.register(SchoolChoice)
# admin.site.register(SourceChoice)
# admin.site.register(NotificationType)
