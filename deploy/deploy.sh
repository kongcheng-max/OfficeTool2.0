#!/bin/bash
# ============================================================
# OfficeTool 轻量化部署脚本
# 适用于: 阿里云 ECS 2C2G + CentOS 7/8 或 Ubuntu 20.04+
# 使用: chmod +x deploy.sh && sudo bash deploy.sh
# ============================================================

set -e

# ========== 配置变量（请修改为实际值）==========
DOMAIN="你的域名"                          # 例如: officetool.example.com
PROJECT_DIR="/opt/officetool"             # 项目安装目录
PYTHON_BIN="python3.11"                   # Python 3.11 可执行文件名

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo "============================================"
echo "  OfficeTool 轻量化部署"
echo "  目标服务器: 2C2G"
echo "============================================"
echo ""

# ========== 1. 检查系统环境 ==========
log "Step 1/8: 检查系统环境..."

# 检查 Python
if ! command -v $PYTHON_BIN &>/dev/null; then
    # 尝试 python3
    if command -v python3 &>/dev/null; then
        PYTHON_BIN="python3"
    else
        err "未找到 Python，请先安装 Python 3.11+"
    fi
fi

PYTHON_VER=$($PYTHON_BIN --version 2>&1 | awk '{print $2}')
log "Python: $PYTHON_VER"

# 检查 Node.js
if ! command -v node &>/dev/null; then
    err "未找到 Node.js，请先安装 Node.js 18+"
fi
NODE_VER=$(node --version)
log "Node.js: $NODE_VER"

# 检查 Nginx
if ! command -v nginx &>/dev/null; then
    warn "Nginx 未安装，正在安装..."
    if command -v apt &>/dev/null; then
        apt update && apt install -y nginx
    elif command -v yum &>/dev/null; then
        yum install -y nginx
    else
        err "无法安装 Nginx，请手动安装"
    fi
fi
log "Nginx: $(nginx -v 2>&1)"

# 检查可用内存
TOTAL_MEM=$(free -m | awk '/Mem:/{print $2}')
log "内存: ${TOTAL_MEM}MB"
if [ "$TOTAL_MEM" -lt 1500 ]; then
    warn "内存不足 1.5GB，服务运行可能不稳定"
fi

# ========== 2. 创建目录 ==========
log "Step 2/8: 创建项目目录..."
mkdir -p "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/app/uploads"

# ========== 3. 上传代码（提示） ==========
log "Step 3/8: 上传项目代码..."
if [ ! -f "$PROJECT_DIR/app/main.py" ]; then
    warn "请将项目代码上传到 $PROJECT_DIR"
    warn "方式一（本地打包上传）:"
    warn "  tar -czf officetool.tar.gz --exclude='.venv' --exclude='node_modules' --exclude='__pycache__' --exclude='.git' app/ deploy/"
    warn "  scp officetool.tar.gz root@你的服务器IP:/opt/officetool/"
    warn "  ssh root@服务器 'cd /opt/officetool && tar -xzf officetool.tar.gz'"
    warn ""
    warn "方式二（从 Git 拉取）:"
    warn "  cd $PROJECT_DIR && git clone <你的仓库地址> ."
    warn ""
    warn "请在另一个终端上传代码后，按回车继续..."
    read -r
fi

if [ ! -f "$PROJECT_DIR/app/main.py" ]; then
    err "未检测到项目代码，请先上传"
fi
log "项目代码已就位"

# ========== 4. 安装 Python 依赖 ==========
log "Step 4/8: 安装 Python 依赖..."

cd "$PROJECT_DIR/app"

# 创建虚拟环境
if [ ! -d ".venv" ]; then
    $PYTHON_BIN -m venv .venv
    log "虚拟环境已创建"
fi

source .venv/bin/activate

# 安装依赖（轻量化：只装核心依赖）
log "安装核心依赖（可能需要几分钟）..."
pip install --upgrade pip -q

pip install \
    fastapi uvicorn[standard] \
    sqlalchemy aiosqlite \
    pydantic[email] pydantic-settings \
    python-jose[cryptography] bcrypt \
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

