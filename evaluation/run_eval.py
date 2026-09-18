"""
Fase de GENERACIÓN de la evaluación comparativa.

Ejecuta cada sistema sobre el dataset y persiste las salidas en JSONL
(reanudable: los pares caso×sistema ya generados se saltan).

Uso:
    python -m evaluation.run_eval --org-urn "urn:li:organization:XXXX" \
        --systems aipost,baseline_context,baseline_vanilla \
        [--dataset evaluation/dataset.json] [--out evaluation/results/run.jsonl] \
        [--limit 5] [--only-kb-dependent]

Estudio de ablación (ejemplos):
    --systems aipost,aipost_no_fact_checker,aipost_no_research_loop
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("AIPOST_CHECKPOINTER", "memory")

from src.core.logger import logger  # noqa: E402
from evaluation.systems import generate  # noqa: E402

DEFAULT_DATASET = Path(__file__).parent / "dataset.json"


def load_dataset(path: str, limit: int | None, only_kb: bool) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    cases = data["cases"]
    if only_kb:
        cases = [c for c in cases if c.get("kb_dependent")]
    if limit:
        cases = cases[:limit]
    return cases


def load_done(out_path: Path) -> set[tuple[str, str]]:
    done = set()
    if out_path.exists():
        with open(out_path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                    if not rec.get("error"):
                        done.add((rec["case_id"], rec["system"]))
                except json.JSONDecodeError:
                    continue
    return done


def main() -> None:
    parser = argparse.ArgumentParser(description="Generación de salidas para la evaluación comparativa de AIPost.")
    parser.add_argument("--org-urn", required=True, help="URN de la organización con perfil y RAG ya indexados.")
    parser.add_argument("--systems", default="aipost,baseline_context,baseline_vanilla",
                        help="Sistemas separados por coma (aipost, baseline_context, baseline_vanilla, aipost_no_<capacidad>).")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--out", default=None, help="Ruta del JSONL de salida (por defecto evaluation/results/run_<fecha>.jsonl).")
    parser.add_argument("--limit", type=int, default=None, help="Limita el número de casos (pruebas rápidas / cuota).")
    parser.add_argument("--only-kb-dependent", action="store_true", help="Solo casos que dependen de la base de conocimientos.")
    args = parser.parse_args()

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    cases = load_dataset(args.dataset, args.limit, args.only_kb_dependent)

    out_path = Path(args.out) if args.out else (
        Path(__file__).parent / "results" / f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.jsonl"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = load_done(out_path)

    total = len(cases) * len(systems)
    logger.info("[eval] %d casos × %d sistemas = %d generaciones (%d ya hechas) -> %s",
                len(cases), len(systems), total, len(done), out_path)

    with open(out_path, "a", encoding="utf-8") as fh:
        for case in cases:
            for system in systems:
                key = (case["id"], system)
                if key in done:
                    logger.info("[eval] SKIP %s/%s (ya generado)", *key)
                    continue

                logger.info("[eval] Generando %s con '%s'...", case["id"], system)
                record = {
                    "case_id": case["id"],
                    "category": case.get("category"),
                    "kb_dependent": case.get("kb_dependent"),
                    "prompt": case["prompt"],
                    "system": system,
                    "org_urn": args.org_urn,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
                try:
                    result = generate(system, case["prompt"], args.org_urn)
                    record.update(result)
                except Exception as exc:
                    logger.exception("[eval] Error generando %s/%s", case["id"], system)
                    record["error"] = str(exc)

                fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                fh.flush()

    logger.info("[eval] Generación completada: %s", out_path)
    print(f"\nResultados en: {out_path}")
    print("Siguiente paso: python -m evaluation.evaluate " + str(out_path))


if __name__ == "__main__":
    main()
