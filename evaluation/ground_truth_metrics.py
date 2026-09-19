"""
Módulo de métricas cuantitativas frente a Ground Truth humano (TFG AIPost).

Calcula las diferencias objetivas y similitudes entre una publicación generada
(AIPost, ChatGPT, Gemini, baselines) y el post real escrito por humanos en LinkedIn:
1. Similitud semántica vectorial (Cosine Similarity con embeddings de Gemini).
2. Métricas de solapamiento n-gramas: ROUGE-1, ROUGE-2 y ROUGE-L (LCS).
3. Puntuación BLEU con smoothing y penalización por brevedad.
4. Alineación de hashtags de marca (Precision, Recall, Jaccard, presencia de #LifeAtBBVA).
5. Cobertura de hechos clave (Key Facts Coverage).
6. Ratio de longitud y estructura.
"""
from __future__ import annotations

import re
import math
from typing import Dict, Any, List, Tuple
import numpy as np

from src.core.logger import logger


def _tokenize(text: str) -> List[str]:
    """Tokeniza texto a palabras en minúscula, eliminando puntuación y acentos residuales."""
    text = text.lower()
    # Conservamos letras, números y hashtags como tokens
    tokens = re.findall(r'#?\w+', text)
    return tokens


def _get_ngrams(tokens: List[str], n: int) -> List[Tuple[str, ...]]:
    """Genera n-gramas a partir de una lista de tokens."""
    if len(tokens) < n:
        return []
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def compute_rouge(candidate: str, reference: str) -> Dict[str, float]:
    """
    Calcula ROUGE-1, ROUGE-2 y ROUGE-L entre un texto candidato y la referencia humana.
    Devuelve precision, recall y F1 para cada uno.
    """
    cand_tokens = _tokenize(candidate)
    ref_tokens = _tokenize(reference)

    if not cand_tokens or not ref_tokens:
        return {
            "rouge1_f1": 0.0, "rouge1_recall": 0.0, "rouge1_precision": 0.0,
            "rouge2_f1": 0.0, "rouge2_recall": 0.0, "rouge2_precision": 0.0,
            "rougeL_f1": 0.0, "rougeL_recall": 0.0, "rougeL_precision": 0.0,
        }

    def _n_gram_rouge(n: int) -> Tuple[float, float, float]:
        cand_ngrams = _get_ngrams(cand_tokens, n)
        ref_ngrams = _get_ngrams(ref_tokens, n)
        if not ref_ngrams:
            return 0.0, 0.0, 0.0

        ref_counts: Dict[Tuple[str, ...], int] = {}
        for ng in ref_ngrams:
            ref_counts[ng] = ref_counts.get(ng, 0) + 1

        overlap = 0
        cand_counts: Dict[Tuple[str, ...], int] = {}
        for ng in cand_ngrams:
            cand_counts[ng] = cand_counts.get(ng, 0) + 1
            if cand_counts[ng] <= ref_counts.get(ng, 0):
                overlap += 1

        rec = overlap / len(ref_ngrams) if ref_ngrams else 0.0
        prec = overlap / len(cand_ngrams) if cand_ngrams else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        return round(prec, 4), round(rec, 4), round(f1, 4)

    # ROUGE-1 y ROUGE-2
    r1_p, r1_r, r1_f = _n_gram_rouge(1)
    r2_p, r2_r, r2_f = _n_gram_rouge(2)

    # ROUGE-L basado en Longest Common Subsequence (LCS)
    m, n = len(cand_tokens), len(ref_tokens)
    # Matriz para LCS (optimización de memoria con dos filas)
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if cand_tokens[i - 1] == ref_tokens[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev, curr = curr, [0] * (n + 1)
    lcs_len = prev[n]

    rl_p = lcs_len / m if m > 0 else 0.0
    rl_r = lcs_len / n if n > 0 else 0.0
    rl_f = (2 * rl_p * rl_r / (rl_p + rl_r)) if (rl_p + rl_r) > 0 else 0.0

    return {
        "rouge1_precision": r1_p,
        "rouge1_recall": r1_r,
        "rouge1_f1": r1_f,
        "rouge2_precision": r2_p,
        "rouge2_recall": r2_r,
        "rouge2_f1": r2_f,
        "rougeL_precision": round(rl_p, 4),
        "rougeL_recall": round(rl_r, 4),
        "rougeL_f1": round(rl_f, 4),
    }


def compute_bleu(candidate: str, reference: str, max_n: int = 4) -> float:
    """
    Calcula la métrica BLEU con penalización por brevedad y suavizado aditivo (Chen & Cherry).
    """
    cand_tokens = _tokenize(candidate)
    ref_tokens = _tokenize(reference)

    c_len = len(cand_tokens)
    r_len = len(ref_tokens)
    if c_len == 0 or r_len == 0:
        return 0.0

    # Brevity Penalty (BP)
    if c_len > r_len:
        bp = 1.0
    else:
        bp = math.exp(1 - (r_len / c_len))

    weights = [1.0 / max_n] * max_n
    precisions = []

    for i in range(1, max_n + 1):
        cand_ng = _get_ngrams(cand_tokens, i)
        ref_ng = _get_ngrams(ref_tokens, i)
        if not cand_ng:
            precisions.append(0.0)
            continue

        ref_counts: Dict[Tuple[str, ...], int] = {}
        for ng in ref_ng:
            ref_counts[ng] = ref_counts.get(ng, 0) + 1

        overlap = 0
        cand_counts: Dict[Tuple[str, ...], int] = {}
        for ng in cand_ng:
            cand_counts[ng] = cand_counts.get(ng, 0) + 1
            if cand_counts[ng] <= ref_counts.get(ng, 0):
                overlap += 1

        # Suavizado aditivo para evitar log(0)
        p = (overlap + 0.1) / (len(cand_ng) + 0.1)
        precisions.append(p)

    log_sum = sum(w * math.log(p) for w, p in zip(weights, precisions) if p > 0)
    bleu = bp * math.exp(log_sum)
    return round(float(bleu), 4)


def compute_hashtag_metrics(candidate_text: str, expected_tags: List[str]) -> Dict[str, Any]:
    """
    Evalúa la alineación de hashtags generados contra los hashtags oficiales del post real.
    """
    cand_tags = [t.lower() for t in re.findall(r'#\w+', candidate_text)]
    exp_tags = [t.lower() for t in (expected_tags or [])]

    cand_set = set(cand_tags)
    exp_set = set(exp_tags)

    intersection = cand_set.intersection(exp_set)
    union = cand_set.union(exp_set)

    jaccard = len(intersection) / len(union) if union else 1.0
    prec = len(intersection) / len(cand_set) if cand_set else 0.0
    rec = len(intersection) / len(exp_set) if exp_set else 1.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

    # Detección específica del hashtag institucional principal (#lifeatbbva)
    has_lifeatbbva = any("lifeatbbva" in t for t in cand_set)

    return {
        "candidate_hashtags": cand_tags,
        "ground_truth_hashtags": exp_tags,
        "hashtag_precision": round(prec, 4),
        "hashtag_recall": round(rec, 4),
        "hashtag_f1": round(f1, 4),
        "hashtag_jaccard": round(jaccard, 4),
        "includes_brand_anchor": has_lifeatbbva,
    }


def compute_key_facts_coverage(candidate: str, expected_facts: List[str]) -> Dict[str, Any]:
    """
    Verifica qué porcentaje de los hechos o entidades clave documentados en el Ground Truth
    fueron reproducidos fielmente por el sistema candidato.
    """
    if not expected_facts:
        return {"facts_present": 0, "facts_total": 0, "coverage_rate": 1.0, "missing_facts": []}

    cand_lower = candidate.lower()
    present = []
    missing = []

    for fact in expected_facts:
        fact_tokens = [w for w in re.findall(r'\w+', fact.lower()) if len(w) > 3]
        if not fact_tokens:
            fact_tokens = [fact.lower()]

        # Consideramos presente si al menos el 60% de los tokens representativos aparecen
        matches = sum(1 for tok in fact_tokens if tok in cand_lower)
        if matches / len(fact_tokens) >= 0.6:
            present.append(fact)
        else:
            missing.append(fact)

    total = len(expected_facts)
    rate = len(present) / total if total > 0 else 1.0

    return {
        "facts_present": len(present),
        "facts_total": total,
        "coverage_rate": round(rate, 4),
        "missing_facts": missing,
    }


def compute_length_metrics(candidate: str, reference: str) -> Dict[str, Any]:
    """Mide la fidelidad de extensión y estructura respecto al post humano."""
    cand_len = len(candidate)
    ref_len = len(reference)

    ratio = cand_len / ref_len if ref_len > 0 else 1.0
    diff = abs(cand_len - ref_len)

    cand_paragraphs = len([p for p in candidate.split("\n\n") if p.strip()])
    ref_paragraphs = len([p for p in reference.split("\n\n") if p.strip()])

    return {
        "candidate_chars": cand_len,
        "ground_truth_chars": ref_len,
        "length_ratio": round(ratio, 4),
        "char_difference": diff,
        "candidate_paragraphs": cand_paragraphs,
        "ground_truth_paragraphs": ref_paragraphs,
    }


def compute_semantic_similarity(candidate: str, reference: str) -> float:
    """
    Calcula la similitud semántica coseno entre el post candidato y el Ground Truth.
    Usa el modelo de embeddings Gemini si está configurado; de lo contrario, aplica
    vectorización TF-IDF con NumPy.
    """
    if not candidate or not reference:
        return 0.0

    # Intento 1: Embeddings vectoriales oficiales
    try:
        from src.services.custom_google_embeddings import CustomGoogleRestEmbeddings
        embedder = CustomGoogleRestEmbeddings()
        vec_cand = np.array(embedder.embed_query(candidate[:1000]))
        vec_ref = np.array(embedder.embed_query(reference[:1000]))

        norm_c = np.linalg.norm(vec_cand)
        norm_r = np.linalg.norm(vec_ref)
        if norm_c > 0 and norm_r > 0:
            sim = np.dot(vec_cand, vec_ref) / (norm_c * norm_r)
            return round(float(np.clip(sim, 0.0, 1.0)), 4)
    except Exception as exc:
        logger.debug("[metrics] Fallback a TF-IDF tras error en embeddings: %s", exc)

    # Intento 2: Fallback determinista TF-IDF con numpy (offline / zero-dependency)
    c_words = _tokenize(candidate)
    r_words = _tokenize(reference)
    vocab = sorted(set(c_words + r_words))
    if not vocab:
        return 0.0

    word_to_idx = {w: i for i, w in enumerate(vocab)}
    v_cand = np.zeros(len(vocab))
    v_ref = np.zeros(len(vocab))

    for w in c_words:
        v_cand[word_to_idx[w]] += 1
    for w in r_words:
        v_ref[word_to_idx[w]] += 1

    norm_c = np.linalg.norm(v_cand)
    norm_r = np.linalg.norm(v_ref)
    if norm_c == 0 or norm_r == 0:
        return 0.0
    sim = np.dot(v_cand, v_ref) / (norm_c * norm_r)
    return round(float(sim), 4)


def evaluate_against_ground_truth(
    candidate_content: str,
    ground_truth_post: str,
    expected_hashtags: List[str],
    expected_key_facts: List[str]
) -> Dict[str, Any]:
    """
    Ejecuta el conjunto completo de métricas comparativas cuantitativas frente al Ground Truth humano.
    """
    if not candidate_content or not candidate_content.strip():
        return {
            "error": "empty_candidate",
            "semantic_similarity": 0.0,
            "rouge": {},
            "bleu": 0.0,
            "hashtags": {},
            "key_facts": {},
            "length": {},
        }

    rouge = compute_rouge(candidate_content, ground_truth_post)
    bleu = compute_bleu(candidate_content, ground_truth_post)
    sem_sim = compute_semantic_similarity(candidate_content, ground_truth_post)
    tags = compute_hashtag_metrics(candidate_content, expected_hashtags)
    facts = compute_key_facts_coverage(candidate_content, expected_key_facts)
    length = compute_length_metrics(candidate_content, ground_truth_post)

    return {
        "semantic_similarity": sem_sim,
        "bleu": bleu,
        "rouge": rouge,
        "hashtags": tags,
        "key_facts": facts,
        "length": length,
    }
