#!/bin/bash
# ============================================================
# OfficeTool 纯命令行部署脚本（SSH 一键部署）
# 使用: ssh root@服务器后执行
#   cd /www/wwwroot/officetool && sudo bash deploy/deploy.sh
# ============================================================

set -e

# ========== 配置 ==========
DOMAIN="${1:-你的域名}"
PROJECT_DIR="/www/wwwroot/officetool"
PYTHON_BIN="python3.11"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

if [ "$DOMAIN" = "你的域名" ]; then
    warn "用法: sudo bash deploy/deploy.sh 你的域名"
    warn "例如: sudo bash deploy/deploy.sh officetool.example.com"
    warn ""
    warn "继续使用默认域名部署（仅用于测试）..."
    echo ""
fi

echo "============================================"
echo "  OfficeTool 一键部署"
echo "  域名: $DOMAIN"
echo "============================================"
echo ""

# ============================================================
# Step 1: 安装 Python 3.11
# ============================================================
log "Step 1/8: 安装 Python 3.11..."

if command -v python3.11 &>/dev/null; then
    log "已安装: $(python3.11 --version)"
else
    warn "安装 Python 3.11（约 2-3 分钟）..."
    if command -v apt &>/dev/null; then
        apt update -qq
        apt install -y -qq software-properties-common
        add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
        apt update -qq
        apt install -y -qq python3.11 python3.11-venv python3.11-dev
    elif command -v yum &>/dev/null; then
        yum install -y -q gcc openssl-devel bzip2-devel libffi-devel zlib-devel
        if [ ! -f /tmp/Python-3.11.9.tar.xz ]; then
            curl -sLo /tmp/Python-3.11.9.tar.xz https://mirrors.huaweicloud.com/python/3.11.9/Python-3.11.9.tar.xz
            tar -xf /tmp/Python-3.11.9.tar.xz -C /tmp
        fi
        cd /tmp/Python-3.11.9
        ./configure --enable-optimizations --prefix=/usr/local/python3.11 -q
        make -j$(nproc) -s
        make install -s
        ln -sf /usr/local/python3.11/bin/python3.11 /usr/bin/python3.11
        ln -sf /usr/local/python3.11/bin/pip3.11 /usr/bin/pip3.11
        cd "$PROJECT_DIR"
    fi
    log "Python 3.11 安装完成"
fi

# ============================================================
# Step 2: 安装 Node.js 18
# ============================================================
log "Step 2/8: 安装 Node.js 18..."

if command -v node &>/dev/null && node -v | grep -q 'v1[89]\|v2[0-9]'; then
    log "已安装: $(node --version)"
else
    warn "安装 Node.js 18..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - 2>/dev/null && \
        apt install -y nodejs 2>/dev/null && log "Node.js 安装完成" || \
    curl -fsSL https://rpm.nodesource.com/setup_18.x | bash - 2>/dev/null && \
        yum install -y nodejs 2>/dev/null && log "Node.js 安装完成" || \
    err "Node.js 安装失败，请手动安装"
fi

# ============================================================
# Step 3: 确认 Nginx 可用
# ============================================================
log "Step 3/8: 检查 Nginx..."

NGINX_BIN=""
for p in /www/server/nginx/sbin/nginx /usr/sbin/nginx /usr/bin/nginx; do
    [ -x "$p" ] && NGINX_BIN="$p" && break
done

if [ -z "$NGINX_BIN" ]; then
    warn "未找到 Nginx，正在安装..."
    if command -v apt &>/dev/null; then
        apt install -y -qq nginx && NGINX_BIN="/usr/sbin/nginx"
    elif command -v yum &>/dev/null; then
        yum install -y -q nginx && NGINX_BIN="/usr/sbin/nginx"
    fi
fi
log "Nginx: $NGINX_BIN ($($NGINX_BIN -v 2>&1))"

# 确定配置文件路径
if [ "$NGINX_BIN" = "/www/server/nginx/sbin/nginx" ]; then
    NGINX_CONF_DIR="/www/server/panel/vhost/nginx"
    mkdir -p "$NGINX_CONF_DIR"
else
    NGINX_CONF_DIR="/etc/nginx/conf.d"
fi

# ============================================================
# Step 4: 安装 Python 依赖
# ============================================================
log "Step 4/8: 安装 Python 依赖..."

cd "$PROJECT_DIR/app"

