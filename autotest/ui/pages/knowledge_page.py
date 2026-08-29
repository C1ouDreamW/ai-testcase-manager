import re

from playwright.sync_api import expect

from .base_page import BasePage


class KnowledgePage(BasePage):
    path = "/knowledge"

    def goto_project(self, project_id: int):
        return self.goto(f"/knowledge?project={project_id}")

    def upload_file(self, file_path: str):
        self.page.locator(".ant-upload input[type='file']").set_input_files(file_path)

    def doc_card(self, title: str):
        return self.page.locator(".knowledge-card", has_text=title).first

    def search(self, query: str):
        self.page.get_by_placeholder("输入问题测试检索效果").fill(query)
        self.page.get_by_role("button", name="检索").click()

    def delete_doc(self, title: str):
        """卡片「...」菜单 → 删除 → 确认弹窗「删除」。"""
        card = self.doc_card(title)
        card.locator("button.ant-btn-icon-only").first.click()
        self.page.get_by_role("menuitem", name="删除").click()
        self.page.locator(".ant-modal", has_text="该知识文档及其向量将一并删除").get_by_role("button", name=re.compile(r"删\s*除")).click()
