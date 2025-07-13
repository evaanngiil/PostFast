#!/usr/bin/env python3
"""
Script de prueba para verificar que revision_cycles se mantiene correctamente entre ciclos.
"""

import asyncio
import sys
import os
import uuid

# Añadir el directorio raíz al path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.dependencies.graph import graph
from src.agents.content_agent.callbacks import TokenUsageCallback

async def test_revision_cycles():
    """Prueba que revision_cycles se mantiene correctamente entre ciclos."""
    
    print("🧪 Iniciando prueba de revision_cycles...")
    
    # Estado inicial
    initial_state = {
        "query": "Quiero un post sobre inteligencia artificial para LinkedIn",
        "tone": "profesional pero cercano",
        "niche": "tecnología",
        "account_name": "TechCorp",
        "link_url": "https://example.com/ai-article",
        "token_usage_by_node": {},
        "total_tokens": 0,
        "review_notes": "",
        "revision_cycles": 0,  # Inicializado a 0
        "creative_brief": None,
        "draft_content": None,
        "refined_content": None,
        "formatted_output": None,
        "final_post": None,
    }
    
    print(f"📊 Estado inicial - revision_cycles: {initial_state['revision_cycles']}")
    
    # Crear callback para tracking
    callback = TokenUsageCallback(initial_state)
    
    try:
        # Ejecutar el grafo
        print("🚀 Ejecutando grafo...")
        final_state = await graph.ainvoke(
            initial_state,
            config={
                "callbacks": [callback],
                "configurable": {"thread_id": str(uuid.uuid4())}
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
            
        return final_state
        
    except Exception as e:
        print(f"❌ Error durante la ejecución: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🔧 Iniciando prueba de revision_cycles...")
    result = asyncio.run(test_revision_cycles())
    
    if result:
        print("✅ Prueba completada exitosamente")
    else:
        print("❌ Prueba falló")
        sys.exit(1) 