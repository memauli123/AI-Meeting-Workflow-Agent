"""
Batch Processor — Meeting Agent Pipeline
Process a folder of transcript files concurrently using a thread pool.
Outputs one JSON result file per transcript + a combined batch summary.

Usage:
    python -m src.batch --input transcripts/ --output outputs/batch/ --date 2025-07-14
    python -m src.batch --input transcripts/ --workers 6 --format all
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from src.pipeline import run_pipeline
from src.exporters import export_all, export_json


# ── Core batch logic ──────────────────────────────────────────────────────────

def process_one(
    transcript_path: str,
    output_dir: str,
    meeting_date: str = None,
    export_fmt: str = "json",
) -> dict:
    """
    Run the pipeline on a single transcript file.

    Returns a result dict with:
      - path, status, duration_seconds
      - output (pipeline result) or error
      - exported_files (paths written)
    """
    stem = Path(transcript_path).stem
    start = time.time()

    try:
        with open(transcript_path, encoding="utf-8") as f:
            transcript = f.read()

        result = run_pipeline(transcript, meeting_date)
        duration = round(time.time() - start, 2)

        # Export
        exported = {}
        if export_fmt == "all":
            exported = export_all(result, output_dir, stem)
        else:
            ext = "md" if export_fmt == "markdown" else export_fmt
            path = os.path.join(output_dir, f"{stem}.{ext}")
            from src.exporters import export
            export(result, export_fmt, path)
            exported[export_fmt] = path

        return {
            "file": transcript_path,
            "stem": stem,
            "status": "success",
            "duration_seconds": duration,
            "task_count": len(result["tasks"]),
            "risk_count": len(result["risks_or_blockers"]),
            "high_risk": sum(1 for r in result["risks_or_blockers"] if r["severity"] == "HIGH"),
            "exported": exported,
            "output": result,
        }

    except Exception as e:
        return {
            "file": transcript_path,
            "stem": stem,
            "status": "error",
            "duration_seconds": round(time.time() - start, 2),
            "error": str(e),
            "output": None,
            "exported": {},
        }


def run_batch(
    input_dir: str,
    output_dir: str,
    meeting_date: str = None,
    max_workers: int = 4,
    export_fmt: str = "json",
    glob: str = "*.txt",
) -> dict:
    """
    Process all transcript files in input_dir using a thread pool.

    Returns a batch summary dict.
    """
    os.makedirs(output_dir, exist_ok=True)

    files = sorted(Path(input_dir).glob(glob))
    if not files:
        raise FileNotFoundError(f"No {glob} files found in: {input_dir}")

    print(f"[Batch] Processing {len(files)} transcripts with {max_workers} workers...")
    batch_start = time.time()

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(process_one, str(f), output_dir, meeting_date, export_fmt): f
            for f in files
        }
        for future in as_completed(futures):
            r = future.result()
            status = "✓" if r["status"] == "success" else "✗"
            print(f"  {status} {r['stem']} ({r['duration_seconds']}s)")
            results.append(r)

    # Sort results by filename for deterministic output
    results.sort(key=lambda r: r["file"])

    total_duration = round(time.time() - batch_start, 2)
    success = [r for r in results if r["status"] == "success"]
    failed  = [r for r in results if r["status"] == "error"]

    summary = {
        "batch_run_at": datetime.now().isoformat(),
        "input_dir": input_dir,
        "output_dir": output_dir,
        "meeting_date": meeting_date,
        "total_files": len(files),
        "succeeded": len(success),
        "failed": len(failed),
        "total_duration_seconds": total_duration,
        "total_tasks_extracted": sum(r.get("task_count", 0) for r in success),
        "total_risks_detected": sum(r.get("risk_count", 0) for r in success),
        "total_high_risks": sum(r.get("high_risk", 0) for r in success),
        "results": results,
        "errors": [{"file": r["file"], "error": r["error"]} for r in failed],
    }

    # Write batch summary
    summary_path = os.path.join(output_dir, "_batch_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        # Exclude full output from summary to keep it readable
        slim = {k: v for k, v in summary.items() if k != "results"}
        slim["result_files"] = [r.get("exported", {}) for r in results]
        json.dump(slim, f, indent=2, ensure_ascii=False)

    print(f"\n[Batch] Done. {len(success)}/{len(files)} succeeded in {total_duration}s.")
    print(f"[Batch] Summary written to: {summary_path}")
    return summary


# ── CLI entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch-process transcript files through the pipeline")
    parser.add_argument("--input",   required=True, help="Directory of .txt transcript files")
    parser.add_argument("--output",  default="outputs/batch", help="Output directory")
    parser.add_argument("--date",    metavar="YYYY-MM-DD", help="Meeting date for deadline normalization")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--format",  choices=["json", "markdown", "csv", "all"], default="json")
    parser.add_argument("--glob",    default="*.txt", help="File glob pattern (default: *.txt)")
    args = parser.parse_args()

    summary = run_batch(
        input_dir=args.input,
        output_dir=args.output,
        meeting_date=args.date,
        max_workers=args.workers,
        export_fmt=args.format,
        glob=args.glob,
    )

    if summary["failed"] > 0:
        print("\nFailed files:")
        for e in summary["errors"]:
            print(f"  {e['file']}: {e['error']}")
        sys.exit(1)
