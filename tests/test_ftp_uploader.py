"""
Unit tests for multi-agency FTP/SFTP uploader and robust error handling.
"""

import unittest
from dashboard.ftp_uploader import format_connection_error, upload_files, test_connection


class TestFtpUploader(unittest.TestCase):
    def test_format_connection_error_adobe(self):
        adobe_host = "sftp.contributor.adobestock.com"
        fake_auth_error = Exception("Authentication failed.")
        msg = format_connection_error(adobe_host, fake_auth_error)
        self.assertIn("Authentication failed", msg)
        self.assertIn("Adobe Stock", msg)
        self.assertIn("dedicated SFTP password", msg)

    def test_format_connection_error_generic(self):
        generic_host = "ftp.pond5.com"
        fake_auth_error = Exception("Authentication failed.")
        msg = format_connection_error(generic_host, fake_auth_error)
        self.assertIn("Authentication failed", msg)
        self.assertIn("ftp.pond5.com", msg)

    def test_upload_files_empty(self):
        res = upload_files("sftp.contributor.adobestock.com", 22, "user", "pass", [], protocol="sftp")
        self.assertEqual(res["total"], 0)
        self.assertEqual(res["uploaded"], 0)
        self.assertIsNotNone(res.get("error"))

    def test_upload_files_connection_failure_no_crash(self):
        # Invalid host should gracefully return error dict without unhandled exceptions
        res = upload_files("invalid.host.local.example", 22, "user", "pass", ["nonexistent.jpg"], protocol="sftp")
        self.assertEqual(res["uploaded"], 0)
        self.assertIsNotNone(res.get("error"))
        self.assertEqual(len(res["failed"]), 1)

    def test_test_connection_invalid_credentials_no_crash(self):
        # Invalid credentials against real Adobe SFTP should return (False, msg) without throwing unhandled exceptions
        ok, msg = test_connection("sftp.contributor.adobestock.com", port=22, user="test_invalid", password="bad_password", protocol="sftp")
        self.assertFalse(ok)
        self.assertIn("Authentication failed", msg)
        self.assertIn("Adobe Stock", msg)

    def test_upload_single_image_to_stock_agency_missing_file(self):
        from dashboard.app import upload_single_image_to_stock_agency
        fake_img = {"id": 999, "file_path": "non_existent_file_xyz.jpg"}
        res = upload_single_image_to_stock_agency(fake_img, "Alamy")
        self.assertFalse(res["success"])
        self.assertIn("not found", res["message"].lower())


if __name__ == "__main__":
    unittest.main()