if [ ! -d ".venv" ]; then
    $PYTHON_BIN -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip -q

log "安装依赖包（首次 3-5 分钟，后续秒过）..."
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
    pyyaml Pillow \
    -q 2>&1 | tail -3
log "依赖安装完成"

# ============================================================
# Step 5: 配置 .env
# ============================================================
log "Step 5/8: 配置环境变量..."

SECRET_KEY=$($PYTHON_BIN -c "import secrets; print(secrets.token_hex(32))")

cat > .env << ENVEOF
APP_NAME=OfficeTool
APP_VERSION=0.1.0
DEBUG=false
SECRET_KEY=$SECRET_KEY
CORS_ORIGINS=http://localhost:5173,https://$DOMAIN
USE_SQLITE=true
LLM_PROVIDER=deepseek
LLM_DEEPSEEK_API_KEY=请填写你的API-Key
LLM_DEEPSEEK_MODEL=deepseek-chat
EMBEDDING_MODEL=text2vec-large-chinese
EMBEDDING_DEVICE=cpu
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
UPLOAD_DIR=./uploads
RETRIEVER_TOP_K=10
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
ENVEOF

mkdir -p uploads
log ".env 已生成（SECRET_KEY 已自动创建）"

# ============================================================
# Step 6: 构建前端
# ============================================================
log "Step 6/8: 构建前端..."

cd "$PROJECT_DIR/app/frontend"

if [ ! -d "node_modules" ]; then
    npm install --silent 2>&1 | tail -3
fi

npm run build 2>&1 | tail -5

[ -d "dist" ] || err "前端构建失败"
log "前端构建完成"

# ============================================================
# Step 7: 配置 Nginx
# ============================================================
log "Step 7/8: 配置 Nginx..."

cat > "$NGINX_CONF_DIR/officetool.conf" << NGINXEOF
server {
    listen 80;
    server_name $DOMAIN;

    root $PROJECT_DIR/app/frontend/dist;
    index index.html;

    client_max_body_size 200m;

    # API 反向代理（SSE 流式支持）
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }

    location /docs  { proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; }
    location /redoc { proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; }
    location /openapi.json { proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; }

    location / { try_files \$uri \$uri/ /index.html; }
}
NGINXEOF

$NGINX_BIN -t && $NGINX_BIN -s reload 2>/dev/null || systemctl reload nginx
log "Nginx 已配置并重载"

# ============================================================
# Step 8: 配置 systemd 并启动
# ============================================================
log "Step 8/8: 启动后端服务..."

cat > /etc/systemd/system/officetool.service << SVCEOF
[Unit]
Description=OfficeTool Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR/app
EnvironmentFile=$PROJECT_DIR/app/.env
ExecStart=$PROJECT_DIR/app/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=5
MemoryMax=800M

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable officetool
systemctl restart officetool
sleep 2

if systemctl is-active --quiet officetool; then
    log "后端服务已启动 ✅"
else
    warn "启动失败，查看: journalctl -u officetool -n 30"
fi

# ============================================================
# SSL 证书
# ============================================================
echo ""
echo "============================================"
echo "  ✅ 部署完成！"
echo "============================================"
echo ""
echo "  📌 接下来配置 SSL 证书（HTTPS）："
echo ""
echo "  方式一 — certbot 自动申请（推荐）："
echo "    yum install -y certbot python3-certbot-nginx"
echo "    certbot --nginx -d $DOMAIN"
echo ""
echo "  方式二 — acme.sh 零配置："
echo "    curl https://get.acme.sh | sh"
echo "    ~/.acme.sh/acme.sh --issue -d $DOMAIN -w $PROJECT_DIR/app/frontend/dist"
echo "    ~/.acme.sh/acme.sh --install-cert -d $DOMAIN \\"
echo "      --key-file /etc/nginx/ssl/$DOMAIN.key \\"
echo "      --fullchain-file /etc/nginx/ssl/$DOMAIN.pem \\"
echo "      --reloadcmd \"$NGINX_BIN -s reload\""
echo ""
echo "  📌 别忘了配置 API Key："
echo "    vim $PROJECT_DIR/app/.env"
echo "    修改 LLM_DEEPSEEK_API_KEY=你的Key"
echo "    systemctl restart officetool"
echo ""
echo "  健康检查: curl http://127.0.0.1:8000/api/health"
echo "  查看日志: journalctl -u officetool -f"
echo "============================================"
