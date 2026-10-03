"""
Angelush StockForge - Streamlit Studio Dashboard.
Unified management for Art Heroes & Displate Print-on-Demand publishing.
"""

import os
import sys
import importlib
from pathlib import Path

# Ensure root repo, dashboard, and stock-metadata directories are in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = Path(__file__).resolve().parent
STOCK_META_DIR = REPO_ROOT / "stock-metadata"

for p in [str(REPO_ROOT), str(DASHBOARD_DIR), str(STOCK_META_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st
import streamlit.components.v1 as components
import json
import io
from datetime import datetime
from PIL import Image

for _m in ["db", "dashboard.db", "llm_client", "dashboard.llm_client", "ftp_uploader", "dashboard.ftp_uploader", "credentials", "dashboard.credentials", "video_studio", "dashboard.video_studio", "stock_metadata", "dashboard.stock_metadata"]:
    if _m in sys.modules and sys.modules[_m] is not None:
        try:
            importlib.reload(sys.modules[_m])
        except Exception:
            pass

try:
    from dashboard import db, llm_client, ftp_uploader, credentials, video_studio, stock_metadata
except ImportError:
    import db, llm_client, ftp_uploader, credentials, video_studio, stock_metadata

from pod_workflow.ArtHeroes.apply_art_heroes_metadata import apply_metadata_to_image, find_exiftool
try:
    from pod_workflow.displate.displate_tool import analyze_displate_compliance, prepare_for_displate
except ImportError:
    analyze_displate_compliance, prepare_for_displate = None, None
from technical_quality_analyzer.config import QualityConfig
from technical_quality_analyzer.analyzer import TechnicalQualityAnalyzer
from technical_quality_analyzer.reporting.diagnostic import draw_diagnostics
from technical_quality_analyzer.models import Status


def render_clipboard_buttons(items_dict, key_prefix="clip"):
    """
    Renders HTML buttons that write directly to the OS clipboard via JS,
    providing visual feedback ('Copied!').
    items_dict: {"Copy Title": text1, "Copy Description": text2, ...}
    """
    buttons_html = """
    <div style="display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 8px 0;">
    """
    for label, val in items_dict.items():
        val_escaped = json.dumps(val or "")
        btn = f"""
        <button onclick='navigator.clipboard.writeText({val_escaped}).then(() => {{
            const orig = this.innerHTML;
            this.innerHTML = "✅ Copied!";
            this.style.background = "#1b4332";
            setTimeout(() => {{ this.innerHTML = orig; this.style.background = "#262730"; }}, 1800);
        }}).catch(err => {{
            alert("Clipboard error: " + err);
        }});' style="
            background: #262730;
            color: #FAFAFA;
            border: 1px solid #4B4B57;
            border-radius: 6px;
            padding: 7px 14px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            transition: all 0.2s ease;
        " onmouseover="this.style.background='#363842'" onmouseout="this.style.background='#262730'">
            📋 {label}
        </button>
        """
        buttons_html += btn
    buttons_html += "</div>"
    components.html(buttons_html, height=52)


FTP_CONFIG_PATH = Path(__file__).resolve().parent / "ftp_config.json"


def load_agency_config(agency_name):
    """Loads agency connection parameters, retrieving secrets securely from Windows Credential Manager / .env."""
    presets = credentials.AGENCY_PRESETS
    preset = presets.get(agency_name, {
        "protocol": "ftp",
        "host": "",
        "port": 21,
        "default_user": "",
        "remote_dir": "/",
        "cred_key": f"{agency_name.upper().replace(' ', '_')}_PASSWORD",
        "notes": ""
    })
    
    saved_all = {}
    if FTP_CONFIG_PATH.exists():
        try:
            with open(FTP_CONFIG_PATH, "r", encoding="utf-8") as f:
                saved_all = json.load(f)
        except Exception:
            saved_all = {}

    saved = saved_all.get(agency_name, {})
    host = (saved.get("host") or "").strip() or preset.get("host", "")
    port = int(saved.get("port") or preset.get("port", 21 if preset.get("protocol") != "sftp" else 22))
    protocol = (saved.get("protocol") or "").strip() or preset.get("protocol", "ftp")
    user = (saved.get("user") or "").strip() or preset.get("default_user", "")
    remote_dir = (saved.get("remote_dir") or "").strip() or preset.get("remote_dir", "/")
    if agency_name == "Alamy" and remote_dir in ["", "/"]:
        remote_dir = "Stock"
    
    # Retrieve password securely from Windows Credential Manager or .env
    cred_key = preset.get("cred_key", f"{agency_name.upper().replace(' ', '_')}_PASSWORD")
    password = credentials.get_secret(cred_key, default=saved.get("password", ""))

    return {
        "agency": agency_name,
        "protocol": protocol,
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "remote_dir": remote_dir,
        "cred_key": cred_key,
        "notes": preset.get("notes", "")
    }


def save_agency_config(agency_name, cfg, save_password_to_keyring=True):
    """Saves agency configuration, storing passwords securely in Windows Credential Manager."""
    saved_all = {}
    if FTP_CONFIG_PATH.exists():
        try:
            with open(FTP_CONFIG_PATH, "r", encoding="utf-8") as f:
                saved_all = json.load(f)
        except Exception:
            saved_all = {}
            
    to_save = {
        "host": cfg.get("host", ""),
        "port": int(cfg.get("port", 21)),
        "protocol": cfg.get("protocol", "ftp"),
        "user": cfg.get("user", ""),
        "remote_dir": cfg.get("remote_dir", "/")
    }
    saved_all[agency_name] = to_save
    try:
        with open(FTP_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(saved_all, f, indent=2)
    except Exception:
        pass
        
    if save_password_to_keyring and cfg.get("password"):
        cred_key = cfg.get("cred_key") or f"{agency_name.upper().replace(' ', '_')}_PASSWORD"
        credentials.set_secret(cred_key, cfg["password"])


def load_ftp_config():
    return load_agency_config("Pond5")


def save_ftp_config(cfg):
    save_agency_config("Pond5", cfg)
    return True


def upload_single_image_to_stock_agency(img_item, agency_name, override_user=None, override_pass=None):
    """
    Uploads a single image to the specified stock agency, ensuring IPTC/XMP metadata
    is embedded and necessary sidecar CSV is generated.
    Returns: dict with {"success": bool, "agency": str, "message": str}
    """
    cfg = load_agency_config(agency_name)
    user = (override_user if override_user is not None else cfg.get("user", "")).strip()
    password = override_pass if override_pass is not None else cfg.get("password", "")

    if not cfg.get("host") or not user or not password:
        return {"success": False, "agency": agency_name, "message": f"Missing host, user, or password for {agency_name}."}

    img_path = Path(img_item["file_path"])
    if not img_path.exists():
        return {"success": False, "agency": agency_name, "message": f"Image file not found: {img_path.name}"}

    # Embed IPTC/XMP into image
    # Note: Adobe Stock uses Posters.cz Hybrid metadata when available and enabled.
    # ALL OTHER AGENCIES (especially Alamy which reads directly from image IPTC/XMP headers)
    # strictly receive pure Microstock metadata.
    is_adobe = agency_name in ("Adobe Stock", "AdobeStock", "Adobe")
    is_hybrid = bool(img_item.get("is_adobe_hybrid", 0))

    if is_adobe and is_hybrid and (img_item.get("adobe_title") or img_item.get("adobe_keywords") or img_item.get("adobe_description")):
        embed_t = (img_item.get("adobe_title") or img_item.get("stock_title") or img_item.get("title") or "").strip()
        embed_d = (img_item.get("adobe_description") or img_item.get("stock_description") or img_item.get("description") or embed_t).strip()
        embed_k = (img_item.get("adobe_keywords") or img_item.get("stock_keywords") or img_item.get("keywords") or "").strip()
    else:
        embed_t = (img_item.get("stock_title") or img_item.get("title") or "").strip()
        embed_d = (img_item.get("stock_description") or img_item.get("description") or embed_t).strip()
        embed_k = (img_item.get("stock_keywords") or img_item.get("keywords") or "").strip()

    try:
        exiftool_exe = stock_metadata.find_exiftool()
        stock_metadata.apply_stock_metadata_to_image(
            image_path=img_path,
            title=embed_t,
            description=embed_d,
            keywords=embed_k,
            exiftool_path=exiftool_exe
        )
    except Exception as em_err:
        pass  # Non-fatal warning

    # Sidecar CSV if required
    files_to_send = [str(img_path)]
    if agency_name in stock_metadata.AGENCY_CSV_FILENAMES:
        parent_dir = img_path.parent
        gen_csv = stock_metadata.generate_agency_csv([img_item], agency_name, parent_dir)
        if str(gen_csv) not in files_to_send:
            files_to_send.append(str(gen_csv))

    try:
        res = ftp_uploader.upload_files(
            cfg["host"],
            port=cfg["port"],
            user=user,
            password=password,
            file_paths=files_to_send,
            protocol=cfg["protocol"],
            remote_dir=cfg["remote_dir"]
        )
        if res["uploaded"] > 0:
            return {"success": True, "agency": agency_name, "message": f"Uploaded {len(files_to_send)} file(s) successfully"}
        err = res.get("error") or (res["failed"][0][1] if res["failed"] else "Upload failed")
        return {"success": False, "agency": agency_name, "message": err}
    except Exception as e:
        return {"success": False, "agency": agency_name, "message": str(e)}


@st.cache_data(max_entries=2000)
def get_thumbnail_bytes(image_path: str, max_dim: int = 240) -> bytes:
    """Generate and cache thumbnail bytes for fast UI rendering, supporting JPG, PNG, and RAW/DNG/ORF."""
    try:
        from dashboard import raw_loader
        tb = raw_loader.get_thumbnail_bytes(image_path, max_dim=max_dim)
        if tb:
            return tb
    except Exception:
        pass
    try:
        with Image.open(image_path) as img:
            if getattr(img, "format", None) == "JPEG":
                img.draft("RGB", (max_dim, max_dim))
            if img.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = bg
            else:
                img = img.convert("RGB")
            img.thumbnail((max_dim, max_dim), Image.Resampling.BILINEAR)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75)
            return buf.getvalue()
    except Exception:
        return b""


@st.cache_data(max_entries=500)
def get_image_histogram_cached(file_path: str):
    """Generate and cache photographic RGB + Luminance histogram and clipping statistics."""
    import dashboard.raw_loader as raw_loader
    importlib.reload(raw_loader)
    hist_bytes, stats, df = raw_loader.generate_histogram(file_path)
    if not hist_bytes:
        raise ValueError("Empty histogram generated.")
    return hist_bytes, stats, df


def pick_folder_native(initial_dir=""):
    """Opens native Windows folder selection dialog using Tkinter with PowerShell fallback."""
    picked = None
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', 1)
        res = filedialog.askdirectory(
            initialdir=initial_dir if initial_dir and os.path.isdir(initial_dir) else None,
            title="Select StockForge Image Folder"
        )
        root.destroy()
        if res:
            picked = res
    except Exception:
        pass

    if not picked:
        try:
            import subprocess
            ps_script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                "$f.Description = 'Select StockForge Working Folder'; "
                "$f.ShowNewFolderButton = $true; "
                f"$f.SelectedPath = '{initial_dir}'; " if (initial_dir and os.path.isdir(initial_dir)) else ""
                "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.SelectedPath }"
            )
            ps_res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=60
            )
            chosen = ps_res.stdout.strip()
            if chosen and os.path.isdir(chosen):
                picked = chosen
        except Exception:
            pass

    return os.path.normpath(picked) if picked else None


def get_available_drives():
    """List available system drive letters."""
    import string
    return [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]


def get_subfolders(folder_path):
    """Safely return list of subdirectories in folder_path."""
    try:
        p = Path(folder_path)
        if p.exists() and p.is_dir():
            return sorted([
                f.name for f in p.iterdir()
                if f.is_dir() and not f.name.startswith(".") and not f.name.startswith("$")
            ])
    except Exception:
        pass
    return []


def count_folder_images(folder_path):
    """Count supported image and RAW files (JPG, PNG, DNG, ORF, RAW) in the specified folder."""
    try:
        p = Path(folder_path)
        if p.exists() and p.is_dir():
            return sum(1 for f in p.iterdir() if f.is_file() and f.suffix.lower() in db.SUPPORTED_IMAGE_EXTENSIONS)
    except Exception:
        pass
    return 0


