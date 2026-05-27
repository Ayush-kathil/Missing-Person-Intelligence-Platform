import importlib
import sys
import types
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _ensure_backend_path() -> None:
    backend_path = str(BACKEND_DIR)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)


def _stub_cv2() -> None:
    if "cv2" in sys.modules:
        return
    cv2 = types.ModuleType("cv2")
    cv2.CAP_PROP_FRAME_COUNT = 7
    cv2.CAP_PROP_FPS = 5
    cv2.IMREAD_COLOR = 1
    cv2.FONT_HERSHEY_SIMPLEX = 0
    cv2.LINE_AA = 0

    class _Capture:
        def __init__(self, _: str):
            self.opened = False

        def isOpened(self) -> bool:
            return self.opened

        def get(self, _prop: int) -> float:
            return 0.0

        def read(self):
            return False, None

        def release(self) -> None:
            return None

    cv2.VideoCapture = _Capture
    cv2.resize = lambda frame, _size: frame
    cv2.imdecode = lambda _arr, _flag: object()
    cv2.imencode = lambda _ext, _frame: (
        True,
        types.SimpleNamespace(tobytes=lambda: b""),
    )
    cv2.rectangle = lambda *_args, **_kwargs: None
    cv2.putText = lambda *_args, **_kwargs: None
    cv2.imwrite = lambda *_args, **_kwargs: True
    sys.modules["cv2"] = cv2


def _stub_deepface() -> None:
    if "deepface" in sys.modules:
        return
    deepface = types.ModuleType("deepface")

    class _DeepFace:
        @staticmethod
        def build_model(_name: str):
            return object()

        @staticmethod
        def represent(**_kwargs):
            return [{"embedding": [1.0, 0.0], "face_confidence": 1.0}]

    deepface.DeepFace = _DeepFace
    sys.modules["deepface"] = deepface


def _stub_ultralytics() -> None:
    if "ultralytics" in sys.modules:
        return
    ultralytics = types.ModuleType("ultralytics")

    class _YOLO:
        def __init__(self, *_args, **_kwargs):
            pass

        def fuse(self) -> None:
            return None

        def track(self, *_args, **_kwargs):
            return []

    ultralytics.YOLO = _YOLO
    sys.modules["ultralytics"] = ultralytics


def _stub_celery() -> None:
    if "celery" not in sys.modules:
        celery = types.ModuleType("celery")

        class _Conf(dict):
            def update(self, *args, **kwargs):
                return super().update(*args, **kwargs)

        class _Celery:
            def __init__(self, *_args, **_kwargs):
                self.conf = _Conf()
                self.control = types.SimpleNamespace(revoke=lambda *_a, **_k: None)

            def task(self, *args, **kwargs):
                def decorator(func):
                    return func

                if args and callable(args[0]) and not kwargs:
                    return args[0]
                return decorator

        celery.Celery = _Celery
        sys.modules["celery"] = celery

    if "celery.result" in sys.modules:
        return
    result_module = types.ModuleType("celery.result")

    class _AsyncResult:
        def __init__(self, *_args, **_kwargs):
            self.state = "PENDING"
            self.info = {}
            self.result = None

        def successful(self) -> bool:
            return False

        def failed(self) -> bool:
            return False

    result_module.AsyncResult = _AsyncResult
    sys.modules["celery.result"] = result_module


def import_backend_module(module_name: str):
    _ensure_backend_path()
    _stub_cv2()
    _stub_deepface()
    _stub_ultralytics()
    _stub_celery()
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)
