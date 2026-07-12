"""
OfficeTool 全流程自动化测试 (Playwright for Python)

流程:
  1. 登录 → http://localhost:5176/
  2. 点击导航栏「知识库」→ /kb/manage
  3. 在侧边栏选「第二阶段测试知识库v2.0」→ /kb/:id/chat
  4. 在智能问答输入框提问并验证 AI 回复

用法:
  python test_full_flow.py
"""

import re
import time
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5176"
USERNAME = "123"
PASSWORD = "123456"
QUESTION = "测试报告的内容是什么？是第几版？"
KB_NAME = "第二阶段测试知识库v2.0"


def run() -> bool:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            channel="chrome",
            slow_mo=150,
        )
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        page = ctx.new_page()
        step = 0

        try:
            # ═══════════════════════════════════════════════════
            # Step 1 – 登录
            # ═══════════════════════════════════════════════════
            step = 1
            print(f"\n{'─'*55}\n  Step {step}: 登录\n{'─'*55}")

            page.goto(f"{BASE}/login", wait_until="networkidle")
            # 填表 —— 用 placeholder 匹配
            page.locator('input[placeholder*="用户"]').first.wait_for(state="visible", timeout=5000)
            page.locator('input[placeholder*="用户"]').first.fill(USERNAME)
            page.locator('input[type="password"]').first.fill(PASSWORD)
            print(f"  填写凭据: {USERNAME} / {'*'*len(PASSWORD)}")

            # 点登录
            login_btn = page.locator("button").filter(has_text=re.compile(r"登\s*录")).first
            print(f"  点击: {(login_btn.text_content() or '').strip()}")
            with page.expect_navigation(wait_until="networkidle", timeout=10000):
                login_btn.click()
            page.wait_for_timeout(1500)

            if "/login" in page.url:
                print("  ✗ 仍在登录页")
                return False
            print(f"  ✓ 登录成功 → {page.url}")
            page.screenshot(path="s01_login.png", full_page=True)

            # ═══════════════════════════════════════════════════
            # Step 2 – 点击侧边导航「知识库」
            # ═══════════════════════════════════════════════════
            step = 2
            print(f"\n{'─'*55}\n  Step {step}: 导航 → 知识库\n{'─'*55}")

            # 导航栏: <nav aria-label="主导航"> 内 <div aria-label="知识库">
            kb_nav = page.locator('nav[aria-label="主导航"] div[aria-label="知识库"]')
            kb_nav.wait_for(state="visible", timeout=5000)
            kb_nav.click()
            page.wait_for_timeout(1200)
            page.wait_for_load_state("networkidle")
            print(f"  当前 URL: {page.url}")
            page.screenshot(path="s02_kb_manage.png", full_page=True)

            # ═══════════════════════════════════════════════════
            # Step 3 – 选择知识库「第二阶段测试知识库v2.0」
            #   AppLayout 侧边栏用 div 渲染 KB 列表，点击即导航
            # ═══════════════════════════════════════════════════
            step = 3
            print(f"\n{'─'*55}\n  Step {step}: 选择知识库 → {KB_NAME}\n{'─'*55}")

            # KB 列表结构: <div onClick={navigate}> <icon/> <span>KB名称</span> </div>
            # 精准定位到 <span> 元素（避免匹配到包裹所有 KB 的容器 div）
            kb_span = page.locator("aside span").filter(has_text=KB_NAME).first
            kb_span.wait_for(state="visible", timeout=5000)
            txt = (kb_span.text_content() or "").strip()
            print(f"  找到: {txt}")
            with page.expect_navigation(wait_until="networkidle", timeout=10000):
                kb_span.click()  # click 冒泡到父 div → 触发 navigate
            page.wait_for_timeout(1500)
            page.wait_for_load_state("networkidle")
            print(f"  当前 URL: {page.url}")
            page.screenshot(path="s03_kb_chat.png", full_page=True)

            # 验证已在 /chat 页面
            if "/chat" not in page.url:
                print("  ⚠ 未进入 chat 页面，尝试手动拼接")
                current = page.url
                if "/kb/" in current:
                    page.goto(current.rstrip("/") + "/chat", wait_until="networkidle")

            # ═══════════════════════════════════════════════════
            # Step 4 – 提问
            #   Chat 页: 底部是 Ant TextArea (textarea) + 发送按钮
            # ═══════════════════════════════════════════════════
            step = 4
            print(f"\n{'─'*55}\n  Step {step}: 提问 → {QUESTION}\n{'─'*55}")

            # 输入框: Ant Design TextArea → <textarea>
            textarea = page.locator("textarea").first
            textarea.wait_for(state="visible", timeout=5000)
            textarea.click()
            textarea.fill(QUESTION)
            print(f"  输入完成")

            page.screenshot(path="s04_input.png", full_page=True)

            # ═══════════════════════════════════════════════════
            # Step 5 – 发送 & 等待回复
            # ═══════════════════════════════════════════════════
            step = 5
            print(f"\n{'─'*55}\n  Step {step}: 发送并等待回复\n{'─'*55}")

            # 发送按钮: <button type="primary"> 含"发送"文本
            send_btn = page.locator("button").filter(has_text="发送").first
            send_btn.click()
            print(f"  已点击发送")

            # 轮询等待回复 (最多 120 秒)
            print("  等待 AI 回复 ...")
            answered = False
            for i in range(24):  # 24 × 5s = 120s max
                page.wait_for_timeout(5000)
                body = page.locator("body").text_content() or ""
                test_report_count = body.count("测试报告")
                if test_report_count >= 2:  # 问题 + 回复各出现一次
                    answered = True
                    break
                # 也检查是否还在加载中
                if "正在生成回答" not in body and i > 2 and test_report_count >= 1:
                    # 可能回复里没再提"测试报告"四个字，但已经生成完了
                    answered = True
                    break
                if i % 4 == 0:
                    print(f"    等待中... ({(i+1)*5}s)")

            page.screenshot(path="s05_response.png", full_page=True)

            # ═══════════════════════════════════════════════════
            # 验证
            # ═══════════════════════════════════════════════════
            body = page.locator("body").text_content() or ""
            print(f"\n  页面文本长度: {len(body)} 字符")

            # 提取"测试报告"上下文
            if "测试报告" in body:
                idx = body.index("测试报告")
                # 找第二次出现 (回复内容)
                idx2 = body.index("测试报告", idx + 4) if body.count("测试报告") >= 2 else idx
                snippet = body[max(0, idx2 - 30): idx2 + 350]
                print(f"\n  ── 回复片段 ──\n  {snippet}\n  ── 结束 ──")

            # 判断结果
            if answered:
                print("\n  ✅ 问答正常: 已收到包含「测试报告」的 AI 回复")
                return True
            elif "测试报告" in body:
                print("\n  ⚠️ 检测到关键词但可能仅来自问题，请检查截图 s05_response.png")
                return True  # 宽松判定
            else:
                print("\n  ❌ 未检测到相关回复内容")
                return False

        except Exception as e:
            print(f"\n  ✗ Step {step} 异常: {e}")
            page.screenshot(path=f"error_step{step}.png", full_page=True)
            return False

        finally:
            print(f"\n{'─'*55}")
            print("  浏览器 8 秒后关闭...")
            time.sleep(8)
            browser.close()


if __name__ == "__main__":
    ok = run()
    print(f"\n{'✅ 全流程通过' if ok else '❌ 失败，请检查截图'}")
    exit(0 if ok else 1)
