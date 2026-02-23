import json
import uuid
from graph import aipost_graph

correct_session = {
    'auth_token_for_url': 'AQVLxw2u7x5oGx-_FNp0J0sTeSmldiv7g3u4ifMac7p0eBCaihkIXyDHlyP_2-JacI52OaloAC-XuXhuEOROEykZSOJ3bspC9l9XVuWK7S3E00UKuKk5ubjE2OMzTDrXhXgukD6KfFwp1-7nvFrKiXGAsy5yZLeEvSzxqdYHp39pu12IT96EYO34nr6Er3tTnee3p3xEMMW2K-3k8qj0wq-HJwhgnmZbCEjw4L9puqSlLb3v5bvGnfj2WWvwh1IPfGGLR4EmXM7tNmQhNImlAAlj6DgjhrKHekiFaJMNRf9ooD7MydZyoo5n6FY50M-N7V4tI3YQYKLM1yh3B9_RseWdR0NEUQ',
    'selected_account': {
        'urn': 'urn:li:organization:106454024',
        'id': 106454024,
        'name': 'AIPost',
        'platform': 'LinkedIn',
        'type': 'organization',
        'defaultLocale': {'country': 'ES', 'language': 'es'},
        'vanityName': 'aipost',
        'localizedSpecialties': ['IA Generativa', 'Marketing', 'Community Managment'],
        'industries': ['Internet'],
        'primaryOrganizationType': 'NONE',
        'versionTag': '1228591621'
    }
}

def run_aipost_from_session():
    """
    Simula la ejecución del agente a partir de un estado de sesión ya existente.
    """
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    print(f"🚀 Iniciando hilo de trabajo AIPost con ID: {thread_id}")

    # Construir el estado inicial para el grafo a partir de la sesión
    initial_state = {
        "linkedin_access_token": correct_session["auth_token_for_url"],
        "selected_account": correct_session["selected_account"],
        "user_post_idea": "Quiero escribir un post sobre la importancia de la IA en el marketing de contenidos.",
    }
    
    # Invocar el grafo una sola vez. Se ejecutará de principio a fin.
    final_state = aipost_graph.invoke(initial_state, config)

    if final_state and final_state.get("draft_post"):
        print("\n" + "="*50)
        print("--- ✅ PROCESO COMPLETADO ---")
        print("="*50)
        draft_json_str = final_state["draft_post"]
        draft = draft_json_str
        print(f"\n📄 CONTENIDO:\n{draft['content']}")
        print(f"\n🏷️ HASHTAGS: {' '.join(draft['hashtags'])}")
        print(f"\n🎯 CTA: {draft['call_to_action']}")
        print("\n" + "="*50)
    else:
        print("\n--- ❌ PROCESO INCOMPLETO ---")

if __name__ == "__main__":
    run_aipost_from_session()