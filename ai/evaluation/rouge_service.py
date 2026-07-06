"""ROUGE evaluation utilities."""

from __future__ import annotations

from typing import Dict, Optional


def evaluate_summary_with_rouge(reference_text: str, candidate_text: str) -> Dict:
    try:
        from rouge_score import rouge_scorer  # type: ignore
    except ImportError as error:
        raise RuntimeError(
            "The 'rouge-score' package is not installed. Run 'pip install -r requirements.txt' first."
        ) from error

    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    scores = scorer.score(reference_text, candidate_text)

    return {
        "rouge_1": round(scores["rouge1"].fmeasure, 4),
        "rouge_2": round(scores["rouge2"].fmeasure, 4),
        "rouge_l": round(scores["rougeL"].fmeasure, 4),
    }


def build_reference_summary(
    explicit_reference_summary: Optional[str],
    redundancy_removed_text: str,
    fallback_sentence_limit: int = 5,
) -> Dict[str, str]:
    if explicit_reference_summary and explicit_reference_summary.strip():
        return {
            "reference_summary": explicit_reference_summary.strip(),
            "evaluation_notes": "ROUGE evaluated against the stored reference summary.",
        }

    fallback_sentences = [segment.strip() for segment in redundancy_removed_text.split(".") if segment.strip()]
    fallback_reference = ". ".join(fallback_sentences[:fallback_sentence_limit]).strip()
    if fallback_reference and not fallback_reference.endswith("."):
        fallback_reference += "."

    return {
        "reference_summary": fallback_reference,
        "evaluation_notes": "ROUGE evaluated against an automatic fallback reference built from the reduced multimodal text.",
    }
