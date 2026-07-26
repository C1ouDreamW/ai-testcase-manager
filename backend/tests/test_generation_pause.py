"""生成任务协作式暂停：节点边界检查、租约抢占与状态收敛。"""

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.database import Base
from app.models.generation import GenerationTask
from app.models.project import Project
from app.models.requirement import RequirementDocument
from app.models.user import User
from app.workflows.generation.control import (
    GenerationPaused,
    claim_run_lease,
    ensure_not_paused,
)


class GenerationPauseControlTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        user = User(id=1, username="u", password_hash="x")
        project = Project(id=1, name="p", user_id=1)
        doc = RequirementDocument(id=1, project_id=1, title="d", status="confirmed")
        task = GenerationTask(
            id=1,
            project_id=1,
            document_id=1,
            status="generating",
            run_lease="lease-1",
            pause_requested=False,
        )
        self.db.add_all([user, project, doc, task])
        self.db.commit()

        # ensure_not_paused / claim 使用全局 SessionLocal，需指向本测试库
        self.session_local_patch = patch(
            "app.workflows.generation.control.SessionLocal",
            self.Session,
        )
        self.session_local_patch.start()

    def tearDown(self):
        self.session_local_patch.stop()
        self.db.close()

    def test_ensure_not_paused_raises_and_marks_paused(self):
        task = self.db.get(GenerationTask, 1)
        task.pause_requested = True
        task.status = "pausing"
        self.db.commit()

        with self.assertRaises(GenerationPaused):
            ensure_not_paused(1)

        self.db.expire_all()
        task = self.db.get(GenerationTask, 1)
        self.assertEqual(task.status, "paused")
        self.assertFalse(task.pause_requested)
        self.assertEqual(task.run_lease, "")

    def test_ensure_not_paused_ignores_completed(self):
        task = self.db.get(GenerationTask, 1)
        task.status = "completed"
        task.pause_requested = True
        self.db.commit()
        ensure_not_paused(1)
        self.db.expire_all()
        self.assertEqual(self.db.get(GenerationTask, 1).status, "completed")

    def test_claim_run_lease_blocks_second_claim(self):
        task = self.db.get(GenerationTask, 1)
        task.status = "paused"
        task.run_lease = ""
        self.db.commit()

        lease1 = claim_run_lease(self.db, task, resume=True)
        self.assertTrue(lease1)
        self.assertEqual(task.status, "generating")

        other = self.Session()
        try:
            current = other.get(GenerationTask, 1)
            with self.assertRaises(RuntimeError):
                claim_run_lease(other, current, resume=True)
        finally:
            other.close()

    def test_claim_fresh_start_from_pending(self):
        task = self.db.get(GenerationTask, 1)
        task.status = "pending"
        task.run_lease = ""
        self.db.commit()
        lease = claim_run_lease(self.db, task, resume=False)
        self.assertTrue(lease)
        self.assertEqual(task.status, "generating")


if __name__ == "__main__":
    unittest.main()
