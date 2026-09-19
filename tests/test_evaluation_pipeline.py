"""
Tests unitarios para el flujo de evaluación y generación de informes de Ground Truth.
"""
import json
from evaluation.evaluate import build_report, run_metrics
from evaluation.run_eval import load_dataset


def test_load_dataset_with_casuistica(tmp_path):
    dataset_file = tmp_path / "test_dataset.json"
    dummy_data = {
        "cases": [
            {"id": "case_1", "prompt": "p1", "casuistica": "C1", "kb_dependent": False},
            {"id": "case_2", "prompt": "p2", "casuistica": "C2", "kb_dependent": True},
            {"id": "case_3", "prompt": "p3", "casuistica": "C4", "kb_dependent": True},
        ]
    }
    dataset_file.write_text(json.dumps(dummy_data), encoding="utf-8")

    # Filter by C2
    c2_cases = load_dataset(str(dataset_file), limit=None, only_kb=False, casuisticas=["C2"])
    assert len(c2_cases) == 1
    assert c2_cases[0]["id"] == "case_2"

    # Filter by C1 and C4
    c1_c4_cases = load_dataset(str(dataset_file), limit=None, only_kb=False, casuisticas=["C1", "C4"])
    assert len(c1_c4_cases) == 2

    # Limit
    limited = load_dataset(str(dataset_file), limit=1, only_kb=False)
    assert len(limited) == 1


def test_run_metrics_ground_truth_only():
    records = [
        {
            "case_id": "c1",
            "system": "aipost",
            "content": "Innovación en BBVA con inteligencia artificial y computación cuántica. #LifeAtBBVA #Quantum",
            "org_urn": "urn:li:organization:136115687",
            "ground_truth_post": "BBVA impulsa la computación cuántica para mejorar la ciberseguridad financiera. #LifeAtBBVA",
            "official_hashtags": ["#LifeAtBBVA", "#Quantum"],
            "expected_key_facts": ["computación cuántica", "ciberseguridad"],
        }
    ]

    run_metrics(records, skip_audit=True, skip_ground_truth=False)

    assert "metrics" in records[0]
    assert "ground_truth" in records[0]["metrics"]
    gt = records[0]["metrics"]["ground_truth"]
    assert gt["semantic_similarity"] > 0.0
    assert gt["rouge"]["rouge1_f1"] > 0.0
    assert gt["hashtags"]["includes_brand_anchor"] is True
    assert gt["key_facts"]["coverage_rate"] > 0.0


def test_build_report_includes_ground_truth_section():
    records = [
        {
            "case_id": "c1",
            "title": "Prueba Cuańtica",
            "system": "aipost",
            "casuistica": "C4",
            "prompt": "Habla de computación cuántica",
            "content": "Post AIPost #LifeAtBBVA",
            "ground_truth_post": "Post Humano BBVA #LifeAtBBVA",
            "metrics": {
                "ground_truth": {
                    "semantic_similarity": 0.88,
                    "rouge": {"rouge1_f1": 0.55, "rouge2_f1": 0.35, "rougeL_f1": 0.50},
                    "bleu": 0.45,
                    "hashtags": {"precision": 1.0, "recall": 0.66, "f1": 0.80, "has_brand_anchor": True},
                    "key_facts": {"coverage_rate": 0.75},
                    "length": {"length_ratio": 0.95},
                }
            },
        },
        {
            "case_id": "c1",
            "title": "Prueba Cuańtica",
            "system": "gemini_commercial",
            "casuistica": "C4",
            "prompt": "Habla de computación cuántica",
            "content": "Post Comercial Genérico #Tech #Innovation",
            "ground_truth_post": "Post Humano BBVA #LifeAtBBVA",
            "metrics": {
                "ground_truth": {
                    "semantic_similarity": 0.65,
                    "rouge": {"rouge1_f1": 0.30, "rouge2_f1": 0.10, "rougeL_f1": 0.25},
                    "bleu": 0.15,
                    "hashtags": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "has_brand_anchor": False},
                    "key_facts": {"coverage_rate": 0.25},
                    "length": {"length_ratio": 1.80},
                }
            },
        },
    ]

    report = build_report(records, judgments=[], reference="aipost")

    assert "## Comparativa cuantitativa frente a Ground Truth humano (BBVA)" in report
    assert "### Resumen global frente a Ground Truth" in report
    assert "### Desglose por Casuística (Matriz 2×2: Complejidad × Contexto)" in report
    assert "C4: Alta Complejidad × Alto Contexto" in report
    assert "### Muestra cualitativa comparativa (Caso representativo)" in report
    assert "Post Humano BBVA #LifeAtBBVA" in report
