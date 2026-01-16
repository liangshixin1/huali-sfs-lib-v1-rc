# 华立学院应用外国语学院资料室借阅系统

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个功能完善的高校图书馆自助借阅管理系统，专为教职工设计，集成 AI 智能搜书、语音合成、移动扫码借还等现代化功能。

## 目录

- [功能特性](#功能特性)
- [系统要求](#系统要求)
- [快速开始](#快速开始)
- [配置指南](#配置指南)
- [云服务器部署指南](#云服务器部署指南)
- [使用说明](#使用说明)
- [API 接口文档](#api-接口文档)
- [数据库结构](#数据库结构)
- [安全特性](#安全特性)
- [常见问题](#常见问题)
- [开发指南](#开发指南)
- [许可证](#许可证)

---

## 功能特性

### 用户功能
- **图书检索**：支持书名、编码、出版社、书柜号多条件模糊搜索
- **在线借阅**：一键借阅，自动计算应还日期（默认30天）
- **图书归还**：支持单本归还和一键归还全部
- **移动扫码**：通过手机摄像头扫描图书编码快速借还
- **借阅记录**：查看个人借阅历史和当前借阅状态
- **借阅意愿**：对感兴趣的图书标记"想要"

### AI 智能功能
- **AI 智能搜书**：基于 TF-IDF 和语义相似度的智能搜索
- **AI 查询扩展**：自动扩展查询词的同义词和相关概念
- **AI 图书推荐**：根据查询内容推荐相关书籍
- **AI 对话服务**：提供关于图书的智能问答
- **文本转语音**：将图书信息转换为语音播报

### 管理员功能
- **图书管理**：增删改查图书信息
- **用户管理**：管理教职工账户
- **批量导入**：支持 Excel 格式批量导入书籍和用户数据
- **借阅统计**：借阅记录筛选、导出和分析
- **AI 索引更新**：维护和更新搜索引擎索引
- **需求分析**：查看图书借阅意愿统计

### 技术亮点
- Fluent Design 风格 UI（毛玻璃效果）
- 完全响应式设计，支持移动端
- 中文分词优化（Jieba）
- 流式 AI 响应（SSE）
- 完善的安全防护机制

---

## 系统要求

### 软件要求
- **Python**：3.8 或更高版本
- **操作系统**：Linux（推荐 Ubuntu 20.04+）、macOS、Windows
- **数据库**：SQLite 3（内置，无需单独安装）

### 硬件要求（生产环境）
- **CPU**：2 核心或以上
- **内存**：2 GB 或以上
- **存储**：10 GB 可用空间
- **网络**：具有公网 IP 或域名

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/liangshixin1/huali-sfs-lib-v1-rc.git
cd huali-sfs-lib-v1-rc
```

### 2. 创建虚拟环境

```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入必要的配置
```

### 5. 启动应用

```bash
# 开发模式
python app.py

# 或指定端口
FLASK_RUN_PORT=8080 python app.py
```

访问 `http://localhost:5000` 即可使用系统。

---

## 配置指南

### 环境变量配置

在项目根目录创建 `.env` 文件：

```ini
# ==================== 基础配置 ====================
# Flask 密钥（生产环境必须设置为随机字符串）
SECRET_KEY=your-super-secret-key-here

# 运行环境：development / production
FLASK_ENV=production

# 最大上传文件大小（字节），默认 10MB
MAX_CONTENT_LENGTH=10485760

# ==================== 管理员配置 ====================
# 管理员初始密码（默认：Admin）
ADMIN_PASSWORD=YourSecureAdminPassword

# ==================== AI 服务配置（DeepSeek API） ====================
# AI 图书详情对话 API 密钥
AI_DETAILS_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# AI 智能搜书 API 密钥
AI_SEARCH_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# 词向量/语义扩展 API 密钥
WORD_VECTOR_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# ==================== 百度语音合成配置 ====================
BAIDU_SPEECH_APP_ID=your_app_id
BAIDU_SPEECH_API_KEY=your_api_key
BAIDU_SPEECH_SECRET_KEY=your_secret_key

# ==================== 备用用户配置（可选） ====================
# 格式：用户名,姓名,密码
FALLBACK_FACULTY_USER=demo,演示用户,demo123
```

### API 密钥获取

#### DeepSeek API
1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com/)
2. 注册并登录账户
3. 在控制台创建 API 密钥
4. 复制密钥填入对应环境变量

#### 百度语音合成 API
1. 访问 [百度智能云](https://cloud.baidu.com/)
2. 创建语音技术应用
3. 获取 App ID、API Key、Secret Key
4. 填入对应环境变量

---

## 云服务器部署指南

本节详细介绍如何在云服务器上部署本系统。

### 一、服务器准备

#### 1.1 选择云服务商

推荐的云服务商：
- 阿里云 ECS
- 腾讯云 CVM
- 华为云 ECS
- AWS EC2
- 其他支持 Linux 的 VPS 服务商

#### 1.2 服务器配置建议

| 规模 | CPU | 内存 | 存储 | 带宽 |
|------|-----|------|------|------|
| 小型（&lt;100用户） | 1核 | 1GB | 20GB | 1Mbps |
| 中型（100-500用户） | 2核 | 2GB | 40GB | 3Mbps |
| 大型（&gt;500用户） | 4核 | 4GB | 80GB | 5Mbps |

#### 1.3 开放端口

在云服务商安全组中开放以下端口：
- **22**：SSH（仅限管理 IP）
- **80**：HTTP
- **443**：HTTPS

### 二、系统环境配置

以 Ubuntu 22.04 LTS 为例：

#### 2.1 更新系统

```bash
sudo apt update && sudo apt upgrade -y
```

#### 2.2 安装 Python 和依赖

```bash
# 安装 Python 3 和 pip
sudo apt install -y python3 python3-pip python3-venv

# 安装编译依赖（如需要）
sudo apt install -y build-essential python3-dev
```

#### 2.3 安装 Nginx

```bash
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

#### 2.4 创建应用用户

```bash
# 创建专用用户
sudo useradd -m -s /bin/bash library
sudo passwd library

# 切换到应用用户
sudo su - library
```

### 三、部署应用

#### 3.1 获取代码

```bash
cd /home/library
git clone https://github.com/liangshixin1/huali-sfs-lib-v1-rc.git app
cd app
```

#### 3.2 创建虚拟环境并安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn  # 生产级 WSGI 服务器
```

#### 3.3 配置环境变量

```bash
# 创建环境变量文件
cat > .env << 'EOF'
SECRET_KEY=这里填写一个长随机字符串
FLASK_ENV=production
ADMIN_PASSWORD=你的管理员密码
AI_DETAILS_API_KEY=你的DeepSeek密钥
AI_SEARCH_API_KEY=你的DeepSeek密钥
WORD_VECTOR_API_KEY=你的DeepSeek密钥
BAIDU_SPEECH_APP_ID=百度语音AppID
BAIDU_SPEECH_API_KEY=百度语音APIKey
BAIDU_SPEECH_SECRET_KEY=百度语音SecretKey
EOF

# 设置权限
chmod 600 .env
```

#### 3.4 初始化数据库

```bash
# 首次运行会自动创建数据库和管理员账户
python app.py &
sleep 5
kill %1
```

### 四、配置 Gunicorn

#### 4.1 创建 Gunicorn 配置文件

```bash
cat > gunicorn.conf.py << 'EOF'
# Gunicorn 配置文件
import multiprocessing

# 绑定地址
bind = "127.0.0.1:8000"

# 工作进程数
workers = multiprocessing.cpu_count() * 2 + 1

# 工作模式
worker_class = "sync"

# 超时时间（秒）
timeout = 120

# 保持连接时间
keepalive = 5

# 最大请求数（防止内存泄漏）
max_requests = 1000
max_requests_jitter = 50

# 日志配置
accesslog = "/home/library/app/logs/access.log"
errorlog = "/home/library/app/logs/error.log"
loglevel = "info"

# 进程名称
proc_name = "library-app"

# 守护进程（由 systemd 管理时设为 False）
daemon = False
EOF

# 创建日志目录
mkdir -p logs
```

### 五、配置 Systemd 服务

#### 5.1 创建服务文件

```bash
sudo tee /etc/systemd/system/library.service << 'EOF'
[Unit]
Description=华立学院资料室借阅系统
After=network.target

[Service]
Type=simple
User=library
Group=library
WorkingDirectory=/home/library/app
Environment="PATH=/home/library/app/venv/bin"
ExecStart=/home/library/app/venv/bin/gunicorn -c gunicorn.conf.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=5

# 安全配置
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
```

#### 5.2 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable library
sudo systemctl start library

# 查看服务状态
sudo systemctl status library
```

### 六、配置 Nginx 反向代理

#### 6.1 创建 Nginx 配置

```bash
sudo tee /etc/nginx/sites-available/library << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名或IP

    # 重定向到 HTTPS（配置SSL后启用）
    # return 301 https://$server_name$request_uri;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持（用于流式 AI 响应）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 超时配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    # 静态文件缓存
    location /static/ {
        alias /home/library/app/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # 上传文件大小限制
    client_max_body_size 20M;
}
EOF
```

#### 6.2 启用站点

```bash
sudo ln -s /etc/nginx/sites-available/library /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 七、配置 SSL 证书（推荐）

#### 7.1 使用 Let's Encrypt 免费证书

```bash
# 安装 Certbot
sudo apt install -y certbot python3-certbot-nginx

# 获取证书（替换为你的域名）
sudo certbot --nginx -d your-domain.com

# 设置自动续期
sudo systemctl enable certbot.timer
```

#### 7.2 更新 Nginx 配置（SSL）

Certbot 会自动修改配置，或手动配置：

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # SSL 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;

    # ... 其他配置同上
}

# HTTP 重定向到 HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### 八、数据库备份

#### 8.1 创建备份脚本

```bash
cat > /home/library/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/library/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# 备份数据库
cp /home/library/app/instance/library.db $BACKUP_DIR/library_$DATE.db

# 保留最近30天的备份
find $BACKUP_DIR -name "library_*.db" -mtime +30 -delete

echo "Backup completed: library_$DATE.db"
EOF

chmod +x /home/library/backup.sh
```

#### 8.2 设置定时备份

```bash
# 编辑 crontab
crontab -e

# 添加每日凌晨3点备份
0 3 * * * /home/library/backup.sh >> /home/library/backups/backup.log 2>&1
```

### 九、监控与日志

#### 9.1 查看应用日志

```bash
# 查看 Gunicorn 访问日志
tail -f /home/library/app/logs/access.log

# 查看错误日志
tail -f /home/library/app/logs/error.log

# 查看 systemd 服务日志
sudo journalctl -u library -f
```

#### 9.2 设置日志轮转

```bash
sudo tee /etc/logrotate.d/library << 'EOF'
/home/library/app/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 library library
    postrotate
        systemctl reload library > /dev/null 2>&1 || true
    endscript
}
EOF
```

### 十、常用运维命令

```bash
# 重启应用
sudo systemctl restart library

# 查看应用状态
sudo systemctl status library

# 重新加载 Nginx
sudo systemctl reload nginx

# 查看实时日志
sudo journalctl -u library -f

# 手动备份数据库
/home/library/backup.sh

# 更新应用代码
cd /home/library/app
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart library
```

---

## 使用说明

### 用户登录

1. 访问系统首页
2. 输入工号和密码登录
3. 初始密码为身份证后四位

### 图书借阅

1. 在首页搜索或浏览图书
2. 点击图书卡片上的「借阅」按钮
3. 确认借阅信息
4. 借阅成功后可在「我的借阅」查看

### 移动扫码借还

1. 点击首页的「扫码借还」按钮
2. 允许浏览器访问摄像头
3. 将图书编码对准扫描框
4. 系统自动识别并处理借还操作

### 管理员操作

1. 使用管理员账户登录
2. 点击右上角进入管理面板
3. 可进行图书管理、用户管理、数据导入等操作

### 批量导入数据

#### 书籍导入 Excel 格式

| 书名 | 出版社 | 书柜号 | ISBN | 图书编码 | 库存数量 |
|------|--------|--------|------|----------|----------|
| 示例书名 | 示例出版社 | A01 | 978-xxx | BK001 | 5 |

#### 用户导入 Excel 格式

| 工号 | 姓名 | 密码 |
|------|------|------|
| T001 | 张三 | 1234 |

---

## API 接口文档

### 认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/login` | 用户登录 |
| POST | `/logout` | 用户登出 |

### 用户接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取图书列表 |
| GET | `/my-records` | 获取借阅记录 |
| POST | `/borrow/<book_id>` | 借阅图书 |
| POST | `/borrow-by-code/<code>` | 扫码借书 |
| POST | `/return/<record_id>` | 归还图书 |
| POST | `/return-by-code/<code>` | 扫码还书 |
| POST | `/return-all` | 一键归还 |
| POST | `/want/<book_id>` | 标记想要 |
| GET/POST | `/profile` | 个人资料 |

### AI 服务接口

| 方法 | 路径 | 说明 | 限制 |
|------|------|------|------|
| POST | `/ask-ai` | AI 问答 | 15次/天 |
| POST | `/ai-search` | AI 搜书 | 15次/天 |
| POST | `/ai-expand-query` | 查询扩展 | 15次/天 |
| POST | `/ai-recommend` | 图书推荐 | 无限制 |
| POST | `/text-to-speech` | 语音合成 | 15次/天 |

### 管理员接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/dashboard` | 管理面板 |
| POST | `/admin/book/add` | 添加图书 |
| POST | `/admin/book/update/<id>` | 更新图书 |
| POST | `/admin/book/delete/<id>` | 删除图书 |
| POST | `/admin/user/add` | 添加用户 |
| POST | `/admin/user/update/<id>` | 更新用户 |
| POST | `/admin/user/delete/<id>` | 删除用户 |
| POST | `/admin/import-books` | 导入书籍 |
| POST | `/admin/import-users` | 导入用户 |
| POST | `/admin/update-ai-catalog` | 更新索引 |
| GET | `/admin/export-records` | 导出记录 |

---

## 数据库结构

### ER 图

```
┌─────────────┐       ┌─────────────────┐       ┌─────────────┐
│    User     │       │  BorrowRecord   │       │    Book     │
├─────────────┤       ├─────────────────┤       ├─────────────┤
│ id (PK)     │───┐   │ id (PK)         │   ┌───│ id (PK)     │
│ username    │   └──>│ user_id (FK)    │   │   │ title       │
│ full_name   │       │ book_id (FK)    │<──┘   │ publisher   │
│ password    │       │ borrow_date     │       │ bookshelf   │
│ role        │       │ due_date        │       │ isbn        │
└─────────────┘       │ return_date     │       │ book_code   │
      │               │ status          │       │ stock       │
      │               └─────────────────┘       │ available   │
      │                                         └─────────────┘
      │               ┌─────────────────┐             │
      │               │      Want       │             │
      │               ├─────────────────┤             │
      └──────────────>│ id (PK)         │<────────────┘
                      │ user_id (FK)    │
                      │ book_id (FK)    │
                      │ timestamp       │
                      └─────────────────┘

┌─────────────────┐
│    ApiUsage     │
├─────────────────┤
│ id (PK)         │
│ user_id (FK)    │──> User
│ api_name        │
│ usage_date      │
│ count           │
└─────────────────┘
```

### 表说明

| 表名 | 说明 |
|------|------|
| User | 用户信息（教职工和管理员） |
| Book | 图书信息 |
| BorrowRecord | 借阅记录 |
| Want | 借阅意愿记录 |
| ApiUsage | API 调用统计 |

---

## 安全特性

### 身份认证
- 基于 Flask-Login 的会话管理
- 密码使用 Werkzeug 安全散列存储
- 支持角色权限控制（管理员/教职工）

### 数据保护
- CSRF 令牌验证
- SQL 注入防护（参数化查询）
- XSS 防护（自动转义输出）
- Excel 公式注入防护

### 网络安全
- Content Security Policy (CSP)
- X-Frame-Options 防点击劫持
- HTTPS 强制（生产环境）
- SSRF 防护（API 白名单）

### 访问控制
- API 调用频率限制（15次/天）
- 文件上传类型验证
- 敏感操作日志记录

---

## 常见问题

### Q: 忘记管理员密码怎么办？

```bash
# 进入 Python shell
cd /home/library/app
source venv/bin/activate
python

# 重置密码
>>> from app import app, db, User
>>> from werkzeug.security import generate_password_hash
>>> with app.app_context():
...     admin = User.query.filter_by(role='admin').first()
...     admin.password_hash = generate_password_hash('新密码')
...     db.session.commit()
>>> exit()
```

### Q: AI 功能不可用？

1. 检查 `.env` 文件中的 API 密钥是否正确
2. 确认 API 余额充足
3. 检查网络连接是否正常
4. 查看错误日志获取详细信息

### Q: 上传 Excel 失败？

1. 确保文件格式为 `.xlsx`
2. 检查文件大小是否超过限制（默认10MB）
3. 确认 Excel 列名与要求一致
4. 检查数据格式是否正确

### Q: 页面加载缓慢？

1. 检查服务器资源使用情况
2. 优化数据库查询（添加索引）
3. 启用 Nginx 静态文件缓存
4. 考虑增加服务器配置

### Q: 如何迁移数据库？

```bash
# 备份数据库
cp instance/library.db library_backup.db

# 迁移到新服务器
scp library_backup.db user@new-server:/home/library/app/instance/library.db
```

---

## 开发指南

### 项目结构

```
huali-sfs-lib-v1-rc/
├── app.py                  # 主应用程序
├── config.py               # 配置文件
├── requirements.txt        # Python 依赖
├── .env                    # 环境变量（不提交）
├── instance/
│   └── library.db          # SQLite 数据库
├── static/
│   ├── background.png      # 登录背景图
│   └── css/
│       └── style.css       # 自定义样式
└── templates/
    ├── layout.html         # 基础布局
    ├── index.html          # 首页
    ├── admin_dashboard.html# 管理面板
    ├── login.html          # 登录页
    ├── records.html        # 借阅记录
    ├── profile.html        # 用户资料
    └── _macros.html        # 模板宏
```

### 技术栈

- **后端**：Flask 3.0、Flask-SQLAlchemy、Flask-Login
- **数据库**：SQLite
- **前端**：Tailwind CSS、Font Awesome、原生 JavaScript
- **AI**：DeepSeek API、百度语音合成
- **NLP**：Jieba 分词、scikit-learn TF-IDF

### 本地开发

```bash
# 开启调试模式
export FLASK_ENV=development
export FLASK_DEBUG=1
python app.py
```

### 添加新功能

1. 在 `app.py` 中添加路由和视图函数
2. 更新 `templates/` 中的模板文件
3. 如需新模型，在 `app.py` 中定义后运行 `db.create_all()`
4. 编写测试并验证功能

---

## 许可证

本项目采用 [MIT 许可证](LICENSE) 开源。

```
MIT License

Copyright (c) 2025 liangshixin1

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

## 致谢

感谢以下开源项目：

- [Flask](https://flask.palletsprojects.com/) - Web 框架
- [Tailwind CSS](https://tailwindcss.com/) - CSS 框架
- [DeepSeek](https://www.deepseek.com/) - AI 服务
- [Jieba](https://github.com/fxsjy/jieba) - 中文分词

---

如有问题或建议，欢迎提交 [Issue](https://github.com/liangshixin1/huali-sfs-lib-v1-rc/issues) 或 [Pull Request](https://github.com/liangshixin1/huali-sfs-lib-v1-rc/pulls)。
