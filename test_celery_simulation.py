#!/usr/bin/env python3
"""
Script que simula exactamente la tarea Celery para verificar el problema con revision_cycles.
"""

import asyncio
import sys
import os
import uuid

# Añadir el directorio raíz al path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.dependencies.graph import graph
from src.agents.content_agent.callbacks import TokenUsageCallback

async def test_celery_simulation():
    """Simula exactamente la tarea Celery para verificar el problema."""
    
    print("🧪 Simulando tarea Celery...")
    
    # Estado inicial exactamente como en la tarea Celery
    payload_dict = {
        "query": "Quiero un post sobre inteligencia artificial para LinkedIn",
        "tone": "profesional pero cercano",
        "niche": "tecnología",
        "account_name": "TechCorp",
        "link_url": "https://example.com/ai-article",
    }
    
    thread_id = str(uuid.uuid4())

    initial_state = {
        **payload_dict, 
        "token_usage_by_node": {}, 
        "total_tokens": 0, 
        "review_notes": "",
        "revision_cycles": 0, 
        "creative_brief": None, 
        "draft_content": None,
        "refined_content": None, 
        "formatted_output": None, 
        "final_post": None,
    }
    
    print(f"📊 Estado inicial - revision_cycles: {initial_state['revision_cycles']}")
    print(f"🔑 Thread ID: {thread_id}")
    
    # Crear callback exactamente como en la tarea Celery
    callback = TokenUsageCallback(initial_state)
    
    try:
        # Ejecutar el grafo exactamente como en la tarea Celery
        print("🚀 Ejecutando grafo (simulación Celery)...")
        final_state = await graph.ainvoke(
            initial_state, 
            config={
                "callbacks": [callback], 
                "configurable": {"thread_id": thread_id}
            }
        )
        
        print(f"✅ Grafo ejecutado exitosamente")
        print(f"📊 Estado final - revision_cycles: {final_state.get('revision_cycles')}")
        print(f"📊 Contenido final: {final_state.get('final_post', 'No disponible')}")
        
        # Verificar que revision_cycles se mantuvo correctamente
        final_cycles = final_state.get('revision_cycles')
        if final_cycles is not None and final_cycles >= 0:
            print(f"✅ revision_cycles se mantuvo correctamente: {final_cycles}")
        else:
            print(f"❌ revision_cycles no se mantuvo correctamente: {final_cycles}")
            
        # Simular el resultado de la tarea Celery
        result = {
            "final_post": final_state.get("final_post", "Error: No se pudo generar el contenido."),
            "token_usage_per_node": final_state.get("token_usage_by_node"),
            "total_tokens_used": final_state.get("total_tokens"),
            "revision_cycles": final_state.get("revision_cycles")  # Añadir para debugging
        }
        
        print(f"📋 Resultado final (simulación Celery): {result}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error durante la ejecución: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🔧 Iniciando simulación de tarea Celery...")
    result = asyncio.run(test_celery_simulation())
    
    if result:
        print("✅ Simulación completada exitosamente")
    else:
        print("❌ Simulación falló")
        sys.exit(1) 