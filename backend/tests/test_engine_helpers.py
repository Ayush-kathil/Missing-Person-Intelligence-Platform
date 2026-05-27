import unittest

import numpy as np

from test_support import import_backend_module

engine = import_backend_module("engine")


class EngineHelperTests(unittest.TestCase):
    def test_get_profile_config_uses_balanced_fallback(self):
        balanced = engine.get_profile_config("balanced")
        unknown = engine.get_profile_config("not-a-real-profile")
        self.assertEqual(unknown, balanced)

    def test_get_profile_config_applies_fast_profile(self):
        fast = engine.get_profile_config("fast")
        self.assertIn("match_threshold", fast)
        self.assertIn("yolo_confidence", fast)
        self.assertIn("confirm_frames", fast)

    def test_cosine_similarity_identical_vectors_is_one(self):
        vector = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        similarity = engine.cosine_similarity(vector, vector)
        self.assertAlmostEqual(similarity, 1.0, places=6)

    def test_cosine_similarity_handles_zero_vectors(self):
        zero = np.zeros(3, dtype=np.float32)
        other = np.array([4.0, 2.0, -1.0], dtype=np.float32)
        similarity = engine.cosine_similarity(zero, other)
        self.assertEqual(similarity, 0.0)

    def test_euclidean_distance_identical_vectors_is_zero(self):
        vector = np.array([0.5, 1.5, -2.0], dtype=np.float32)
        distance = engine.euclidean_distance(vector, vector)
        self.assertAlmostEqual(distance, 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
