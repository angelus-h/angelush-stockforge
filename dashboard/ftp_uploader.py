"""
FTP / FTPS Uploader Module for Angelush StockForge.
Provides safe, background or progress-tracked uploads to remote POD/Stock FTP servers.
"""

import os
from pathlib import Path
from ftplib import FTP, FTP_TLS, error_perm


def get_ftp_connection(host, port=21, user="", password="", use_tls=False, timeout=15):
    """Establishes and returns an FTP or FTPS connection."""
    if use_tls:
        ftp = FTP_TLS(timeout=timeout)
    else:
        ftp = FTP(timeout=timeout)

    ftp.connect(host=host, port=int(port))
    if user:
        ftp.login(user=user, passwd=password)
    else:
        ftp.login()

    if use_tls:
        ftp.prot_p()  # Secure data connection

    return ftp


def test_ftp_connection(host, port=21, user="", password="", use_tls=False):
    """Tests FTP connection and returns (success: bool, message: str)."""
    try:
        ftp = get_ftp_connection(host, port, user, password, use_tls, timeout=10)
        welcome = ftp.getwelcome()
        ftp.quit()
        return True, f"Connected successfully! Server response: {welcome[:120]}"
    except Exception as e:
        return False, f"Connection failed: {e}"


def ensure_remote_dir(ftp, remote_dir):
    """Navigates to or creates the remote directory path."""
    if not remote_dir or remote_dir in [".", "/"]:
        return
    parts = [p for p in remote_dir.replace("\\", "/").split("/") if p]
    for part in parts:
        try:
            ftp.cwd(part)
        except error_perm:
            try:
                ftp.mkd(part)
                ftp.cwd(part)
            except Exception as e:
                raise RuntimeError(f"Failed to create/navigate to remote dir '{part}': {e}")


def upload_images(host, port, user, password, file_paths, remote_dir="", use_tls=False, progress_callback=None):
    """
    Uploads a list of files to the remote FTP server.
    
    Args:
        host, port, user, password: FTP credentials
        file_paths: list of local file paths (str or Path)
        remote_dir: remote folder path (e.g. 'incoming' or 'art_heroes')
        use_tls: whether to use FTPS
        progress_callback: callable(index, total, file_name, status)
    
    Returns:
        dict: {"total": int, "uploaded": int, "failed": list of (path, error)}
    """
    results = {"total": len(file_paths), "uploaded": 0, "failed": []}
    if not file_paths:
        return results

    ftp = None
    try:
        ftp = get_ftp_connection(host, port, user, password, use_tls=use_tls)
        if remote_dir:
            ensure_remote_dir(ftp, remote_dir)

        total = len(file_paths)
        for idx, fpath in enumerate(file_paths):
            path_obj = Path(fpath)
            if not path_obj.exists():
                results["failed"].append((str(path_obj), "File not found"))
                if progress_callback:
                    progress_callback(idx + 1, total, path_obj.name, "Not found")
                continue

            try:
                with open(path_obj, "rb") as fp:
                    ftp.storbinary(f"STOR {path_obj.name}", fp)
                results["uploaded"] += 1
                if progress_callback:
                    progress_callback(idx + 1, total, path_obj.name, "Uploaded")
            except Exception as e:
                results["failed"].append((str(path_obj), str(e)))
                if progress_callback:
                    progress_callback(idx + 1, total, path_obj.name, f"Error: {e}")

    finally:
        if ftp:
            try:
                ftp.quit()
            except Exception:
                ftp.close()

    return results
