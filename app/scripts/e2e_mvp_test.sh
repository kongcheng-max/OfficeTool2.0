#!/bin/bash
# MVP 全链路 E2E 测试脚本
# 用法: bash scripts/e2e_mvp_test.sh
# 前提: PG + Redis 已启动, BE 运行在 localhost:8000

BASE="http://127.0.0.1:8000"
API="$BASE/api/v1"
PASS=0
FAIL=0

green() { echo -e "\033[32m✅ $1\033[0m"; ((PASS++)); }
red()   { echo -e "\033[31m❌ $1\033[0m"; ((FAIL++)); }

echo "====================================="
echo "  OfficeTool MVP 全链路 E2E 测试"
echo "====================================="
echo ""

# ── 1. Health Check ──
echo "── 1. 健康检查 ──"
HEALTH=$(curl -s "$BASE/api/health")
if echo "$HEALTH" | grep -q '"ok"'; then
  green "Health check: $HEALTH"
else
  red "Health check 失败: $HEALTH"
  exit 1
fi

# ── 2. 注册用户 ──
echo ""
echo "── 2. 注册用户 ──"
REG=$(curl -s -X POST "$API/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"e2etest","password":"test123456"}')
echo "   Response: $REG"
if echo "$REG" | grep -q '"code":0'; then
  green "注册成功"
  TOKEN=$(echo "$REG" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
else
  # 可能已存在，尝试登录
  echo "   (用户可能已存在，尝试登录)"
  TOKEN=""
fi

# ── 3. 登录 ──
echo ""
echo "── 3. 登录 ──"
if [ -z "$TOKEN" ]; then
  LOGIN=$(curl -s -X POST "$API/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"e2etest","password":"test123456"}')
  echo "   Response: $LOGIN"
  if echo "$LOGIN" | grep -q '"code":0'; then
    green "登录成功"
    TOKEN=$(echo "$LOGIN" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
  else
    red "登录失败: $LOGIN"
  fi
else
  green "使用注册返回的 token"
fi

if [ -z "$TOKEN" ]; then
  red "无法获取 Token，终止测试"
  exit 1
fi

AUTH="Authorization: Bearer $TOKEN"

# ── 4. 获取当前用户信息 ──
echo ""
echo "── 4. 获取用户信息 ──"
ME=$(curl -s "$API/users/me" -H "$AUTH")
echo "   Response: $ME"
if echo "$ME" | grep -q '"code":0'; then
  green "用户信息获取成功"
else
  red "用户信息获取失败"
fi

# ── 5. 创建知识库 ──
echo ""
echo "── 5. 创建知识库 ──"
printf '{"name":"E2E测试知识库","description":"自动化测试用"}' > /tmp/e2e_kb_body.json
KB=$(curl -s -X POST "$API/knowledge-bases" \
  -H "$AUTH" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d @/tmp/e2e_kb_body.json)
echo "   Response: $KB"
KB_ID=$(echo "$KB" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
if [ -n "$KB_ID" ]; then
  green "知识库创建成功 ID=$KB_ID"
else
  red "知识库创建失败"
fi

# ── 6. 列出知识库 ──
echo ""
echo "── 6. 列出知识库 ──"
KB_LIST=$(curl -s "$API/knowledge-bases" -H "$AUTH")
echo "   KB count: $(echo "$KB_LIST" | grep -o '"id"' | wc -l)"
if echo "$KB_LIST" | grep -q '"code":0'; then
  green "知识库列表获取成功"
else
  red "知识库列表获取失败"
fi

# ── 7. 上传文档 ──
echo ""
echo "── 7. 上传测试文档 ──"
# 创建测试文件
echo "# E2E 测试文档" > /tmp/e2e_test.md
echo "" >> /tmp/e2e_test.md
echo "这是一个用于自动化测试的 Markdown 文档。" >> /tmp/e2e_test.md
echo "" >> /tmp/e2e_test.md
echo "## 核心特性" >> /tmp/e2e_test.md
echo "- 支持多格式文档解析" >> /tmp/e2e_test.md
echo "- 基于 RAG 的智能问答" >> /tmp/e2e_test.md
echo "- 向量相似度检索" >> /tmp/e2e_test.md

if [ -n "$KB_ID" ]; then
  UPLOAD=$(curl -s -X POST "$API/kb/$KB_ID/documents" \
    -H "$AUTH" \
    -F "file=@/tmp/e2e_test.md")
  echo "   Response: $UPLOAD"
  DOC_ID=$(echo "$UPLOAD" | grep -o '"document_id":"[^"]*"' | cut -d'"' -f4)
  if [ -n "$DOC_ID" ]; then
    green "文档上传成功 doc_id=$DOC_ID status=$(echo "$UPLOAD" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)"
  else
    red "文档上传失败: $UPLOAD"
  fi
else
  red "跳过上传 (无 KB_ID)"
fi

# ── 8. 文档列表 ──
echo ""
echo "── 8. 查询文档列表 ──"
if [ -n "$KB_ID" ]; then
  DOC_LIST=$(curl -s "$API/kb/$KB_ID/documents?page=1&page_size=10" -H "$AUTH")
  echo "   Total: $(echo "$DOC_LIST" | grep -o '"total":[0-9]*' | cut -d: -f2)"
  if echo "$DOC_LIST" | grep -q '"code":0'; then
    green "文档列表获取成功"
  else
    red "文档列表获取失败"
  fi
else
  red "跳过文档列表 (无 KB_ID)"
fi

# ── 9. 单次问答 (可能 LLM 不可用，测试 API 结构) ──
echo ""
echo "── 9. 单次问答 ──"
if [ -n "$KB_ID" ]; then
  printf '{"question":"核心特性有哪些？"}' > /tmp/e2e_qa_body.json
  QA=$(curl -s -X POST "$API/kb/$KB_ID/qa" \
    -H "$AUTH" \
    -H "Content-Type: application/json; charset=utf-8" \
    -d @/tmp/e2e_qa_body.json)
  echo "   Answer preview: $(echo "$QA" | head -c 200)"
  if echo "$QA" | grep -q '"code":0'; then
    green "问答 API 调用成功"
    # 检查 sources 字段
    if echo "$QA" | grep -q '"sources"'; then
      green "返回了 sources 来源引用"
    fi
  else
    red "问答 API 失败: $QA"
  fi
else
  red "跳过问答 (无 KB_ID)"
fi

# ── 10. 删除文档 ──
echo ""
echo "── 10. 删除文档 ──"
if [ -n "$KB_ID" ] && [ -n "$DOC_ID" ]; then
  DEL_DOC=$(curl -s -X DELETE "$API/kb/$KB_ID/documents/$DOC_ID" -H "$AUTH")
  if echo "$DEL_DOC" | grep -q '"code":0'; then
    green "文档删除成功"
  else
    red "文档删除失败: $DEL_DOC"
  fi
else
  red "跳过删除 (无 DOC_ID)"
fi

# ── 11. 删除知识库 ──
echo ""
echo "── 11. 删除知识库 ──"
if [ -n "$KB_ID" ]; then
  DEL_KB=$(curl -s -X DELETE "$API/knowledge-bases/$KB_ID" -H "$AUTH")
  if echo "$DEL_KB" | grep -q '"code":0'; then
    green "知识库删除成功"
  else
    red "知识库删除失败: $DEL_KB"
  fi
fi

# ── Summary ──
echo ""
echo "====================================="
echo "  测试完成: 通过 $PASS / 失败 $FAIL"
echo "====================================="
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