def main():
    st.set_page_config(
        page_title="Angelush StockForge Studio",
        page_icon="📸",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("📸 Angelush StockForge Studio")
    st.caption("Print-on-Demand (Art Heroes & Displate) Automated Metadata & Catalog Management")

    # --- SIDEBAR CONTROLS ---
    with st.sidebar:
        st.header("🎯 Studio Workflow")
        studio_mode = st.radio(
            "Select Active Studio",
            ["📸 Photo & Fine Art Studio", "🎬 Stock Video Studio"],
            index=0,
            key="global_studio_mode"
        )
        st.divider()

        st.header("⚙️ AI Engine Setup")
        
        engine_choice = st.selectbox(
            "AI Engine",
            ["Google Gemini Cloud (~$0.002/img)", "Local Ollama (100% Free - $0.00)"],
            index=0
        )

        active_api_key = ""
        if "Gemini" in engine_choice:
            env_key = os.environ.get("GEMINI_API_KEY", "")
            api_key_input = st.text_input("Gemini API Key", value=env_key, type="password")
            active_api_key = api_key_input.strip() or env_key
        else:
            st.success("💻 Running offline via local Ollama models (llava + llama3.2).")

        if studio_mode == "📸 Photo & Fine Art Studio":
            st.divider()
            st.header("📁 Working Directory")

            default_folder = r"G:\upload_temp\Art-Heroes_temp"
            if "active_folder" not in st.session_state:
                st.session_state["active_folder"] = default_folder if Path(default_folder).exists() else str(Path.home())

            current_folder = st.session_state["active_folder"]
            img_count = count_folder_images(current_folder)

            st.caption("Active Location:")
            st.code(current_folder, language="text")
            st.caption(f"📸 **{img_count} images (JPG, PNG)** found in folder")

            # 1. Native Windows Explorer Browse & Parent Directory buttons
            col_browse, col_up = st.columns([2.5, 1])
            if col_browse.button("📂 Browse Folder...", use_container_width=True, help="Open native Windows Explorer folder selection dialog"):
                picked = pick_folder_native(current_folder)
                if picked:
                    st.session_state["active_folder"] = picked
                    st.rerun()

            parent_dir = Path(current_folder).parent
            if str(parent_dir) != current_folder:
                if col_up.button("⬆️ Up", use_container_width=True, help=f"Go up to {parent_dir.name or str(parent_dir)}"):
                    st.session_state["active_folder"] = str(parent_dir)
                    st.rerun()

            # 2. Subfolder Navigator Dropdown
            subdirs = get_subfolders(current_folder)
            if subdirs:
                chosen_sub = st.selectbox(
                    "📁 Enter Subfolder",
                    ["(Select subfolder...)"] + subdirs,
                    key=f"subnav_{current_folder}"
                )
                if chosen_sub != "(Select subfolder...)":
                    st.session_state["active_folder"] = str((Path(current_folder) / chosen_sub).resolve())
                    st.rerun()

            # 3. Recent Folders History Dropdown
            known_dirs = db.get_known_folders()
            if known_dirs:
                other_known = [d for d in known_dirs if os.path.normpath(d) != os.path.normpath(current_folder)]
                if other_known:
                    chosen_recent = st.selectbox(
                        "🕒 Recent Folders",
                        ["(Select from history...)"] + other_known,
                        key="recent_folders_history"
                    )
                    if chosen_recent != "(Select from history...)":
                        st.session_state["active_folder"] = chosen_recent
                        st.rerun()

            # 4. Quick Drive Switcher
            drives = get_available_drives()
            current_drive = os.path.splitdrive(current_folder)[0].upper() + "\\"
            other_drives = [d for d in drives if d.upper() != current_drive]
            if other_drives:
                chosen_drive = st.selectbox(
                    "💾 Switch Drive",
                    ["(Current: " + current_drive + ")"] + other_drives,
                    key="drive_switcher"
                )
                if not chosen_drive.startswith("(Current:"):
                    st.session_state["active_folder"] = chosen_drive
                    st.rerun()

            # 5. Optional manual override expander
            with st.expander("✏️ Type / Paste Custom Path", expanded=False):
                manual_input = st.text_input("Custom Path", value=current_folder, key="manual_path_override")
                if st.button("Apply Path", use_container_width=True, key="apply_manual_btn"):
                    if manual_input and Path(manual_input).is_dir():
                        st.session_state["active_folder"] = os.path.normpath(manual_input)
                        st.rerun()
                    else:
                        st.error("Directory not found!")

            folder_path = st.session_state["active_folder"]
            scope_to_folder = st.checkbox("🎯 Scope catalog & batch actions to this folder", value=True)

            platform = st.selectbox("Catalog Target", ["ArtHeroes", "Displate", "ALL"], index=0)

            scan_col1, scan_col2 = st.columns([1.6, 1.2])
            if scan_col1.button("🔄 Scan & Import", use_container_width=True, type="primary"):
                try:
                    stats = db.scan_and_sync_folder(folder_path, platform=platform if platform != "ALL" else "ArtHeroes")
                    st.success(f"Scanned {stats['scanned']} files (Imported: {stats['imported']}, Updated: {stats['updated']})")
                    st.rerun()
                except Exception as e:
                    st.error(f"Scan failed: {e}")

            if scan_col2.button("🔃 Reload View", use_container_width=True, help="Clear cache and reload all items"):
                st.cache_data.clear()
                st.rerun()

            st.divider()
            st.subheader("📷 Series Context & Location")
            st.caption("Optional guidance about equipment, technique, or location for this folder:")
            folder_context = st.text_area(
                "Folder Context",
                value="",
                placeholder="e.g. Fine art 720nm infrared, Pentax K-r, Lednice-Valtice...",
                height=80,
                help="Optional. If provided, this context is automatically included when generating titles and descriptions."
            )

            st.divider()
            st.subheader("🔍 Filters")
            status_filter = st.selectbox("Metadata Status", ["ALL", "NEW", "GENERATED", "APPLIED"])
            qc_filter = st.selectbox("QC Preflight Filter", ["ALL", "UNCHECKED", "PASS", "REVIEW", "HIGH_RISK"])
            grade_filter = st.selectbox(
                "Grade Filter",
                ["ALL", "FINE_ART", "STOCK", "BOTH", "UNASSIGNED"],
                format_func=lambda x: {
                    "ALL": "ALL Grades",
                    "FINE_ART": "🎨 Fine Art (incl. Dual)",
                    "STOCK": "📸 Stock (incl. Dual)",
                    "BOTH": "🎨📸 Dual Grade Only",
                    "UNASSIGNED": "⚪ Unassigned Only"
                }[x]
            )
            uploaded_filter = st.selectbox(
                "Upload Status Filter",
                [
                    "ALL", "NOT_UPLOADED", "ANY_UPLOADED",
                    "Adobe Stock", "Vecteezy", "Shutterstock", "Alamy",
                    "Art Heroes", "Displate", "Pond5", "Dreamstime", "Depositphotos", "Fine Art America"
                ],
                format_func=lambda x: {
                    "ALL": "ALL Upload States",
                    "NOT_UPLOADED": "⚪ Not uploaded anywhere",
                    "ANY_UPLOADED": "🟢 Uploaded to at least one",
                    "Adobe Stock": "🟢 Uploaded: Adobe Stock",
                    "Vecteezy": "🟢 Uploaded: Vecteezy",
                    "Shutterstock": "🟢 Uploaded: Shutterstock",
                    "Alamy": "🟢 Uploaded: Alamy",
                    "Art Heroes": "🟢 Uploaded: Art Heroes",
                    "Displate": "🟢 Uploaded: Displate",
                    "Pond5": "🟢 Uploaded: Pond5",
                    "Dreamstime": "🟢 Uploaded: Dreamstime",
                    "Depositphotos": "🟢 Uploaded: Depositphotos",
                    "Fine Art America": "🟢 Uploaded: Fine Art America"
                }.get(x, x)
            )
            search_query = st.text_input("Search (Filename / Tag)", "")

            st.divider()
            st.subheader("📤 Export Metadata")
            export_target = st.selectbox("Export Platform", ["Adobe Stock", "Alamy", "Depositphotos", "Vecteezy", "Pond5", "Dreamstime", "Shutterstock", "ArtHeroes", "Displate"])
            if st.button(f"📊 Export {export_target} CSV", use_container_width=True):
                target_slug = export_target.lower().replace(" ", "_")
                csv_out = Path(folder_path) / f"stockforge_{target_slug}_export.csv"
                saved_path = db.export_catalog_csv(
                    csv_out,
                    platform=export_target,
                    folder_path=folder_path if scope_to_folder and folder_path else None
                )
                st.success(f"Saved: {saved_path}")

        st.divider()
        with st.expander("🚀 Agency FTP / SFTP Uploader Hub", expanded=False):
            agency_list = ["Adobe Stock", "Alamy", "Depositphotos", "Vecteezy", "Shutterstock", "Pond5", "Dreamstime", "Custom FTP / SFTP"]
            chosen_agency = st.selectbox("Target Agency Profile", agency_list, index=0, key="sb_agency_profile")
            
            cfg = load_agency_config(chosen_agency)
            
            proto_col, port_col = st.columns([1.5, 1])
            proto_options = ["sftp", "ftps", "ftp"]
            curr_proto_idx = proto_options.index(cfg["protocol"]) if cfg["protocol"] in proto_options else 0
            u_proto = proto_col.selectbox("Protocol", proto_options, index=curr_proto_idx, key=f"proto_{chosen_agency}")
            u_port = port_col.number_input("Port", value=int(cfg["port"]), min_value=1, max_value=65535, key=f"port_{chosen_agency}")
            
            u_host = st.text_input("Server Host", value=cfg["host"], placeholder="sftp.contributor.adobestock.com", key=f"host_{chosen_agency}")
            u_user = st.text_input("Username / ID", value=cfg["user"], placeholder="208758992", key=f"user_{chosen_agency}")
            u_remote_dir = st.text_input("Remote Path", value=cfg.get("remote_dir", "/"), placeholder="/", key=f"rdir_{chosen_agency}")
            
            pass_stored = bool(cfg["password"])
            pass_help = f"🔒 Retrieved securely from Windows Credential Manager ({cfg['cred_key']})" if pass_stored else "Enter password to save securely to Windows Credential Manager"
            u_pass = st.text_input("Password", value=cfg["password"], type="password", help=pass_help, key=f"pass_{chosen_agency}")
            
            host_changed = (u_host.strip() != (cfg.get("host") or "").strip())
            user_changed = (u_user.strip() != (cfg.get("user") or "").strip())
            proto_changed = (u_proto != cfg.get("protocol"))
            port_changed = (int(u_port) != int(cfg.get("port") or 21))
            pass_changed = bool(u_pass and u_pass != cfg.get("password"))
            if host_changed or user_changed or proto_changed or port_changed or pass_changed:
                save_agency_config(chosen_agency, {
                    "host": u_host.strip(),
                    "port": int(u_port),
                    "protocol": u_proto,
                    "user": u_user.strip(),
                    "password": u_pass if u_pass else cfg.get("password", ""),
                    "remote_dir": (u_remote_dir or "/").strip(),
                    "cred_key": cfg["cred_key"]
                }, save_password_to_keyring=pass_changed)
                cfg["host"] = u_host.strip()
                cfg["user"] = u_user.strip()
                cfg["protocol"] = u_proto
                cfg["port"] = int(u_port)
                if u_pass:
                    cfg["password"] = u_pass
            
            has_csv = chosen_agency in stock_metadata.AGENCY_CSV_FILENAMES
            if has_csv:
                target_csv_file = stock_metadata.AGENCY_CSV_FILENAMES[chosen_agency]
                auto_csv = st.checkbox(f"Auto-generate & upload {target_csv_file}", value=True, key=f"auto_csv_{chosen_agency}")
            else:
                auto_csv = False
            auto_embed_stock = st.checkbox("Auto-embed Stock IPTC/XMP into image files", value=True, key=f"auto_embed_{chosen_agency}", help="Directly embeds Title and 30-45 Keywords into JPEG headers via ExifTool before upload (vital for Alamy and agency parsers).")
                
            test_col, save_col = st.columns(2)
            if test_col.button("🔌 Test Connection", key=f"test_{chosen_agency}", use_container_width=True):
                if not u_host or not u_user:
                    st.warning("Please provide host and username.")
                else:
                    if u_pass and u_pass != cfg["password"]:
                        save_agency_config(chosen_agency, {
                            "host": u_host.strip(),
                            "port": int(u_port),
                            "protocol": u_proto,
                            "user": u_user.strip(),
                            "password": u_pass,
                            "remote_dir": u_remote_dir.strip(),
                            "cred_key": cfg["cred_key"]
                        }, save_password_to_keyring=True)
                    with st.spinner(f"Testing {u_proto.upper()} connection to {u_host}..."):
                        ok, msg = ftp_uploader.test_connection(
                            u_host, port=u_port, user=u_user, password=u_pass,
                            protocol=u_proto, remote_dir=u_remote_dir
                        )
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                            
            if save_col.button("🔒 Save to Windows", key=f"save_{chosen_agency}", use_container_width=True):
                save_agency_config(chosen_agency, {
                    "host": u_host.strip(),
                    "port": int(u_port),
                    "protocol": u_proto,
                    "user": u_user.strip(),
                    "password": u_pass,
                    "remote_dir": u_remote_dir.strip(),
                    "cred_key": cfg["cred_key"]
                }, save_password_to_keyring=True)
                st.success("Credentials saved securely to Windows Credential Manager!")

            st.caption(f"Profile: **{chosen_agency}** ({cfg.get('notes', '')})")
            
            upload_scope = st.radio(
                "Upload Scope",
                ["All Images in View", "Only APPLIED / Generated", "Selected Single Image"],
                index=0,
                key=f"scope_{chosen_agency}"
            )
            
            if st.button(f"⬆️ Upload to {chosen_agency}", type="primary", use_container_width=True, key=f"btn_up_{chosen_agency}"):
                if not u_host or not u_user or not u_pass:
                    st.error("Please ensure host, username, and password are provided.")
                else:
                    current_view_imgs = db.get_images(
                        platform=platform,
                        status=status_filter,
                        search_query=search_query,
                        folder_path=folder_path if scope_to_folder and folder_path else None,
                        grade=grade_filter if grade_filter != "ALL" else None
                    )
                    if "Only APPLIED" in upload_scope:
                        target_imgs = [i for i in current_view_imgs if i["status"] in ("APPLIED", "GENERATED")]
                    elif "Selected Single" in upload_scope:
                        target_imgs = [i for i in current_view_imgs if i["id"] == st.session_state.get("selected_img_id")]
                    else:
                        target_imgs = current_view_imgs

                    if not target_imgs:
                        st.warning("No images matching the selected upload scope.")
                    else:
                        upload_list = [i["file_path"] for i in target_imgs]
                        
                        # 1. Embed Stock IPTC/XMP into image files before upload
                        if auto_embed_stock:
                            try:
                                exif_tool_path = stock_metadata.find_exiftool()
                                for t_img in target_imgs:
                                    stock_metadata.apply_stock_metadata_to_image(
                                        image_path=Path(t_img["file_path"]),
                                        title=t_img.get("stock_title") or t_img.get("title") or "",
                                        description=t_img.get("stock_description") or t_img.get("description") or t_img.get("stock_title") or "",
                                        keywords=t_img.get("stock_keywords") or t_img.get("keywords") or "",
                                        exiftool_path=exif_tool_path
                                    )
                            except Exception as em_err:
                                st.warning(f"Stock IPTC embedding note: {em_err}")

                        # 2. Auto-generate and attach platform CSV
                        if auto_csv and target_imgs:
                            parent_dir = Path(target_imgs[0]["file_path"]).parent
                            gen_csv = stock_metadata.generate_agency_csv(target_imgs, chosen_agency, parent_dir)
                            if str(gen_csv) not in upload_list:
                                upload_list.append(str(gen_csv))

                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        def upload_cb(idx, total, fname, status):
                            progress_bar.progress(idx / total)
                            status_text.text(f"[{idx}/{total}] {fname}: {status}")

                        with st.spinner(f"Uploading {len(upload_list)} files to {chosen_agency}..."):
                            try:
                                res = ftp_uploader.upload_files(
                                    u_host, port=u_port, user=u_user, password=u_pass,
                                    file_paths=upload_list, protocol=u_proto, remote_dir=u_remote_dir,
                                    progress_callback=upload_cb
                                )
                                if res["uploaded"] > 0:
                                    st.success(f"🎉 Successfully uploaded {res['uploaded']}/{res['total']} files to {chosen_agency}!")
                                    st.toast(f"✅ {res['uploaded']} file(s) uploaded to {chosen_agency}!", icon="🚀")
                                    # Update database for successfully uploaded images
                                    for t_img in target_imgs:
                                        if any(res_failed_path == t_img["file_path"] for res_failed_path, _ in res.get("failed", [])):
                                            continue
                                        latest_upl = [p.strip() for p in (t_img.get("uploaded_to") or "").split(",") if p.strip()]
                                        if chosen_agency not in latest_upl:
                                            latest_upl.append(chosen_agency)
                                            db.update_image(t_img["id"], uploaded_to=", ".join(latest_upl))
                                            st.session_state[f"upl_tracker_ver_{t_img['id']}"] = st.session_state.get(f"upl_tracker_ver_{t_img['id']}", 0) + 1
                                    st.rerun()
                                if res.get("error"):
                                    st.error(f"❌ Connection error: {res['error']}")
                                    st.toast(f"❌ Connection error: {chosen_agency}", icon="⚠️")
                                if res["failed"]:
                                    st.error(f"Failed ({len(res['failed'])}): " + ", ".join([f"{Path(f).name}: {err}" for f, err in res["failed"][:3]]))
                                    st.toast(f"⚠️ {len(res['failed'])} file(s) failed!", icon="⚠️")
                            except Exception as up_err:
                                st.error(f"❌ Unexpected upload error: {up_err}")
                                st.toast("❌ Unexpected error", icon="⚠️")

    if studio_mode == "🎬 Stock Video Studio":
        video_studio.render_video_studio(active_api_key=active_api_key)
        return

    # Fetch Images with folder scope, grade, and QC filter if enabled
    images = db.get_images(
        platform=platform,
        status=status_filter,
        search_query=search_query,
        folder_path=folder_path if scope_to_folder and folder_path else None,
        qc_status=qc_filter if qc_filter != "ALL" else None,
        grade=grade_filter if grade_filter != "ALL" else None,
        uploaded_filter=uploaded_filter if uploaded_filter != "ALL" else None
    )

    # Top Metric Bar
    all_images = db.get_images(
        platform="ALL",
        folder_path=folder_path if scope_to_folder and folder_path else None
    )
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total in Scope", len(all_images))
    col2.metric("🎨 Fine Art", len([i for i in all_images if i.get("grade") == "FINE_ART"]))
    col3.metric("📸 Stock", len([i for i in all_images if i.get("grade") == "STOCK"]))
    col4.metric("🎨📸 Dual Grade", len([i for i in all_images if i.get("grade") == "BOTH"]))
    col5.metric("⚪ Unassigned", len([i for i in all_images if not i.get("grade") or i.get("grade") == "NONE"]))
    col6.metric("🔵 Metadata Ready", len([i for i in all_images if i.get("status") in ("GENERATED", "APPLIED")]))

    st.divider()

    if not images:
        st.info("No images found matching criteria. Scan a folder from the sidebar to populate.")
        return

    # Two-column layout: List on the left, Inspector on the right
    list_col, detail_col = st.columns([1.1, 1.9], gap="large")

    with list_col:
        st.subheader(f"🖼️ Images ({len(images)})")

        # 1. Batch Grade Classifier Expander
        with st.expander(f"🏷️ Batch Grade Classifier ({len(images)} items)", expanded=False):
            st.caption("Quickly assign grade to all currently filtered images in view:")
            bg_col1, bg_col2 = st.columns([1.8, 1.2])
            batch_grade_val = bg_col1.radio(
                "Target Grade:",
                ["FINE_ART", "STOCK", "BOTH", "NONE"],
                format_func=lambda x: {"FINE_ART": "🎨 Fine Art", "STOCK": "📸 Stock", "BOTH": "🎨📸 Dual (Both)", "NONE": "⚪ Unassigned"}[x],
                horizontal=True,
                key="batch_grade_radio"
            )
            if bg_col2.button("Apply to All in View", use_container_width=True):
                for img in images:
                    db.update_image(img["id"], grade=batch_grade_val)
                st.success(f"Updated all {len(images)} images to {batch_grade_val}!")
                st.rerun()

        # 2. Batch Generate button for filtered list (SKIPS UNASSIGNED / NONE)
        new_items = [img for img in images if img["status"] == "NEW"]
        if new_items:
            eligible_items = [img for img in new_items if img.get("grade") in ("FINE_ART", "STOCK", "BOTH")]
            unassigned_count = len(new_items) - len(eligible_items)
            st.caption(f"**{len(eligible_items)} of {len(new_items)} new images eligible for AI**")
            if unassigned_count > 0:
                st.caption(f"ℹ️ {unassigned_count} unassigned images will be skipped by AI (no grade set).")

            batch_target = st.selectbox(
                "Batch Target Platform",
                ["All", "Both", "Stock", "ArtHeroes", "Displate"],
                format_func=lambda x: {
                    "All": "✨ All (Art Heroes + Displate + Stock)",
                    "Both": "🎨🏆 Both POD (Art Heroes + Displate)",
                    "Stock": "📸 Stock Only (Vecteezy, Adobe, Alamy)",
                    "ArtHeroes": "🎨 Art Heroes Only",
                    "Displate": "🏆 Displate Only"
                }[x],
                key="batch_target_select"
            )
            batch_hybrid = st.checkbox(
                "🖼️ Adobe Stock / Posters.cz Hybrid Mode for Batch",
                value=False,
                key="batch_hybrid_check",
                help="Applies hybrid stock + interior design copywriting to stock metadata across the batch for https://www.posters.cz/."
            )
            if st.button(f"✨ Batch Generate ({len(eligible_items)} items)", type="primary", use_container_width=True):
                if not eligible_items:
                    st.warning("⚠️ No images with 'Fine Art' or 'Stock' grade selected. Please assign a grade to images before running batch generation.")
                elif "Gemini" in engine_choice and not active_api_key:
                    st.error("Please provide a Gemini API Key in the sidebar.")
                else:
                    progress_bar = st.progress(0)
                    for idx, item in enumerate(eligible_items):
                        try:
                            item_custom = item.get("custom_prompt") or ""
                            full_batch_ctx = f"{folder_context}\n{item_custom}".strip()
                            item_hybrid = batch_hybrid or bool(item.get("is_adobe_hybrid")) or llm_client.is_hybrid_requested(full_batch_ctx)
                            meta = llm_client.generate_metadata(
                                item["file_path"],
                                target=batch_target,
                                engine=engine_choice,
                                api_key=active_api_key,
                                user_context=full_batch_ctx,
                                is_editorial=bool(item.get("is_editorial")),
                                is_ai_generated=bool(item.get("is_ai_generated")),
                                is_infrared=bool(item.get("is_infrared")),
                                is_surreal=bool(item.get("is_surreal")),
                                is_adobe_hybrid=item_hybrid
                            )
                            update_kwargs = {"status": "GENERATED"}
                            if item_hybrid:
                                update_kwargs["is_adobe_hybrid"] = 1
                            if "artheroes" in meta:
                                ah = meta["artheroes"]
                                update_kwargs["title"] = ah.get("title")
                                update_kwargs["description"] = ah.get("description")
                                update_kwargs["keywords"] = ", ".join(ah.get("keywords", [])) if isinstance(ah.get("keywords"), list) else ah.get("keywords", "")
                            if "displate" in meta:
                                disp = meta["displate"]
                                update_kwargs["displate_title"] = disp.get("title")
                                update_kwargs["displate_description"] = disp.get("description")
                                update_kwargs["displate_tags"] = ", ".join(disp.get("tags", [])) if isinstance(disp.get("tags"), list) else disp.get("tags", "")
                            if "stock" in meta:
                                stk = meta["stock"]
                                update_kwargs["stock_title"] = stk.get("title")
                                update_kwargs["stock_description"] = stk.get("description")
                                update_kwargs["stock_keywords"] = ", ".join(stk.get("keywords", [])) if isinstance(stk.get("keywords"), list) else stk.get("keywords", "")
                                update_kwargs["stock_category"] = stk.get("category", "Travel")
                            if "adobe" in meta:
                                adb = meta["adobe"]
                                update_kwargs["adobe_title"] = adb.get("title")
                                update_kwargs["adobe_description"] = adb.get("description")
                                update_kwargs["adobe_keywords"] = ", ".join(adb.get("keywords", [])) if isinstance(adb.get("keywords"), list) else adb.get("keywords", "")
                                update_kwargs["adobe_category"] = adb.get("category", "Travel")

                            db.update_image(item["id"], **update_kwargs)
                        except Exception as err:
                            st.warning(f"Error on {item['file_name']}: {err}")
                        progress_bar.progress((idx + 1) / len(eligible_items))
                    st.success("Batch metadata generation completed!")
                    st.rerun()

        # 3. Batch Embed EXIF buttons
        ready_for_exif = [img for img in images if (img.get("title") or img.get("stock_title")) and img["status"] != "APPLIED"]
        if ready_for_exif:
            st.caption(f"**{len(ready_for_exif)} items ready for metadata embedding**")
            b_emb_c1, b_emb_c2 = st.columns(2)
            with b_emb_c1:
                if st.button(f"💾 Stock IPTC/XMP ({len(ready_for_exif)})", help="Embed Stock title & full 30-45 tags for Alamy, Adobe Stock, and microstock parsers", type="primary", use_container_width=True):
                    try:
                        exiftool_exe = stock_metadata.find_exiftool()
                        exif_progress = st.progress(0)
                        success_count = 0
                        for idx, item in enumerate(ready_for_exif):
                            stock_metadata.apply_stock_metadata_to_image(
                                image_path=Path(item["file_path"]),
                                title=item.get("stock_title") or item.get("title") or "",
                                description=item.get("stock_description") or item.get("description") or item.get("stock_title") or "",
                                keywords=item.get("stock_keywords") or item.get("keywords") or "",
                                exiftool_path=exiftool_exe
                            )
                            db.update_image(item["id"], status="APPLIED")
                            success_count += 1
                            exif_progress.progress((idx + 1) / len(ready_for_exif))
                        st.success(f"Successfully embedded Stock IPTC/XMP into {success_count} images!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Batch Stock ExifTool error: {e}")

            with b_emb_c2:
                if st.button(f"💾 Art Heroes EXIF ({len(ready_for_exif)})", help="Embed Art Heroes fine art POD 3-paragraph text & top 12 tags", use_container_width=True):
                    try:
                        exiftool_exe = find_exiftool()
                        exif_progress = st.progress(0)
                        success_count = 0
                        for idx, item in enumerate(ready_for_exif):
                            tags_clean = [t.strip() for t in (item.get("keywords") or "").split(",") if t.strip()]
                            meta_payload = {
                                "title": item.get("title") or "",
                                "description": item.get("description") or "",
                                "keywords": tags_clean[:12]
                            }
                            apply_metadata_to_image(exiftool_exe, Path(item["file_path"]), meta_payload)
                            db.update_image(item["id"], status="APPLIED")
                            success_count += 1
                            exif_progress.progress((idx + 1) / len(ready_for_exif))
                        st.success(f"Successfully embedded Art Heroes metadata into {success_count} images!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Batch ExifTool error: {e}")

        st.divider()

        # 4. Visual Thumbnail Gallery with Pagination
        if "selected_img_id" not in st.session_state or not any(img["id"] == st.session_state["selected_img_id"] for img in images):
            st.session_state["selected_img_id"] = images[0]["id"]

        PAGE_SIZE = 8
        total_pages = max(1, (len(images) + PAGE_SIZE - 1) // PAGE_SIZE)
        if total_pages > 1:
            p_col1, p_col2 = st.columns([1.3, 1.7])
            page_num = p_col1.number_input(f"Page (1-{total_pages})", min_value=1, max_value=total_pages, value=1, step=1, key="gallery_page_input")
            start_idx = (page_num - 1) * PAGE_SIZE
            paged_images = images[start_idx : start_idx + PAGE_SIZE]
            p_col2.caption(f"Showing **{start_idx+1}-{min(start_idx+PAGE_SIZE, len(images))}** of {len(images)}")
        else:
            paged_images = images

        qc_icons = {"PASS": "🟢", "REVIEW": "🟠", "HIGH_RISK": "🔴", "UNCHECKED": "⚪"}
        grade_badges = {"FINE_ART": "🎨 Fine Art", "STOCK": "📸 Stock", "BOTH": "🎨📸 Dual", "NONE": "⚪ Unassigned"}

        for img_item in paged_images:
            is_active = (img_item["id"] == st.session_state["selected_img_id"])
            card_border = "#2e7d32" if is_active else "#3b3d4a"
            card_bg = "#1b2a1e" if is_active else "#1c1d24"

            st_b = {"NEW": "🟠 NEW", "GENERATED": "🔵 READY", "APPLIED": "🟢 EMBEDDED"}.get(img_item.get("status"), img_item.get("status"))
            qc_b = qc_icons.get(img_item.get("qc_status") or "UNCHECKED", "⚪")
            curr_g = img_item.get("grade") or "NONE"
            gr_b = grade_badges.get(curr_g, curr_g)

            with st.container():
                st.markdown(
                    f"""<div style="border: 2px solid {card_border}; background-color: {card_bg}; border-radius: 6px; padding: 7px 10px; margin-bottom: 6px;">
                        <span style="font-weight: 600; font-size: 13px;">{'👉 [EDITING] ' if is_active else ''}{img_item['file_name']}</span>
                    </div>""",
                    unsafe_allow_html=True
                )
                del_col, t_col, meta_col = st.columns([0.22, 1.0, 1.28])
                with del_col:
                    if st.button("🗑️", key=f"quick_del_{img_item['id']}", help=f"🚨 Immediate permanent deletion from disk and database: {img_item['file_name']}", type="secondary"):
                        ok, msg = db.delete_image(img_item["id"], delete_from_disk=True)
                        if st.session_state.get("selected_img_id") == img_item["id"]:
                            st.session_state["selected_img_id"] = None
                        st.cache_data.clear()
                        st.toast(f"🗑️ Deleted from disk: {img_item['file_name']}")
                        st.rerun()
                with t_col:
                    tb = get_thumbnail_bytes(img_item["file_path"], max_dim=220)
                    if tb:
                        st.image(tb, width="stretch")
                    else:
                        st.caption("No preview")

                with meta_col:
                    st.caption(f"Status: `{st_b}` | QC: {qc_b}")
                    attr_badges = []
                    if img_item.get("is_ai_generated"): attr_badges.append("🤖 AI")
                    if img_item.get("is_infrared"): attr_badges.append("🔴 IR")
                    if img_item.get("is_surreal"): attr_badges.append("🌌 Surreal")
                    if img_item.get("is_editorial"): attr_badges.append("📰 Editorial")
                    attr_str = " ".join(attr_badges)
                    st.caption(f"Grade: **{gr_b}**" + (f" | {attr_str}" if attr_str else ""))

                    upl_str = img_item.get("uploaded_to") or ""
                    if upl_str:
                        upl_tags = [p.strip() for p in upl_str.split(",") if p.strip()]
                        st.caption("📤 **Uploaded:** " + " • ".join([f"`{u}`" for u in upl_tags]))
                    else:
                        st.caption("📤 **Uploaded:** ⚪ *Not uploaded yet*")

                    # Quick 1-click grade buttons
                    gc1, gc2, gc3, gc4 = st.columns(4)
                    if gc1.button("🎨", key=f"qg_fa_{img_item['id']}", help="Mark as Fine Art Grade"):
                        db.update_image(img_item["id"], grade="FINE_ART")
                        st.rerun()
                    if gc2.button("📸", key=f"qg_st_{img_item['id']}", help="Mark as Stock Grade"):
                        db.update_image(img_item["id"], grade="STOCK")
                        st.rerun()
                    if gc3.button("🎨📸", key=f"qg_both_{img_item['id']}", help="Mark as Dual Grade (Both)"):
                        db.update_image(img_item["id"], grade="BOTH")
                        st.rerun()
                    if gc4.button("✖️", key=f"qg_no_{img_item['id']}", help="Unassign Grade"):
                        db.update_image(img_item["id"], grade="NONE")
                        st.rerun()

                    if is_active:
                        st.button("✅ Selected", key=f"btn_act_{img_item['id']}", disabled=True, use_container_width=True, type="primary")
                    else:
                        if st.button("🔍 Select & Edit", key=f"btn_sel_{img_item['id']}", use_container_width=True):
                            st.session_state["selected_img_id"] = img_item["id"]
                            st.rerun()
                st.markdown("---")

        st.divider()
        # Batch QC Audit Expander
        with st.expander(f"🔬 Batch QC Audit ({len(images)} items)", expanded=False):
            st.caption("Perform automated quality check on all displayed images and save results.")
            qc_batch_mode = st.selectbox("Batch QC Sensitivity", ["production", "paranoid"], index=0, key="batch_qc_mode")
            if st.button("🚀 Run QC on All Displayed Images", use_container_width=True):
                qc_progress = st.progress(0)
                qc_results = []
                config = QualityConfig(mode=qc_batch_mode)
                db_path = str(Path(REPO_ROOT) / "stock-metadata" / "dust_fingerprints.yaml")
                analyzer = TechnicalQualityAnalyzer(config, db_path=db_path)
                for idx, img_item in enumerate(images):
                    try:
                        rep = analyzer.analyze_image(img_item["file_path"])
                        sharp = rep.technical_quality.get("sharpness")
                        dust = rep.technical_quality.get("sensor_dust")
                        noise = rep.technical_quality.get("noise")
                        sharp_val = float(sharp.score) if sharp and sharp.score is not None else None
                        sharp_str = f"{sharp_val:.1f}" if sharp_val is not None else "-"
                        dust_cnt = len(dust.anomalies) if dust and hasattr(dust, "anomalies") else 0
                        noise_val = float(noise.score) if noise and noise.score is not None else None
                        noise_str = f"{noise_val:.1f}" if noise_val is not None else "-"
                        warn_list = [w for d in rep.technical_quality.values() for w in d.warnings]
                        warns_str = "; ".join(warn_list)

                        # Persist to SQLite
                        db.update_image(
                            img_item["id"],
                            qc_status=rep.overall_status.value,
                            qc_sharpness=sharp_val,
                            qc_dust_count=dust_cnt,
                            qc_noise=noise_val,
                            qc_warnings=warns_str
                        )

                        qc_results.append({
                            "File": img_item["file_name"],
                            "QC Status": rep.overall_status.value,
                            "Sharpness": sharp_str,
                            "Noise": noise_str,
                            "Dust Spots": dust_cnt,
                            "Warnings": len(warn_list)
                        })
                    except Exception as e:
                        db.update_image(img_item["id"], qc_status="ERROR", qc_warnings=str(e))
                        qc_results.append({
                            "File": img_item["file_name"],
                            "QC Status": "ERROR",
                            "Sharpness": "-",
                            "Dust Spots": "-",
                            "Warnings": str(e)
                        })
                    qc_progress.progress((idx + 1) / len(images))
                import pandas as pd
                st.dataframe(pd.DataFrame(qc_results), use_container_width=True)
                st.success("Batch QC completed and saved to database!")
                st.rerun()

    # Selected image object from active session state ID (re-fetched directly from DB to guarantee freshest state)
    sel_id = st.session_state.get("selected_img_id")
    if not sel_id and images:
        sel_id = images[0]["id"]
        st.session_state["selected_img_id"] = sel_id
    selected_img = db.get_image_by_id(sel_id) if sel_id else None

    with detail_col:
        if selected_img:
            insp_h1, insp_h2 = st.columns([2.6, 1])
            insp_h1.subheader(f"📝 Inspector: {selected_img['file_name']}")
            if insp_h2.button("🔄 Reload Image", key=f"insp_ref_{selected_img['id']}", use_container_width=True, help="Force refresh image data and reset form fields to latest database state"):
                st.session_state[f"rev_{selected_img['id']}"] = st.session_state.get(f"rev_{selected_img['id']}", 0) + 1
                st.cache_data.clear()
                st.rerun()
            
            # Status Indicator
            status_colors = {"NEW": "🟠", "GENERATED": "🔵", "APPLIED": "🟢"}
            st.caption(f"Status: {status_colors.get(selected_img['status'], '⚪')} **{selected_img['status']}** | Path: `{selected_img['file_path']}`")

            # Grade Classification in Inspector
            curr_insp_grade = selected_img.get("grade") or "NONE"
            insp_grade_col1, insp_grade_col2 = st.columns([2.5, 1])
            new_insp_grade = insp_grade_col1.radio(
                "Art / Commercial Grade Classification:",
                ["FINE_ART", "STOCK", "BOTH", "NONE"],
                format_func=lambda x: {
                    "FINE_ART": "🎨 Fine Art (Art Heroes / Displate)",
                    "STOCK": "📸 Stock Grade (Microstock / Alamy / Vecteezy)",
                    "BOTH": "🎨📸 Dual Grade (Fine Art & Microstock)",
                    "NONE": "⚪ Unassigned"
                }[x],
                horizontal=True,
                index=["FINE_ART", "STOCK", "BOTH", "NONE"].index(curr_insp_grade) if curr_insp_grade in ["FINE_ART", "STOCK", "BOTH", "NONE"] else 3,
                key=f"insp_grade_{selected_img['id']}"
            )
            if new_insp_grade != curr_insp_grade:
                db.update_image(selected_img["id"], grade=new_insp_grade)
                st.rerun()

            # Editorial Mode & Artistic/Medium Attributes
            attr_c1, attr_c2, attr_c3, attr_c4 = st.columns(4)
            img_id = selected_img["id"]
            fn_low = selected_img["file_name"].lower()

            ed_key = f"editorial_cb_{img_id}"
            ai_key = f"ai_cb_{img_id}"
            ir_key = f"ir_cb_{img_id}"
            surreal_key = f"surreal_cb_{img_id}"

            # Smart defaults when not yet in session state
            if ed_key not in st.session_state:
                st.session_state[ed_key] = bool(selected_img.get("is_editorial"))
            if ai_key not in st.session_state:
                val_ai = bool(selected_img.get("is_ai_generated"))
                if not val_ai and any(k in fn_low for k in ["chatgpt", "midjourney", "dall", "flux", "stable_diff", "codex", "ai_"]):
                    val_ai = True
                st.session_state[ai_key] = val_ai
            if ir_key not in st.session_state:
                val_ir = bool(selected_img.get("is_infrared"))
                if not val_ir and any(k in fn_low for k in ["infrared", "720nm", "ir_"]):
                    val_ir = True
                st.session_state[ir_key] = val_ir
            if surreal_key not in st.session_state:
                val_surr = bool(selected_img.get("is_surreal"))
                if not val_surr and any(k in fn_low for k in ["dreamy", "surreal", "fantasy"]):
                    val_surr = True
                st.session_state[surreal_key] = val_surr

            def on_attr_change(i_id=img_id, k_ed=ed_key, k_ai=ai_key, k_ir=ir_key, k_surr=surreal_key):
                db.update_image(
                    i_id,
                    is_editorial=1 if st.session_state.get(k_ed) else 0,
                    is_ai_generated=1 if st.session_state.get(k_ai) else 0,
                    is_infrared=1 if st.session_state.get(k_ir) else 0,
                    is_surreal=1 if st.session_state.get(k_surr) else 0
                )

            new_editorial = attr_c1.checkbox(
                "📰 Editorial",
                key=ed_key,
                on_change=on_attr_change,
                help="Check if this is an editorial asset (requires CITY, DATE format, non-commercial)."
            )
            new_ai = attr_c2.checkbox(
                "🤖 AI Generated",
                key=ai_key,
                on_change=on_attr_change,
                help="Check if this is generative AI artwork. Strictly prevents 'Original photography' in copy!"
            )
            new_ir = attr_c3.checkbox(
                "🔴 Infrared (IR)",
                key=ir_key,
                on_change=on_attr_change,
                help="Check if this is 720nm infrared (highlights white foliage, dark skies)."
            )
            new_surreal = attr_c4.checkbox(
                "🌌 Surreal",
                key=surreal_key,
                on_change=on_attr_change,
                help="Check if this has a surreal, dreamlike, or conceptual style."
            )
            curr_editorial = bool(new_editorial)

            # Manual Platform Upload Tracker
            TRACKER_AGENCIES = [
                "Adobe Stock", "Vecteezy", "Shutterstock", "Alamy",
                "Art Heroes", "Displate", "Pond5", "Dreamstime", "Depositphotos", "Fine Art America"
            ]
            raw_upl = selected_img.get("uploaded_to") or ""
            curr_upl_list = [p.strip() for p in raw_upl.split(",") if p.strip()]
            valid_defaults = [p for p in curr_upl_list if p in TRACKER_AGENCIES]
            tracker_ver = st.session_state.get(f"upl_tracker_ver_{selected_img['id']}", 0)
            k_track = f"upl_tracker_{selected_img['id']}_{tracker_ver}"

            def on_tracker_change(i_id=selected_img["id"], key_name=k_track):
                new_selections = st.session_state.get(key_name, [])
                db.update_image(i_id, uploaded_to=", ".join(new_selections))

            st.multiselect(
                "📤 Uploaded to Agencies (Manual Tracker):",
                options=TRACKER_AGENCIES,
                default=valid_defaults,
                key=k_track,
                on_change=on_tracker_change,
                help="Manually track which stock agencies or POD platforms this image has been published to."
            )

            # Delete Action & Quick Controls
            del_row_c1, del_row_c2 = st.columns([2, 1])
            with del_row_c2:
                with st.expander("🗑️ Delete from Disk", expanded=False):
                    st.caption("Permanently delete this file:")
                    del_conf = st.checkbox("Confirm delete", key=f"del_conf_{selected_img['id']}")
                    if st.button("🚨 Delete File", type="primary", disabled=not del_conf, key=f"del_btn_{selected_img['id']}", use_container_width=True):
                        ok, msg = db.delete_image(selected_img["id"], delete_from_disk=True)
                        if ok:
                            st.success(msg)
                            st.session_state["selected_img_id"] = None
                            st.rerun()
                        else:
                            st.error(msg)

            # 1-Click Agency Upload in Inspector
            with st.expander("🚀 1-Click Remote Agency Upload (Multi & Single Agency)", expanded=False):
                STOCK_AGENCIES_LIST = ["Adobe Stock", "Alamy", "Depositphotos", "Vecteezy", "Shutterstock", "Pond5", "Dreamstime"]

                # Display last broadcast or last single upload notification if present
                last_broad_key = f"last_broadcast_{selected_img['id']}"
                if last_broad_key in st.session_state:
                    b_items = st.session_state[last_broad_key]
                    s_count = sum(1 for item in b_items if item.get("success"))
                    total_cnt = len(b_items)
                    if s_count == total_cnt and total_cnt > 0:
                        st.success(f"🎉 **Broadcast Complete:** `{selected_img['file_name']}` uploaded to all {total_cnt} selected agencies!")
                    else:
                        st.info(f"📊 **Last Broadcast Results:** {s_count}/{total_cnt} successful.")
                    for item in b_items:
                        if item.get("success"):
                            st.caption(f"✅ **{item['agency']}**: {item['message']}")
                        else:
                            st.caption(f"❌ **{item['agency']}**: {item['message']}")

                last_up_key = f"last_up_{selected_img['id']}"
                if last_up_key in st.session_state:
                    l_res = st.session_state[last_up_key]
                    if l_res.get("status") == "SUCCESS":
                        st.success(f"🎉 **Last Upload Success:** `{selected_img['file_name']}` uploaded to **{l_res.get('agency')}** at {l_res.get('time')}.")
                    elif l_res.get("status") == "ERROR":
                        st.error(f"❌ **Last Upload Failed:** {l_res.get('message')}")

                tab_multi, tab_single = st.tabs(["🌐 Broadcast to ALL Stock Agencies", "🎯 Single Agency Upload"])

                with tab_multi:
                    curr_upl = [p.strip() for p in (selected_img.get("uploaded_to") or "").split(",") if p.strip()]

                    # Compute readiness and default targets
                    agency_status = {}
                    ready_agencies = []
                    for ag in STOCK_AGENCIES_LIST:
                        c = load_agency_config(ag)
                        has_creds = bool(c.get("host") and c.get("user") and c.get("password"))
                        is_upl = (ag in curr_upl)
                        agency_status[ag] = {
                            "ready": has_creds,
                            "uploaded": is_upl,
                            "user": c.get("user", ""),
                            "host": c.get("host", "")
                        }
                        if has_creds and not is_upl:
                            ready_agencies.append(ag)

                    # Default to ready non-uploaded agencies, or all ready if none pending
                    default_bcast = ready_agencies if ready_agencies else [ag for ag in STOCK_AGENCIES_LIST if agency_status[ag]["ready"]]

                    # Status summary row
                    st.caption("Agency Credential & Upload Status:")
                    st_cols = st.columns(len(STOCK_AGENCIES_LIST))
                    for col_idx, ag in enumerate(STOCK_AGENCIES_LIST):
                        astat = agency_status[ag]
                        with st_cols[col_idx]:
                            if astat["uploaded"]:
                                st.markdown(f"**{ag}**<br><span style='color:green'>🟢 Uploaded</span>", unsafe_allow_html=True)
                            elif astat["ready"]:
                                st.markdown(f"**{ag}**<br><span style='color:blue'>🔒 Ready</span>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"**{ag}**<br><span style='color:orange'>🔑 No Pass</span>", unsafe_allow_html=True)

                    st.write("")
                    chosen_broadcast = st.multiselect(
                        "Agencies to Broadcast to:",
                        options=STOCK_AGENCIES_LIST,
                        default=default_bcast,
                        key=f"bcast_select_{selected_img['id']}",
                        help="Select stock agencies to receive this image. IPTC/XMP metadata and agency-specific CSV sidecars will be processed automatically."
                    )

                    btn_bcast_label = f"🚀 1-Click Broadcast `{selected_img['file_name']}` to {len(chosen_broadcast)} Agencies"
                    if st.button(btn_bcast_label, type="primary", disabled=(len(chosen_broadcast) == 0), use_container_width=True, key=f"btn_bcast_run_{selected_img['id']}"):
                        broadcast_res = []
                        b_progress = st.progress(0.0)

                        # Step 1: Embed IPTC/XMP once
                        with st.spinner("Embedding IPTC/XMP metadata into JPEG header..."):
                            try:
                                exiftool_exe = stock_metadata.find_exiftool()
                                stock_metadata.apply_stock_metadata_to_image(
                                    image_path=Path(selected_img["file_path"]),
                                    title=selected_img.get("stock_title") or selected_img.get("title") or "",
                                    description=selected_img.get("stock_description") or selected_img.get("description") or selected_img.get("stock_title") or "",
                                    keywords=selected_img.get("stock_keywords") or selected_img.get("keywords") or "",
                                    exiftool_path=exiftool_exe
                                )
                            except Exception as em_err:
                                st.warning(f"Stock IPTC embed warning: {em_err}")

                        # Step 2: Upload to each selected agency
                        for idx, ag_target in enumerate(chosen_broadcast):
                            with st.spinner(f"Uploading to {ag_target}..."):
                                r = upload_single_image_to_stock_agency(selected_img, ag_target)
                                broadcast_res.append(r)
                                if r["success"]:
                                    fresh_img = db.get_image_by_id(selected_img["id"])
                                    latest_upl = [p.strip() for p in (fresh_img.get("uploaded_to") or "").split(",") if p.strip()]
                                    if ag_target not in latest_upl:
                                        latest_upl.append(ag_target)
                                        db.update_image(selected_img["id"], uploaded_to=", ".join(latest_upl))
                            b_progress.progress((idx + 1) / len(chosen_broadcast))

                        st.session_state[f"upl_tracker_ver_{selected_img['id']}"] = tracker_ver + 1
                        st.session_state[last_broad_key] = broadcast_res
                        st.toast(f"🚀 Broadcast finished for {len(chosen_broadcast)} agencies!", icon="🎉")
                        st.rerun()

                with tab_single:
                    insp_agencies = ["Adobe Stock", "Alamy", "Depositphotos", "Vecteezy", "Shutterstock", "Pond5", "Dreamstime", "Custom FTP / SFTP"]
                    insp_chosen = st.selectbox("Select Target Agency", insp_agencies, index=0, key=f"insp_target_{selected_img['id']}")
                    insp_cfg = load_agency_config(insp_chosen)

                    # Check if this image has already been uploaded to this agency
                    curr_upl_single = [p.strip() for p in (selected_img.get("uploaded_to") or "").split(",") if p.strip()]
                    if insp_chosen in curr_upl_single:
                        st.info(f"🟢 **Already Uploaded:** This asset is recorded as uploaded to **{insp_chosen}**.")

                    insp_host_c1, insp_host_c2 = st.columns([2.5, 1])
                    insp_host_c1.caption(f"Host: `{insp_cfg['host']}` ({insp_cfg['protocol'].upper()})")
                    insp_host_c2.caption(f"Port: `{insp_cfg['port']}`")

                    insp_u_col, insp_p_col = st.columns([1, 1.2])
                    with insp_u_col:
                        insp_user = st.text_input(
                            f"Username / ID",
                            value=insp_cfg.get("user") or "",
                            key=f"agency_shared_user_{insp_chosen}",
                            help=f"Username or Contributor Account ID for {insp_chosen}."
                        )
                    with insp_p_col:
                        insp_pass = insp_cfg.get("password") or ""
                        pass_label = f"Password" + (" (🔒 Loaded)" if insp_pass else " (🔑 Missing)")
                        entered_pass = st.text_input(
                            pass_label,
                            value=insp_pass,
                            type="password",
                            key=f"agency_shared_pass_{insp_chosen}",
                            help=f"Password for {insp_chosen}. Automatically remembered and stored securely."
                        )

                    insp_user_changed = (insp_user.strip() != (insp_cfg.get("user") or "").strip())
                    insp_pass_changed = bool(entered_pass and entered_pass != insp_pass)
                    if insp_user_changed or insp_pass_changed:
                        save_agency_config(insp_chosen, {
                            **insp_cfg,
                            "user": insp_user.strip(),
                            "password": entered_pass if entered_pass else insp_pass
                        }, save_password_to_keyring=insp_pass_changed)
                        insp_cfg["user"] = insp_user.strip()
                        if entered_pass:
                            insp_cfg["password"] = entered_pass

                    if not insp_pass and "Adobe" in insp_chosen:
                        st.caption("ℹ️ **Adobe Stock SFTP:** Dedicated SFTP password generated on Contributor Portal (Upload → SFTP tab) is required (NOT your personal Adobe password).")

                    btn_col1, btn_col2 = st.columns([1, 1.8])
                    active_user = insp_user.strip() or insp_cfg.get("user", "")
                    active_pass = entered_pass or insp_pass

                    if btn_col1.button("🔌 Test Connection", key=f"insp_test_{selected_img['id']}_{insp_chosen}", use_container_width=True):
                        if not insp_cfg["host"] or not active_user:
                            st.warning("Host and username are required.")
                        else:
                            with st.spinner(f"Testing connection to {insp_chosen}..."):
                                ok, test_msg = ftp_uploader.test_connection(
                                    insp_cfg["host"],
                                    port=insp_cfg["port"],
                                    user=active_user,
                                    password=active_pass,
                                    protocol=insp_cfg["protocol"],
                                    remote_dir=insp_cfg["remote_dir"]
                                )
                                if ok:
                                    st.success(test_msg)
                                else:
                                    st.error(test_msg)

                    if btn_col2.button(f"⬆️ Upload to {insp_chosen}", type="primary", use_container_width=True, key=f"insp_up_{selected_img['id']}"):
                        if not insp_cfg["host"] or not active_user or not active_pass:
                            st.error(f"Missing host, user, or password for {insp_chosen}. Please enter your credentials above.")
                        else:
                            with st.spinner(f"Uploading {selected_img['file_name']} to {insp_chosen}..."):
                                res = upload_single_image_to_stock_agency(
                                    selected_img,
                                    insp_chosen,
                                    override_user=active_user,
                                    override_pass=active_pass
                                )
                                if res["success"]:
                                    st.toast(f"✅ {selected_img['file_name']} uploaded to {insp_chosen}!", icon="🚀")
                                    latest_upl = [p.strip() for p in (selected_img.get("uploaded_to") or "").split(",") if p.strip()]
                                    if insp_chosen not in latest_upl:
                                        latest_upl.append(insp_chosen)
                                        db.update_image(selected_img["id"], uploaded_to=", ".join(latest_upl))
                                        st.session_state[f"upl_tracker_ver_{selected_img['id']}"] = tracker_ver + 1
                                    st.session_state[last_up_key] = {
                                        "status": "SUCCESS",
                                        "agency": insp_chosen,
                                        "time": datetime.now().strftime("%H:%M:%S")
                                    }
                                    st.rerun()
                                else:
                                    err_detail = res["message"]
                                    st.error(f"❌ Upload error ({insp_chosen}): {err_detail}")
                                    st.toast(f"❌ Upload error ({insp_chosen})", icon="⚠️")
                                    st.session_state[last_up_key] = {
                                        "status": "ERROR",
                                        "agency": insp_chosen,
                                        "message": err_detail,
                                        "time": datetime.now().strftime("%H:%M:%S")
                                    }

            # Image thumbnail preview
            img_path = Path(selected_img["file_path"])
            if img_path.exists():
                prev_c1, prev_c2 = st.columns([3, 1.2])
                prev_c1.caption(f"📁 `{selected_img['file_name']}`")
                if prev_c2.button("🖥️ Open Full Size", key=f"open_sys_{selected_img['id']}", use_container_width=True, help="Open original file in default Windows photo viewer"):
                    try:
                        os.startfile(str(img_path))
                    except Exception as e:
                        st.error(f"Could not open in system viewer: {e}")

                tb = get_thumbnail_bytes(selected_img["file_path"], max_dim=2048)
                if tb:
                    st.image(tb, width="stretch")
                else:
                    st.warning("Could not render image thumbnail.")

                # Photographic RGB + Luminance Histogram
                with st.expander("📊 Image Histogram & Exposure Analysis", expanded=False):
                    try:
                        try:
                            hist_bytes, h_stats, h_df = get_image_histogram_cached(selected_img["file_path"])
                        except Exception:
                            import dashboard.raw_loader as raw_loader
                            importlib.reload(raw_loader)
                            hist_bytes, h_stats, h_df = raw_loader.generate_histogram(selected_img["file_path"])

                        if hist_bytes:
                            st.image(hist_bytes, caption="Photographic RGB + Luminance Histogram", width="stretch")
                            hc1, hc2, hc3, hc4 = st.columns(4)
                            s_clip = h_stats.get("shadow_clip_pct", 0.0)
                            h_clip = h_stats.get("highlight_clip_pct", 0.0)
                            hc1.metric("Shadow Clip", f"{s_clip:.2f}%", delta="Crushed" if s_clip > 1.0 else "Clean", delta_color="inverse")
                            hc2.metric("Highlight Clip", f"{h_clip:.2f}%", delta="Blown" if h_clip > 1.0 else "Clean", delta_color="inverse")
                            hc3.metric("Mean Luma", f"{h_stats.get('mean_luma', 0.0):.1f} / 255")
                            hc4.metric("Contrast (Std)", f"{h_stats.get('contrast_std', 0.0):.1f}")
                        else:
                            st.caption("Histogram could not be rendered for this image.")
                    except Exception as e:
                        st.warning(f"Could not calculate histogram: {e}")

            # Technical Quality Preflight Check
            saved_qc_status = selected_img.get("qc_status") or "UNCHECKED"
            qc_header_badge = {"PASS": "🟢 PASS", "REVIEW": "🟠 REVIEW", "HIGH_RISK": "🔴 HIGH RISK", "UNCHECKED": "⚪ Not Checked"}.get(saved_qc_status, saved_qc_status)
            with st.expander(f"🔬 Technical Quality Preflight: {qc_header_badge}", expanded=(saved_qc_status != "UNCHECKED")):
                qc_col1, qc_col2 = st.columns([1.2, 1])
                qc_mode = qc_col1.selectbox("Sensitivity Mode", ["production", "paranoid"], index=0, key=f"qc_mode_{selected_img['id']}")
                run_qc = qc_col2.button("🔍 Run Quality Check", use_container_width=True, key=f"qc_btn_{selected_img['id']}")

                report_key = f"qc_report_{selected_img['id']}"
                if run_qc:
                    with st.spinner("Analyzing image sharpness, exposure, sensor dust..."):
                        try:
                            config = QualityConfig(mode=qc_mode)
                            db_path = str(Path(REPO_ROOT) / "stock-metadata" / "dust_fingerprints.yaml")
                            analyzer = TechnicalQualityAnalyzer(config, db_path=db_path)
                            report = analyzer.analyze_image(selected_img["file_path"])
                            st.session_state[report_key] = report

                            # Persist to database
                            sharp = report.technical_quality.get("sharpness")
                            dust = report.technical_quality.get("sensor_dust")
                            noise = report.technical_quality.get("noise")
                            sharp_val = float(sharp.score) if sharp and sharp.score is not None else None
                            dust_cnt = len(dust.anomalies) if dust and hasattr(dust, "anomalies") else 0
                            noise_val = float(noise.score) if noise and noise.score is not None else None
                            warn_list = [w for d in report.technical_quality.values() for w in d.warnings]
                            db.update_image(
                                selected_img["id"],
                                qc_status=report.overall_status.value,
                                qc_sharpness=sharp_val,
                                qc_dust_count=dust_cnt,
                                qc_noise=noise_val,
                                qc_warnings="; ".join(warn_list)
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Quality check failed: {e}")

                if report_key in st.session_state:
                    rep = st.session_state[report_key]
                    status_badge = {
                        Status.PASS: "🟢 PASS - Excellent Quality",
                        Status.REVIEW: "🟠 REVIEW REQUIRED - Minor Warnings",
                        Status.HIGH_RISK: "🔴 HIGH RISK - Rejection Likely",
                        Status.ERROR: "⚠️ ERROR"
                    }
                    st.write(f"### Result: **{status_badge.get(rep.overall_status, rep.overall_status.value)}**")
                    st.caption(f"Resolution: **{rep.width} x {rep.height}** | Format: **{rep.format}** | Time: {rep.processing_time_seconds:.2f}s")

                    # Metrics
                    mcol1, mcol2, mcol3, mcol4, mcol5 = st.columns(5)
                    sharp_res = rep.technical_quality.get("sharpness")
                    noise_res = rep.technical_quality.get("noise")
                    dust_res = rep.technical_quality.get("sensor_dust")
                    exp_res = rep.technical_quality.get("exposure")
                    dead_res = rep.technical_quality.get("dead_pixels")

                    if sharp_res:
                        score_str = f"{sharp_res.score:.1f}" if sharp_res.score is not None else "N/A"
                        mcol1.metric("Sharpness", score_str, delta="OK" if sharp_res.status == Status.PASS else "Low")
                    if noise_res:
                        noise_score_str = f"{noise_res.score:.1f}" if noise_res.score is not None else "N/A"
                        delta_noise = "Clean" if noise_res.status == Status.PASS else ("Review" if noise_res.status == Status.REVIEW else "High Risk")
                        mcol2.metric("Noise (Grain)", noise_score_str, delta=delta_noise)
                    if dust_res:
                        cand_count = len(dust_res.anomalies) if hasattr(dust_res, "anomalies") else dust_res.metrics.get("candidates", 0)
                        sky_cnt = dust_res.metrics.get("sky_candidates", 0)
                        pers_cnt = dust_res.metrics.get("persistent", 0)
                        delta_str = "Clean"
                        if pers_cnt > 0:
                            delta_str = f"⚠️ {pers_cnt} Persistent!"
                        elif cand_count > 0:
                            delta_str = f"{cand_count} spots ({sky_cnt} sky)"
                        mcol3.metric("Dust Spots", cand_count, delta=delta_str)
                    if exp_res:
                        mcol4.metric("Exposure", exp_res.status.value)
                    if dead_res:
                        mcol5.metric("Dead Pixels", dead_res.status.value)

                    # Warnings
                    all_warns = []
                    for dname, dres in rep.technical_quality.items():
                        for w in dres.warnings:
                            all_warns.append(f"**{dname.upper()}**: {w}")
                    if all_warns:
                        st.warning("\n\n".join(all_warns))

                    # Diagnostic Overlay
                    has_anomalies = any(getattr(d, "anomalies", None) for d in rep.technical_quality.values())
                    if has_anomalies:
                        show_overlay = st.checkbox("Show Defect & Dust Visual Map Overlay", value=False, key=f"overlay_{selected_img['id']}")
                        if show_overlay:
                            diag_path = Path(REPO_ROOT) / "dashboard" / f"_temp_diag_{selected_img['id']}.jpg"
                            import dataclasses
                            draw_diagnostics(selected_img["file_path"], dataclasses.asdict(rep), str(diag_path))
                            if diag_path.exists():
                                st.image(diag_path.read_bytes(), caption="Diagnostic Map (Red = Dust / Defect Candidate, Orange = Sky, Yellow = Persistent)", width="stretch")
                            else:
                                st.warning("Could not generate diagnostic overlay map.")
                elif selected_img.get("qc_status") and selected_img.get("qc_status") != "UNCHECKED":
                    st.write(f"### Saved Result: **{qc_header_badge}**")
                    m1, m2, m3 = st.columns(3)
                    sharp_val = selected_img.get("qc_sharpness")
                    noise_val = selected_img.get("qc_noise")
                    m1.metric("Sharpness Score", f"{sharp_val:.1f}" if sharp_val is not None else "N/A")
                    m2.metric("Noise Level", f"{noise_val:.1f}" if noise_val is not None else "N/A")
                    m3.metric("Dust Candidates", selected_img.get("qc_dust_count") or 0)
                    if selected_img.get("qc_warnings"):
                        st.info(f"Warnings: {selected_img['qc_warnings']}")

            # Displate Preflight & Auto-Format Expander
            with st.expander("🏆 Displate Technical Compliance & Preflight", expanded=False):
                if analyze_displate_compliance is None:
                    st.warning("Displate tool module not loaded.")
                else:
                    disp_c1, disp_c2 = st.columns([1, 1])
                    check_disp = disp_c1.button("🔍 Check Displate Specs", key=f"disp_check_{selected_img['id']}", use_container_width=True)
                    prep_disp = disp_c2.button("🛠️ Auto-Format (1.4:1 / 300 DPI / Grain)", key=f"disp_prep_{selected_img['id']}", use_container_width=True)

                    disp_rep_key = f"disp_rep_{selected_img['id']}"
                    if check_disp:
                        with st.spinner("Auditing Displate requirements (1.4:1, 300 DPI, Safe Zone, margins)..."):
                            try:
                                disp_analysis = analyze_displate_compliance(Path(selected_img["file_path"]))
                                st.session_state[disp_rep_key] = disp_analysis
                            except Exception as e:
                                st.error(f"Displate analysis failed: {e}")

                    if prep_disp:
                        with st.spinner("Preparing image for Displate (Cropping 1.4:1, 300 DPI, sRGB, micrograin)..."):
                            try:
                                orig_p = Path(selected_img["file_path"])
                                out_dir = orig_p.parent / "displate_ready"
                                out_p = out_dir / f"{orig_p.stem}_displate.jpg"
                                prepare_for_displate(orig_p, out_p, add_grain=0.01)
                                st.success(f"Displate ready file created: `{out_p.name}` in `{out_dir.name}/`")
                                disp_analysis = analyze_displate_compliance(out_p)
                                st.session_state[disp_rep_key] = disp_analysis
                            except Exception as e:
                                st.error(f"Displate preparation failed: {e}")

                    if disp_rep_key in st.session_state:
                        da = st.session_state[disp_rep_key]
                        status_badge = "🟢 PASS" if da["status"] == "PASS" else ("🟡 WARN" if da["status"] == "WARN" else "🔴 FAIL")
                        st.write(f"### Displate Status: **{status_badge}** (`{da['filename']}`)")

                        dm1, dm2, dm3, dm4 = st.columns(4)
                        ar = da["checks"].get("aspect_ratio", 0)
                        dm1.metric("Aspect Ratio", f"{ar}:1", delta="OK (1.40:1)" if abs(ar - 1.4) <= 0.015 else "Invalid")
                        ss = da["checks"].get("short_side", 0)
                        dm2.metric("Short Side", f"{ss} px", delta="OK (>= 2900)" if ss >= 2900 else "Too small")
                        dpi_val = da["checks"].get("dpi")
                        dpi_str = f"{dpi_val[0]}x{dpi_val[1]}" if dpi_val else "Missing"
                        dm3.metric("DPI", dpi_str, delta="OK (>= 300)" if dpi_val and dpi_val[0] >= 300 else "Invalid")
                        fs_mb = da["checks"].get("file_size_mb", 0)
                        dm4.metric("File Size", f"{fs_mb} MB", delta="OK (<= 30MB)" if fs_mb <= 30 else "Too large")

                        if da["errors"]:
                            for err in da["errors"]:
                                st.error(f"❌ {err}")
                        if da["warnings"]:
                            for warn in da["warnings"]:
                                st.warning(f"⚠️ {warn}")
                        if not da["errors"] and not da["warnings"]:
                            st.success("✅ Perfect! This artwork fully meets Displate's technical upload requirements.")

            # Form for editing with Platform Tabs
            form_rev = st.session_state.get(f"rev_{selected_img['id']}", 0)
            form_head_c1, form_head_c2 = st.columns([3, 1])
            form_head_c1.markdown("#### 📝 Edit Platform Metadata")
            if form_head_c2.button("🔄 Reload Form", key=f"form_reset_{selected_img['id']}", use_container_width=True, help="Discard unsubmitted form edits and reload latest database values"):
                st.session_state[f"rev_{selected_img['id']}"] = form_rev + 1
                st.rerun()

            cat_options = ["Buildings and Architecture", "Travel", "Landscapes", "The Environment", "Transport", "Technology", "People", "Culture and Religion", "Industry", "Nature", "Lifestyle", "Graphic Resources"]
            is_hybrid_img = bool(selected_img.get("is_adobe_hybrid")) or bool(st.session_state.get(f"hybrid_mode_{selected_img['id']}")) or llm_client.is_hybrid_requested(selected_img.get("custom_prompt") or "")

            with st.form(key=f"edit_form_{selected_img['id']}_{form_rev}"):
                if is_hybrid_img:
                    tab_artheroes, tab_displate, tab_adobe, tab_stock = st.tabs([
                        "🎨 Art Heroes", "🏆 Displate", "🖼️ Adobe Stock (Hybrid)", "📸 Microstock (Alamy, Vecteezy, etc.)"
                    ])
                else:
                    tab_artheroes, tab_displate, tab_stock = st.tabs([
                        "🎨 Art Heroes", "🏆 Displate", "📸 Microstock (Stock)"
                    ])
                    tab_adobe = None

                with tab_artheroes:
                    new_title = st.text_input("Title (Art Heroes)", value=selected_img["title"] or "", key=f"ah_t_{selected_img['id']}_{form_rev}")
                    new_desc = st.text_area("Description (Art Heroes - 3 Paragraphs)", value=selected_img["description"] or "", height=170, key=f"ah_d_{selected_img['id']}_{form_rev}")
                    new_kws = st.text_area("Keywords / Tags (Art Heroes)", value=selected_img["keywords"] or "", height=70, key=f"ah_k_{selected_img['id']}_{form_rev}")
                    
                    ah_tags = [k.strip() for k in new_kws.split(",") if k.strip()]
                    st.caption(f"Tags: **{len(ah_tags)} / 12** {'⚠️ Exceeds 12!' if len(ah_tags) > 12 else '✅ Optimal'}")

                with tab_displate:
                    new_disp_title = st.text_input("Title (Displate - Max 60 chars)", value=selected_img.get("displate_title") or "", key=f"disp_t_{selected_img['id']}_{form_rev}")
                    disp_title_len = len(new_disp_title)
                    if disp_title_len > 60:
                        st.caption(f"⚠️ Length: **{disp_title_len} / 60 chars** (Exceeds limit!)")
                    else:
                        st.caption(f"Length: **{disp_title_len} / 60 chars** ✅")

                    new_disp_desc = st.text_area("Description (Displate - Target: 450-470 chars)", value=selected_img.get("displate_description") or "", height=170, key=f"disp_d_{selected_img['id']}_{form_rev}")
                    disp_desc_len = len(new_disp_desc)
                    if 450 <= disp_desc_len <= 470:
                        st.caption(f"Description Length: **{disp_desc_len} chars** ✅ (Target: 450-470 chars)")
                    elif disp_desc_len < 450:
                        diff = 450 - disp_desc_len
                        st.caption(f"Description Length: **{disp_desc_len} chars** ℹ️ ({diff} chars under target 450-470)")
                    else:
                        diff = disp_desc_len - 470
                        st.caption(f"Description Length: **{disp_desc_len} chars** ⚠️ ({diff} chars over target 450-470)")

                    new_disp_tags = st.text_area("Tags (Displate - Max 20)", value=selected_img.get("displate_tags") or "", height=70, key=f"disp_tags_{selected_img['id']}_{form_rev}")

                    disp_tags_list = [k.strip() for k in new_disp_tags.split(",") if k.strip()]
                    st.caption(f"Tags: **{len(disp_tags_list)} / 20** {'⚠️ Exceeds 20!' if len(disp_tags_list) > 20 else '✅ Optimal'}")

                if tab_adobe is not None:
                    with tab_adobe:
                        new_adobe_title = st.text_input(
                            "Title (Adobe Stock & Posters.cz Hybrid - Target: 6-14 words, max 200 chars)",
                            value=selected_img.get("adobe_title") or selected_img.get("stock_title") or "",
                            key=f"adb_t_{selected_img['id']}_{form_rev}"
                        )
                        adb_words = len(new_adobe_title.split())
                        adb_len = len(new_adobe_title)
                        if adb_len <= 150 and adb_words >= 5:
                            st.caption(f"Hybrid Title: **{adb_words} words ({adb_len} chars)** ✅ Optimal for Adobe Stock & Posters.cz (Limit: 200 chars)")
                        elif adb_len > 200:
                            st.caption(f"Hybrid Title: **{adb_len} / 200 chars** ⚠️ Exceeds Adobe limit!")
                        else:
                            st.caption(f"Hybrid Title: **{adb_words} words ({adb_len} chars)** ℹ️ Good for Adobe & Posters.cz")

                        new_adobe_desc = st.text_area(
                            "Description / Caption [ADOBE HYBRID / POSTERS.CZ]",
                            value=selected_img.get("adobe_description") or selected_img.get("stock_description") or "",
                            height=140,
                            key=f"adb_d_{selected_img['id']}_{form_rev}"
                        )
                        st.caption(f"Description Length: **{len(new_adobe_desc)} chars** (Combines landmark details with posters.cz room styling advice)")

                        new_adobe_kws = st.text_area(
                            "Keywords (Comma-separated, 35-45 tags for Adobe & Posters.cz)",
                            value=selected_img.get("adobe_keywords") or selected_img.get("stock_keywords") or "",
                            height=70,
                            key=f"adb_k_{selected_img['id']}_{form_rev}"
                        )
                        adb_tags_list = [k.strip() for k in new_adobe_kws.split(",") if k.strip()]
                        st.caption(f"Tags: **{len(adb_tags_list)} tags** {'✅ Optimal for Adobe & Posters.cz' if 30 <= len(adb_tags_list) <= 49 else '⚠️ Exceeds Adobe 49 tag limit!' if len(adb_tags_list) > 49 else 'ℹ️ Optimal: 35-45 tags for Adobe Hybrid'}")

                        curr_adb_cat = selected_img.get("adobe_category") or selected_img.get("stock_category") or "Travel"
                        cat_adb_idx = cat_options.index(curr_adb_cat) if curr_adb_cat in cat_options else 1
                        new_adobe_cat = st.selectbox("Adobe Stock Category", cat_options, index=cat_adb_idx, key=f"adb_cat_{selected_img['id']}_{form_rev}")
                else:
                    new_adobe_title = None
                    new_adobe_desc = None
                    new_adobe_kws = None
                    new_adobe_cat = None

                with tab_stock:
                    stock_title_label = "Title (Microstock - Target: 3-8 words, e.g. for Vecteezy, Alamy, Shutterstock)"
                    new_stock_title = st.text_input(stock_title_label, value=selected_img.get("stock_title") or "", key=f"stk_t_{selected_img['id']}_{form_rev}")
                    stock_words = len(new_stock_title.split())
                    title_len = len(new_stock_title)

                    if 3 <= stock_words <= 8:
                        st.caption(f"Title Words: **{stock_words} / 8 words** ✅ (Optimal for Vecteezy, Alamy, Shutterstock)")
                    elif stock_words > 8:
                        st.caption(f"Title Words: **{stock_words} words** ℹ️ Max 8 words recommended for microstock")
                    elif stock_words > 0:
                        st.caption(f"Title Words: **{stock_words} words** ℹ️ At least 3 words recommended")

                    stock_caption_label = "Description / Caption [FACTUAL MICROSTOCK]" + (" [EDITORIAL]" if curr_editorial else " [COMMERCIAL]")
                    new_stock_desc = st.text_area(stock_caption_label, value=selected_img.get("stock_description") or "", height=140, key=f"stk_d_{selected_img['id']}_{form_rev}", help="Pure factual description without posters.cz/wall art copywriting")
                    st.caption(f"Description Length: **{len(new_stock_desc)} chars** (Max 500 chars)")

                    kws_label = "Keywords (Comma-separated, 20-35 tags for Microstock)"
                    new_stock_kws = st.text_area(kws_label, value=selected_img.get("stock_keywords") or "", height=70, key=f"stk_k_{selected_img['id']}_{form_rev}")
                    stk_tags_list = [k.strip() for k in new_stock_kws.split(",") if k.strip()]
                    st.caption(f"Tags: **{len(stk_tags_list)} tags** {'✅ Optimal' if 20 <= len(stk_tags_list) <= 35 else 'ℹ️ Optimal: 20-30 for Vecteezy, 30-50 for Alamy'}")

                    curr_cat = selected_img.get("stock_category") or "Travel"
                    cat_idx = cat_options.index(curr_cat) if curr_cat in cat_options else 1
                    new_stock_cat = st.selectbox("Microstock Category", cat_options, index=cat_idx, key=f"stk_cat_{selected_img['id']}_{form_rev}")

                save_btn = st.form_submit_button("💾 Save All Changes to Database", type="secondary")

                if save_btn:
                    save_payload = {
                        "title": new_title,
                        "description": new_desc,
                        "keywords": new_kws,
                        "displate_title": new_disp_title,
                        "displate_description": new_disp_desc,
                        "displate_tags": new_disp_tags,
                        "stock_title": new_stock_title,
                        "stock_description": new_stock_desc,
                        "stock_keywords": new_stock_kws,
                        "stock_category": new_stock_cat,
                        "status": "GENERATED" if selected_img["status"] == "NEW" else selected_img["status"]
                    }
                    if is_hybrid_img and new_adobe_title is not None:
                        save_payload["adobe_title"] = new_adobe_title
                        save_payload["adobe_description"] = new_adobe_desc
                        save_payload["adobe_keywords"] = new_adobe_kws
                        save_payload["adobe_category"] = new_adobe_cat

                    db.update_image(selected_img["id"], **save_payload)
                    st.success("Metadata saved successfully across all platforms!")
                    st.rerun()

            # --- ONE-CLICK CLIPBOARD HUB ---
            st.divider()
            st.subheader("📋 One-Click Clipboard Copy")
            st.caption("Copy individual fields or the full bundle directly into your clipboard:")

            if is_hybrid_img:
                clip_ah, clip_disp, clip_adb, clip_stk = st.tabs(["🎨 Art Heroes", "🏆 Displate", "🖼️ Adobe Stock (Hybrid)", "📸 Microstock"])
            else:
                clip_ah, clip_disp, clip_stk = st.tabs(["🎨 Art Heroes", "🏆 Displate", "📸 Microstock"])
                clip_adb = None

            with clip_ah:
                ah_t = selected_img.get("title") or ""
                ah_d = selected_img.get("description") or ""
                ah_k = selected_img.get("keywords") or ""
                ah_bundle = f"{ah_t}\n\n{ah_d}\n\n{ah_k}".strip()

                render_clipboard_buttons({
                    "Copy Title": ah_t,
                    "Copy Description": ah_d,
                    "Copy Keywords (12)": ah_k,
                    "Copy All": ah_bundle
                }, key_prefix="ah")

            with clip_disp:
                disp_t = selected_img.get("displate_title") or ""
                disp_d = selected_img.get("displate_description") or ""
                disp_tg = selected_img.get("displate_tags") or ""
                disp_bundle = f"{disp_t}\n\n{disp_d}\n\n{disp_tg}".strip()

                render_clipboard_buttons({
                    "Copy Title (Max 60)": disp_t,
                    "Copy Description": disp_d,
                    "Copy Tags (20)": disp_tg,
                    "Copy All": disp_bundle
                }, key_prefix="disp")

            if clip_adb is not None:
                with clip_adb:
                    adb_t = selected_img.get("adobe_title") or selected_img.get("stock_title") or ""
                    adb_d = selected_img.get("adobe_description") or selected_img.get("stock_description") or ""
                    adb_k = selected_img.get("adobe_keywords") or selected_img.get("stock_keywords") or ""
                    adb_bundle = f"{adb_t}\n\n{adb_d}\n\n{adb_k}".strip()

                    render_clipboard_buttons({
                        "Copy Adobe Hybrid Title": adb_t,
                        "Copy Hybrid Description": adb_d,
                        "Copy Keywords (35-45)": adb_k,
                        "Copy All": adb_bundle
                    }, key_prefix="adb")

            with clip_stk:
                stk_t = selected_img.get("stock_title") or ""
                stk_d = selected_img.get("stock_description") or ""
                stk_k = selected_img.get("stock_keywords") or ""
                stk_bundle = f"{stk_t}\n\n{stk_d}\n\n{stk_k}".strip()

                render_clipboard_buttons({
                    "Copy Stock Title": stk_t,
                    "Copy Description / Caption": stk_d,
                    "Copy Keywords": stk_k,
                    "Copy All": stk_bundle
                }, key_prefix="stk")

            st.divider()
            st.subheader("⚡ AI Generation & Context Guidance")
            
            # Per-image specific context / notes
            saved_custom_prompt = selected_img.get("custom_prompt") or ""
            img_custom_ctx = st.text_input(
                "Image-Specific Landmark / Subject Notes (e.g. Minaret reflection, storm clouds):",
                value=saved_custom_prompt,
                key=f"custom_hint_{selected_img['id']}",
                help="Notes specific to this frame. Automatically combined with the folder-level context."
            )
            if img_custom_ctx != saved_custom_prompt:
                db.update_image(selected_img["id"], custom_prompt=img_custom_ctx)

            full_img_context = f"{folder_context}\n{img_custom_ctx}".strip()
            with st.expander("👁️ View Full Combined Context sent to AI", expanded=False):
                st.code(full_img_context or "(No context provided)")

            # Adobe Stock / Posters.cz Hybrid Mode
            hybrid_db_val = bool(selected_img.get("is_adobe_hybrid", 0))
            context_suggests_hybrid = llm_client.is_hybrid_requested(full_img_context)
            initial_hybrid_state = hybrid_db_val or context_suggests_hybrid

            adobe_hybrid_enabled = st.checkbox(
                "🖼️ Adobe Stock / Posters.cz Hybrid Mode (Stock + Interior Design Wall Art)",
                value=initial_hybrid_state,
                key=f"hybrid_mode_{selected_img['id']}",
                help="Generates high-converting hybrid stock metadata optimized for https://www.posters.cz/! Fuses factual stock landmark details with interior design wall art copywriting."
            )
            if adobe_hybrid_enabled != hybrid_db_val:
                db.update_image(selected_img["id"], is_adobe_hybrid=1 if adobe_hybrid_enabled else 0)

            if adobe_hybrid_enabled:
                st.info("💡 **Adobe / Posters.cz Hybrid Active:** Stock metadata combines factual landmark/subject details with interior design copywriting (wall art, room styling, posters.cz keywords) for optimal poster sales.")

            gen_col1, gen_col2, gen_col3, gen_col4 = st.columns(4)
            
            # Art Heroes Only
            if gen_col1.button("🎨 Art Heroes", use_container_width=True):
                if "Gemini" in engine_choice and not active_api_key:
                    st.error("Please supply Gemini API Key in the sidebar.")
                else:
                    with st.spinner("Generating Art Heroes metadata..."):
                        try:
                            meta = llm_client.generate_metadata(
                                selected_img["file_path"],
                                target="ArtHeroes",
                                engine=engine_choice,
                                api_key=active_api_key,
                                user_context=full_img_context,
                                is_editorial=new_editorial,
                                is_ai_generated=new_ai,
                                is_infrared=new_ir,
                                is_surreal=new_surreal
                            )
                            ah = meta.get("artheroes", {})
                            ah_kws = ", ".join(ah.get("keywords", [])) if isinstance(ah.get("keywords"), list) else ah.get("keywords", "")
                            db.update_image(
                                selected_img["id"],
                                title=ah.get("title"),
                                description=ah.get("description"),
                                keywords=ah_kws,
                                grade="FINE_ART" if not selected_img.get("grade") or selected_img.get("grade") == "NONE" else selected_img.get("grade"),
                                status="GENERATED"
                            )
                            st.session_state[f"rev_{selected_img['id']}"] = form_rev + 1
                            st.success("Art Heroes metadata updated!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Generation error: {e}")

            # Displate Only
            if gen_col2.button("🏆 Displate", use_container_width=True):
                if "Gemini" in engine_choice and not active_api_key:
                    st.error("Please supply Gemini API Key in the sidebar.")
                else:
                    with st.spinner("Generating Displate metadata..."):
                        try:
                            meta = llm_client.generate_metadata(
                                selected_img["file_path"],
                                target="Displate",
                                engine=engine_choice,
                                api_key=active_api_key,
                                user_context=full_img_context,
                                is_editorial=new_editorial,
                                is_ai_generated=new_ai,
                                is_infrared=new_ir,
                                is_surreal=new_surreal
                            )
                            disp = meta.get("displate", {})
                            disp_tags = ", ".join(disp.get("tags", [])) if isinstance(disp.get("tags"), list) else disp.get("tags", "")
                            db.update_image(
                                selected_img["id"],
                                displate_title=disp.get("title"),
                                displate_description=disp.get("description"),
                                displate_tags=disp_tags,
                                grade="FINE_ART" if not selected_img.get("grade") or selected_img.get("grade") == "NONE" else selected_img.get("grade"),
                                status="GENERATED"
                            )
                            st.session_state[f"rev_{selected_img['id']}"] = form_rev + 1
                            st.success("Displate metadata updated!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Generation error: {e}")

            # Stock Only
            stock_btn_label = "📸 Stock (Hybrid)" if adobe_hybrid_enabled else "📸 Stock"
            if gen_col3.button(stock_btn_label, use_container_width=True):
                if "Gemini" in engine_choice and not active_api_key:
                    st.error("Please supply Gemini API Key in the sidebar.")
                else:
                    with st.spinner("Generating Stock metadata..." if not adobe_hybrid_enabled else "Generating Adobe / Posters.cz Hybrid metadata..."):
                        try:
                            meta = llm_client.generate_metadata(
                                selected_img["file_path"],
                                target="Stock",
                                engine=engine_choice,
                                api_key=active_api_key,
                                user_context=full_img_context,
                                is_editorial=new_editorial,
                                is_ai_generated=new_ai,
                                is_infrared=new_ir,
                                is_surreal=new_surreal,
                                is_adobe_hybrid=adobe_hybrid_enabled
                            )
                            stk = meta.get("stock", {})
                            adb = meta.get("adobe", {})
                            stk_kws = ", ".join(stk.get("keywords", [])) if isinstance(stk.get("keywords"), list) else stk.get("keywords", "")
                            adb_kws = ", ".join(adb.get("keywords", [])) if isinstance(adb.get("keywords"), list) else adb.get("keywords", "")
                            curr_g = selected_img.get("grade")
                            new_g = curr_g if curr_g in ("STOCK", "BOTH") else ("BOTH" if curr_g == "FINE_ART" else "STOCK")

                            update_stock_data = {
                                "stock_title": stk.get("title"),
                                "stock_description": stk.get("description"),
                                "stock_keywords": stk_kws,
                                "stock_category": stk.get("category", "Travel"),
                                "is_adobe_hybrid": 1 if adobe_hybrid_enabled else 0,
                                "grade": new_g,
                                "status": "GENERATED"
                            }
                            if adb:
                                update_stock_data["adobe_title"] = adb.get("title")
                                update_stock_data["adobe_description"] = adb.get("description")
                                update_stock_data["adobe_keywords"] = adb_kws
                                update_stock_data["adobe_category"] = adb.get("category", "Travel")

                            db.update_image(selected_img["id"], **update_stock_data)
                            st.session_state[f"rev_{selected_img['id']}"] = form_rev + 1
                            st.success("Stock metadata updated!" if not adobe_hybrid_enabled else "Adobe Hybrid & Pure Stock metadata updated!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Generation error: {e}")

            # All Platforms
            all_btn_label = "✨ Gen All (Hybrid)" if adobe_hybrid_enabled else "✨ Gen All"
            if gen_col4.button(all_btn_label, use_container_width=True):
                if "Gemini" in engine_choice and not active_api_key:
                    st.error("Please supply Gemini API Key in the sidebar.")
                else:
                    with st.spinner("Generating All Platforms metadata (POD + Stock)..."):
                        try:
                            meta = llm_client.generate_metadata(
                                selected_img["file_path"],
                                target="All",
                                engine=engine_choice,
                                api_key=active_api_key,
                                user_context=full_img_context,
                                is_editorial=new_editorial,
                                is_ai_generated=new_ai,
                                is_infrared=new_ir,
                                is_surreal=new_surreal,
                                is_adobe_hybrid=adobe_hybrid_enabled
                            )
                            ah = meta.get("artheroes", {})
                            disp = meta.get("displate", {})
                            stk = meta.get("stock", {})
                            adb = meta.get("adobe", {})

                            ah_kws = ", ".join(ah.get("keywords", [])) if isinstance(ah.get("keywords"), list) else ah.get("keywords", "")
                            disp_tags = ", ".join(disp.get("tags", [])) if isinstance(disp.get("tags"), list) else disp.get("tags", "")
                            stk_kws = ", ".join(stk.get("keywords", [])) if isinstance(stk.get("keywords"), list) else stk.get("keywords", "")
                            adb_kws = ", ".join(adb.get("keywords", [])) if isinstance(adb.get("keywords"), list) else adb.get("keywords", "")

                            update_all_data = {
                                "title": ah.get("title"),
                                "description": ah.get("description"),
                                "keywords": ah_kws,
                                "displate_title": disp.get("title"),
                                "displate_description": disp.get("description"),
                                "displate_tags": disp_tags,
                                "stock_title": stk.get("title"),
                                "stock_description": stk.get("description"),
                                "stock_keywords": stk_kws,
                                "stock_category": stk.get("category", "Travel"),
                                "is_adobe_hybrid": 1 if adobe_hybrid_enabled else 0,
                                "grade": "BOTH",
                                "status": "GENERATED"
                            }
                            if adb:
                                update_all_data["adobe_title"] = adb.get("title")
                                update_all_data["adobe_description"] = adb.get("description")
                                update_all_data["adobe_keywords"] = adb_kws
                                update_all_data["adobe_category"] = adb.get("category", "Travel")

                            db.update_image(selected_img["id"], **update_all_data)
                            st.session_state[f"rev_{selected_img['id']}"] = form_rev + 1
                            st.success("All platforms metadata generated (including Adobe Hybrid & Pure Stock) and grade set to Dual (BOTH)!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Generation error: {e}")

            st.write("")
            # Write EXIF / IPTC / XMP to file
            ex_c1, ex_c2 = st.columns(2)
            with ex_c1:
                if st.button("💾 Embed Stock IPTC/XMP (Alamy / Adobe)", type="primary", use_container_width=True, help="Embeds Stock Title, Description, and full 30-45 keywords directly into JPEG headers via ExifTool."):
                    try:
                        exiftool_exe = stock_metadata.find_exiftool()
                        stock_metadata.apply_stock_metadata_to_image(
                            image_path=Path(selected_img["file_path"]),
                            title=selected_img.get("stock_title") or selected_img.get("title") or "",
                            description=selected_img.get("stock_description") or selected_img.get("description") or selected_img.get("stock_title") or "",
                            keywords=selected_img.get("stock_keywords") or selected_img.get("keywords") or "",
                            exiftool_path=exiftool_exe
                        )
                        db.update_image(selected_img["id"], status="APPLIED")
                        st.success("Embedded Stock IPTC/XMP metadata into JPEG header successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Stock ExifTool write failed: {e}")

            with ex_c2:
                if st.button("💾 Embed Art Heroes EXIF", use_container_width=True, help="Embeds Art Heroes POD 3-paragraph text and top 12 keywords."):
                    try:
                        exiftool_exe = find_exiftool()
                        tags_clean = [t.strip() for t in (selected_img["keywords"] or "").split(",") if t.strip()]
                        meta_payload = {
                            "title": selected_img["title"] or "",
                            "description": selected_img["description"] or "",
                            "keywords": tags_clean[:12]
                        }
                        apply_metadata_to_image(exiftool_exe, Path(selected_img["file_path"]), meta_payload)
                        db.update_image(selected_img["id"], status="APPLIED")
                        st.success("Embedded Art Heroes metadata into JPEG header successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"ExifTool write failed: {e}")


if __name__ == "__main__":
    main()
