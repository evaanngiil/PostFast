"""
Tests unitarios para las métricas de comparación frente a Ground Truth (ROUGE, BLEU, Cosine, Hashtags).
"""
from evaluation.ground_truth_metrics import (
    compute_rouge,
    compute_bleu,
    compute_hashtag_metrics,
    compute_key_facts_coverage,
    compute_semantic_similarity,
    evaluate_against_ground_truth,
)


def test_rouge_identical_texts():
    text = "La computación cuántica de BBVA refuerza la seguridad con QRNG y claves irrompibles."
    scores = compute_rouge(text, text)
    assert scores["rouge1_f1"] == 1.0
    assert scores["rouge2_f1"] == 1.0
    assert scores["rougeL_f1"] == 1.0


def test_rouge_partial_overlap():
    ref = "BBVA presenta FrauDfense junto a Santander y CaixaBank para frenar el fraude financiero."
    cand = "FrauDfense es una alianza creada para combatir el fraude financiero en la banca."
    scores = compute_rouge(cand, ref)
    assert 0.0 < scores["rouge1_f1"] < 1.0
    assert 0.0 < scores["rouge2_f1"] < 1.0
    assert 0.0 < scores["rougeL_f1"] < 1.0


def test_bleu_identical_and_different():
    ref = "Juntas en una sala a 40 de las mentes más prometedoras de Data Science en el Datathon."
    cand = "Juntas en una sala a 40 de las mentes más prometedoras de Data Science en el Datathon."
    assert compute_bleu(cand, ref) > 0.95

    diff = "Hoy hace un día soleado en la playa con gaviotas y arena."
    assert compute_bleu(diff, ref) < 0.2


def test_hashtag_metrics():
    expected = ["#LifeAtBBVA", "#Ciberseguridad", "#BBVAQuantum"]
    candidate = "Post de tecnología cuántica #LifeAtBBVA #Ciberseguridad #Fintech"
    metrics = compute_hashtag_metrics(candidate, expected)

    assert metrics["includes_brand_anchor"] is True
    assert metrics["hashtag_recall"] == round(2 / 3, 4)
    assert metrics["hashtag_precision"] == round(2 / 3, 4)


def test_key_facts_coverage():
    expected_facts = [
        "Generadores Cuánticos de Números Aleatorios QRNG",
        "simulaciones Montecarlo",
        "Santander y CaixaBank",
    ]
    cand = "En BBVA usamos Generadores Cuánticos de Números Aleatorios QRNG para simulaciones Montecarlo de riesgo."
    result = compute_key_facts_coverage(cand, expected_facts)

    assert result["facts_present"] == 2
    assert result["facts_total"] == 3
    assert result["coverage_rate"] == round(2 / 3, 4)
    assert "Santander y CaixaBank" in result["missing_facts"]


def test_semantic_similarity_fallback_and_embedding():
    t1 = "BBVA invierte en tecnología cuántica para ciberseguridad."
    t2 = "BBVA investiga la computación cuántica para mejorar la ciberseguridad."
    sim = compute_semantic_similarity(t1, t2)
    assert 0.4 <= sim <= 1.0


def test_evaluate_against_ground_truth_full():
    cand = "Innovación cuántica con QRNG en BBVA #LifeAtBBVA #Ciberseguridad"
    gt = "¿Y si el desorden fuera la clave? QRNG cuántico en BBVA #LifeAtBBVA #Ciberseguridad"
    res = evaluate_against_ground_truth(
        candidate_content=cand,
        ground_truth_post=gt,
        expected_hashtags=["#LifeAtBBVA", "#Ciberseguridad"],
        expected_key_facts=["QRNG cuántico", "innovación"],
    )
    assert "rouge" in res
    assert "bleu" in res
    assert "semantic_similarity" in res
    assert res["hashtags"]["includes_brand_anchor"] is True


def test_ground_truth_empty_inputs():
    res = evaluate_against_ground_truth("", "", [], [])
    assert res.get("error") == "empty_candidate"
    assert res["semantic_similarity"] == 0.0

    scores = compute_rouge("", "")
    assert scores["rouge1_f1"] == 0.0
    assert scores["rougeL_f1"] == 0.0


def test_hashtag_metrics_edge_cases():
    # No hashtags in candidate
    m1 = compute_hashtag_metrics("Texto sin hashtags", ["#LifeAtBBVA"])
    assert m1["hashtag_precision"] == 0.0
    assert m1["hashtag_recall"] == 0.0
    assert m1["includes_brand_anchor"] is False

    # Empty expected hashtags
    m2 = compute_hashtag_metrics("Texto con #Hashtag", [])
    assert m2["hashtag_precision"] == 0.0
    assert m2["hashtag_recall"] == 1.0

    # Case insensitive matching
    m3 = compute_hashtag_metrics("Texto con #lifeatbbva y #quantum", ["#LifeAtBBVA", "#QUANTUM"])
    assert m3["includes_brand_anchor"] is True
    assert m3["hashtag_f1"] == 1.0


def test_key_facts_empty_expected():
    res = compute_key_facts_coverage("Cualquier texto", [])
    assert res["coverage_rate"] == 1.0
    assert res["facts_total"] == 0
