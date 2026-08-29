"""设置页：多模型页签展示与生成模型保存。"""

import pytest
from playwright.sync_api import expect

from ui.pages.settings_page import SettingsPage


@pytest.mark.smoke
def test_settings_tabs_visible(page, base_url):
    sp = SettingsPage(page)
    sp.goto()
    expect(sp.page.locator(".page-title", has_text="个人模型配置")).to_be_visible()
    for label in ("生成模型", "评测模型", "视觉模型", "Embedding", "Rerank"):
        expect(sp.tab(label)).to_be_visible()


def test_save_generation_model(page, base_url):
    sp = SettingsPage(page)
    sp.goto()
    sp.save_generation_model("ui-test-model")
    sp.expect_message("配置已保存")
