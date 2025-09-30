# QA瓜田V4后端项目

## 开发

根据环境变量`GT_MODE`判断是否为开发环境，可选`dev`|`dev-mysql`|`prod`，默认为`dev`

### 数据库迁移

```bash
python manage.py makemigrations gt_auth gt_forum gt_file gt_admin gt_coin gt_alumni
python manage.py migrate
```

### 设置密钥

参考`config.yaml.example`创建`config.yaml`，并修改其中的内容。

不需要测试阿里云上传签名可不配置`ali_*`。

### 创建数据库缓存表

dev 环境需要。

```bash
python manage.py createcachetable dev_cache
```

### 通过 Django Shell 创建第一个用户

```python
from gt_auth.models import (
    User,
    Role,
    Quota,
    Permission,
    Privacy,
)
from gt_coin.models import Coin

quota = Quota.objects.create()
permission = Permission.objects.create()
privacy = Privacy.objects.create()
coin = Coin.objects.create()
user = User.objects.create_user(
    username="admin",
    password="123456",
    real_name="管理员",
    student_id="00000000",
    identity="学生",
    school="qa",
    quota=quota,
    permission=permission,
    privacy=privacy,
    coin=coin,
)

Role.generate_default_role(user)
```
