#!/bin/bash
# ============================================================
# OfficeTool 轻量化部署脚本 — 宝塔 Linux 面板专用
# 使用: 在宝塔【文件】页面上传代码后，在【终端】中运行:
#   cd /www/wwwroot/officetool && sudo bash deploy/deploy.sh
# ============================================================

set -e

# ========== 配置变量（请修改）==========
DOMAIN="你的域名"
PROJECT_DIR="/www/wwwroot/officetool"
PYTHON_BIN="python3.11"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo "============================================"
echo "  OfficeTool 轻量化部署（宝塔面板）"
echo "============================================"
echo ""

# ========== 1. 安装 Python 3.11 ==========
log "Step 1/7: 安装 Python 3.11..."

if command -v python3.11 &>/dev/null; then
    log "Python 3.11 已安装: $(python3.11 --version)"
else
    warn "正在安装 Python 3.11（需要 2-3 分钟）..."
    if command -v apt &>/dev/null; then
        # Ubuntu/Debian
        apt update -qq
        apt install -y -qq software-properties-common
        add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
        apt update -qq
        apt install -y -qq python3.11 python3.11-venv python3.11-dev
    elif command -v yum &>/dev/null; then
        # CentOS 7
        yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel
        cd /tmp
        if [ ! -f Python-3.11.9.tar.xz ]; then
            curl -O https://mirrors.huaweicloud.com/python/3.11.9/Python-3.11.9.tar.xz
            tar -xf Python-3.11.9.tar.xz
        fi
        cd Python-3.11.9
        ./configure --enable-optimizations --prefix=/usr/local/python3.11
        make -j$(nproc)
        make install
        ln -sf /usr/local/python3.11/bin/python3.11 /usr/bin/python3.11
        ln -sf /usr/local/python3.11/bin/pip3.11 /usr/bin/pip3.11
        cd "$PROJECT_DIR"
    else
        err "不支持的系统，请手动安装 Python 3.11"
    fi
    log "Python 3.11 安装完成"
fi

# 确保 pip 可用
$PYTHON_BIN -m pip --version &>/dev/null || $PYTHON_BIN -m ensurepip --upgrade

# ========== 2. 安装 Node.js 18 ==========
log "Step 2/7: 安装 Node.js 18..."

if command -v node &>/dev/null; then
    NODE_VER=$(node --version)
    log "Node.js 已安装: $NODE_VER"
else
    warn "正在安装 Node.js 18..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - 2>/dev/null && \
        apt install -y nodejs 2>/dev/null || \
    (
        # CentOS 备用方案
        curl -fsSL https://rpm.nodesource.com/setup_18.x | bash - 2>/dev/null && \
        yum install -y nodejs 2>/dev/null
    ) || (
        # 通用方案：使用 nvm
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
        nvm install 18
        nvm use 18
    )
    log "Node.js 安装完成: $(node --version)"
fi

# ========== 3. 安装 Python 依赖 ==========
log "Step 3/7: 安装 Python 依赖..."

cd "$PROJECT_DIR/app"

# 创建虚拟环境
if [ ! -d ".venv" ]; then
    $PYTHON_BIN -m venv .venv
    log "虚拟环境已创建"
fi

source .venv/bin/activate
pip install --upgrade pip -q

log "安装核心依赖（首次运行约 3-5 分钟）..."
pip install \
    fastapi "uvicorn[standard]" \
    sqlalchemy aiosqlite \
    "pydantic[email]" pydantic-settings \
    "python-jose[cryptography]" bcrypt \
    python-multipart httpx \
    loguru pymupdf \
    python-docx openpyxl python-pptx \
    beautifulsoup4 lxml \
    langchain-text-splitters \
    sentence-transformers \
    pyyaml \
    Pillow \
    2>&1 | tail -5

log "Python 依赖安装完成"

# ========== 4. 配置环境变量 ==========
log "Step 4/7: 配置环境变量..."

if [ ! -f ".env" ]; then
    cp ../deploy/.env.lightweight .env 2>/dev/null || cat > .env << 'ENVEOF'
APP_NAME=OfficeTool
APP_VERSION=0.1.0
DEBUG=false
SECRET_KEY=changeme
USE_SQLITE=true
LLM_PROVIDER=deepseek
LLM_DEEPSEEK_API_KEY=你的API-Key
LLM_DEEPSEEK_MODEL=deepseek-chat
EMBEDDING_MODEL=text2vec-large-chinese
EMBEDDING_DEVICE=cpu
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
UPLOAD_DIR=./uploads
RETRIEVER_TOP_K=10
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
CORS_ORIGINS=http://localhost:5173
ENVEOF
fi

