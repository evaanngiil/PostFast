from src.agents.content_agent.agent_state import InternalState

# Excepción personalizada para una interrupción limpia
class HumanReviewRequired(Exception):
    """Excepción para señalar que el grafo debe pausarse para input humano."""
    def __init__(self, state: dict):
        self.state = state
        super().__init__("Human review required")

def quality_gate(state: InternalState) -> str:
    """
    Control de calidad que decide si refinar, finalizar o pausar para revisión humana.
    """
    print("--- Realizando Control de Calidad ---")
    current_cycles = state.get("revision_cycles", 0)
    print(f"REVISION CYCLE: {current_cycles}")

    feedback =  state.get("human_feedback")
    print(f"Feedback Quality Gate: {feedback}")

    if current_cycles >= 1:
        print(f"--- Ciclo #{current_cycles} completo. Pausando para revisión humana. ---")
        state["revision_cycles"] = 0
        raise HumanReviewRequired(state)
    
    if isinstance(feedback, str) and feedback.strip().lower() == "aprobar":
        print("--- Feedback de aprobación explícito detectado. Finalizando. ---")
        state["revision_cycles"] = 0
        return "end"


    # Si es el ciclo 0, significa que acabamos de generar el draft, así que pasamos a refinar.
    print("--- Ciclo inicial. Pasando a refinar. ---")
    return "refine"