"""Transparent DecisionEngine fusing ML probabilities, evidence stance, fact-checks, and source risk."""
from __future__ import annotations

from typing import Any
from realtime_models import AnalysisResult, Claim, Evidence, utc_now_iso


class DecisionEngine:
    """Fuses multi-source verification signals into explainable risk assessments.
    
    Formula:
    Risk = 100 * (0.50 * P_ML + 0.30 * S_Evidence + 0.20 * S_Source) ± Adjustments
    """

    def __init__(self, threshold: float = 0.50, uncertainty_margin: float = 0.10) -> None:
        self.threshold = threshold
        self.uncertainty_margin = uncertainty_margin

    def evaluate(
        self,
        article_id: str,
        ml_prob_fake: float,
        evidence: list[Evidence],
        source_risk: float,
        fact_check_result: dict[str, Any] | None = None,
        model_version: str = "tfidf-logreg-baseline",
    ) -> AnalysisResult:
        reasons: list[str] = []

        # 1. Base ML Probability Reason
        reasons.append(f"Baseline TF-IDF/LR classifier estimated fake-style probability at {ml_prob_fake:.1%}.")

        # 2. Evidence Score & Stance Calculation
        support_weight = sum(e.relevance_score for e in evidence if e.stance == "SUPPORTS")
        contradict_weight = sum(e.relevance_score for e in evidence if e.stance == "CONTRADICTS")
        total_ev = support_weight + contradict_weight

        if total_ev > 0:
            evidence_score = contradict_weight / total_ev
            if contradict_weight > support_weight:
                reasons.append(
                    f"External factual evidence presents more contradictions ({contradict_weight:.1f}) than support ({support_weight:.1f})."
                )
            elif support_weight > contradict_weight:
                reasons.append(
                    f"External factual evidence predominantly supports the claim entities (support: {support_weight:.1f})."
                )
            else:
                reasons.append("Retrieved external evidence contains neutral or balanced coverage.")
        else:
            evidence_score = 0.50
            reasons.append("External factual evidence was unverified or neutral; reliance shifted to stylistic and source signals.")

        # 3. Source Reputation
        normalized_source_risk = max(0.0, min(100.0, source_risk)) / 100.0
        if source_risk >= 70.0:
            reasons.append(f"Publisher domain risk is elevated ({source_risk:.0f}/100) based on historical or TLD patterns.")
        elif source_risk <= 35.0:
            reasons.append(f"Publisher domain is established with high institutional reliability ({source_risk:.0f}/100).")

        # 4. Composite Risk Computation
        composite_risk = 100.0 * (
            0.50 * ml_prob_fake
            + 0.30 * evidence_score
            + 0.20 * normalized_source_risk
        )

        # 5. Fact-Check Adjustments (if available)
        fc_status = "NOT_CHECKED"
        if fact_check_result:
            fc_status = str(fact_check_result.get("status", "NOT_CHECKED")).upper()
            if fc_status == "CONTRADICTED":
                composite_risk = min(100.0, composite_risk + 20.0)
                reasons.append("Third-party ClaimReview fact-checker verified the claim as False/Debunked (+20% risk).")
            elif fc_status == "SUPPORTED":
                composite_risk = max(0.0, composite_risk - 15.0)
                reasons.append("Third-party ClaimReview fact-checker verified the claim as Accurate (-15% risk).")

        composite_risk = max(0.0, min(100.0, composite_risk))

        # 6. Uncertainty Engine (Refuses to force binary label when within margin)
        half_margin = self.uncertainty_margin / 2.0
        lower_bound = max(0.0, self.threshold - half_margin)
        upper_bound = min(1.0, self.threshold + half_margin)

        if lower_bound <= ml_prob_fake <= upper_bound:
            ml_label = "UNCERTAIN"
        else:
            ml_label = "FAKE" if ml_prob_fake > upper_bound else "REAL"

        # Final Verdict Determination
        if ml_label == "UNCERTAIN" or (total_ev == 0 and 45.0 <= composite_risk <= 55.0):
            verdict = "UNCERTAIN"
            reasons.append(
                f"Prediction falls within the configurable uncertainty band ({lower_bound:.0%}–{upper_bound:.0%}). System abstains from forced verdict."
            )
        elif composite_risk >= 60.0:
            verdict = "LIKELY FAKE"
        else:
            verdict = "LIKELY REAL"

        # Confidence Estimation
        confidence = max(0.0, min(1.0, abs(ml_prob_fake - self.threshold) * 2.0))

        # Human Review Triggering
        human_review = (
            verdict == "UNCERTAIN"
            or fc_status in {"CONTRADICTED", "SUPPORTED"}
            or source_risk >= 70.0
            or composite_risk >= 85.0
        )

        return AnalysisResult(
            article_id=article_id,
            verdict=verdict,
            risk_score=round(composite_risk, 2),
            confidence=round(confidence, 4),
            ml_probability_fake=round(ml_prob_fake, 4),
            ml_label=ml_label,
            evidence_score=round(evidence_score, 4),
            source_risk_score=round(source_risk, 2),
            fact_check_status=fc_status,
            reasons=reasons,
            human_review_required=human_review,
            model_version=model_version,
            analyzed_at=utc_now_iso(),
        )
