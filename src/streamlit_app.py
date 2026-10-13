#!/usr/bin/env python3
"""Streamlit app for interactive fake-news style-risk classification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import streamlit as st

from detect_fake_news import classify_probability
from model_compat import load_pipeline as load_model_pipeline
from realtime_store import Store
from realtime_engine import RealTimeAnalyzer
from realtime_models import article_from_dict


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_pipeline_path() -> Path:
    return project_root() / "outputs" / "pipeline.joblib"


def default_metrics_path() -> Path:
    return project_root() / "outputs" / "metrics.json"


def default_realtime_db() -> Path:
    return project_root() / "outputs" / "realtime.db"


@st.cache_resource
def load_pipeline(path: str):
    return load_model_pipeline(path)


def load_metrics(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def is_short_input(text: str) -> bool:
    tokens = [token for token in text.strip().split() if token]
    return len(tokens) < 8 or len(text.strip()) < 50


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--pipeline", default=str(default_pipeline_path()))
    args, _ = parser.parse_known_args()

    pipeline_path = Path(args.pipeline).resolve()
    metrics_path = default_metrics_path()

    st.set_page_config(page_title="Misinformation Intelligence", layout="wide")
    st.title("Real-Time Misinformation Intelligence")
    st.caption("TF-IDF + Logistic Regression baseline with claim, evidence, source-risk, and review layers")

    realtime_db = default_realtime_db()
    store = Store(realtime_db)
    live_items = store.recent(100)

    with st.sidebar:
        st.subheader("Live platform")
        st.metric("Articles stored", len(live_items))
        high_risk = sum(1 for x in live_items if x.get("analysis", {}).get("risk_score", 0) >= 70) 
        uncertain = sum(1 for x in live_items if x.get("analysis", {}).get("verdict") == "UNCERTAIN")
        st.metric("High-risk", high_risk)
        st.metric("Uncertain", uncertain)
    with st.sidebar:
        st.subheader("Model")
        st.code(str(pipeline_path))
        st.write("Loaded:" if pipeline_path.exists() else "Missing:", pipeline_path.name)
        metrics = load_metrics(metrics_path)
        if metrics:
            test = metrics.get("holdout_test", {})
            st.subheader("Holdout metrics")
            st.write(f"Accuracy: **{test.get('accuracy', 0):.3f}**")
            st.write(f"Macro F1: **{test.get('macro_f1', 0):.3f}**")
            st.write(f"ROC-AUC: **{test.get('roc_auc', 0):.3f}**")
        st.warning(
            "This is an educational style-risk classifier. It can learn dataset/source artifacts "
            "and should not be used as a truth oracle."
        )

    if not pipeline_path.exists():
        st.error(
            "Model artifact not found. Run `python src/train_model.py` from the project root, "
            "then restart Streamlit."
        )
        st.stop()

    pipeline = load_pipeline(str(pipeline_path))
    st.subheader("Live feed")
    if live_items:
        for item in live_items[:12]:
            article = item["article"]
            analysis = item.get("analysis") or {}
            st.write(
                f"**{analysis.get('verdict', 'PENDING')}** · risk {analysis.get('risk_score', 0):.0f} · "
                f"{article.get('source_name') or article.get('source_domain') or 'Unknown source'} · "
                f"{article.get('title', '')}"
            )
    else:
        st.info("No ingested articles yet. Run: python src/realtime_worker.py")

    st.divider()
    st.subheader("Instant analysis")
    text = st.text_area("Paste a headline or article excerpt:", height=220)
    threshold = st.slider("FAKE decision threshold", 0.05, 0.95, 0.50, 0.01)
    uncertainty_margin = st.slider(
        "UNCERTAIN band width",
        0.00,
        0.30,
        0.10,
        0.01,
        help="A band around the threshold where the app refuses to force a REAL/FAKE label.",
    )

    if st.button("Analyze", type="primary"):
        if not text.strip():
            st.warning("Paste some text first.")
            st.stop()

        prob_fake = float(pipeline.predict_proba([text])[0, 1])
        label = classify_probability(prob_fake, threshold, uncertainty_margin)
        half_margin = uncertainty_margin / 2
        lower = max(0.0, threshold - half_margin)
        upper = min(1.0, threshold + half_margin)

        st.metric("Prediction", label, help="This is a statistical style-risk prediction, not a fact-check.")
        st.write(f"Fake probability: **{prob_fake:.1%}**")
        st.caption(f"Decision rule: REAL < {lower:.0%}, UNCERTAIN = {lower:.0%}–{upper:.0%}, FAKE > {upper:.0%}.")

        if label == "UNCERTAIN":
            st.warning(
                "The model is close to the decision boundary. Treat this as low confidence and provide a longer excerpt if possible."
            )
        elif label == "FAKE":
            st.progress(prob_fake, text=f"Displayed-label confidence proxy: {prob_fake:.1%}")
        else:
            st.progress(1 - prob_fake, text=f"Displayed-label confidence proxy: {1 - prob_fake:.1%}")

        if is_short_input(text):
            st.warning(
                "The input is very short. The model works better with full headlines or article excerpts."
            )

        st.info(
            "For real-world use, verify claims against primary sources. This model was trained on a limited educational dataset."
        )


if __name__ == "__main__":
    main()
