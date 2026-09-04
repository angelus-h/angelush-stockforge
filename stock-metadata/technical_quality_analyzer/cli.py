import argparse
import json
import os
import dataclasses
from enum import Enum
from .config import QualityConfig
from .analyzer import TechnicalQualityAnalyzer
from .reporting.diagnostic import draw_diagnostics
from .models import QualityReport, Status

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, Enum):
            return o.value
        return super().default(o)

def print_human_report(report: QualityReport):
    print("\n" + "="*40)
    print("TECHNICAL QUALITY REPORT")
    print("="*40)
    print(f"File: {report.filename}")
    print(f"Resolution: {report.width} x {report.height}")
    print(f"Format: {report.format}")
    print(f"Overall Status: {report.overall_status.value}")
    
    if report.overall_status in [Status.REVIEW, Status.HIGH_RISK]:
        print("\nATTENTION REQUIRED:")
        for det_name, det_res in report.technical_quality.items():
            if det_res.status in [Status.REVIEW, Status.HIGH_RISK]:
                print(f"- {det_name.upper()}: {det_res.status.value}")
                for w in det_res.warnings:
                    print(f"  * {w}")
    print("-" * 40)
    
    for det_name, det_res in report.technical_quality.items():
        if det_res.status not in [Status.REVIEW, Status.HIGH_RISK]:
            continue # Only print details for things that need attention to keep it concise
        print(f"\n{det_name.upper()} DETAILS")
        if det_res.score is not None:
            print(f"Score: {det_res.score:.2f}")
        if det_res.error_msg:
            print(f"- ERROR: {det_res.error_msg}")
        for k, v in det_res.metrics.items():
            if isinstance(v, list): continue
            print(f"  {k}: {v}")
    
    print("\n" + "="*40)

def main():
    parser = argparse.ArgumentParser(description="Pre-submission Technical Quality Preflight")
    parser.add_argument("input", help="Path to image or directory")
    parser.add_argument("--json", help="Path to output JSON report (optional)")
    parser.add_argument("--diagnostic", action="store_true", help="Generate diagnostic images")
    parser.add_argument("--batch", action="store_true", help="Process directory")
    parser.add_argument("--db", default="dust_fingerprints.yaml", help="Dust fingerprint DB path")
    parser.add_argument("--mode", choices=["conservative", "normal", "paranoid"], default="paranoid", help="Sensitivity mode")
    
    args = parser.parse_args()
    
    config = QualityConfig(mode=args.mode)
    analyzer = TechnicalQualityAnalyzer(config, db_path=args.db)
    
    files_to_process = []
    if args.batch:
        if not os.path.isdir(args.input):
            print(f"Error: {args.input} is not a directory.")
            return
        for root, _, files in os.walk(args.input):
            for f in files:
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.webp')):
                    files_to_process.append(os.path.join(root, f))
    else:
        files_to_process.append(args.input)
        
    all_reports = []
    
    for i, file_path in enumerate(files_to_process):
        print(f"[{i+1}/{len(files_to_process)}] Analyzing {file_path}...")
        report = analyzer.analyze_image(file_path)
        all_reports.append(report)
        
        print_human_report(report)
        
        if args.diagnostic:
            diag_path = f"{os.path.splitext(file_path)[0]}_diagnostic.jpg"
            draw_diagnostics(file_path, dataclasses.asdict(report), diag_path)
            print(f"Saved diagnostic image to {diag_path}")
            
    if args.json:
        with open(args.json, 'w') as f:
            if len(all_reports) == 1:
                json.dump(all_reports[0], f, cls=EnhancedJSONEncoder, indent=2)
            else:
                json.dump(all_reports, f, cls=EnhancedJSONEncoder, indent=2)
        print(f"Saved JSON report to {args.json}")
