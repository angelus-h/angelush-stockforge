"""
ftp_uploader.py
Multi-agency FTP / FTPS / SFTP Uploader Module for Angelush StockForge.
Supports:
1. Standard FTP (e.g. Pond5, Dreamstime)
2. FTPS with TLS (e.g. Shutterstock)
3. SFTP via SSH (e.g. Adobe Stock, Vecteezy)
"""

import os
import ssl
from pathlib import Path
from ftplib import FTP, FTP_TLS, error_perm

try:
    import paramiko
except ImportError:
    paramiko = None


def get_ftp_connection(host, port=21, user="", password="", use_tls=False, timeout=25, passive_mode=True):
    """Establishes and returns an FTP or FTPS connection with robust SSL context and passive mode."""
    if use_tls:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ftp = FTP_TLS(context=ctx, timeout=timeout)
    else:
        ftp = FTP(timeout=timeout)

    ftp.connect(host=host, port=int(port or 21))
    if user:
        ftp.login(user=user, passwd=password)
    else:
        ftp.login()

    if use_tls:
        ftp.prot_p()  # Secure data connection

    ftp.set_pasv(passive_mode)
    return ftp


def get_sftp_connection(host, port=22, user="", password="", timeout=25):
    """Establishes and returns a paramiko SFTP client and the underlying SSHClient."""
    if not paramiko:
        raise RuntimeError("The 'paramiko' package is not installed in the active Python environment. Install via: pip install paramiko")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        port=int(port or 22),
        username=user,
        password=password,
        timeout=timeout,
        look_for_keys=False,
        allow_agent=False
    )
    sftp = client.open_sftp()
    return sftp, client


def format_connection_error(host, exc):
    """Format exceptions into human-friendly error messages with agency-specific hints."""
    msg = str(exc)
    err_type = type(exc).__name__
    h_low = str(host).lower()
    
    if "Authentication failed" in msg or "AuthenticationException" in err_type:
        if "adobestock" in h_low:
            return "Authentication failed: Invalid Adobe Stock username or password. Note: Adobe Stock SFTP requires the dedicated SFTP password generated on the Contributor Portal (Upload → SFTP tab), NOT your personal Adobe account password."
        if "pond5" in h_low:
            return f"Pond5 Authentication failed: Invalid username ('AngelusH') or password for ftp.pond5.com."
        if "dreamstime" in h_low:
            return f"Dreamstime Authentication failed: Invalid Contributor ID ('61235210') or password for upload.dreamstime.com."
        return f"Authentication failed: Please check username and password for {host}."
    
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return f"Connection timed out connecting to {host}. Please verify internet connection and firewall settings."
    
    return f"{err_type}: {msg}"


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
            return False, "The 'paramiko' package is not installed in the active Python environment."
        client = None
        sftp = None
        try:
            sftp, client = get_sftp_connection(host, port=port or 22, user=user, password=password, timeout=12)
            try:
                if remote_dir and remote_dir not in [".", "/"]:
                    ensure_sftp_remote_dir(sftp, remote_dir)
                listing = sftp.listdir(".")[:3]
                return True, f"✅ SFTP Connected successfully to {host}:{port or 22} ({user})! Root accessible ({len(listing)} item(s))."
            except Exception as dir_err:
                return True, f"✅ SFTP Authentication successful ({user} @ {host})! (Directory note: {dir_err})"
        except Exception as e:
            return False, format_connection_error(host, e)
        finally:
            if sftp:
                try:
                    sftp.close()
                except Exception:
                    pass
            if client:
                try:
                    client.close()
                except Exception:
                    pass
    else:
        use_tls = (protocol == "ftps")
        ftp = None
        try:
            ftp = get_ftp_connection(host, port=port or 21, user=user, password=password, use_tls=use_tls, timeout=12)
            welcome = ftp.getwelcome()
            if remote_dir and remote_dir not in [".", "/"]:
                ensure_ftp_remote_dir(ftp, remote_dir)
            return True, f"✅ {protocol.upper()} Connected successfully! Server message: {welcome[:100]}"
        except Exception as e:
            return False, format_connection_error(host, e)
        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:
                    try:
                        ftp.close()
                    except Exception:
                        pass


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
        dict: {"total": int, "uploaded": int, "failed": list of (path, error), "error": str or None}
    """
    protocol = protocol.lower().strip()
    results = {"total": len(file_paths), "uploaded": 0, "failed": [], "error": None}
    if not file_paths:
        results["error"] = "No files provided for upload."
        return results

    total = len(file_paths)

    if protocol == "sftp":
        if not paramiko:
            err_msg = "The 'paramiko' library is missing from the environment (install via: pip install paramiko)."
            results["error"] = err_msg
            results["failed"] = [(str(p), err_msg) for p in file_paths]
            return results

        sftp, client = None, None
        try:
            sftp, client = get_sftp_connection(host, port=port or 22, user=user, password=password)
        except Exception as conn_err:
            err_msg = format_connection_error(host, conn_err)
            results["error"] = err_msg
            results["failed"] = [(str(p), err_msg) for p in file_paths]
            if progress_callback:
                progress_callback(0, total, "Connection", f"Error: {err_msg}")
            return results

        try:
            if remote_dir and remote_dir not in [".", "/"]:
                ensure_sftp_remote_dir(sftp, remote_dir)

            for idx, fpath in enumerate(file_paths):
                path_obj = Path(fpath)
                if not path_obj.exists():
                    results["failed"].append((str(path_obj), "File not found on disk"))
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
            if client:
                try:
                    client.close()
                except Exception:
                    pass

    else:
        use_tls = (protocol == "ftps")
        ftp = None
        try:
            ftp = get_ftp_connection(host, port=port or 21, user=user, password=password, use_tls=use_tls)
        except Exception as conn_err:
            err_msg = format_connection_error(host, conn_err)
            results["error"] = err_msg
            results["failed"] = [(str(p), err_msg) for p in file_paths]
            if progress_callback:
                progress_callback(0, total, "Connection", f"Error: {err_msg}")
            return results

        try:
            if remote_dir and remote_dir not in [".", "/"]:
                ensure_ftp_remote_dir(ftp, remote_dir)

            for idx, fpath in enumerate(file_paths):
                path_obj = Path(fpath)
                if not path_obj.exists():
                    results["failed"].append((str(path_obj), "File not found on disk"))
                    if progress_callback:
                        progress_callback(idx + 1, total, path_obj.name, "Not found")
                    continue

                try:
                    with open(path_obj, "rb") as fp:
                        ftp.storbinary(f"STOR {path_obj.name}", fp, blocksize=262144)
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
                    try:
                        ftp.close()
                    except Exception:
                        pass

    return results


# Backward compatibility aliases
def test_ftp_connection(host, port=21, user="", password="", use_tls=False):
    return test_connection(host, port, user, password, protocol="ftps" if use_tls else "ftp")

def upload_images(host, port, user, password, file_paths, remote_dir="", use_tls=False, progress_callback=None):
    return upload_files(host, port, user, password, file_paths, protocol="ftps" if use_tls else "ftp", remote_dir=remote_dir, progress_callback=progress_callback)
