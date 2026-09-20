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
from PIL import Image

try:
    from dashboard import db, llm_client, ftp_uploader
except ImportError:
    import db, llm_client, ftp_uploader

# Force reload cached modules so the running Streamlit server immediately reflects disk changes
for mod_name in ["db", "dashboard.db", "llm_client", "dashboard.llm_client", "ftp_uploader", "dashboard.ftp_uploader"]:
    if mod_name in sys.modules and sys.modules[mod_name] is not None:
        try:
            importlib.reload(sys.modules[mod_name])
        except Exception:
            pass

from pod_workflow.ArtHeroes.apply_art_heroes_metadata import apply_metadata_to_image, find_exiftool
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
    components.html(buttons_html, height=45)


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
        st.header("⚙️ AI Engine Setup")
        
        engine_choice = st.selectbox(
            "AI Engine",
            ["Local Ollama (100% Free - $0.00)", "Google Gemini Cloud (~$0.002/img)"],
            index=0
        )

        active_api_key = ""
        if "Gemini" in engine_choice:
            env_key = os.environ.get("GEMINI_API_KEY", "")
            api_key_input = st.text_input("Gemini API Key", value=env_key, type="password")
            active_api_key = api_key_input.strip() or env_key
        else:
            st.success("💻 Running offline via local Ollama models (llava + llama3.2).")

        st.divider()
        st.header("📁 Working Directory")
        known_dirs = db.get_known_folders()
        default_folder = r"G:\upload_temp\Art-Heroes_temp"

        # Folder quick selector
        selected_known = st.selectbox(
            "Recent Folders",
            ["(Custom / Current)"] + known_dirs,
            index=0
        )
        current_folder_input = selected_known if selected_known != "(Custom / Current)" else default_folder
        folder_path = st.text_input("Active Folder Path", value=current_folder_input)
        scope_to_folder = st.checkbox("🎯 Scope catalog & batch actions to this folder", value=True)

        platform = st.selectbox("Catalog Target", ["ArtHeroes", "Displate", "ALL"], index=0)

        if st.button("🔄 Scan & Import Folder", use_container_width=True):
            try:
                stats = db.scan_and_sync_folder(folder_path, platform=platform if platform != "ALL" else "ArtHeroes")
                st.success(f"Scanned {stats['scanned']} files (Imported: {stats['imported']}, Updated: {stats['updated']})")
                st.rerun()
            except Exception as e:
                st.error(f"Scan failed: {e}")

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
        search_query = st.text_input("Search (Filename / Tag)", "")

        st.divider()
        st.subheader("📤 Export Metadata")
        export_target = st.selectbox("Export Platform", ["ArtHeroes", "Displate"])
        if st.button(f"📊 Export {export_target} CSV", use_container_width=True):
            csv_out = Path(folder_path) / f"stockforge_{export_target.lower()}_export.csv"
            saved_path = db.export_catalog_csv(csv_out, platform=export_target)
            st.success(f"Saved: {saved_path}")

        st.divider()
        with st.expander("🚀 Remote FTP Uploader", expanded=False):
            ftp_host = st.text_input("FTP Host", value="", placeholder="ftp.artheroes.com")
            ftp_col1, ftp_col2 = st.columns(2)
            ftp_port = ftp_col1.number_input("Port", value=21, min_value=1, max_value=65535)
            ftp_tls = ftp_col2.checkbox("FTPS (TLS)", value=False)
            ftp_user = st.text_input("Username", value="", placeholder="angelush")
            ftp_pass = st.text_input("Password", value="", type="password")
            ftp_remote_dir = st.text_input("Remote Path", value="", placeholder="/incoming")

            if st.button("🔌 Test Connection"):
                if not ftp_host:
                    st.warning("Please enter an FTP Host.")
                else:
                    with st.spinner("Connecting to FTP..."):
                        ok, msg = ftp_uploader.test_ftp_connection(
                            ftp_host, port=ftp_port, user=ftp_user, password=ftp_pass, use_tls=ftp_tls
                        )
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

            upload_scope = st.radio(
                "Upload Scope",
                ["Only APPLIED Images", "All Images in View"],
                index=0
            )

            if st.button("⬆️ Upload to FTP", type="primary"):
                if not ftp_host:
                    st.error("Please enter an FTP Host.")
                else:
                    current_view_imgs = db.get_images(
                        platform=platform,
                        status=status_filter,
                        search_query=search_query,
                        folder_path=folder_path if scope_to_folder and folder_path else None
                    )
                    target_imgs = [i for i in current_view_imgs if i["status"] == "APPLIED"] if "APPLIED" in upload_scope else current_view_imgs
                    if not target_imgs:
                        st.warning("No matching images to upload.")
                    else:
                        file_paths = [i["file_path"] for i in target_imgs]
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        def upload_cb(idx, total, fname, status):
                            progress_bar.progress(idx / total)
                            status_text.text(f"[{idx}/{total}] {fname}: {status}")

                        with st.spinner(f"Uploading {len(file_paths)} files..."):
                            res = ftp_uploader.upload_images(
                                ftp_host, port=ftp_port, user=ftp_user, password=ftp_pass,
                                file_paths=file_paths, remote_dir=ftp_remote_dir, use_tls=ftp_tls,
                                progress_callback=upload_cb
                            )
                            if res["uploaded"] > 0:
                                st.success(f"Successfully uploaded {res['uploaded']}/{res['total']} files!")
                            if res["failed"]:
                                st.error(f"Failed ({len(res['failed'])}): " + ", ".join([f"{Path(f).name}: {err}" for f, err in res["failed"][:3]]))

    # Fetch Images with folder scope and QC filter if enabled
    images = db.get_images(
        platform=platform,
        status=status_filter,
        search_query=search_query,
        folder_path=folder_path if scope_to_folder and folder_path else None,
        qc_status=qc_filter if qc_filter != "ALL" else None
    )

    # Top Metric Bar
    all_images = db.get_images(
        platform="ALL",
        folder_path=folder_path if scope_to_folder and folder_path else None
    )
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total in Scope", len(all_images))
    col2.metric("Untreated", len([i for i in all_images if i["status"] == "NEW"]))
    col3.metric("Metadata Ready", len([i for i in all_images if i["status"] == "GENERATED"]))
    col4.metric("Embedded EXIF", len([i for i in all_images if i["status"] == "APPLIED"]))
    qc_pass_count = len([i for i in all_images if i.get("qc_status") == "PASS"])
    col5.metric("QC Passed", f"{qc_pass_count}/{len(all_images)}", delta="Ready" if qc_pass_count == len(all_images) and len(all_images) > 0 else None)

    st.divider()

    if not images:
        st.info("No images found matching criteria. Scan a folder from the sidebar to populate.")
        return

    # Two-column layout: List on the left, Inspector on the right
    list_col, detail_col = st.columns([1.1, 1.9], gap="large")

    with list_col:
        st.subheader(f"🖼️ Images ({len(images)})")
        
        # Batch Generate button for filtered list
        new_items = [img for img in images if img["status"] == "NEW"]
        if new_items:
            st.caption(f"**{len(new_items)} unprocessed items**")
            batch_target = st.selectbox(
                "Batch Target Platform",
                ["Both", "ArtHeroes", "Displate"],
                format_func=lambda x: "Both Platforms" if x == "Both" else ("Art Heroes Only" if x == "ArtHeroes" else "Displate Only"),
                key="batch_target_select"
            )
            if st.button(f"✨ Batch Generate ({batch_target})", type="primary", use_container_width=True):
                if "Gemini" in engine_choice and not active_api_key:
                    st.error("Please provide a Gemini API Key in the sidebar.")
                else:
                    progress_bar = st.progress(0)
                    for idx, item in enumerate(new_items):
                        try:
                            item_custom = item.get("custom_prompt") or ""
                            full_batch_ctx = f"{folder_context}\n{item_custom}".strip()
                            meta = llm_client.generate_metadata(
                                item["file_path"],
                                target=batch_target,
                                engine=engine_choice,
                                api_key=active_api_key,
                                user_context=full_batch_ctx
                            )
                            update_kwargs = {"status": "GENERATED"}
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

                            db.update_image(item["id"], **update_kwargs)
                        except Exception as err:
                            st.warning(f"Error on {item['file_name']}: {err}")
                        progress_bar.progress((idx + 1) / len(new_items))
                    st.success("Batch metadata generation completed!")
                    st.rerun()

        # Image selection table / radio
        qc_icons = {"PASS": "🟢", "REVIEW": "🟠", "HIGH_RISK": "🔴", "UNCHECKED": "⚪"}
        
        def format_img_label(fname):
            item = next((i for i in images if i["file_name"] == fname), None)
            if not item:
                return fname
            st_badge = item.get("status", "NEW")
            qc_badge = qc_icons.get(item.get("qc_status") or "UNCHECKED", "⚪")
            return f"[{st_badge}] [{qc_badge}] {fname}"

        selected_file_name = st.radio(
            "Select an image to inspect & edit:",
            options=[img["file_name"] for img in images],
            format_func=format_img_label
        )

        st.divider()
        # Batch QC Audit Expander
        with st.expander(f"🔬 Batch QC Audit ({len(images)} items)", expanded=False):
            st.caption("Perform automated quality check on all displayed images and save results.")
            qc_batch_mode = st.selectbox("Batch QC Sensitivity", ["normal", "conservative", "paranoid"], index=0, key="batch_qc_mode")
            if st.button("🚀 Run QC on All Displayed Images", use_container_width=True):
                qc_progress = st.progress(0)
                qc_results = []
                config = QualityConfig(mode=qc_batch_mode)
                analyzer = TechnicalQualityAnalyzer(config)
                for idx, img_item in enumerate(images):
                    try:
                        rep = analyzer.analyze_image(img_item["file_path"])
                        sharp = rep.technical_quality.get("sharpness")
                        dust = rep.technical_quality.get("sensor_dust")
                        sharp_val = float(sharp.score) if sharp and sharp.score is not None else None
                        sharp_str = f"{sharp_val:.1f}" if sharp_val is not None else "-"
                        dust_cnt = len(dust.anomalies) if dust and hasattr(dust, "anomalies") else 0
                        warn_list = [w for d in rep.technical_quality.values() for w in d.warnings]
                        warns_str = "; ".join(warn_list)

                        # Persist to SQLite
                        db.update_image(
                            img_item["id"],
                            qc_status=rep.overall_status.value,
                            qc_sharpness=sharp_val,
                            qc_dust_count=dust_cnt,
                            qc_warnings=warns_str
                        )

                        qc_results.append({
                            "File": img_item["file_name"],
                            "QC Status": rep.overall_status.value,
                            "Sharpness": sharp_str,
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

    # Selected image object
    selected_img = next((img for img in images if img["file_name"] == selected_file_name), None)

    with detail_col:
        if selected_img:
            st.subheader(f"📝 Inspector: {selected_img['file_name']}")
            
            # Status Indicator
            status_colors = {"NEW": "🟠", "GENERATED": "🔵", "APPLIED": "🟢"}
            st.caption(f"Status: {status_colors.get(selected_img['status'], '⚪')} **{selected_img['status']}** | Path: `{selected_img['file_path']}`")

            # Image thumbnail preview
            img_path = Path(selected_img["file_path"])
            if img_path.exists():
                try:
                    with Image.open(img_path) as preview:
                        preview.thumbnail((550, 360))
                        st.image(preview, use_container_width=False)
                except Exception:
                    st.warning("Could not render image thumbnail.")

            # Technical Quality Preflight Check
            saved_qc_status = selected_img.get("qc_status") or "UNCHECKED"
            qc_header_badge = {"PASS": "🟢 PASS", "REVIEW": "🟠 REVIEW", "HIGH_RISK": "🔴 HIGH RISK", "UNCHECKED": "⚪ Not Checked"}.get(saved_qc_status, saved_qc_status)
            with st.expander(f"🔬 Technical Quality Preflight: {qc_header_badge}", expanded=(saved_qc_status != "UNCHECKED")):
                qc_col1, qc_col2 = st.columns([1.2, 1])
                qc_mode = qc_col1.selectbox("Sensitivity Mode", ["normal", "paranoid", "conservative"], index=0, key=f"qc_mode_{selected_img['id']}")
                run_qc = qc_col2.button("🔍 Run Quality Check", use_container_width=True, key=f"qc_btn_{selected_img['id']}")

                report_key = f"qc_report_{selected_img['id']}"
                if run_qc:
                    with st.spinner("Analyzing image sharpness, exposure, sensor dust..."):
                        try:
                            config = QualityConfig(mode=qc_mode)
                            analyzer = TechnicalQualityAnalyzer(config)
                            report = analyzer.analyze_image(selected_img["file_path"])
                            st.session_state[report_key] = report

                            # Persist to database
                            sharp = report.technical_quality.get("sharpness")
                            dust = report.technical_quality.get("sensor_dust")
                            sharp_val = float(sharp.score) if sharp and sharp.score is not None else None
                            dust_cnt = len(dust.anomalies) if dust and hasattr(dust, "anomalies") else 0
                            warn_list = [w for d in report.technical_quality.values() for w in d.warnings]
                            db.update_image(
                                selected_img["id"],
                                qc_status=report.overall_status.value,
                                qc_sharpness=sharp_val,
                                qc_dust_count=dust_cnt,
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
                    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                    sharp_res = rep.technical_quality.get("sharpness")
                    dust_res = rep.technical_quality.get("sensor_dust")
                    exp_res = rep.technical_quality.get("exposure")
                    dead_res = rep.technical_quality.get("dead_pixels")

                    if sharp_res:
                        score_str = f"{sharp_res.score:.1f}" if sharp_res.score is not None else "N/A"
                        mcol1.metric("Sharpness", score_str, delta="OK" if sharp_res.status == Status.PASS else "Low")
                    if dust_res:
                        cand_count = len(dust_res.anomalies) if hasattr(dust_res, "anomalies") else len(dust_res.metrics.get("candidates", []))
                        mcol2.metric("Dust Spots", cand_count, delta="Clean" if dust_res.status == Status.PASS else f"{cand_count} spots")
                    if exp_res:
                        mcol3.metric("Exposure", exp_res.status.value)
                    if dead_res:
                        mcol4.metric("Dead Pixels", dead_res.status.value)

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
                                st.image(str(diag_path), caption="Diagnostic Map (Red = Dust / Defect Candidate)", use_container_width=True)
                elif selected_img.get("qc_status") and selected_img.get("qc_status") != "UNCHECKED":
                    st.write(f"### Saved Result: **{qc_header_badge}**")
                    m1, m2 = st.columns(2)
                    sharp_val = selected_img.get("qc_sharpness")
                    m1.metric("Sharpness Score", f"{sharp_val:.1f}" if sharp_val is not None else "N/A")
                    m2.metric("Dust Candidates", selected_img.get("qc_dust_count") or 0)
                    if selected_img.get("qc_warnings"):
                        st.info(f"Warnings: {selected_img['qc_warnings']}")

            # Form for editing with Platform Tabs
            with st.form(key=f"edit_form_{selected_img['id']}"):
                tab_artheroes, tab_displate = st.tabs(["🎨 Art Heroes", "🏆 Displate"])

                with tab_artheroes:
                    new_title = st.text_input("Title (Art Heroes)", value=selected_img["title"] or "")
                    new_desc = st.text_area("Description (Art Heroes - 3 Paragraphs)", value=selected_img["description"] or "", height=170)
                    new_kws = st.text_area("Keywords / Tags (Art Heroes)", value=selected_img["keywords"] or "", height=70)
                    
                    ah_tags = [k.strip() for k in new_kws.split(",") if k.strip()]
                    st.caption(f"Tags: **{len(ah_tags)} / 12** {'⚠️ Exceeds 12!' if len(ah_tags) > 12 else '✅ Optimal'}")

                with tab_displate:
                    new_disp_title = st.text_input("Title (Displate - Max 60 chars)", value=selected_img.get("displate_title") or "")
                    disp_title_len = len(new_disp_title)
                    if disp_title_len > 60:
                        st.caption(f"⚠️ Length: **{disp_title_len} / 60 chars** (Exceeds limit!)")
                    else:
                        st.caption(f"Length: **{disp_title_len} / 60 chars** ✅")

                    new_disp_desc = st.text_area("Description (Displate - Target: 450-470 chars)", value=selected_img.get("displate_description") or "", height=170)
                    disp_desc_len = len(new_disp_desc)
                    if 450 <= disp_desc_len <= 470:
                        st.caption(f"Description Length: **{disp_desc_len} chars** ✅ (Target: 450-470 chars)")
                    elif disp_desc_len < 450:
                        diff = 450 - disp_desc_len
                        st.caption(f"Description Length: **{disp_desc_len} chars** ℹ️ ({diff} chars under target 450-470)")
                    else:
                        diff = disp_desc_len - 470
                        st.caption(f"Description Length: **{disp_desc_len} chars** ⚠️ ({diff} chars over target 450-470)")

                    new_disp_tags = st.text_area("Tags (Displate - Max 20)", value=selected_img.get("displate_tags") or "", height=70)

                    disp_tags_list = [k.strip() for k in new_disp_tags.split(",") if k.strip()]
                    st.caption(f"Tags: **{len(disp_tags_list)} / 20** {'⚠️ Exceeds 20!' if len(disp_tags_list) > 20 else '✅ Optimal'}")

                save_btn = st.form_submit_button("💾 Save All Changes to Database", type="secondary")

                if save_btn:
                    db.update_image(
                        selected_img["id"],
                        title=new_title,
                        description=new_desc,
                        keywords=new_kws,
                        displate_title=new_disp_title,
                        displate_description=new_disp_desc,
                        displate_tags=new_disp_tags,
                        status="GENERATED" if selected_img["status"] == "NEW" else selected_img["status"]
                    )
                    st.success("Metadata saved successfully for both platforms!")
                    st.rerun()

            # --- ONE-CLICK CLIPBOARD HUB ---
            st.divider()
            st.subheader("📋 One-Click Clipboard Copy")
            st.caption("Copy individual fields or the full bundle directly into your clipboard:")

            clip_ah, clip_disp = st.tabs(["🎨 Art Heroes Clipboard", "🏆 Displate Clipboard"])

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

            gen_col1, gen_col2, gen_col3 = st.columns(3)
            
            # Art Heroes Only
            if gen_col1.button("✨ Gen Art Heroes", use_container_width=True):
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
                                user_context=full_img_context
                            )
                            ah = meta.get("artheroes", {})
                            ah_kws = ", ".join(ah.get("keywords", [])) if isinstance(ah.get("keywords"), list) else ah.get("keywords", "")
                            db.update_image(
                                selected_img["id"],
                                title=ah.get("title"),
                                description=ah.get("description"),
                                keywords=ah_kws,
                                status="GENERATED"
                            )
                            st.success("Art Heroes metadata updated!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Generation error: {e}")

            # Displate Only
            if gen_col2.button("✨ Gen Displate", use_container_width=True):
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
                                user_context=full_img_context
                            )
                            disp = meta.get("displate", {})
                            disp_tags = ", ".join(disp.get("tags", [])) if isinstance(disp.get("tags"), list) else disp.get("tags", "")
                            db.update_image(
                                selected_img["id"],
                                displate_title=disp.get("title"),
                                displate_description=disp.get("description"),
                                displate_tags=disp_tags,
                                status="GENERATED"
                            )
                            st.success("Displate metadata updated!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Generation error: {e}")

            # Both Platforms
            if gen_col3.button("✨ Gen Both", use_container_width=True):
                if "Gemini" in engine_choice and not active_api_key:
                    st.error("Please supply Gemini API Key in the sidebar.")
                else:
                    with st.spinner("Generating Both platforms metadata..."):
                        try:
                            meta = llm_client.generate_metadata(
                                selected_img["file_path"],
                                target="Both",
                                engine=engine_choice,
                                api_key=active_api_key,
                                user_context=full_img_context
                            )
                            ah = meta.get("artheroes", {})
                            disp = meta.get("displate", {})
                            ah_kws = ", ".join(ah.get("keywords", [])) if isinstance(ah.get("keywords"), list) else ah.get("keywords", "")
                            disp_tags = ", ".join(disp.get("tags", [])) if isinstance(disp.get("tags"), list) else disp.get("tags", "")

                            db.update_image(
                                selected_img["id"],
                                title=ah.get("title"),
                                description=ah.get("description"),
                                keywords=ah_kws,
                                displate_title=disp.get("title"),
                                displate_description=disp.get("description"),
                                displate_tags=disp_tags,
                                status="GENERATED"
                            )
                            st.success("Both platforms metadata generated!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Generation error: {e}")

            st.write("")
            # Write EXIF to file now (Art Heroes format)
            if st.button("💾 Embed Art Heroes EXIF with ExifTool", type="primary", use_container_width=True):
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