# 生成 SECRET_KEY
if grep -q "changeme\|change-me" .env 2>/dev/null; then
    NEW_KEY=$($PYTHON_BIN -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$NEW_KEY/" .env
    log "SECRET_KEY 已自动生成"
fi

warn "============================================"
warn "请编辑 .env 填写 LLM API Key！"
warn "  vim $PROJECT_DIR/app/.env"
warn "  修改 LLM_DEEPSEEK_API_KEY=你的Key"
warn "============================================"

# ========== 5. 构建前端 ==========
log "Step 5/7: 构建前端..."

cd "$PROJECT_DIR/app/frontend"

if [ ! -d "node_modules" ]; then
    log "安装前端依赖..."
    npm install 2>&1 | tail -5
fi

log "构建生产版本..."
npm run build 2>&1 | tail -10

if [ -d "dist" ]; then
    log "前端构建完成 ($(du -sh dist | cut -f1))"
else
    err "前端构建失败"
fi

# ========== 6. 生成 Nginx 配置文件 ==========
log "Step 6/7: 生成 Nginx 配置..."

# 宝塔 Nginx 配置目录
BT_NGINX_VHOST="/www/server/panel/vhost/nginx"

if [ -d "$BT_NGINX_VHOST" ]; then
    NGINX_CONF="$BT_NGINX_VHOST/officetool.conf"
    log "检测到宝塔面板，配置写入: $NGINX_CONF"
else
    NGINX_CONF="/www/server/nginx/conf/conf.d/officetool.conf"
    mkdir -p "$(dirname "$NGINX_CONF")"
fi

cat > "$NGINX_CONF" << NGINXEOF
server {
    listen 80;
    server_name $DOMAIN;

    root $PROJECT_DIR/app/frontend/dist;
    index index.html;

    client_max_body_size 200m;

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # API 文档
    location /docs {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
    }
    location /redoc {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
    }
    location /openapi.json {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
    }

    # SPA 路由
    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
NGINXEOF

# 重载 Nginx
if command -v nginx &>/dev/null; then
    nginx -t && nginx -s reload && log "Nginx 已重载"
else
    warn "Nginx 路径: /www/server/nginx/sbin/nginx"
    /www/server/nginx/sbin/nginx -t && /www/server/nginx/sbin/nginx -s reload && log "Nginx 已重载"
fi

# ========== 7. 配置 systemd 并启动 ==========
log "Step 7/7: 配置 systemd 并启动..."

cat > /etc/systemd/system/officetool.service << SVCEOF
[Unit]
Description=OfficeTool FastAPI Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR/app
EnvironmentFile=$PROJECT_DIR/app/.env
ExecStart=$PROJECT_DIR/app/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
MemoryMax=800M

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable officetool
systemctl restart officetool

sleep 3

if systemctl is-active --quiet officetool; then
    log "OfficeTool 服务已启动 ✅"
else
    warn "服务启动失败，查看日志: journalctl -u officetool -n 50"
fi

# ========== 完成 ==========
echo ""
echo "============================================"
echo "  ✅ 部署完成！接下来在宝塔面板中操作："
echo "============================================"
echo ""
echo "  📌 第 1 步：添加网站"
echo "     宝塔 → 网站 → 添加站点"
echo "     域名: $DOMAIN"
echo "     根目录: $PROJECT_DIR/app/frontend/dist"
echo "     （如果已添加，修改根目录即可）"
echo ""
echo "  📌 第 2 步：配置反向代理"
echo "     宝塔 → 网站 → $DOMAIN → 反向代理"
echo "     添加: 名称=API, URL=http://127.0.0.1:8000"
echo "     发送域名=\$host"
echo ""
echo "  📌 第 3 步：一键 SSL"
echo "     宝塔 → 网站 → $DOMAIN → SSL"
echo "     选择 Let's Encrypt → 申请"
echo ""
echo "  📌 第 4 步：编辑 .env 填 LLM API Key"
echo "     宝塔 → 文件 → $PROJECT_DIR/app/.env"
echo "     修改 LLM_DEEPSEEK_API_KEY=你的Key"
echo "     然后在终端执行: systemctl restart officetool"
echo ""
echo "  测试: https://$DOMAIN"
echo "  API文档: https://$DOMAIN/docs"
echo "============================================"
