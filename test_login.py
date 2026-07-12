"""
OfficeTool 登录自动化测试脚本 (Playwright for Python)

流程：
  1. 打开登录页 http://localhost:5176/login
  2. 定位用户名 / 密码输入框，填入凭据 (123 / 123456)
  3. 找到「登 录」按钮并点击
  4. 等待页面跳转，验证是否成功进入 http://localhost:5176/
"""

import re
from playwright.sync_api import sync_playwright


def run_login_test(username: str = "123", password: str = "123456") -> bool:
    """
    执行登录自动化流程，返回是否成功。

    Args:
        username: 用户名
        password: 密码

    Returns:
        bool: 登录是否成功（最终 URL 不含 /login 即视为成功）
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            # ── 1. 打开登录页面 ──────────────────────────
            print("[1/4] 打开登录页 → http://localhost:5176/login")
            page.goto("http://localhost:5176/login", wait_until="networkidle")
            print(f"      页面标题: {page.title()}")
            print(f"      当前 URL: {page.url}")

            # ── 2. 填写用户名和密码 ────────────────────────
            print("[2/4] 填写登录凭据...")

            # 用户名输入框（按 placeholder / name / id 优先级匹配）
            username_input = page.locator(
                'input[placeholder*="用户"], '
                'input[placeholder*="账号"], '
                'input[placeholder*="用户名"], '
                'input[name="username"], '
                'input#username'
            ).first
            username_input.wait_for(state="visible", timeout=5000)

            # 密码输入框
            password_input = page.locator(
                'input[type="password"], '
                'input[placeholder*="密码"], '
                'input[name="password"], '
                'input#password'
            ).first
            password_input.wait_for(state="visible", timeout=5000)

            username_input.fill(username)
            password_input.fill(password)
            print(f"      已填入 username={username}, password={'*' * len(password)}")

            # ── 3. 点击登录按钮 ────────────────────────────
            print("[3/4] 查找并点击登录按钮...")

            # 优先匹配文本包含「登录」的按钮（按文本过滤）
            login_btn = page.locator("button").filter(
                has_text=re.compile(r"登\s*录|Login|login")
            ).first
            # 备用：type=submit 的按钮
            submit_btn = page.locator('button[type="submit"]').first

            if login_btn.count() > 0:
                btn = login_btn
            elif submit_btn.count() > 0:
                btn = submit_btn
            else:
                # 最后兜底：主区域内任意可见含文本按钮
                btn = page.locator("button:visible").filter(
                    has_text=re.compile(r".+")
                ).first

            btn_text = btn.text_content() or "(none)"
            print(f"      点击按钮: {btn_text.strip()}")

            # 等待点击触发的页面跳转
            with page.expect_navigation(wait_until="networkidle", timeout=10000):
                btn.click()

            # 额外等待确保重定向完成
            page.wait_for_timeout(2000)
            page.wait_for_load_state("networkidle")

            # ── 4. 验证结果 ────────────────────────────────
            print("[4/4] 验证登录结果...")
            final_url = page.url
            print(f"      最终 URL: {final_url}")
            print(f"      页面标题: {page.title()}")

            success = final_url in (
                "http://localhost:5176/",
                "http://localhost:5176",
            ) or (
                final_url.startswith("http://localhost:5176")
                and "/login" not in final_url
            )

            if success:
                print("\n✓ 登录成功！已进入 http://localhost:5176/")
            else:
                print("\n✗ 登录失败，仍在登录页或跳转至未知页面")

            # 截图留档
            page.screenshot(path="login_result.png", full_page=True)
            print("      截图已保存 → login_result.png")

            return success

        except Exception as exc:
            print(f"\n✗ 错误: {exc}")
            try:
                page.screenshot(path="login_error.png", full_page=True)
                print("      错误截图已保存 → login_error.png")
            except Exception:
                pass
            return False

        finally:
            browser.close()


if __name__ == "__main__":
    ok = run_login_test()
    exit(0 if ok else 1)
