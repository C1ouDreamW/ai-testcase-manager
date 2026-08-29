from .base_page import BasePage


class SettingsPage(BasePage):
    path = "/settings"

    def tab(self, label: str):
        return self.page.locator(".ant-tabs-tab", has_text=label).first

    def save_generation_model(self, model: str):
        self.tab("生成模型").click()
        self.page.locator("#llm_model").fill(model)
        self.page.get_by_role("button", name="保存并测试连接").click()
