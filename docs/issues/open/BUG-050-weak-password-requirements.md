# BUG-050: 密码强度无复杂度要求

| 属性 | 值 |
|------|---|
| **严重级别** | 🟢 Low |
| **影响模块** | 安全性 |
| **发现方式** | 代码审查 |
| **状态** | Open |
| **发现日期** | 2026-07-06 |

## 现象

用户注册时密码仅要求最少 6 个字符，无任何复杂度要求。弱密码如 `123456`、`password`、`111111` 均可通过校验。

## 根因

`schemas/schemas.py:13`:

```python
class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    email: Optional[EmailStr] = None
    password: str = Field(min_length=6, max_length=128)
```

仅设置了 `min_length=6`，没有：
- 大小写字母要求
- 数字要求
- 特殊字符要求
- 常见弱密码黑名单
- 用户名与密码相似度检查

## 复现步骤

1. 访问注册页面
2. 用户名: `test`
3. 密码: `123456`
4. 点击注册 → 成功

## 影响

- 🟢 弱密码增加账号被盗风险
- 🟢 企业级产品预期有基本的密码策略
- 🟢 不符合安全合规要求（ISO 27001、等保等）

## 修复建议

在后端 `RegisterRequest` 和前端 `Login.tsx` 表单中添加密码复杂度校验：

```python
import re
from pydantic import field_validator

class RegisterRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r'[A-Z]', v):
            raise ValueError('密码必须包含至少一个大写字母')
        if not re.search(r'[a-z]', v):
            raise ValueError('密码必须包含至少一个小写字母')
        if not re.search(r'[0-9]', v):
            raise ValueError('密码必须包含至少一个数字')
        # 可选：检查是否包含用户名
        return v
```

同时建议：
1. 将最小长度从 6 提升到 8
2. 添加常见弱密码黑名单（如 `12345678`, `password`, `admin123` 等）
3. 前端增加密码强度指示器（weak/medium/strong）
