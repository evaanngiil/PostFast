"""
Genera el diagrama Mermaid PNG del grafo multi-agente de AIPost.

Uso:
    AIPOST_CHECKPOINTER=memory python scripts/draw_graph.py [ruta_salida.png]
"""
import os
import sys

os.environ.setdefault("AIPOST_CHECKPOINTER", "memory")

from src.agents.multi_agent.graph import compile_graph  # noqa: E402


def main() -> None:
    output = sys.argv[1] if len(sys.argv) > 1 else "final_multiagent_graph.png"
    compiled = compile_graph()
    compiled.get_graph().draw_mermaid_png(output_file_path=output)
    print(f"Diagrama generado en {output}")


if __name__ == "__main__":
    main()
