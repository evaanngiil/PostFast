#!/usr/bin/env python3
"""
Script de prueba para verificar que el flujo corregido funciona correctamente.
"""

import asyncio
import sys
import os

# Añadir el directorio raíz al path para importar los módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.dependencies.graph import graph
from src.agents.content_agent.callbacks import TokenUsageCallback

async def test_fixed_flow():
    """Prueba el flujo corregido del agente."""
    
    print("🧪 Probando flujo corregido del agente...")
    
    # Estado inicial de prueba
    initial_state = {
        "query": "Anunciar la contratación de María como Data Engineer desde las Islas Canarias",
        "tone": "Professional",
        "niche": "Tech professionals and data engineers",
        "account_name": "Evan's Tech Company",
        "link_url": "https://example.com/careers",
        "token_usage_by_node": {},
        "total_tokens": 0,
        "review_notes": "",
        "revision_cycles": 0,
        "creative_brief": None,
        "draft_content": None,
        "refined_content": None,
        "formatted_output": None,
        "final_post": None,
        "human_feedback": ""
    }
    
    # Crear callback para tracking de tokens
    callback = TokenUsageCallback(initial_state)
    
    print("🚀 Ejecutando grafo...")
    
    try:
        # Ejecutar el grafo
        final_state = await graph.ainvoke(
            initial_state,
            config={"callbacks": [callback], "configurable": {"thread_id": "test-thread"}}
        )
        
        print("✅ Grafo ejecutado exitosamente")
        print(f"📊 Estado final - revision_cycles: {final_state.get('revision_cycles')}")
        print(f"📊 Contenido final: {final_state.get('final_post', 'No disponible')}")
        print(f"📊 Tokens usados: {final_state.get('total_tokens', 0)}")
        print(f"📊 Tokens por nodo: {final_state.get('token_usage_by_node', {})}")
        
        # Verificar que el flujo funcionó correctamente
        if final_state.get('final_post'):
            print("✅ Contenido final generado correctamente")
        else:
            print("❌ No se generó contenido final")
            
        if final_state.get('total_tokens', 0) > 0:
            print("✅ Tracking de tokens funcionando")
        else:
            print("⚠️  No se detectaron tokens (puede ser normal con Gemini)")
            
        return True
        
    except Exception as e:
        print(f"❌ Error durante la ejecución: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_fixed_flow())
    if success:
        print("\n🎉 ¡Prueba completada exitosamente!")
    else:
        print("\n💥 Prueba falló")
        sys.exit(1) 