"""
video_studio.py
Stock Video Studio for Streamlit Dashboard.
Automated multimodal AI keyframe extraction, video telemetry, metadata generation,
people/editorial auditing, and multi-agency CSV exporting (Adobe Stock, Shutterstock, Pond5, Dreamstime).
"""

import os
import sys
import re
import json
import csv
import time
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd
from PIL import Image

try:
    from dashboard import credentials, ftp_uploader
except ImportError:
    import credentials, ftp_uploader

REPO_ROOT = Path(__file__).resolve().parent.parent
VIDEO_WORKFLOW_DIR = REPO_ROOT / "stock-video-workflow"

if str(VIDEO_WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(VIDEO_WORKFLOW_DIR))

try:
    import extract_video_keyframes as evk
    import generate_ai_metadata as gam
    import audit_lednice_editorial as ale
except ImportError:
    evk = None
    gam = None
    ale = None


SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}


def get_video_files(folder_path):
    """Returns sorted list of video files in directory."""
    try:
        p = Path(folder_path)
        if p.exists() and p.is_dir():
            return sorted([
                f for f in p.iterdir()
                if f.is_file() and f.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS and not f.name.startswith(".")
            ])
    except Exception:
        pass
    return []


def render_video_clipboard_buttons(items_dict):
    """Renders HTML buttons that write directly to the OS clipboard via JS."""
    import streamlit.components.v1 as components
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


