import unittest
from unittest.mock import patch

from test_support import import_backend_module

tasks = import_backend_module("tasks")


class DummyCapture:
    def __init__(self, opened: bool, frame_count: int):
        self._opened = opened
        self._frame_count = frame_count
        self.released = False

    def isOpened(self) -> bool:
        return self._opened

    def get(self, _prop: int) -> int:
        return self._frame_count

    def release(self) -> None:
        self.released = True


class TaskHelperTests(unittest.TestCase):
    def test_video_frame_count_returns_zero_when_video_cannot_open(self):
        capture = DummyCapture(opened=False, frame_count=200)
        with patch.object(tasks.cv2, "VideoCapture", return_value=capture):
            count = tasks._video_frame_count("dummy.mp4")
        self.assertEqual(count, 0)
        self.assertTrue(capture.released)

    def test_video_frame_count_reads_frame_count_when_open(self):
        capture = DummyCapture(opened=True, frame_count=321)
        with patch.object(tasks.cv2, "VideoCapture", return_value=capture):
            count = tasks._video_frame_count("dummy.mp4")
        self.assertEqual(count, 321)
        self.assertTrue(capture.released)

    def test_is_ml_critical_error_detects_model_related_failures(self):
        err = RuntimeError("CUDA out of memory while loading YOLO model")
        self.assertTrue(tasks._is_ml_critical_error(err))

    def test_is_ml_critical_error_ignores_non_ml_failures(self):
        err = RuntimeError("disk write failed in tmp directory")
        self.assertFalse(tasks._is_ml_critical_error(err))


if __name__ == "__main__":
    unittest.main()
