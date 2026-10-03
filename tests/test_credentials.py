"""
Unit tests for automatic password persistence and credential management.
"""

import unittest
import os
from pathlib import Path
from dashboard import credentials


class TestCredentialsPersistence(unittest.TestCase):
    def setUp(self):
        self.test_key = "TEST_AGENCY_SECRET_KEY"
        self.test_val = "secret_pass_12345"

    def tearDown(self):
        credentials.delete_secret(self.test_key)

    def test_set_and_get_secret_persistence(self):
        # Save secret
        ok = credentials.set_secret(self.test_key, self.test_val)
        self.assertTrue(ok)

        # Retrieve secret
        loaded = credentials.get_secret(self.test_key)
        self.assertEqual(loaded, self.test_val)

        # Ensure env file fallback is updated
        env_vars = credentials._read_env_file()
        self.assertEqual(env_vars.get(self.test_key), self.test_val)

        # Delete secret
        credentials.delete_secret(self.test_key)
        loaded_after = credentials.get_secret(self.test_key, default="DEFAULT")
        self.assertEqual(loaded_after, "DEFAULT")


if __name__ == "__main__":
    unittest.main()