def render_video_studio(active_api_key=""):
    """Main rendering entry point for the Stock Video Studio in Streamlit."""
    st.header("🎬 Stock Video Studio")
    st.caption("AI-powered Keyframe Extraction, Vision Telemetry, Editorial Compliance & Multi-Agency Stock Video Metadata Hub")

    # Ensure API Key is available to environment for Gemini
    if active_api_key:
        os.environ["GEMINI_API_KEY"] = active_api_key

    # Active Folder Management
    default_vid_dir = r"G:\VIDEOS\Lednice\final"
    if "active_video_dir" not in st.session_state:
        st.session_state["active_video_dir"] = default_vid_dir if Path(default_vid_dir).exists() else str(Path.home())

    vid_dir = st.session_state["active_video_dir"]

    # Top Controls Bar
    c_path, c_browse = st.columns([4, 1])
    new_path = c_path.text_input("Active Video Directory", value=vid_dir, key="video_studio_dir_input")
    if new_path != vid_dir and Path(new_path).is_dir():
        st.session_state["active_video_dir"] = os.path.normpath(new_path)
        st.rerun()

    # Discover videos and assets
    vid_files = get_video_files(vid_dir)
    frames_dir = os.path.join(vid_dir, "_temp_frames")
    metadata_dir = os.path.join(vid_dir, "_metadata")
    summary_json_path = os.path.join(frames_dir, "video_metadata_summary.json")
    cache_json_path = os.path.join(metadata_dir, "ai_metadata_cache.json")

    has_summary = os.path.exists(summary_json_path)
    has_cache = os.path.exists(cache_json_path)

    summary_data = []
    if has_summary:
        try:
            with open(summary_json_path, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
        except Exception:
            pass

    cache_data = []
    if has_cache:
        try:
            with open(cache_json_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
        except Exception:
            pass

    # Status Dashboard Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📹 Video Clips", len(vid_files))
    m2.metric("🎞️ Extracted Filmstrips", len(summary_data))
    m3.metric("🤖 AI Metadata Generated", len(cache_data))
    
    ed_count = sum(1 for c in cache_data if c.get("editorial"))
    m4.metric("📰 Editorial / Commercial", f"{ed_count} / {len(cache_data) - ed_count}" if cache_data else "0 / 0")

    st.divider()

    # Workflow Pipeline Section
    tab_pipeline, tab_catalog, tab_exports = st.tabs([
        "⚡ Automated Processing Pipeline",
        "📂 Video Catalog & Inspector",
        "📊 Agency CSV Downloads"
    ])

    with tab_pipeline:
        st.subheader("⚙️ Pipeline Configuration & Batch Operations")

        cfg_c1, cfg_c2, cfg_c3 = st.columns(3)
        default_city = "Lednice"
        default_country = "Czech Republic"
        default_hint = "Lednice Castle and Park UNESCO World Heritage site, South Moravia"

        # If summary data has location, prefill from it
        if summary_data and summary_data[0].get("location"):
            loc = summary_data[0]["location"]
            if loc.get("city") and loc["city"] != "Unknown":
                default_city = loc["city"]
            if loc.get("country") and loc["country"] != "Unknown":
                default_country = loc["country"]
            if loc.get("hint"):
                default_hint = loc["hint"]

        city_input = cfg_c1.text_input("City / Region", value=default_city)
        country_input = cfg_c2.text_input("Country", value=default_country)
        loc_hint_input = cfg_c3.text_input("Location Hint", value=default_hint)

        ctx_input = st.text_area(
            "Event & Specific Location Context (Guides Gemini AI vision analysis)",
            value="Lednice Castle, Chateau and Park, UNESCO World Heritage site, South Moravia, Czech Republic.",
            height=70
        )

        opt_c1, opt_c2 = st.columns(2)
        force_ed = opt_c1.checkbox("Force Strict Editorial Mode (All clips)", value=False)
        auto_rename = opt_c2.checkbox("Auto-Rename Video Files on Disk (Stock Best Practice)", value=True)

        st.markdown("---")

        # 3 Step Action Buttons
        btn_c1, btn_c2, btn_c3 = st.columns(3)

        with btn_c1:
            st.markdown("#### Step 1: Keyframe Extraction")
            st.caption("Extracts 5 keyframes (10%, 25%, 50%, 75%, 90%), reads GPS and telemetry into composite filmstrips.")
            if st.button("🎞️ Run Keyframe Extractor", use_container_width=True, type="primary" if not has_summary else "secondary"):
                if not vid_files:
                    st.error("No video files found in target directory!")
                else:
                    with st.spinner("Extracting keyframes & generating filmstrips..."):
                        p_bar = st.progress(0)
                        status_txt = st.empty()
                        os.makedirs(frames_dir, exist_ok=True)
                        
                        def_loc = {"city": city_input, "country": country_input, "hint": loc_hint_input}
                        extracted = []
                        for idx, vf in enumerate(vid_files):
                            status_txt.text(f"Processing ({idx+1}/{len(vid_files)}): {vf.name}")
                            res = evk.extract_frames_from_video(str(vf), frames_dir, default_loc=def_loc)
                            if res:
                                extracted.append(res)
                            p_bar.progress((idx + 1) / len(vid_files))

                        extracted.sort(key=lambda x: x["filename"])
                        with open(summary_json_path, "w", encoding="utf-8") as jf:
                            json.dump(extracted, jf, indent=2, ensure_ascii=False)

                        status_txt.text("✅ All keyframes extracted successfully!")
                        st.success(f"Extracted {len(extracted)} filmstrips into {frames_dir}")
                        st.rerun()

        with btn_c2:
            st.markdown("#### Step 2: AI Metadata Generation")
            st.caption("Sends composite filmstrips to Gemini Flash. Produces titles, descriptions, categories, keywords, and agency CSVs.")
            btn_active = has_summary and (not has_cache or len(cache_data) < len(summary_data))
            if st.button("✨ Run Gemini AI Metadata Engine", use_container_width=True, type="primary" if btn_active else "secondary"):
                if not os.environ.get("GEMINI_API_KEY"):
                    st.error("GEMINI_API_KEY is not set! Please enter your key in the sidebar.")
                elif not has_summary:
                    st.error("Please run Step 1 (Keyframe Extraction) first!")
                else:
                    with st.spinner("Analyzing filmstrips with Gemini Flash..."):
                        p_bar = st.progress(0)
                        status_txt = st.empty()
                        os.makedirs(metadata_dir, exist_ok=True)
                        model = gam.setup_gemini()

                        meta_lookup = {item["filename"]: item for item in summary_data}
                        results = list(cache_data)
                        seen_originals = {r["original_filename"] for r in results}

                        filmstrips = sorted(list(Path(frames_dir).glob("*_filmstrip.jpg")))
                        new_count = 0

                        for idx, fs in enumerate(filmstrips):
                            base_name = fs.name.replace("_filmstrip.jpg", "")
                            orig_video = next((f.name for f in vid_files if f.stem == base_name), None)
                            if not orig_video:
                                continue

                            if orig_video in seen_originals:
                                p_bar.progress((idx + 1) / len(filmstrips))
                                continue

                            status_txt.text(f"Analyzing with AI ({idx+1}/{len(filmstrips)}): {orig_video}")
                            vid_meta = meta_lookup.get(orig_video, {})
                            loc = vid_meta.setdefault("location", {})
                            if city_input: loc["city"] = city_input
                            if country_input: loc["country"] = country_input

                            meta = gam.generate_metadata(model, str(fs), vid_meta, custom_context=ctx_input, force_editorial=force_ed)
                            if meta:
                                orig_ext = Path(orig_video).suffix
                                new_name = Path(meta["new_filename"]).stem + orig_ext
                                new_name = re.sub(r'[^a-z0-9_.]', '', new_name.lower())

                                all_text = " ".join([
                                    meta.get("adobe", {}).get("title", ""),
                                    meta.get("shutterstock", {}).get("description", ""),
                                    meta.get("keywords", ""),
                                    meta.get("pond5", {}).get("title", "")
                                ]).lower()
                                if any(w in all_text for w in ["time-lapse", "timelapse", "time lapse", "hyperlapse", "fast motion"]):
                                    if "timelapse" not in new_name:
                                        new_name = f"{Path(new_name).stem}_timelapse{orig_ext}"

                                meta["new_filename"] = new_name
                                meta["original_filename"] = orig_video
                                results.append(meta)
                                seen_originals.add(orig_video)
                                new_count += 1

                                with open(cache_json_path, "w", encoding="utf-8") as f:
                                    json.dump(results, f, indent=2, ensure_ascii=False)
                                time.sleep(1.5)

                            p_bar.progress((idx + 1) / len(filmstrips))

                        # Deduplicate names
                        seen_names = {}
                        for r in results:
                            stem = Path(r["new_filename"]).stem
                            ext = Path(r["new_filename"]).suffix
                            if r["new_filename"] in seen_names:
                                seen_names[r["new_filename"]] += 1
                                r["new_filename"] = f"{stem}_{seen_names[r['new_filename']]}{ext}"
                            else:
                                seen_names[r["new_filename"]] = 1

                        with open(cache_json_path, "w", encoding="utf-8") as f:
                            json.dump(results, f, indent=2, ensure_ascii=False)

                        if auto_rename:
                            status_txt.text("Renaming video files on disk...")
                            for r in results:
                                old_p = os.path.join(vid_dir, r["original_filename"])
                                new_p = os.path.join(vid_dir, r["new_filename"])
                                if os.path.exists(old_p) and old_p != new_p:
                                    try:
                                        os.rename(old_p, new_p)
                                    except Exception:
                                        pass

                        # Regenerate CSVs
                        ale.regenerate_csvs(results, meta_lookup, metadata_dir)
                        status_txt.text(f"✅ Completed! Generated {new_count} new entries. CSVs saved.")
                        st.success("AI Metadata generation and CSV export complete!")
                        st.rerun()

        with btn_c3:
            st.markdown("#### Step 3: People & Editorial Audit")
            st.caption("Deep-scans filmstrips for people/tourists/faces. Converts commercial clips with pedestrians into compliant Editorial format.")
            if st.button("👥 Run Editorial & People Audit", use_container_width=True):
                if not os.environ.get("GEMINI_API_KEY"):
                    st.error("GEMINI_API_KEY is not set!")
                elif not has_cache:
                    st.error("Please run Step 2 (Metadata Generation) first!")
                else:
                    with st.spinner("Auditing clips for human presence..."):
                        p_bar = st.progress(0)
                        status_txt = st.empty()
                        model = ale.setup_gemini()
                        meta_lookup = {item["filename"]: item for item in summary_data}

                        audit_cache_file = os.path.join(metadata_dir, "people_audit_cache.json")
                        audit_cache = {}
                        if os.path.exists(audit_cache_file):
                            try:
                                with open(audit_cache_file, "r", encoding="utf-8") as f:
                                    audit_cache = json.load(f)
                            except Exception:
                                pass

                        updated_count = 0
                        for idx, item in enumerate(cache_data):
                            new_fn = item.get("new_filename", "")
                            orig_fn = item.get("original_filename", "")
                            base_orig = Path(orig_fn).stem
                            status_txt.text(f"Auditing ({idx+1}/{len(cache_data)}): {new_fn}")

                            if not item.get("editorial", False):
                                fs_path = os.path.join(frames_dir, f"{base_orig}_filmstrip.jpg")
                                if os.path.exists(fs_path):
                                    res = audit_cache.get(new_fn)
                                    if not res:
                                        res = ale.detect_people_in_filmstrip(model, fs_path, new_fn)
                                        if res:
                                            audit_cache[new_fn] = res
                                            with open(audit_cache_file, "w", encoding="utf-8") as f:
                                                json.dump(audit_cache, f, indent=2, ensure_ascii=False)
                                            time.sleep(1)

                                    if res and res.get("people_visible"):
                                        item["editorial"] = True
                                        updated_count += 1
                                        vid_meta = meta_lookup.get(orig_fn, {})
                                        date_rec = vid_meta.get("date_recorded", "2024-09-29 12:00:00")
                                        ed_date = ale.format_editorial_date(date_rec)
                                        p5_date = ale.format_pond5_editorial_date(date_rec)

                                        desc_txt = res.get("editorial_description", "").strip() or "Tourists explore the historic castle grounds."
                                        item.setdefault("shutterstock", {})["description"] = f"{city_input}, {country_input} - {ed_date}: {desc_txt}"
                                        item["shutterstock"]["categories"] = "people,buildings/landmarks"

                                        item.setdefault("pond5", {})["title"] = f"{city_input}, {country_input} {p5_date}: Tourists in Park Scene"
                                        item["pond5"]["description"] = f"{city_input}, {country_input} {p5_date}: {desc_txt}"

                                        item.setdefault("dreamstime", {})["video_name"] = f"{city_input}, {country_input} - {ed_date}: Tourists in Park"
                                        item["dreamstime"]["description"] = f"{city_input}, {country_input} - {ed_date}: {desc_txt}"

                            p_bar.progress((idx + 1) / len(cache_data))

                        with open(cache_json_path, "w", encoding="utf-8") as f:
                            json.dump(cache_data, f, indent=2, ensure_ascii=False)

                        ale.regenerate_csvs(cache_data, meta_lookup, metadata_dir)
                        status_txt.text(f"✅ Audit complete! Converted {updated_count} clips to Editorial.")
                        st.success(f"Audit finished. {updated_count} clips converted to Editorial.")
                        st.rerun()

    with tab_catalog:
        st.subheader("📂 Interactive Video Catalog & Metadata Editor")

        if not cache_data:
            st.info("No AI metadata generated yet. Run Step 1 and Step 2 in the Automated Processing Pipeline tab.")
        else:
            cat_filter_col1, cat_filter_col2 = st.columns([2, 1])
            search_term = cat_filter_col1.text_input("🔍 Search video metadata (Filename, Title, Keyword)", "")
            filter_mode = cat_filter_col2.selectbox("License Filter", ["ALL", "Editorial Only", "Commercial Only"])

            filtered_cache = cache_data
            if search_term:
                s_lower = search_term.lower()
                filtered_cache = [
                    c for c in filtered_cache
                    if s_lower in c.get("new_filename", "").lower()
                    or s_lower in c.get("adobe", {}).get("title", "").lower()
                    or s_lower in c.get("shutterstock", {}).get("description", "").lower()
                    or s_lower in c.get("keywords", "").lower()
                ]

            if filter_mode == "Editorial Only":
                filtered_cache = [c for c in filtered_cache if c.get("editorial")]
            elif filter_mode == "Commercial Only":
                filtered_cache = [c for c in filtered_cache if not c.get("editorial")]

            st.caption(f"Showing **{len(filtered_cache)}** of **{len(cache_data)}** clips")

            if filtered_cache:
                selected_fn = st.selectbox(
                    "Select Video Clip to Inspect & Edit:",
                    [c["new_filename"] for c in filtered_cache],
                    key="video_item_selector"
                )

                item = next(c for c in filtered_cache if c["new_filename"] == selected_fn)
                orig_fn = item.get("original_filename", "")
                base_orig = Path(orig_fn).stem
                filmstrip_path = os.path.join(frames_dir, f"{base_orig}_filmstrip.jpg")

                v_col_left, v_col_right = st.columns([1.1, 1.4])

                with v_col_left:
                    st.markdown(f"#### 🎞️ Filmstrip: `{item['new_filename']}`")
                    if os.path.exists(filmstrip_path):
                        st.image(filmstrip_path, width="stretch")
                    else:
                        st.caption("No filmstrip contact sheet found.")

                    meta_info = next((s for s in summary_data if s["filename"] == orig_fn), None)
                    if meta_info:
                        st.markdown(f"""
                        - **Resolution:** `{meta_info.get('resolution')}` ({'4K' if meta_info.get('is_4k') else 'HD'})
                        - **Duration:** `{meta_info.get('duration_seconds')}s` | **FPS:** `{meta_info.get('fps')}`
                        - **Recorded:** `{meta_info.get('date_recorded')}`
                        - **GPS:** `{meta_info.get('gps_latitude')}, {meta_info.get('gps_longitude')}`
                        """)

                    is_ed = item.get("editorial", False)
                    new_ed = st.checkbox("Editorial License (Tourists / Recognizable people / Trademarks)", value=is_ed, key=f"ed_toggle_{item['new_filename']}")
                    if new_ed != is_ed:
                        item["editorial"] = new_ed
                        with open(cache_json_path, "w", encoding="utf-8") as f:
                            json.dump(cache_data, f, indent=2, ensure_ascii=False)
                        ale.regenerate_csvs(cache_data, {s['filename']: s for s in summary_data}, metadata_dir)
                        st.rerun()

                with v_col_right:
                    st.markdown("#### 📝 Edit Agency Metadata")
                    p_tab_adobe, p_tab_shutter, p_tab_pond5, p_tab_dream = st.tabs([
                        "Adobe Stock", "Shutterstock", "Pond5", "Dreamstime"
                    ])

                    with p_tab_adobe:
                        ad_t = st.text_input("Adobe Title (Max 70 chars, plain text, no commas/periods)", value=item.get("adobe", {}).get("title", ""), key=f"ad_t_{item['new_filename']}")
                        st.caption(f"Characters: **{len(ad_t)} / 70**")
                        ad_cat = st.text_input("Adobe Category ID (e.g. 2=Architecture, 21=Travel, 11=Nature)", value=str(item.get("adobe", {}).get("category", "21")), key=f"ad_c_{item['new_filename']}")

                    with p_tab_shutter:
                        sh_d = st.text_area("Shutterstock Description (Dateline required if Editorial)", value=item.get("shutterstock", {}).get("description", ""), height=100, key=f"sh_d_{item['new_filename']}")
                        sh_c = st.text_input("Shutterstock Categories (1 or 2, comma separated)", value=item.get("shutterstock", {}).get("categories", "buildings/landmarks"), key=f"sh_c_{item['new_filename']}")

                    with p_tab_pond5:
                        p5_t = st.text_input("Pond5 Title (Strictly 40-80 chars)", value=item.get("pond5", {}).get("title", ""), key=f"p5_t_{item['new_filename']}")
                        st.caption(f"Characters: **{len(p5_t)} / 80** ({'✅ Optimal' if 40 <= len(p5_t) <= 80 else '⚠️ Out of bounds'})")
                        p5_d = st.text_area("Pond5 Description", value=item.get("pond5", {}).get("description", ""), height=100, key=f"p5_d_{item['new_filename']}")

                    with p_tab_dream:
                        dt_n = st.text_input("Dreamstime Video Name", value=item.get("dreamstime", {}).get("video_name", ""), key=f"dt_n_{item['new_filename']}")
                        dt_d = st.text_area("Dreamstime 5 Ws Description", value=item.get("dreamstime", {}).get("description", ""), height=100, key=f"dt_d_{item['new_filename']}")
                        dt_cats = st.text_input("Dreamstime Category IDs (Comma separated)", value=f"{item.get('dreamstime', {}).get('cat1','70')}, {item.get('dreamstime', {}).get('cat2','59')}, {item.get('dreamstime', {}).get('cat3','72')}", key=f"dt_cats_{item['new_filename']}")

                    kws_input = st.text_area("Keywords (25-45 comma separated tags)", value=item.get("keywords", ""), height=80, key=f"kws_{item['new_filename']}")
                    kw_list = [k.strip() for k in kws_input.split(",") if k.strip()]
                    st.caption(f"Tags count: **{len(kw_list)} tags** ({'✅ Optimal' if 25 <= len(kw_list) <= 45 else '⚠️ Should be 25-45 tags'})")

                    if st.button("💾 Save Metadata to Database & Refresh CSVs", type="primary", use_container_width=True):
                        item.setdefault("adobe", {})["title"] = ad_t
                        item["adobe"]["category"] = ad_cat
                        item.setdefault("shutterstock", {})["description"] = sh_d
                        item["shutterstock"]["categories"] = sh_c
                        item.setdefault("pond5", {})["title"] = p5_t
                        item["pond5"]["description"] = p5_d
                        item.setdefault("dreamstime", {})["video_name"] = dt_n
                        item["dreamstime"]["description"] = dt_d

                        # parse dreamstime categories
                        cat_parts = [c.strip() for c in dt_cats.split(",") if c.strip()]
                        if len(cat_parts) >= 1: item["dreamstime"]["cat1"] = cat_parts[0]
                        if len(cat_parts) >= 2: item["dreamstime"]["cat2"] = cat_parts[1]
                        if len(cat_parts) >= 3: item["dreamstime"]["cat3"] = cat_parts[2]

                        item["keywords"] = kws_input

                        with open(cache_json_path, "w", encoding="utf-8") as f:
                            json.dump(cache_data, f, indent=2, ensure_ascii=False)
                        ale.regenerate_csvs(cache_data, {s['filename']: s for s in summary_data}, metadata_dir)
                        st.success("Metadata updated and CSVs regenerated!")
                        st.rerun()

                    # One-Click Clipboard Hub for Videos
                    st.divider()
                    st.markdown("##### 📋 Quick Clipboard Copy")
                    render_video_clipboard_buttons({
                        "Adobe Title": ad_t,
                        "Shutterstock Desc": sh_d,
                        "Pond5 Title": p5_t,
                        "Keywords": kws_input
                    })

    with tab_exports:
        st.subheader("📊 Multi-Agency Ready-to-Upload CSV Hub")
        st.caption(f"All files exported directly into: `{metadata_dir}`")

        csv_files = [
            ("Adobe Stock", "adobe_stock_video.csv"),
            ("Shutterstock", "shutterstock_video.csv"),
            ("Pond5", "pond5_video.csv"),
            ("Dreamstime", "dreamstime_video.csv"),
        ]

        exp_c1, exp_c2, exp_c3, exp_c4 = st.columns(4)
        for col, (agency, csv_name) in zip([exp_c1, exp_c2, exp_c3, exp_c4], csv_files):
            p = os.path.join(metadata_dir, csv_name)
            if os.path.exists(p):
                with open(p, "rb") as f:
                    col.download_button(
                        label=f"📥 Download {agency} CSV",
                        data=f.read(),
                        file_name=csv_name,
                        mime="text/csv",
                        use_container_width=True
                    )
            else:
                col.button(f"⚪ {agency} (Not Generated)", disabled=True, use_container_width=True)

        st.divider()

        # Preview Data Table
        selected_csv = st.selectbox("Inspect Exported CSV Table:", [c[1] for c in csv_files])
        inspect_p = os.path.join(metadata_dir, selected_csv)
        if os.path.exists(inspect_p):
            try:
                df = pd.read_csv(inspect_p)
                st.dataframe(df, use_container_width=True)
            except Exception as e:
                st.error(f"Error reading CSV: {e}")
        else:
            st.info("Selected CSV has not been generated yet.")

        # --- DIRECT VIDEO FTP / SFTP BATCH DELIVERY HUB ---
        st.divider()
        st.subheader("🚀 Direct Video Remote FTP / SFTP Delivery Hub")
        st.caption("Upload full-resolution MP4/MOV footage directly to Pond5, Dreamstime, Adobe Stock, and other agencies.")

        v_folder = Path(folder_path)
        v_files = sorted([f for f in v_folder.iterdir() if f.is_file() and f.suffix.lower() in [".mp4", ".mov", ".mkv", ".avi"]])

        vid_agencies = ["Pond5", "Dreamstime", "Adobe Stock", "Shutterstock", "Depositphotos", "Custom FTP / SFTP"]
        v_agency = st.selectbox("Select Target Video Agency Profile:", vid_agencies, index=0, key="vid_agency_select")

        # Load Agency Config & Presets
        v_preset = credentials.AGENCY_PRESETS.get(v_agency, {})
        v_default_user = v_preset.get("default_user", "")
        v_default_rdir = "video" if v_agency == "Dreamstime" else v_preset.get("remote_dir", "/")
        v_default_proto = v_preset.get("protocol", "ftp")
        v_default_port = v_preset.get("port", 21)
        v_default_host = v_preset.get("host", "")
        v_cred_key = v_preset.get("cred_key", f"{v_agency.upper().replace(' ', '_')}_PASSWORD")

        v_pass_saved = credentials.get_secret(v_cred_key, default="")

        v_col1, v_col2, v_col3 = st.columns([1.5, 1.2, 1])
        u_host = v_col1.text_input("Server Host:", value=v_default_host, key=f"v_host_{v_agency}")
        u_user = v_col2.text_input("Username / ID:", value=v_default_user, key=f"v_user_{v_agency}")
        u_port = v_col3.number_input("Port:", value=int(v_default_port), min_value=1, max_value=65535, key=f"v_port_{v_agency}")

        v_c4, v_c5 = st.columns([1.5, 1.5])
        u_proto = v_c4.selectbox("Protocol:", ["ftp", "sftp", "ftps"], index=["ftp", "sftp", "ftps"].index(v_default_proto), key=f"v_proto_{v_agency}")
        u_rdir = v_c5.text_input("Remote Path:", value=v_default_rdir, key=f"v_rdir_{v_agency}", help="For Dreamstime video footage, this MUST be 'video' (cd video; mput *.mp4).")

        v_pass_input = st.text_input(
            f"{v_agency} Password" + (" (🔒 Loaded)" if v_pass_saved else " (🔑 Missing)"),
            value=v_pass_saved,
            type="password",
            key=f"v_pass_input_{v_agency}",
            help=f"Password for {v_agency}. Stored securely in Windows Credential Manager & .env."
        )
        if v_pass_input and v_pass_input != v_pass_saved:
            credentials.set_secret(v_cred_key, v_pass_input)
            v_pass_saved = v_pass_input

        active_v_pass = v_pass_input or v_pass_saved

        if v_agency == "Pond5":
            st.info("💡 **Pond5 Video Delivery:** Standard FTP to `ftp://ftp.pond5.com/` as `AngelusH`. Files will be uploaded to root `/`.")
        elif v_agency == "Dreamstime":
            st.info("💡 **Dreamstime Video Delivery:** Passive mode FTP to `upload.dreamstime.com` as `61235210`. Target folder: `video`.")

        v_btn_c1, v_btn_c2 = st.columns([1, 1.8])
        if v_btn_c1.button("🔌 Test Agency Connection", key=f"v_test_{v_agency}", use_container_width=True):
            if not u_host or not u_user:
                st.warning("Please provide server host and username.")
            else:
                if active_v_pass and active_v_pass != v_pass_saved:
                    credentials.set_secret(v_cred_key, active_v_pass)
                with st.spinner(f"Testing {u_proto.upper()} connection to {u_host}..."):
                    ok, test_msg = ftp_uploader.test_connection(
                        u_host, port=int(u_port), user=u_user, password=active_v_pass,
                        protocol=u_proto, remote_dir=u_rdir
                    )
                    if ok:
                        st.success(test_msg)
                    else:
                        st.error(test_msg)

        if not v_files:
            st.warning(f"No video files (.mp4, .mov) found in folder: `{folder_path}`")
        else:
            st.caption(f"📁 **{len(v_files)} video file(s) available for upload in current folder.**")
            if v_btn_c2.button(f"⬆️ Upload {len(v_files)} Video(s) to {v_agency}", type="primary", use_container_width=True, key=f"v_up_btn_{v_agency}"):
                if not u_host or not u_user or not active_v_pass:
                    st.error(f"Missing host, user, or password for {v_agency}. Please type your password above.")
                else:
                    if active_v_pass and active_v_pass != v_pass_saved:
                        credentials.set_secret(v_cred_key, active_v_pass)

                    vid_paths = [str(f) for f in v_files]
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    def v_upload_cb(idx, total, fname, status):
                        progress_bar.progress(idx / total)
                        status_text.text(f"[{idx}/{total}] {fname}: {status}")

                    with st.spinner(f"Uploading {len(vid_paths)} video file(s) to {v_agency} ({u_host})..."):
                        try:
                            res = ftp_uploader.upload_files(
                                u_host, port=int(u_port), user=u_user, password=active_v_pass,
                                file_paths=vid_paths, protocol=u_proto, remote_dir=u_rdir,
                                progress_callback=v_upload_cb
                            )
                            if res["uploaded"] > 0:
                                st.success(f"🎉 **UPLOAD SUCCESSFUL!** {res['uploaded']}/{res['total']} video(s) uploaded to **{v_agency}** successfully!")
                                st.toast(f"✅ {res['uploaded']} video(s) uploaded to {v_agency}!", icon="🚀")
                            if res.get("error"):
                                st.error(f"❌ Connection error: {res['error']}")
                                st.toast(f"❌ Connection error: {v_agency}", icon="⚠️")
                            if res["failed"]:
                                st.error(f"Failed ({len(res['failed'])}): " + ", ".join([f"{Path(f).name}: {err}" for f, err in res["failed"][:3]]))
                                st.toast(f"⚠️ {len(res['failed'])} file(s) failed!", icon="⚠️")
                        except Exception as up_err:
                            st.error(f"❌ Unexpected error during video upload: {up_err}")
                            st.toast("❌ Unexpected error", icon="⚠️")
