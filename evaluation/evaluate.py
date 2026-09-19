"""
Fase de EVALUACIÓN: métricas objetivas + juez LLM ciego + informe Markdown.

Consume el JSONL producido por run_eval, calcula para cada salida las métricas
objetivas (factualidad CRAG, compliance, duplicación, forma), enfrenta a AIPost
contra cada baseline con el juez ciego y agrega todo en un informe listo para
la memoria del TFG.

Uso:
    python -m evaluation.evaluate evaluation/results/run_XXXX.jsonl \
        [--reference-system aipost] [--no-judge] [--no-metrics] [--seed 42]
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import os
os.environ.setdefault("AIPOST_CHECKPOINTER", "memory")

from src.core.logger import logger  # noqa: E402
from evaluation.metrics import compute_all_metrics  # noqa: E402
from evaluation.judges import judge_pair  # noqa: E402
from evaluation.contexts import build_shared_context  # noqa: E402
from evaluation.ground_truth_metrics import evaluate_against_ground_truth  # noqa: E402


def load_records(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return [r for r in records if not r.get("error") and r.get("content")]


def run_metrics(records: list[dict], skip_audit: bool = False, skip_ground_truth: bool = False) -> None:
    for i, rec in enumerate(records, 1):
        if "metrics" not in rec or not isinstance(rec["metrics"], dict):
            rec["metrics"] = {}

        # Métricas objetivas estándar (Fact Checker CRAG, Safety Guard, Duplicación, Forma)
        if not skip_audit and "factuality" not in rec["metrics"]:
            logger.info("[evaluate] Métricas auditoría %d/%d (%s/%s)...", i, len(records), rec["case_id"], rec["system"])
            rec["metrics"].update(compute_all_metrics(rec["content"], rec["org_urn"]))

        # Métricas cuantitativas frente a Ground Truth humano
        gt_post = rec.get("ground_truth_post")
        if gt_post and not skip_ground_truth and "ground_truth" not in rec["metrics"]:
            logger.info("[evaluate] Métricas Ground Truth %d/%d (%s/%s)...", i, len(records), rec["case_id"], rec["system"])
            rec["metrics"]["ground_truth"] = evaluate_against_ground_truth(
                candidate_content=rec.get("content", ""),
                ground_truth_post=gt_post,
                expected_hashtags=rec.get("official_hashtags") or [],
                expected_key_facts=rec.get("expected_key_facts") or [],
            )


def _judge_context(org_urn: str, prompt: str, output_1: str, output_2: str) -> str:
    """
    Contexto del juez SIN sesgo de recuperación: además del contexto del prompt,
    recupera evidencia de la base de conocimientos usando el contenido de AMBOS
    posts como query (tratamiento simétrico, ciego respecto al sistema).

    Sin esto, el juez penaliza como "inventados" los datos que un sistema
    obtuvo investigando más allá del contexto mínimo del prompt, favoreciendo
    estructuralmente al baseline (que solo puede citar ese contexto mínimo).
    """
    from src.services.rag_service import search_knowledge

    base = build_shared_context(org_urn, prompt, rag_limit=6)

    extra_hits = []
    for content in (output_1, output_2):
        try:
            extra_hits += search_knowledge(
                query=content[:600], org_urn=org_urn, threshold=0.45, limit=4
            )
        except Exception as exc:
            logger.warning("[evaluate] Evidencia adicional del juez no disponible: %s", exc)

    seen, evidence = set(), []
    for hit in extra_hits:
        key = (hit.get("source_id"), (hit.get("content") or "")[:80])
        if key in seen:
            continue
        seen.add(key)
        evidence.append(f"- [{hit.get('source_type', 'kb')}] {(hit.get('content') or '')[:500]}")

    if evidence:
        base += (
            "\n**Evidencia adicional de la base de conocimientos "
            "(recuperada para verificar los datos citados en los posts):**\n"
            + "\n".join(evidence[:8])
        )
    return base


def _audit_summary(rec: dict) -> str:
    """
    Resume la auditoría factual objetiva de una salida para el anexo del juez.
    El auditor (Fact Checker CRAG, recuperación por claim) es el MISMO para
    todos los sistemas: el juez recibe información simétrica y ciega.
    """
    fact = (rec.get("metrics") or {}).get("factuality") or {}
    if not fact or fact.get("error") or not fact.get("evaluated", True):
        return "No disponible."
    n = fact.get("n_claims", 0)
    bad = fact.get("n_unverified_claims", 0)
    if n == 0:
        return "El post no contiene afirmaciones factuales verificables."
    summary = f"{n - bad}/{n} afirmaciones verificadas contra la base de conocimientos y la web."
    examples = fact.get("unverified_examples") or []
    if examples:
        summary += " Afirmaciones SIN evidencia encontrada: " + "; ".join(f'"{e}"' for e in examples)
    return summary


def run_judgments(records: list[dict], reference: str, seed: int) -> list[dict]:
    """Enfrenta al sistema de referencia contra cada otro sistema, caso por caso."""
    rng = random.Random(seed)
    by_case: dict[str, dict[str, dict]] = defaultdict(dict)
    for rec in records:
        by_case[rec["case_id"]][rec["system"]] = rec

    judgments = []
    for case_id, outputs in sorted(by_case.items()):
        if reference not in outputs:
            continue
        ref_rec = outputs[reference]
        for system, rec in outputs.items():
            if system == reference:
                continue
            logger.info("[evaluate] Juez: %s | %s vs %s", case_id, reference, system)
            context = _judge_context(
                ref_rec["org_urn"], ref_rec["prompt"], ref_rec["content"], rec["content"]
            )
            verdict = judge_pair(
                prompt=ref_rec["prompt"],
                output_1=ref_rec["content"],
                output_2=rec["content"],
                company_context=context,
                system_1=reference,
                system_2=system,
                rng=rng,
                audit_1=_audit_summary(ref_rec),
                audit_2=_audit_summary(rec),
            )
            judgments.append({
                "case_id": case_id,
                "pair": [reference, system],
                **verdict,
            })
    return judgments


def _mean(values: list) -> float:
    values = [v for v in values if isinstance(v, (int, float))]
    return round(sum(values) / len(values), 3) if values else 0.0


def build_report(records: list[dict], judgments: list[dict], reference: str) -> str:
    systems = sorted({r["system"] for r in records})
    by_system = {s: [r for r in records if r["system"] == s] for s in systems}

    lines = ["# Informe de Evaluación Comparativa — AIPost", ""]
    lines.append(f"- Casos evaluados: {len({r['case_id'] for r in records})}")
    lines.append(f"- Sistemas: {', '.join(systems)}")
    lines.append(f"- Sistema de referencia: `{reference}`")
    lines.append("")

    # ---- Métricas objetivas (Auditores) ----
    has_audit = any("factuality" in (r.get("metrics") or {}) for r in records)
    if has_audit:
        lines.append("## Métricas objetivas (auditores: Fact Checker CRAG y Safety Guard)")
        lines.append("")
        lines.append("| Sistema | Tasa verificación claims | Alucinaciones/post | Pasa gate compliance | Infracciones graves/post | Similitud máx. c/ histórico | Hashtags OK | Latencia media (s) | Tokens medios |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for s in systems:
            recs = by_system[s]
            fact = [r.get("metrics", {}).get("factuality", {}) for r in recs]
            comp = [r.get("metrics", {}).get("compliance", {}) for r in recs]
            dup = [r.get("metrics", {}).get("duplication", {}) for r in recs]
            form = [r.get("metrics", {}).get("form", {}) for r in recs]
            ver_rate = _mean([f.get("verification_rate") for f in fact])
            halluc = _mean([f.get("n_unverified_claims") for f in fact])
            approved = _mean([1 if c.get("passes_gate", c.get("approved")) else 0 for c in comp if c])
            grave = _mean([
                c.get("n_issues", 0) if c.get("severity") in ("medium", "high", "critical") else 0
                for c in comp if c
            ])
            sim = _mean([d.get("max_similarity_to_history") for d in dup])
            ht_ok = _mean([1 if f.get("hashtags_in_range") else 0 for f in form if f])
            lat = _mean([r.get("latency_s") for r in recs])
            tok = _mean([(r.get("token_usage") or {}).get("total_tokens") for r in recs])
            lines.append(
                f"| {s} | {ver_rate:.1%} | {halluc:.2f} | {approved:.1%} | {grave:.2f} | {sim:.3f} | {ht_ok:.1%} | {lat:.1f} | {tok:.0f} |"
            )
        lines.append("")

    # ---- Métricas cuantitativas frente a Ground Truth humano (BBVA) ----
    gt_recs = [r for r in records if (r.get("metrics") or {}).get("ground_truth")]
    if gt_recs:
        lines.append("## Comparativa cuantitativa frente a Ground Truth humano (BBVA)")
        lines.append("")
        lines.append(
            "Esta sección evalúa numéricamente el grado de alineación, fidelidad y cercanía estilística, "
            "léxica y factual de cada sistema respecto a los posts reales redactados y publicados por profesionales "
            "de comunicación de BBVA en LinkedIn (Ground Truth humano real)."
        )
        lines.append("")
        lines.append("### Resumen global frente a Ground Truth")
        lines.append("")
        lines.append(
            "| Sistema | Similitud semántica (Cosine) | ROUGE-1 F1 | ROUGE-2 F1 | ROUGE-L F1 | BLEU | "
            "Cobertura hechos clave | Precisión hashtags | Recall hashtags | Hashtags F1 | Presencia #LifeAtBBVA | Ratio longitud |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for s in systems:
            recs = [r for r in gt_recs if r["system"] == s]
            if not recs:
                continue
            gt_metrics = [r["metrics"]["ground_truth"] for r in recs]
            sem_sim = _mean([g.get("semantic_similarity") for g in gt_metrics])
            r1 = _mean([g.get("rouge", {}).get("rouge1_f1") for g in gt_metrics])
            r2 = _mean([g.get("rouge", {}).get("rouge2_f1") for g in gt_metrics])
            rl = _mean([g.get("rouge", {}).get("rougeL_f1") for g in gt_metrics])
            bleu = _mean([g.get("bleu") for g in gt_metrics])
            facts_cov = _mean([g.get("key_facts", {}).get("coverage_rate") for g in gt_metrics])
            ht_p = _mean([g.get("hashtags", {}).get("precision") for g in gt_metrics])
            ht_r = _mean([g.get("hashtags", {}).get("recall") for g in gt_metrics])
            ht_f1 = _mean([g.get("hashtags", {}).get("f1") for g in gt_metrics])
            anchor = _mean([1 if g.get("hashtags", {}).get("has_brand_anchor") else 0 for g in gt_metrics])
            len_ratio = _mean([g.get("length", {}).get("length_ratio") for g in gt_metrics])
            lines.append(
                f"| {s} | {sem_sim:.3f} | {r1:.3f} | {r2:.3f} | {rl:.3f} | {bleu:.3f} | "
                f"{facts_cov:.1%} | {ht_p:.1%} | {ht_r:.1%} | {ht_f1:.3f} | {anchor:.1%} | {len_ratio:.2f} |"
            )
        lines.append("")

        # Desglose por casuística (Matriz 2x2: Complejidad x Contexto)
        casuisticas = sorted({r.get("casuistica") for r in gt_recs if r.get("casuistica")})
        if casuisticas:
            lines.append("### Desglose por Casuística (Matriz 2×2: Complejidad × Contexto)")
            lines.append("")
            casuistica_labels = {
                "C1": "C1: Baja Complejidad × Bajo Contexto (Hitos cotidianos, aniversarios)",
                "C2": "C2: Baja Complejidad × Alto Contexto (Cultura interna, BBVA Tech / The Place)",
                "C3": "C3: Alta Complejidad × Bajo Contexto (Tendencias sectoriales, fintech macro)",
                "C4": "C4: Alta Complejidad × Alto Contexto (Finanzas, planes ESG y compliance)",
            }
            lines.append("| Casuística | Sistema | Similitud semántica | ROUGE-L F1 | Cobertura hechos | Hashtags F1 | Presencia #LifeAtBBVA |")
            lines.append("|---|---|---|---|---|---|---|")
            for c_code in casuisticas:
                c_label = casuistica_labels.get(c_code, c_code)
                for s in systems:
                    c_recs = [r for r in gt_recs if r.get("casuistica") == c_code and r["system"] == s]
                    if not c_recs:
                        continue
                    c_gt = [r["metrics"]["ground_truth"] for r in c_recs]
                    sem_sim = _mean([g.get("semantic_similarity") for g in c_gt])
                    rl = _mean([g.get("rouge", {}).get("rougeL_f1") for g in c_gt])
                    facts_cov = _mean([g.get("key_facts", {}).get("coverage_rate") for g in c_gt])
                    ht_f1 = _mean([g.get("hashtags", {}).get("f1") for g in c_gt])
                    anchor = _mean([1 if g.get("hashtags", {}).get("has_brand_anchor") else 0 for g in c_gt])
                    lines.append(f"| {c_label} | {s} | {sem_sim:.3f} | {rl:.3f} | {facts_cov:.1%} | {ht_f1:.3f} | {anchor:.1%} |")
            lines.append("")

        # Comparativa Cualitativa de Muestra (Ejemplo representativo)
        sample_cases = [r["case_id"] for r in gt_recs if r.get("casuistica") in ("C4", "C2")]
        if not sample_cases:
            sample_cases = [r["case_id"] for r in gt_recs]
        if sample_cases:
            target_case_id = sample_cases[0]
            case_records = {r["system"]: r for r in gt_recs if r["case_id"] == target_case_id}
            first_rec = next(iter(case_records.values()))
            lines.append("### Muestra cualitativa comparativa (Caso representativo)")
            lines.append("")
            lines.append(f"**Caso**: `{target_case_id}` — *{first_rec.get('title', '')}* (Casuística: `{first_rec.get('casuistica', 'N/A')}`)")
            lines.append("")
            lines.append(f"**Prompt de entrada**:\n> {first_rec.get('prompt', '')}")
            lines.append("")
            gt_text = first_rec.get("ground_truth_post") or ""
            lines.append(f"#### Ground Truth Humano (BBVA Real):\n```text\n{gt_text.strip()}\n```\n")
            for sys_name in systems:
                if sys_name in case_records:
                    sys_content = case_records[sys_name].get("content", "").strip()
                    lines.append(f"#### Salida sistema: `{sys_name}`\n```text\n{sys_content}\n```\n")

    # ---- Juez ciego ----
    if judgments:
        lines.append("## Juez LLM ciego (pairwise aleatorizado)")
        lines.append("")
        pair_results: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        dim_scores: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for j in judgments:
            if j.get("error"):
                continue
            opponent = [p for p in j["pair"] if p != reference][0]
            winner = j.get("winner_system")
            if winner == reference:
                pair_results[opponent]["ref_wins"] += 1
            elif winner == opponent:
                pair_results[opponent]["opp_wins"] += 1
            else:
                pair_results[opponent]["ties"] += 1
            for sys_name, scores in (j.get("scores") or {}).items():
                for dim, val in scores.items():
                    dim_scores[sys_name][dim].append(val)

        lines.append(f"| Rival | Victorias `{reference}` | Victorias rival | Empates | Win rate |")
        lines.append("|---|---|---|---|---|")
        for opp, res in sorted(pair_results.items()):
            total = res["ref_wins"] + res["opp_wins"] + res["ties"]
            wr = res["ref_wins"] / total if total else 0
            lines.append(f"| {opp} | {res['ref_wins']} | {res['opp_wins']} | {res['ties']} | {wr:.1%} |")
        lines.append("")

        lines.append("### Puntuaciones medias por dimensión (1-5)")
        lines.append("")
        dims = ["brand_fidelity", "factual_grounding", "linkedin_craft", "originality", "strategic_value"]
        lines.append("| Sistema | " + " | ".join(dims) + " |")
        lines.append("|---" * (len(dims) + 1) + "|")
        for sys_name, per_dim in sorted(dim_scores.items()):
            row = [f"{_mean(per_dim.get(d, [])):.2f}" for d in dims]
            lines.append(f"| {sys_name} | " + " | ".join(row) + " |")
        lines.append("")

    # ---- Desglose por dependencia de KB ----
    kb_recs = [r for r in records if r.get("kb_dependent")]
    if kb_recs:
        lines.append("## Casos dependientes de la base de conocimientos (donde se juega la factualidad)")
        lines.append("")
        lines.append("| Sistema | Tasa verificación claims (solo KB) | Alucinaciones/post (solo KB) |")
        lines.append("|---|---|---|")
        for s in systems:
            recs = [r for r in kb_recs if r["system"] == s]
            fact = [r.get("metrics", {}).get("factuality", {}) for r in recs]
            ver_rate = _mean([f.get("verification_rate") for f in fact])
            halluc = _mean([f.get("n_unverified_claims") for f in fact])
            lines.append(f"| {s} | {ver_rate:.1%} | {halluc:.2f} |")
        lines.append("")

    lines.append("---")
    lines.append("*Generado por `evaluation/evaluate.py`. Metodología: comparación frente a Ground Truth humano real (BBVA), "
                 "juez ciego con orden A/B aleatorizado, modelo de juez distinto del generador, métricas objetivas mediante "
                 "auditoría CRAG claim-por-claim aplicada simétricamente a todos los sistemas, y anexo de auditoría factual "
                 "entregado al juez para la dimensión factual_grounding.*")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Métricas + juez + informe de la evaluación comparativa.")
    parser.add_argument("results", help="JSONL producido por run_eval.")
    parser.add_argument("--reference-system", default="aipost")
    parser.add_argument("--no-judge", action="store_true", help="Omite el juez LLM (solo métricas objetivas).")
    parser.add_argument("--no-metrics", action="store_true", help="Omite las métricas objetivas (solo juez).")
    parser.add_argument("--skip-audit", action="store_true", help="Omite la auditoría LLM (Fact Checker y Safety Guard), calculando solo Ground Truth.")
    parser.add_argument("--no-ground-truth", action="store_true", help="Omite el cálculo de métricas frente a Ground Truth.")
    parser.add_argument("--seed", type=int, default=42, help="Semilla de la aleatorización A/B del juez.")
    args = parser.parse_args()

    path = Path(args.results)
    records = load_records(path)
    if not records:
        raise SystemExit("No hay registros válidos en el fichero de resultados.")

    if not args.no_metrics:
        run_metrics(records, skip_audit=args.skip_audit, skip_ground_truth=args.no_ground_truth)

    judgments = []
    if not args.no_judge:
        if args.no_metrics or args.skip_audit:
            logger.warning(
                "[evaluate] Juzgando sin auditoría completa: el juez no recibirá el anexo de "
                "auditoría factual y puede penalizar datos verificables (sesgo de contexto parcial)."
            )
        judgments = run_judgments(records, args.reference_system, args.seed)

    enriched_path = path.with_suffix(".evaluated.json")
    with open(enriched_path, "w", encoding="utf-8") as fh:
        json.dump({"records": records, "judgments": judgments}, fh, ensure_ascii=False, indent=2, default=str)

    report = build_report(records, judgments, args.reference_system)
    report_path = path.with_suffix(".report.md")
    report_path.write_text(report, encoding="utf-8")

    print(f"\nDatos enriquecidos: {enriched_path}")
    print(f"Informe Markdown:   {report_path}\n")
    print(report)


if __name__ == "__main__":
    main()
