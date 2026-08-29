"""全局导航：侧边栏各入口可达，页面标题正确。"""

import pytest
from playwright.sync_api import expect

from ui.pages.base_page import BasePage


@pytest.mark.smoke
def test_sidebar_brand_visible(page, base_url):
    BasePage(page).goto("/")
    expect(page.locator(".app-brand-title", has_text="AI用例管理平台")).to_be_visible()


def test_nav_to_testcases(page, base_url):
    base = BasePage(page)
    base.goto("/")
    base.sidebar_link("全部用例").click()
    expect(page).to_have_url(f"{base_url}/testcases")
    expect(page.locator(".page-title", has_text="全部用例")).to_be_visible()


def test_nav_to_knowledge(page, base_url):
    base = BasePage(page)
    base.goto("/")
    base.sidebar_link("知识库").click()
    expect(page).to_have_url(f"{base_url}/knowledge")
    expect(page.locator(".page-title", has_text="知识库")).to_be_visible()


def test_nav_to_evaluation(page, base_url):
    base = BasePage(page)
    base.goto("/")
    base.sidebar_link("AI 评测").click()
    expect(page).to_have_url(f"{base_url}/evaluation")
    expect(page.locator(".page-title", has_text="AI 评测")).to_be_visible()


def test_nav_to_agent(page, base_url):
    base = BasePage(page)
    base.goto("/")
    base.sidebar_link("AI小助手").click()
    expect(page).to_have_url(f"{base_url}/agent")


def test_nav_to_settings_via_user_menu(page, base_url):
    """设置入口在侧边栏底部用户菜单内。"""
    base = BasePage(page)
    base.goto("/")
    page.locator(".sidebar-user").click()
    page.get_by_role("menuitem", name="个人设置").click()
    expect(page).to_have_url(f"{base_url}/settings")
    expect(page.locator(".page-title", has_text="个人模型配置")).to_be_visible()
