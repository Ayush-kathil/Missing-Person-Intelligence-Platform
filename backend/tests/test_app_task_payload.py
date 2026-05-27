import unittest
from unittest.mock import patch

from test_support import import_backend_module

app_module = import_backend_module("app")


class FakeTask:
    def __init__(
        self,
        *,
        state: str = "PENDING",
        info: dict | None = None,
        result: dict | str | None = None,
        successful: bool = False,
        failed: bool = False,
    ):
        self.state = state
        self.info = info or {}
        self.result = result
        self._successful = successful
        self._failed = failed

    def successful(self) -> bool:
        return self._successful

    def failed(self) -> bool:
        return self._failed


class AppTaskPayloadTests(unittest.TestCase):
    def setUp(self):
        app_module.app.state.sessions = {}

    def test_task_payload_returns_not_found_for_missing_session(self):
        payload = app_module._task_payload("missing")
        self.assertEqual(payload["state"], "not_found")
        self.assertEqual(payload["error"], "Session not found")

    def test_task_payload_returns_pending_when_task_id_missing(self):
        app_module.app.state.sessions["session-1"] = {"profile": "fast"}
        payload = app_module._task_payload("session-1")
        self.assertEqual(payload["state"], "pending")
        self.assertEqual(payload["alerts_count"], 0)
        self.assertIsNone(payload["error"])

    def test_task_payload_includes_progress_meta(self):
        app_module.app.state.sessions["session-2"] = {
            "task_id": "abc",
            "profile": "accurate",
        }
        fake_task = FakeTask(
            state="PROGRESS",
            info={
                "progress_percent": 38,
                "processed_frames": 190,
                "total_frames": 500,
                "alerts_count": 2,
                "alerts": [{"camera": "CAM-1"}],
                "latest_boxes": {"CAM-1": {"bbox": [1, 2, 3, 4]}, "CAM-2": None},
                "current_camera": "CAM-2",
            },
        )
        with patch.object(app_module, "AsyncResult", return_value=fake_task):
            payload = app_module._task_payload("session-2")

        self.assertEqual(payload["state"], "progress")
        self.assertEqual(payload["progress_percent"], 38)
        self.assertEqual(payload["current_camera"], "CAM-2")
        self.assertEqual(payload["alerts_count"], 2)
        self.assertEqual(payload["profile"], "accurate")

    def test_task_payload_prefers_success_result(self):
        app_module.app.state.sessions["session-3"] = {
            "task_id": "done",
            "profile": "balanced",
        }
        fake_task = FakeTask(
            state="SUCCESS",
            info={"processed_frames": 10, "total_frames": 20},
            result={
                "state": "completed",
                "progress_percent": 100,
                "processed_frames": 20,
                "total_frames": 20,
                "alerts_count": 1,
                "alerts": [{"camera": "CAM-1"}],
                "profile": "fast",
            },
            successful=True,
        )
        with patch.object(app_module, "AsyncResult", return_value=fake_task):
            payload = app_module._task_payload("session-3")

        self.assertEqual(payload["state"], "completed")
        self.assertEqual(payload["progress_percent"], 100)
        self.assertEqual(payload["processed_frames"], 20)
        self.assertEqual(payload["profile"], "fast")
        self.assertIsNone(payload["error"])

    def test_task_payload_sets_failed_state(self):
        app_module.app.state.sessions["session-4"] = {
            "task_id": "fail",
            "profile": "balanced",
        }
        fake_task = FakeTask(
            state="FAILURE",
            info={"progress_percent": 42},
            result=RuntimeError("camera pipeline crashed"),
            failed=True,
        )
        with patch.object(app_module, "AsyncResult", return_value=fake_task):
            payload = app_module._task_payload("session-4")

        self.assertEqual(payload["state"], "failed")
        self.assertIn("camera pipeline crashed", payload["error"])


if __name__ == "__main__":
    unittest.main()
