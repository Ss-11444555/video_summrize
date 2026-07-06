"""Text cleaning, tokenization, and redundancy removal."""

from __future__ import annotations

import re
from typing import Dict, List


MULTISPACE_PATTERN = re.compile(r"\s+")
TOKEN_PATTERN = re.compile(r"\b[\w'-]+\b")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+|\n+")


def clean_text(text: str) -> str:
    text = text.replace("\r", " ").replace("\t", " ")
    text = re.sub(r"\s*([:;,])\s*", r"\1 ", text)
    text = re.sub(r"\s*([.!?])\s*", r"\1 ", text)
    text = MULTISPACE_PATTERN.sub(" ", text)
    return text.strip()


def tokenize_words(text: str) -> List[str]:
    return TOKEN_PATTERN.findall(text.lower())


def split_sentences(text: str) -> List[str]:
    sentences = [segment.strip() for segment in SENTENCE_SPLIT_PATTERN.split(text) if segment.strip()]
    return sentences


def _sentence_signature(sentence: str) -> frozenset[str]:
    return frozenset(tokenize_words(sentence))


def _is_near_duplicate(candidate_tokens: frozenset[str], existing_tokens: frozenset[str], threshold: float) -> bool:
    if not candidate_tokens or not existing_tokens:
        return False

    overlap = len(candidate_tokens.intersection(existing_tokens))
    union = len(candidate_tokens.union(existing_tokens))
    if union == 0:
        return False

    return overlap / union >= threshold


def remove_redundant_sentences(sentences: List[str], threshold: float = 0.82) -> List[str]:
    filtered: List[str] = []
    exact_signatures = set()
    token_signatures: List[frozenset[str]] = []

    for sentence in sentences:
        normalized = clean_text(sentence).lower()
        if not normalized:
            continue

        candidate_tokens = _sentence_signature(normalized)
        if candidate_tokens in exact_signatures:
            continue

        is_redundant = any(_is_near_duplicate(candidate_tokens, existing_tokens, threshold) for existing_tokens in token_signatures)
        if not is_redundant:
            filtered.append(sentence)
            exact_signatures.add(candidate_tokens)
            token_signatures.append(candidate_tokens)

    return filtered


def preprocess_multimodal_text(transcript_text: str, captions_text: str, fused_text: str) -> Dict:
    cleaned_transcript = clean_text(transcript_text)
    cleaned_captions = clean_text(captions_text)
    cleaned_fused_text = clean_text(fused_text)

    transcript_sentences = split_sentences(cleaned_transcript)
    caption_sentences = split_sentences(cleaned_captions)
    fused_sentences = split_sentences(cleaned_fused_text)

    all_sentences = transcript_sentences + caption_sentences + fused_sentences
    non_empty_sentences = [sentence for sentence in all_sentences if sentence]
    unique_sentences = remove_redundant_sentences(non_empty_sentences)
    redundancy_removed_text = " ".join(unique_sentences).strip()

    return {
        "cleaned_transcript": cleaned_transcript,
        "cleaned_captions": cleaned_captions,
        "cleaned_fused_text": cleaned_fused_text,
        "sentences": unique_sentences,
        "redundancy_removed_text": redundancy_removed_text,
        "token_count": len(tokenize_words(redundancy_removed_text)),
    }
