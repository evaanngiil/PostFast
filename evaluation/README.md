# Evaluación comparativa de AIPost

Harness reproducible que sustenta la tesis central del TFG: **el pipeline
multi-agente de AIPost produce contenido de mayor valor que un LLM con el mismo
contexto en un único prompt** ("LLM + contexto") y que un LLM vanilla.

## Diseño experimental

| Elemento | Decisión | Motivo |
|---|---|---|
| Dataset | 20 casos fijos (`dataset.json`), etiquetados por categoría y `kb_dependent` | Reproducibilidad; los casos KB-dependientes son donde el baseline alucina |
| Baseline principal | Mismo modelo, MISMO contexto estático (perfil + persona + RAG top-k + posts recientes), un solo prompt | Aísla el efecto de la *arquitectura agéntica* frente al *acceso a datos* |
| Métricas objetivas | Fact Checker CRAG y Safety Guard del propio sistema usados como auditores sobre TODOS los sistemas | Cuantifica alucinaciones e infracciones sin subjetividad |
| Juez LLM | Modelo distinto del generador (`JUDGE_LLM`), pairwise ciego, orden A/B aleatorizado con semilla | Mitiga auto-preferencia y sesgo de posición |
| Ablación | `aipost_no_<capacidad>` desactiva nodos individuales vía estado | Demuestra la contribución causal de cada agente |
| Coste | Latencia y tokens por generación registrados | Trade-off calidad/coste transparente |

## Requisitos previos

1. `.env` con `GENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY` (y `TAVILY_API_KEY` para tendencias/verificación web).
2. La organización evaluada debe tener el perfil extraído y el RAG indexado
   (ejecutar antes la extracción batch desde la app).
3. Recomendado: `LANGCHAIN_API_KEY` para trazas por nodo en LangSmith.

## Uso

```bash
# 1. Generar salidas (reanudable; --limit para probar con pocos casos)
python -m evaluation.run_eval --org-urn "urn:li:organization:XXXX" \
    --systems aipost,baseline_context,baseline_vanilla

# 2. Métricas objetivas + juez ciego + informe Markdown
python -m evaluation.evaluate evaluation/results/run_<fecha>.jsonl

# Estudio de ablación (contribución de cada agente)
python -m evaluation.run_eval --org-urn "urn:li:organization:XXXX" \
    --systems aipost,aipost_no_fact_checker,aipost_no_research_loop,aipost_no_trend_researcher \
    --only-kb-dependent
```

Capacidades ablacionables: `engagement_analyzer`, `persona_analyst`,
`duplicate_detector`, `trend_researcher`, `fact_checker`, `safety_guard`,
`research_loop`.

## Presupuesto de cuota (free tier de Gemini)

Una pasada completa (20 casos × 3 sistemas) consume del orden de 150-250
llamadas LLM entre generación, métricas y juez. Con los límites RPD del free
tier, planifica: usa `--limit`, reparte en días, o configura `SMART_LLM` /
`JUDGE_LLM` / `AIPOST_DEFAULT_LLM` en el `.env` hacia modelos con cuota
disponible. El runner es **reanudable**: relanzarlo continúa donde se quedó.

## Salidas

- `results/run_<fecha>.jsonl` — una línea por (caso × sistema) con contenido, latencia y tokens.
- `results/run_<fecha>.evaluated.json` — registros enriquecidos con métricas + veredictos del juez.
- `results/run_<fecha>.report.md` — informe agregado listo para la memoria del TFG.
