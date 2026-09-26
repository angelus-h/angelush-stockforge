"""
ftp_uploader.py
Multi-agency FTP / FTPS / SFTP Uploader Module for Angelush StockForge.
Supports:
1. Standard FTP (e.g. Pond5, Dreamstime)
2. FTPS with TLS (e.g. Shutterstock)
3. SFTP via SSH (e.g. Adobe Stock, Vecteezy)
"""

import os
from pathlib import Path
from ftplib import FTP, FTP_TLS, error_perm

try:
    import paramiko
except ImportError:
    paramiko = None


def get_ftp_connection(host, port=21, user="", password="", use_tls=False, timeout=20):
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

    ftp.set_pasv(True)
    return ftp


def get_sftp_connection(host, port=22, user="", password="", timeout=20):
    """Establishes and returns a paramiko SFTP client and transport."""
    if not paramiko:
        raise RuntimeError("paramiko library is required for SFTP. Install via 'pip install paramiko'.")

    transport = paramiko.Transport((host, int(port)))
    transport.banner_timeout = timeout
    transport.connect(username=user, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    return sftp, transport


def ensure_ftp_remote_dir(ftp, remote_dir):
    """Navigates to or creates the remote directory path for FTP/FTPS."""
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


def ensure_sftp_remote_dir(sftp, remote_dir):
    """Navigates to or creates the remote directory path for SFTP."""
    if not remote_dir or remote_dir in [".", "/"]:
        return
    parts = [p for p in remote_dir.replace("\\", "/").split("/") if p]
    current = ""
    for part in parts:
        current += f"/{part}"
        try:
            sftp.chdir(current)
        except IOError:
            try:
                sftp.mkdir(current)
                sftp.chdir(current)
            except Exception as e:
                raise RuntimeError(f"Failed to create/navigate to SFTP dir '{current}': {e}")


def test_connection(host, port=21, user="", password="", protocol="ftp", remote_dir=""):
    """
    Tests connection to remote server (FTP, FTPS, or SFTP).
    Returns: (success: bool, message: str)
    """
    protocol = protocol.lower().strip()
    if protocol == "sftp":
        if not paramiko:
            return False, "paramiko is not installed for SFTP support."
        try:
            sftp, transport = get_sftp_connection(host, port=port or 22, user=user, password=password, timeout=12)
            try:
                if remote_dir:
                    ensure_sftp_remote_dir(sftp, remote_dir)
                listing = sftp.listdir(".")[:3]
                sftp.close()
                transport.close()
                return True, f"SFTP Connected successfully! Remote files in root: {len(listing)} item(s)."
            except Exception as e:
                sftp.close()
                transport.close()
                return True, f"SFTP Authenticated successfully! (Directory note: {e})"
        except Exception as e:
            return False, f"SFTP Connection failed: {e}"
    else:
        use_tls = (protocol == "ftps")
        try:
            ftp = get_ftp_connection(host, port=port or 21, user=user, password=password, use_tls=use_tls, timeout=12)
            welcome = ftp.getwelcome()
            if remote_dir:
                ensure_ftp_remote_dir(ftp, remote_dir)
            ftp.quit()
            return True, f"Connected successfully! Server response: {welcome[:120]}"
        except Exception as e:
            return False, f"Connection failed: {e}"


def upload_files(host, port, user, password, file_paths, protocol="ftp", remote_dir="", progress_callback=None):
    """
    Uploads a list of files to the remote server using FTP, FTPS, or SFTP.

    Args:
        host, port, user, password: login credentials
        file_paths: list of paths (str or Path)
        protocol: 'ftp', 'ftps', or 'sftp'
        remote_dir: remote folder (e.g. '/' or 'video')
        progress_callback: callable(index, total, filename, status_msg)

    Returns:
        dict: {"total": int, "uploaded": int, "failed": list of (path, error)}
    """
    protocol = protocol.lower().strip()
    results = {"total": len(file_paths), "uploaded": 0, "failed": []}
    if not file_paths:
        return results

    total = len(file_paths)

    if protocol == "sftp":
        # SFTP Upload via Paramiko
        sftp, transport = None, None
        try:
            sftp, transport = get_sftp_connection(host, port=port or 22, user=user, password=password)
            if remote_dir:
                ensure_sftp_remote_dir(sftp, remote_dir)

            for idx, fpath in enumerate(file_paths):
                path_obj = Path(fpath)
                if not path_obj.exists():
                    results["failed"].append((str(path_obj), "File not found"))
                    if progress_callback:
                        progress_callback(idx + 1, total, path_obj.name, "Not found")
                    continue

                try:
                    sftp.put(str(path_obj), path_obj.name)
                    results["uploaded"] += 1
                    if progress_callback:
                        progress_callback(idx + 1, total, path_obj.name, "Uploaded (SFTP)")
                except Exception as e:
                    results["failed"].append((str(path_obj), str(e)))
                    if progress_callback:
                        progress_callback(idx + 1, total, path_obj.name, f"Error: {e}")
        finally:
            if sftp:
                try:
                    sftp.close()
                except Exception:
                    pass
            if transport:
                try:
                    transport.close()
                except Exception:
                    pass

    else:
        # FTP / FTPS Upload via ftplib
        use_tls = (protocol == "ftps")
        ftp = None
        try:
            ftp = get_ftp_connection(host, port=port or 21, user=user, password=password, use_tls=use_tls)
            if remote_dir:
                ensure_ftp_remote_dir(ftp, remote_dir)

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
                        progress_callback(idx + 1, total, path_obj.name, f"Uploaded ({protocol.upper()})")
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


# Backward compatibility aliases
def test_ftp_connection(host, port=21, user="", password="", use_tls=False):
    return test_connection(host, port, user, password, protocol="ftps" if use_tls else "ftp")

def upload_images(host, port, user, password, file_paths, remote_dir="", use_tls=False, progress_callback=None):
    return upload_files(host, port, user, password, file_paths, protocol="ftps" if use_tls else "ftp", remote_dir=remote_dir, progress_callback=progress_callback)
