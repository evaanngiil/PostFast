# PostFast (AIPost) 🚀

> **Plataforma Multi-Agente Autónoma para la Generación, Auditoría y Publicación de Contenido B2B en LinkedIn**  
> *Trabajo de Fin de Grado en Ingeniería Informática*

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16.3-black.svg?logo=next.js)](https://nextjs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2+-blueviolet.svg)](https://langchain-ai.github.io/langgraph/)
[![Supabase](https://img.shields.io/badge/Supabase-pgvector-3ECF8E.svg?logo=supabase)](https://supabase.com/)
[![Celery](https://img.shields.io/badge/Celery-5.6+-37814A.svg?logo=celery)](https://docs.celeryq.dev/)
[![MCP](https://img.shields.io/badge/Model_Context_Protocol-v2.2-FF6F00.svg)](https://modelcontextprotocol.io/)
[![Pytest](https://img.shields.io/badge/Tests-87%2F87%20passing-brightgreen.svg?logo=pytest)](https://docs.pytest.org/)

---

## 📋 Tabla de Contenidos
1. [Descripción General](#-descripción-general)
2. [Arquitectura del Sistema (5 Planos)](#-arquitectura-del-sistema-5-planos)
3. [Topología del Grafo Multi-Agente (11 Nodos)](#-topología-del-grafo-multi-agente-11-nodos)
4. [Requisitos Previos](#-requisitos-previos)
5. [Guía de Instalación Paso a Paso](#-guía-de-instalación-paso-a-paso)
6. [Puesta en Marcha y Ejecución Local](#-puesta-en-marcha-y-ejecución-local)
7. [Modo Demostración Rápida (Demo Mode)](#-modo-demostración-rápida-demo-mode)
8. [Servidor Model Context Protocol (MCP)](#-servidor-model-context-protocol-mcp)
9. [Batería de Pruebas y Control de Calidad](#-batería-de-pruebas-y-control-de-calidad)
10. [Harness de Evaluación Empírica](#-harness-de-evaluación-empírica)
11. [Estructura del Proyecto](#-estructura-del-proyecto)
12. [Preguntas Frecuentes y Solución de Problemas (FAQ)](#-preguntas-frecuentes-y-solución-de-problemas-faq)

---

## 💡 Descripción General

**PostFast** es un sistema de ingeniería de software e inteligencia artificial agéntica diseñado para resolver de raíz las limitaciones de los LLMs tradicionales (*prompting* monolítico) en la comunicación corporativa B2B de LinkedIn: **alucinaciones fácticas**, **amnesia editorial**, **tono genérico sin identidad de marca** y **ausencia de supervisión humana**.

A diferencia de un asistente que genera texto en una sola llamada sin verificar fuentes:
- **Supervisor Determinista**: La máquina de estados se controla mediante lógica algorítmica pura en Python sobre el grafo de LangGraph, eliminando bucles infinitos y reduciendo el consumo innecesario de tokens.
- **Auditoría Factual Claim-a-Claim (Corrective RAG - CRAG)**: El nodo `fact_checker` descompone el borrador en afirmaciones independientes y busca evidencias en la base de conocimientos vectorial corporativa (`pgvector`) y en la web en tiempo real (Tavily).
- **Salvaguarda de Marca y Compliance (*Safety Guard*)**: Filtra proactivamente fugas de Información de Identificación Personal (PII), superlativos no demostrables y directivas prohibidas del Código de Conducta.
- **Memoria Agéntica de 4 Niveles**: Memoria de trabajo transaccional, semántica (RAG vectorial), episódica (historial de publicaciones en PostgreSQL) y procedural (Skills editoriales en Markdown).
- **Human-in-the-Loop (HITL) Transaccional**: Punto de pausa persistente antes de la entrega final con edición quirúrgica asistida.
- **Interoperabilidad Abierta vía MCP**: Expone sus capacidades como herramientas estandarizadas bajo el **Model Context Protocol** para clientes como Claude Desktop o Cursor IDE.

![Grafo multi-agente](final_mutiagent_graph.png)

---

## 🏛 Arquitectura del Sistema (5 Planos)

La plataforma está diseñada siguiendo un desacoplamiento estricto en cinco planos funcionales:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   1. PLANO DE PRESENTACIÓN (Frontend)                  │
│       Next.js 16 (React 19) + Tailwind CSS v4 + Server Actions         │
│         Dashboard, Studio, Terminal Agéntica, Auditoría en Vivo        │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │ HTTP / WebSockets
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    2. PLANO DE API GATEWAY (FastAPI)                   │
│       OpenAPI 3.1, Sesiones Multi-Tenant, Ingesta RAG, OAuth 2.0       │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │ Encolamiento Asíncrono
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│              3. PLANO DE CÓMPUTO DISTRIBUIDO (Celery + Redis)          │
│       Workers en segundo plano ejecutando grafos de LangGraph          │
│         Bucle de investigación RAG, Fan-out concurrente, HITL          │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │ Checkpoints & Embeddings
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│             4. PLANO DE PERSISTENCIA HÍBRIDA (PostgreSQL)              │
│       Supabase (pgvector con índice HNSW 768d + Supavisor :6543)       │
│    Checkpointer LangGraph, Company Knowledge, Skills, Realtime Pub/Sub │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│             5. PLANO DE INTEROPERABILIDAD EXTERNA (Servidor MCP)       │
│       Model Context Protocol v2.2 (src/mcp_server.py vía stdio)        │
│       5 Tools disponibles para Claude Desktop, Cursor IDE y Agentes    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🧠 Topología del Grafo Multi-Agente (11 Nodos)

El flujo cognitivo se ejecuta a través de una secuencia de fases coordinadas por el supervisor determinista:

| Fase | Nodos | Rol / Responsabilidad | Modelo LLM |
|---|---|---|---|
| **Fase 1** | `supervisor` | Lógica determinista de ruteo según el estado (sin LLM) | *Algorítmico puro* |
| **Fase 2** | `engagement_analyzer`<br>`persona_analyst` | Extrae métricas de impacto de posts pasados y destila el tono de voz de la marca | `gemini-3.1-flash-lite-preview` |
| **Fase 3** | `duplicate_detector`<br>`trend_researcher` | *(Paralelo)* Evalúa canibalización semántica en `post_embeddings` e investiga tendencias con Tavily | `gemini-3.1-flash-lite-preview`<br>`gemini-3.6-flash` |
| **Fase 4** | `idea_expander`<br>`content_writer` | Estructura los ángulos editoriales y redacta el borrador con bucle autónomo RAG | `gemini-3.6-flash` |
| **Fase 5** | `fact_checker`<br>`safety_guard` | *(Paralelo)* Verificación CRAG claim-a-claim y auditoría de compliance/PII | `gemini-3.6-flash`<br>`gemini-3.1-flash-lite-preview` |
| **Fase 6** | `content_editor` | Aplica correcciones quirúrgicas ante fallos de auditoría o sugerencias humanas | `gemini-3.6-flash` |
| **Fase 7** | `human_review` | Interrupción persistente HITL para validación humana final y publicación | *Intervención humana* |

---

## 📦 Requisitos Previos

Antes de comenzar, asegúrate de contar con el siguiente software instalado:

1. **Python**: Versión `>= 3.11` y `< 3.13` (recomendada `3.12`).
2. **Poetry**: Gestor de paquetes y entornos virtuales de Python (`curl -sSL https://install.python-poetry.org | python3 -`).
3. **Node.js**: Versión `>= 18.18` o `>= 20.x` junto con `npm`.
4. **Redis**: Servidor de Redis en ejecución (puerto `6379`).
5. **Cuenta en Supabase**: Proyecto activo con PostgreSQL y extensión `vector` (`pgvector`).
6. **Claves de API**:
   - **Google Gemini API Key** (`GENAI_API_KEY`): Inferencia de LLMs y generación de embeddings (`text-embedding-004`).
   - **Tavily Search API Key** (`TAVILY_API_KEY`): Búsqueda web para tendencias y verificación fáctica externa.
   - *(Opcional)* **LinkedIn Developer App**: Si se desea sincronizar perfiles y publicar posts reales.
   - *(Opcional)* **LangSmith API Key**: Para observabilidad y trazabilidad distribuida por nodo.

---

## 🚀 Guía de Instalación Paso a Paso

### Paso 1: Clonar el Repositorio

```bash
git clone https://github.com/evaanngiil/PostFast.git
cd PostFast
```

### Paso 2: Instalar Dependencias del Backend (Python)

Instala el entorno virtual con todas las dependencias principales y de desarrollo con Poetry:

```bash
poetry install --with dev
```

Verifica la instalación activando el entorno o comprobando la versión:

```bash
poetry run python --version
```

### Paso 3: Configurar Variables de Entorno

Copia la plantilla de entorno base a la raíz del proyecto:

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales. A continuación se detallan las variables obligatorias y recomendadas:

```env
# ==== Inferencia y Embeddings (Google Gemini) ====
GENAI_API_KEY=tu_gemini_api_key_aqui

# ==== Base de Datos y Persistencia (Supabase) ====
SUPABASE_URL=https://tu-proyecto.supabase.co
# Clave PRIVILEGIADA del backend (service_role secret). NUNCA exponer al cliente:
SUPABASE_KEY=tu_supabase_service_role_key
# Clave PÚBLICA (anon) para Realtime en frontend:
SUPABASE_ANON_KEY=tu_supabase_anon_key
# String de conexión para checkpointer LangGraph (Supavisor transaccional en puerto 6543):
SUPABASE_CONN_STRING=postgresql://postgres.tu-proyecto:tu_password@aws-0-eu-central-1.pooler.supabase.com:6543/postgres?prepare_threshold=0

# ==== Colas de Mensajería y Caché (Redis / Celery) ====
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379

# ==== Búsqueda Web en Vivo (Tendencias y Fact-Checking Externo) ====
TAVILY_API_KEY=tu_tavily_api_key

# ==== URLs de la Aplicación y Sesiones ====
BASE_URL=http://localhost:3000
FASTAPI_URL=http://localhost:8000
SECRET_KEY=clave_secreta_aleatoria_para_cookies_de_sesion

# ==== Flags de Ejecución ====
# false = Producción/Desarrollo normal; true = Habilita tokens 'mock_*' de prueba sin LinkedIn OAuth
AIPOST_DEMO_MODE=true
AIPOST_ENFORCE_ORG_ACCESS=true
```

> [!IMPORTANT]
> **Supavisor y Checkpointer**: En `SUPABASE_CONN_STRING`, asegúrate de incluir el parámetro `?prepare_threshold=0`. El connection pooler transaccional de Supabase (puerto 6543) no admite sentencias SQL preparadas persistentes en el pool, y este parámetro evita errores de protocolo `prepared statement does not exist`.

### Paso 4: Inicializar la Base de Datos en Supabase

Abre el **SQL Editor** en el panel de control de tu proyecto Supabase y ejecuta los siguientes scripts en orden:

1. **[`docs/enable_pgvector.sql`](docs/enable_pgvector.sql)**:
   - Activa la extensión `vector`.
   - Crea la tabla `company_knowledge` con índice HNSW (`vector(768)`).
   - Crea la tabla `post_embeddings` con índice HNSW (`vector(768)`).
   - Registra las funciones almacenadas RPC `match_company_knowledge` y `match_similar_posts`.

2. **[`docs/create_skills_table.sql`](docs/create_skills_table.sql)**:
   - Crea la tabla `skills` para el catálogo de directrices editoriales en Markdown.

3. **[`migrations/001_user_organizations.sql`](migrations/001_user_organizations.sql)**:
   - Crea la tabla `user_organizations` para control de acceso y membresía multi-tenant.

4. **[`migrations/002_exclude_full_documents_from_match.sql`](migrations/002_exclude_full_documents_from_match.sql)**:
   - Actualiza la función `match_company_knowledge` para excluir filas maestras completas y enfocar la búsqueda semántica únicamente en chunks atómicos.

### Paso 5: Instalar Dependencias del Frontend (Next.js)

Accede a la carpeta de la interfaz y descarga los módulos de Node:

```bash
cd postfast-frontend
npm install
cd ..
```

---

## 💻 Puesta en Marcha y Ejecución Local

Para levantar el ecosistema completo en desarrollo, abre cuatro terminales independientes:

### Terminal 1: Broker de Mensajes (Redis)

Si tienes Docker instalado:
```bash
docker run --name redis-postfast -p 6379:6379 -d redis:alpine
```
O si tienes Redis instalado localmente:
```bash
redis-server
```

### Terminal 2: Worker de Celery (Grafo de Agentes)

Ejecuta el worker asíncrono. En entornos **macOS** o plataformas con restricciones de bifurcación (`fork`), se recomienda explícitamente el pool de hilos:

```bash
poetry run celery -A src.celery_app worker -P threads -c 4 --loglevel=info
```

### Terminal 3: Backend API (FastAPI)

Inicia el servidor REST con recarga en caliente:

```bash
poetry run uvicorn src.main:app --reload --port 8000
```
- **Documentación Interactiva (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Especificación OpenAPI**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

### Terminal 4: Frontend Web (Next.js)

Levanta la interfaz web:

```bash
cd postfast-frontend
npm run dev
```
- **Aplicación Web**: [http://localhost:3000](http://localhost:3000)

---

## 🧪 Modo Demostración Rápida (Demo Mode)

Si deseas probar la plataforma de inmediato sin necesidad de configurar una aplicación de desarrollador en LinkedIn OAuth:

1. Configura en tu archivo `.env`:
   ```env
   AIPOST_DEMO_MODE=true
   ```
2. Inicia sesión en [http://localhost:3000/login](http://localhost:3000/login) o utiliza el token de pruebas en las cabeceras HTTP:
   ```http
   Authorization: Bearer mock_token_tfg
   ```
3. El sistema habilitará las rutas de prueba, simulará una organización corporativa con sus métricas y permitirá lanzar el pipeline multi-agente al completo.

---

## 🔌 Servidor Model Context Protocol (MCP)

PostFast incorpora un servidor oficial **Model Context Protocol (MCP)** en [`src/mcp_server.py`](src/mcp_server.py) que permite a clientes de IA externos (como **Claude Desktop** o **Cursor IDE**) consultar la base de conocimiento corporativa y disparar la generación de posts de forma interoperable.

### Herramientas Expuestas

| Herramienta | Parámetros Principales | Descripción |
|---|---|---|
| `search_company_knowledge` | `query`, `org_urn`, `match_count` | Búsqueda semántica en RAG vectorial con aislamiento multi-tenant |
| `list_organization_skills` | `org_urn` | Consulta el catálogo de directrices de estilo en Markdown |
| `check_post_cannibalization` | `text`, `org_urn`, `threshold` | Detección de duplicados semánticos en posts históricos |
| `trigger_agent_generation` | `topic`, `org_urn`, `mode`, `skills` | Encola de forma asíncrona la tarea en Celery devolviendo `task_id` |
| `check_pipeline_status` | `task_id` | Consulta en tiempo real el estado y resultado del pipeline |

### Integración con Claude Desktop

Añade la siguiente configuración a tu archivo de Claude Desktop:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "postfast": {
      "command": "poetry",
      "args": ["run", "python", "-m", "src.mcp_server"],
      "cwd": "/ruta/absoluta/a/PostFast"
    }
  }
}
```

### Ejecución Manual del Servidor MCP

```bash
poetry run python -m src.mcp_server
```

---

## 🧪 Batería de Pruebas y Control de Calidad

El proyecto cuenta con una cobertura integral de pruebas automatizadas mediante **Pytest** (**87 de 87 tests pasando al 100%** en ~2.5 segundos):

```bash
poetry run pytest tests/ -v
```

### Desglose de Pruebas

- **Pruebas Unitarias de Componentes (32 tests)**:
  - Supervisor determinista ([`tests/test_supervisor.py`](tests/test_supervisor.py)): 19 tests que validan todas las transiciones de estado, fan-outs paralelos, bucles de corrección y ablación.
  - Chunking semántico RAG ([`tests/test_rag_chunking.py`](tests/test_rag_chunking.py)): 5 tests de preservación de texto, división por párrafos y bordes de token.
  - Editor quirúrgico ([`tests/test_content_editor.py`](tests/test_content_editor.py)): 8 tests de resolución de directivas y compatibilidad con feedback humano.
- **Pruebas de Integración y Persistencia (5 tests)**:
  - [`tests/test_graph_flow.py`](tests/test_graph_flow.py): Ejecución de extremo a extremo del grafo con mocks de modelos, pausa HITL en `human_review`, actualización de checkpoints y reanudación con feedback.
- **Pruebas de Seguridad y Aislamiento Multi-Tenant (6 tests)**:
  - [`tests/test_multi_tenant_security.py`](tests/test_multi_tenant_security.py): Comprueba que las búsquedas RAG, detección de duplicados, subida de documentos y gestión de skills filtran de forma inmutable por `org_urn`.
- **Pruebas del Servidor MCP (6 tests)**:
  - [`tests/test_mcp_server.py`](tests/test_mcp_server.py): Validación del registro de herramientas, llamadas asíncronas y despacho a Celery.
- **Otras Pruebas de API y Autenticación (38 tests)**:
  - Endpoints REST, tokens OAuth de LinkedIn, parsing de publicaciones y métricas.

### Análisis Estático de Código (Linter)

```bash
poetry run ruff check src evaluation tests
```

---

## 📊 Harness de Evaluación Empírica

Para la validación experimental y la defensa académica del TFG, el proyecto incluye un harness de evaluación científica reproducible sobre 20 casos de prueba:

```bash
# 1. Generar publicaciones comparativas (Multi-Agente vs. Baselines)
python -m evaluation.run_eval --org-urn "urn:li:organization:XXXX" \
    --systems aipost,baseline_context,baseline_vanilla

# 2. Ejecutar auditoría objetiva y evaluación ciega con Juez LLM
python -m evaluation.evaluate evaluation/results/run_<fecha>.jsonl

# 3. Estudio de ablación (evaluar impacto al apagar nodos específicos)
python -m evaluation.run_eval --org-urn "urn:li:organization:XXXX" \
    --systems aipost,aipost_no_fact_checker,aipost_no_research_loop \
    --only-kb-dependent
```

Consulta [`evaluation/README.md`](evaluation/README.md) para conocer la metodología detallada, el dataset etiquetado y los criterios de desempate del juez ciego.

---

## 📁 Estructura del Proyecto

```text
PostFast/
├── docs/                               # Esquemas SQL, guías de prueba y memoria del TFG
│   ├── enable_pgvector.sql             # Tablas vectoriales e índices HNSW en Supabase
│   ├── create_skills_table.sql         # Tabla de directrices de estilo en Markdown
│   └── GUIA_REDACCION_MEMORIA_TFG.md   # Guía canónica de redacción de los 12 capítulos
├── evaluation/                         # Harness de experimentación y evaluación empírica
│   ├── dataset.json                    # 20 casos de prueba etiquetados para el benchmark
│   ├── evaluate.py                     # Juez LLM ciego y cálculo de métricas objetivas
│   └── run_eval.py                     # Orquestador de ejecuciones comparativas
├── migrations/                         # Migraciones incrementales de PostgreSQL
│   ├── 001_user_organizations.sql     # Mapeo de membresía multi-tenant
│   └── 002_exclude_full_documents...   # Ajuste fino de similitud en RAG
├── postfast-frontend/                  # Aplicación SPA en Next.js 16 (React 19)
│   ├── src/app/dashboard/              # Dashboard, Estudio Editorial, Auditoría, Skills
│   └── package.json                    # Dependencias frontend (Next.js, Tailwind v4)
├── src/                                # Código fuente del Backend y Sistema Agéntico
│   ├── agents/
│   │   └── multi_agent/
│   │       ├── graph.py                # Definición del grafo LangGraph y checkpoints
│   │       └── nodes/                  # Los 11 nodos cognitivos especializados
│   │           ├── supervisor.py       # Supervisor determinista por estado
│   │           ├── content_writer.py   # Redactor con bucle de investigación RAG
│   │           ├── fact_checker.py     # Auditor fáctico CRAG claim-a-claim
│   │           ├── safety_guard.py     # Auditor de compliance, PII y tono
│   │           └── content_editor.py   # Editor quirúrgico para autocorrección
│   ├── celery_app.py                   # Configuración del broker Celery
│   ├── main.py                         # API Gateway FastAPI y middlewares
│   ├── mcp_server.py                   # Servidor Model Context Protocol v2.2
│   ├── routers/content.py              # Endpoints de generación, HITL y documentos
│   ├── services/                       # Clientes de Supabase, pgvector y LinkedIn
│   └── tasks.py                        # Tareas asíncronas de ejecución del grafo
├── tests/                              # Batería de 87 tests automatizados en Pytest
├── pyproject.toml                      # Gestión de dependencias y configuración Poetry
└── README.md                           # Documentación principal del repositorio
```

---

## ❓ Preguntas Frecuentes y Solución de Problemas (FAQ)

### 1. Error `prepared statement "..." does not exist` en Supabase
- **Causa**: Ocurre cuando el checkpointer de LangGraph intenta reutilizar sentencias preparadas en PostgreSQL a través del connection pooler transaccional Supavisor (puerto 6543).
- **Solución**: Añade `?prepare_threshold=0` al final de la variable `SUPABASE_CONN_STRING` en tu archivo `.env`.

### 2. El worker de Celery se congela o falla en macOS
- **Causa**: Las políticas de seguridad de macOS bloquean llamadas de sistema `fork()` en procesos que cargan ciertas librerías nativas de C / Objective-C.
- **Solución**: Ejecuta el worker indicando explícitamente el pool de hilos:
  ```bash
  poetry run celery -A src.celery_app worker -P threads -c 4 --loglevel=info
  ```

### 3. Límites de Tasa (*Rate Limits*) con Google Gemini
- **Causa**: Superar las cuotas por minuto (RPM) o por día (RPD) del plan gratuito de Gemini API.
- **Solución**: Configura en `.env` el modelo `FAST_LLM=gemini-3.1-flash-lite-preview` para los nodos de análisis frecuente y reserva `SMART_LLM=gemini-3.6-flash` exclusivamente para la redacción final y el juez.

### 4. ¿Cómo pruebo la subida de documentos RAG?
- Desde el frontend, accede a la sección **Base de Conocimiento**, selecciona tu organización y sube un archivo PDF institucional. El sistema lo fragmentará automáticamente en chunks atómicos (`CHUNK_SIZE = 800`) y generará los embeddings en `company_knowledge`.

---

## 📄 Licencia y Reconocimientos

Este proyecto ha sido desarrollado como Trabajo de Fin de Grado (TFG) en Ingeniería Informática.  
- **Autor**: Evan  
- **Contacto**: [evaanngc@gmail.com](mailto:evaanngc@gmail.com)  
- **Repositorio**: [https://github.com/evaanngiil/PostFast](https://github.com/evaanngiil/PostFast)
