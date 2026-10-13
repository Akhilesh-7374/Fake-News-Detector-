#!/usr/bin/env python3
"""Unified Command-Line Interface (CLI) for the Misinformation Intelligence Platform."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure src/ is in sys.path
SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from db.repository import Repository
from media_analyzer import MediaAnalyzer
from providers.news import CompositeNewsProvider, GoogleNewsRSSProvider, BBCNewsRSSProvider
from realtime_engine import RealTimeAnalyzer
from realtime_worker import run_once

PIPELINE_PATH = ROOT_DIR / "outputs" / "pipeline.joblib"
METRICS_PATH = ROOT_DIR / "outputs" / "metrics.json"
DB_PATH = ROOT_DIR / "outputs" / "realtime.db"


def cmd_analyze_text(args: argparse.Namespace) -> None:
    analyzer = MediaAnalyzer(RealTimeAnalyzer(args.pipeline))
    job = analyzer.analyze_text(args.text, source_name=args.source)
    res = job.analysis.get("result", {})
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print("=" * 60)
        print(f"VERDICT:    {res.get('verdict')}")
        print(f"RISK SCORE: {res.get('risk_score')}/100")
        print(f"CONFIDENCE: {res.get('confidence'):.1%}")
        print(f"ML FAKE %:  {res.get('ml_probability_fake'):.1%}")
        print("=" * 60)
        print("Decision Reasons:")
        for r in res.get("reasons", []):
            print(f"  • {r}")


def cmd_analyze_url(args: argparse.Namespace) -> None:
    analyzer = MediaAnalyzer(RealTimeAnalyzer(args.pipeline))
    job = analyzer.analyze_url(args.url)
    if job.status == "FAILED":
        print(f"Error: {job.error}", file=sys.stderr)
        sys.exit(1)
    res = job.analysis.get("result", {})
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        art = job.analysis.get("article", {})
        print(f"URL:        {args.url}")
        print(f"TITLE:      {art.get('title')}")
        print(f"VERDICT:    {res.get('verdict')}")
        print(f"RISK SCORE: {res.get('risk_score')}/100")


def cmd_analyze_file(args: argparse.Namespace) -> None:
    analyzer = MediaAnalyzer(RealTimeAnalyzer(args.pipeline))
    job = analyzer.analyze_file(Path(args.path))
    res = job.analysis.get("result", {})
    if args.json:
        print(json.dumps({"job_status": job.status, "extracted": job.extracted_text, "result": res}, indent=2))
    else:
        print(f"File:       {args.path}")
        print(f"Media Type: {job.media_type}")
        print(f"Job Status: {job.status}")
        if job.extracted_text:
            print(f"Extracted:  {job.extracted_text[:120]}...")
        if res:
            print(f"VERDICT:    {res.get('verdict')} (Risk: {res.get('risk_score')}/100)")


def cmd_ingest_news(args: argparse.Namespace) -> None:
    stats = run_once(args.pipeline, args.provider, ROOT_DIR / "demo" / "news.json", args.db, set())
    print(json.dumps(stats, indent=2))


def cmd_run_worker(args: argparse.Namespace) -> None:
    import time
    seen = set()
    print(f"[*] Starting ingestion worker (Interval: {args.interval}s, Provider: {args.provider})...")
    while True:
        stats = run_once(args.pipeline, args.provider, ROOT_DIR / "demo" / "news.json", args.db, seen)
        print(f"[{time.strftime('%X')}] Processed: {stats.get('processed')}, Seen: {stats.get('total_seen')}")
        if args.interval <= 0:
            break
        time.sleep(args.interval)


def cmd_show_article(args: argparse.Namespace) -> None:
    repo = Repository(args.db)
    art = repo.get_article(args.id)
    if not art:
        print(f"Article {args.id} not found.", file=sys.stderr)
        sys.exit(1)
    analysis = repo.get_prediction(args.id)
    claims = repo.get_claims_for_article(args.id)
    evidence = repo.get_evidence_for_article(args.id)
    payload = {"article": art, "analysis": analysis, "claims": claims, "evidence": evidence}
    print(json.dumps(payload, indent=2))


def cmd_show_metrics(args: argparse.Namespace) -> None:
    if not METRICS_PATH.exists():
        print("Metrics file not found.", file=sys.stderr)
        sys.exit(1)
    data = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    test = data.get("holdout_test", {})
    cm = test.get("confusion_matrix", [[0, 0], [0, 0]])
    print("=" * 60)
    print("MODEL EVALUATION & METRICS SUMMARY")
    print("=" * 60)
    print(f"Holdout Accuracy:  {test.get('accuracy', 0):.1%}")
    print(f"Macro F1 Score:    {test.get('macro_f1', 0):.4f}")
    print(f"ROC-AUC Score:     {test.get('roc_auc', 0):.4f}")
    print("Confusion Matrix:")
    print(f"  Actual REAL -> True Real: {cm[0][0]}, False Fake: {cm[0][1]}")
    print(f"  Actual FAKE -> False Real: {cm[1][0]}, True Fake: {cm[1][1]}")
    sc = data.get("source_confounding", {})
    print(f"Source Confounding: {sc.get('confounding_score', 0):.0%}")


def cmd_run_evaluation(args: argparse.Namespace) -> None:
    from train_model import main as train_main
    print("[*] Running full evaluation pipeline...")
    # Calls training pipeline logic
    sys.argv = ["train_model.py", "--real", str(ROOT_DIR / "data" / "True.csv"), "--fake", str(ROOT_DIR / "data" / "Fake.csv"), "--outdir", str(ROOT_DIR / "outputs")]
    train_main()


def cmd_list_alerts(args: argparse.Namespace) -> None:
    repo = Repository(args.db)
    alerts = repo.list_alerts(unacknowledged_only=args.unread)
    print(json.dumps(alerts, indent=2))


def cmd_review_queue(args: argparse.Namespace) -> None:
    repo = Repository(args.db)
    if args.action == "list":
        reviews = repo.list_reviews()
        print(json.dumps(reviews, indent=2))
    elif args.action == "submit":
        if not args.article_id or not args.decision:
            print("Error: --article-id and --decision required for submit.", file=sys.stderr)
            sys.exit(1)
        rid = repo.save_review(args.article_id, args.reviewer or "CLI", args.decision, args.notes or "")
        print(f"Review recorded: {rid}")


def cmd_health_check(args: argparse.Namespace) -> None:
    model_ok = PIPELINE_PATH.exists()
    db_ok = DB_PATH.exists()
    print("=" * 50)
    print("SYSTEM HEALTH STATUS")
    print("=" * 50)
    print(f"Baseline Model:    {'ONLINE' if model_ok else 'OFFLINE'} ({PIPELINE_PATH})")
    print(f"SQLite Store:      {'ONLINE' if db_ok else 'READY'} ({DB_PATH})")
    print(f"Overall Status:    {'HEALTHY' if model_ok else 'DEGRADED'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="TrustSignal CLI Operations Suite")
    parser.add_argument("--pipeline", type=Path, default=PIPELINE_PATH, help="Path to model pipeline")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Path to database file")

    sub = parser.add_subparsers(dest="command", required=True)

    # analyze-text
    p_text = sub.add_parser("analyze-text", help="Analyze news text")
    p_text.add_argument("--text", required=True, help="Text to classify")
    p_text.add_argument("--source", default="CLI", help="Source name")
    p_text.add_argument("--json", action="store_true", help="Output JSON")

    # analyze-url
    p_url = sub.add_parser("analyze-url", help="Scrape and analyze URL")
    p_url.add_argument("--url", required=True, help="URL to analyze")
    p_url.add_argument("--json", action="store_true", help="Output JSON")

    # analyze-file
    p_file = sub.add_parser("analyze-file", help="Analyze media file")
    p_file.add_argument("--path", required=True, help="File path")
    p_file.add_argument("--json", action="store_true", help="Output JSON")

    # ingest-news
    p_ing = sub.add_parser("ingest-news", help="Fetch and analyze latest news")
    p_ing.add_argument("--provider", default="composite", choices=["composite", "google_news", "bbc", "demo"])

    # run-worker
    p_work = sub.add_parser("run-worker", help="Run periodic ingestion loop")
    p_work.add_argument("--provider", default="composite", choices=["composite", "google_news", "bbc", "demo"])
    p_work.add_argument("--interval", type=float, default=60.0, help="Seconds between cycles")

    # show-article
    p_art = sub.add_parser("show-article", help="Show article details and analysis")
    p_art.add_argument("--id", required=True, help="Article ID")

    # show-metrics
    sub.add_parser("show-metrics", help="Display model accuracy and confusion matrix")

    # run-evaluation
    sub.add_parser("run-evaluation", help="Run full evaluation and leakage diagnostic")

    # list-alerts
    p_alt = sub.add_parser("list-alerts", help="List compliance alerts")
    p_alt.add_argument("--unread", action="store_true", help="Unacknowledged only")

    # review-queue
    p_rev = sub.add_parser("review-queue", help="Manage analyst reviews")
    p_rev.add_argument("--action", choices=["list", "submit"], default="list")
    p_rev.add_argument("--article-id", help="Article ID for submission")
    p_rev.add_argument("--reviewer", help="Reviewer identity")
    p_rev.add_argument("--decision", choices=["CONFIRMED REAL", "CONFIRMED FAKE", "UNCERTAIN", "NEED MORE EVIDENCE"])
    p_rev.add_argument("--notes", default="")

    # health-check
    sub.add_parser("health-check", help="Check system liveness and components")

    args = parser.parse_args()

    commands = {
        "analyze-text": cmd_analyze_text,
        "analyze-url": cmd_analyze_url,
        "analyze-file": cmd_analyze_file,
        "ingest-news": cmd_ingest_news,
        "run-worker": cmd_run_worker,
        "show-article": cmd_show_article,
        "show-metrics": cmd_show_metrics,
        "run-evaluation": cmd_run_evaluation,
        "list-alerts": cmd_list_alerts,
        "review-queue": cmd_review_queue,
        "health-check": cmd_health_check,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