# ========== 5. 配置环境变量 ==========
log "Step 5/8: 配置环境变量..."

if [ ! -f ".env" ]; then
    if [ -f "../deploy/.env.lightweight" ]; then
        cp ../deploy/.env.lightweight .env
    else
        # 手动创建
        warn "未找到模板文件，生成默认 .env"
        cat > .env << 'ENVEOF'
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
fi

# 生成 SECRET_KEY
if grep -q "change-me\|changeme" .env 2>/dev/null; then
    NEW_KEY=$($PYTHON_BIN -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$NEW_KEY/" .env
    log "SECRET_KEY 已自动生成"
fi

warn "请编辑 $PROJECT_DIR/app/.env 填写你的 LLM API Key！"
warn "  vim $PROJECT_DIR/app/.env"
warn "  修改 LLM_DEEPSEEK_API_KEY 或 LLM_TONGYI_API_KEY"
warn ""

# ========== 6. 构建前端 ==========
log "Step 6/8: 构建前端..."

cd "$PROJECT_DIR/app/frontend"

if [ ! -d "node_modules" ]; then
    log "安装前端依赖..."
    npm install 2>&1 | tail -5
fi

log "构建生产版本..."
npm run build 2>&1 | tail -10

if [ -d "dist" ]; then
    log "前端构建完成: $(du -sh dist | cut -f1)"
else
    err "前端构建失败"
fi

# ========== 7. 配置 Nginx ==========
log "Step 7/8: 配置 Nginx..."

if [ -f "$PROJECT_DIR/deploy/nginx.conf" ]; then
    cp "$PROJECT_DIR/deploy/nginx.conf" /etc/nginx/conf.d/officetool.conf
else
    # 内联生成 Nginx 配置
    cat > /etc/nginx/conf.d/officetool.conf << NGINXEOF
server {
    listen 80;
    server_name $DOMAIN;

    root $PROJECT_DIR/app/frontend/dist;
    index index.html;

    client_max_body_size 200m;

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

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
}
NGINXEOF
fi

# 替换域名占位符
sed -i "s/你的域名/$DOMAIN/g" /etc/nginx/conf.d/officetool.conf

# 测试 Nginx 配置
nginx -t || err "Nginx 配置校验失败"

# 重载 Nginx
systemctl reload nginx || nginx -s reload
log "Nginx 已配置"

# ========== 8. 配置 systemd 服务 ==========
log "Step 8/8: 配置 systemd 服务..."

if [ -f "$PROJECT_DIR/deploy/officetool.service" ]; then
    cp "$PROJECT_DIR/deploy/officetool.service" /etc/systemd/system/officetool.service
else
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
CPUQuota=100%

[Install]
WantedBy=multi-user.target
SVCEOF
fi

systemctl daemon-reload
systemctl enable officetool
systemctl restart officetool

sleep 3

# 检查服务状态
if systemctl is-active --quiet officetool; then
    log "OfficeTool 服务已启动"
else
    warn "OfficeTool 服务启动失败，查看日志: journalctl -u officetool -n 50"
fi

# ========== 完成 ==========
echo ""
echo "============================================"
echo "  ✅ 部署完成！"
echo "============================================"
echo ""
echo "  访问地址:  http://$DOMAIN"
echo "  API 文档:  http://$DOMAIN/docs"
echo ""
echo "  常用命令:"
echo "    查看日志:  journalctl -u officetool -f"
echo "    重启服务:  systemctl restart officetool"
echo "    查看状态:  systemctl status officetool"
echo ""
echo "  ⚠️  别忘了编辑 .env 填入 LLM API Key:"
echo "      vim $PROJECT_DIR/app/.env"
echo "      systemctl restart officetool"
echo ""
echo "  ⚠️  配置 SSL（Let's Encrypt 免费证书）:"
echo "      yum install -y certbot python3-certbot-nginx"
echo "      certbot --nginx -d $DOMAIN"
echo "============================================"
