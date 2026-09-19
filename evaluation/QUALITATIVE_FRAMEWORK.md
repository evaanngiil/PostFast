# Marco Metodológico de Validación Cualitativa (TFG AIPost)

Este documento define el diseño experimental, la matriz de casuísticas, las hipótesis de partida y la rúbrica de análisis cualitativo para comparar la propuesta agéntica **AIPost** frente a las soluciones comerciales directas del mercado (**ChatGPT** y **Google Gemini**).

---

## 1. Justificación y Objetivos de la Validación Cualitativa

En el procesamiento de lenguaje natural aplicado a la comunicación corporativa, las métricas puramente automáticas (como longitud, n-gramas o recuento de tokens) son insuficientes para capturar la idoneidad editorial, el rigor factual y la seguridad jurídica de un texto. Un post puede tener una gramática perfecta pero ser completamente inaceptable para el departamento de comunicación de una multinacional como BBVA si:
- Inventa una alianza con un competidor o atribuye citas falsas a directivos (alucinación factual).
- Emplea superlativos no demostrables ("somos la entidad más infalible del mundo"), incurriendo en publicidad engañosa y violando normativas financieras (CNMV/EBA).
- Utiliza estructuras genéricas de IA ("¡En el vertiginoso mundo actual...!", "Estamos encantados de anunciar...") que degradan la credibilidad de la marca y saturan a la audiencia de LinkedIn.
- Ignora la arquitectura oficial de hashtags (`#LifeAtBBVA`), enlaces verificados y formatos de lectura móvil (gancho inicial, párrafos de 1-2 líneas, viñetas visuales).

**Objetivo central**: Demostrar cualitativamente, mediante inspección ciega y análisis crítico del output, por qué un flujo agéntico especializado con verificación factual (CRAG), auditoría de compliance y Human-in-the-Loop supera a la interacción directa con ChatGPT o Gemini.

---

## 2. Matriz de Casuísticas de Evaluación (2×2)

Para garantizar una experimentación representativa, los prompts y publicaciones de prueba se estructuran en una matriz bidimensional basada en dos variables ortogonales:

```
                  ALTO CONTEXTO CORPORATIVO (RAG-dependiente)
                                      ▲
                                      │
              ESCENARIO 2 (C2)        │        ESCENARIO 4 (C4)
        Baja Complejidad Técnica       │    Alta Complejidad Técnica
        Alto Contexto Corporativo     │    Alto Contexto Corporativo
        (e.g., Premios ViVa, BeTalent,│    (e.g., Cripto cuántica QRNG,
         Orgullo LGTBIQ+ Be Yourself) │     FrauDfense, Deals sostenibles)
                                      │
  BAJA COMPLEJIDAD ───────────────────┼───────────────────► ALTA COMPLEJIDAD
                                      │
              ESCENARIO 1 (C1)        │        ESCENARIO 3 (C3)
        Baja Complejidad Técnica       │    Alta Complejidad Técnica
        Bajo Contexto Corporativo     │    Bajo Contexto Corporativo
        (e.g., Yellow Day, empatía,   │    (e.g., Divulgación de IA ética,
         debate abierto en finanzas)  │     Fronteras del Conocimiento)
                                      │
                                      ▼
                  BAJO CONTEXTO CORPORATIVO (Conocimiento Abierto)
```

### 2.1 Definición y Justificación de las Variables

1. **Nivel de Contexto Corporativo Requerido**:
   - **Bajo**: Peticiones fundamentadas en conocimiento de dominio público, conceptos universales o reflexiones donde no se precisa acceder a bases documentales privadas ni a directivas internas de la entidad.
   - **Alto (KB-dependiente)**: Peticiones que exigen información específica, verídica y documentada en la base de conocimientos de BBVA (Código de Conducta art. 4.20, Política de Sostenibilidad 2022, Política de Comunicación Publicitaria 2026, marcas internas como *FrauDfense* o *Polaris*, y métricas reales de programas).
   - *Justificación*: Permite aislar si la solución comercial alucina cuando se le pide hablar de proyectos internos concretos.

2. **Complejidad del Contenido**:
   - **Baja**: Contenido social, emocional, formativo introductorio, felicitaciones o ganchos de debate donde la estructura es flexible y el vocabulario es accesible para cualquier lector.
   - **Alta**: Contenido técnico-financiero, criptografía avanzada (QRNG, simulaciones Montecarlo), marcos regulatorios europeos (reglamento PSR de pagos), auditoría de descarbonización de clientes corporativos o gestión de crisis institucional (sismos, donaciones humanitarias).
   - *Justificación*: Evalúa si el sistema es capaz de mantener el rigor conceptual sin perder la capacidad divulgativa propia de LinkedIn.

---

## 3. Hipótesis Experimentales por Escenario

| Escenario | Hipótesis para Soluciones Comerciales (ChatGPT / Gemini directo) | Hipótesis para AIPost (Propuesta TFG) | Diferencial Demostrable del TFG |
|---|---|---|---|
| **C1: Baja Complejidad + Bajo Contexto** | Generan textos sintácticamente correctos, pero con tono genérico, clichés repetitivos de IA ("En este día tan especial...", "El éxito radica en...") y hashtags de relleno sin relación con la empresa. | Genera ganchos orientados a retención móvil, espaciado legible y aplica la voz de marca definida por el `persona_analyst`. | Estructura optimizada para el algoritmo de LinkedIn y consistencia editorial sin clichés. |
| **C2: Baja Complejidad + Alto Contexto** | **Alucinación de cultura y programas**: inventan nombres de iniciativas internas, mencionan eventos inexistentes o usan hashtags genéricos (`#Banking`, `#Jobs`) ignorando la convención oficial (`#LifeAtBBVA`, `#PremiosViVaBBVA`). | El `idea_expander` y `content_writer` recuperan los detalles de los programas reales desde el RAG; el `fact_checker` corrobora que las etapas y nombres coinciden con la documentación interna. | Anclaje institucional verídico: el post parece escrito por el equipo de Talento de la entidad. |
| **C3: Alta Complejidad + Bajo Contexto** | Generan explicaciones técnicas competentes pero excesivamente académicas o estilo enciclopedia (estilo Wikipedia), sin adaptación al formato ágil y persuasivo de LinkedIn. | El agente traduce conceptos complejos en analogías y viñetas estructuradas (emojis temáticos como bullets) con llamada a la acción clara. | Capacidad de síntesis ejecutiva y divulgación profesional adaptada a redes. |
| **C4: Alta Complejidad + Alto Contexto** (Escenario crítico) | **Alto riesgo de alucinación técnica y violación de compliance**: confunden partners (e.g., no saben que FrauDfense es una alianza con Santander y CaixaBank), inventan cifras numéricas ("hemos reducido el fraude un 99%"), o usan superlativos prohibidos ("el sistema más infalible"). | **Triunfo del pipeline agéntico**: <br>1. El writer busca en el RAG y en la web con bucle autónomo.<br>2. El `fact_checker` CRAG extrae los claims y verifica cada dato contra la evidencia.<br>3. El `safety_guard` audita políticas publicitarias.<br>4. Si hay fallos, el ciclo de autocorrección reescribe el borrador antes de entregarlo. | **Eliminación demostrable de alucinaciones y blindaje legal**: la empresa no puede publicar lo que entrega un LLM directo sin riesgo reputacional. |

---

## 4. Rúbrica Cualitativa de Evaluación (5 Dimensiones)

Para la comparativa cualitativa, cada post generado por los sistemas en liza se evalúa mediante una rúbrica ciega de 1 a 5 puntos en las siguientes dimensiones:

### Dimensión 1: Estructura y Redacción de LinkedIn (Linkedin Craft)
- **Criterio**: Gancho inicial (hook) que incite a pulsar "ver más", párrafos cortos (1-2 oraciones), uso inteligente de espacios en blanco para lectura en smartphone, viñetas visuales (emojis como bullets) y llamada a la acción (CTA) orientada a la interacción o visita de enlace.
- **Puntuación**: 1 (bloque de texto plano o estilo ensayo) a 5 (maquetación profesional nativa de LinkedIn).

### Dimensión 2: Fidelidad a la Voz de Marca y Ausencia de Clichés (Brand Voice & Anti-Cliché)
- **Criterio**: Tono profesional, sobrio, cercano y seguro, coherente con una entidad bancaria de primer nivel. Ausencia total de frases hechas de LLM genérico ("En el mundo acelerado de hoy...", "¡Notición!", "Sumérgete en...", "Un hito sin precedentes").
- **Puntuación**: 1 (IA genérica evidente y tono artificial) a 5 (voz corporativa auténtica y creíble).

### Dimensión 3: Anclaje Factual y Precisión de Datos (Factual Grounding)
- **Criterio**: Todos los datos, cifras, nombres de programas, socios tecnológicos o certificaciones mencionados en el texto están fundamentados en hechos reales documentados. Ausencia de datos inventados.
- **Puntuación**: 1 (alucinaciones graves de nombres o cifras) a 5 (100% verídico y demostrable).

### Dimensión 4: Cumplimiento Normativo y Políticas de Marca (Compliance & Safety)
- **Criterio**: Cumplimiento del Código de Conducta y la Política de Comunicación Publicitaria de BBVA: ausencia de superlativos no demostrables ("los mejores", "100% infalible"), respeto al GDPR (sin revelar datos privados de clientes), mención rigurosa de alianzas con competidores y ausencia de promesas financieras engañosas.
- **Puntuación**: 1 (infracción severa que bloquearía la publicación) a 5 (cumplimiento estricto y seguro).

### Dimensión 5: Arquitectura de Marca y Enlaces (Brand Assets & Hashtags)
- **Criterio**: Empleo de los hashtags institucionales correctos (`#LifeAtBBVA` combinado con el específico de campaña: `#Ciberseguridad`, `#BeTalentBBVA`, `#Sostenibilidad`) y presencia de estructura de enlace oficial (`bbva.info/...`).
- **Puntuación**: 1 (hashtags inventados o genéricos como `#Fintech #Money`) a 5 (ecosistema oficial de hashtags y assets de marca).

---

## 5. Parámetros de Configuración y Variabilidad

En la experimentación se controlan y documentan los siguientes parámetros:

1. **Soluciones Comerciales Directas**:
   - **ChatGPT Comercial**: Modelo `gpt-4o` (o interfaz comercial equivalente) con temperatura 0.7, prompt crudo del usuario sin inyección de archivos.
   - **Gemini Comercial**: Modelo `gemini-2.5-flash` con temperatura 0.7, prompt crudo del usuario.
2. **Propuesta TFG (AIPost)**:
   - Configuración estándar: `aipost` (pipeline completo con 11 nodos, bucles de corrección de máx. 3 iteraciones, checkpointer persistente).
   - Variantes de ablación para aislar la contribución de los componentes:
     - `aipost_no_fact_checker`: para medir el impacto de suprimir la verificación CRAG.
     - `aipost_no_safety_guard`: para cuantificar los falsos positivos/negativos de compliance.
     - `aipost_no_research_loop`: para comparar la investigación autónoma frente a una pasada fija.
   - Parámetro HITL: Evaluación del impacto de 1 ciclo de feedback humano asistido por el nodo quirúrgico `content_editor`.

---

## 6. Plantilla de Análisis Cualitativo Caso por Caso

Para cada caso del dataset de evaluación, la memoria del TFG incluirá una ficha analítica comparativa con el siguiente formato:

```markdown
### Caso [ID]: [Título] (Casuística: [C1/C2/C3/C4])
- **Prompt del usuario**: "..."
- **Contexto corporativo**: [Alto / Bajo] | **Complejidad**: [Alta / Baja]
- **Ground Truth (Post real humano de BBVA)**: "..."

#### Comparativa de Salidas:
| Dimensión | ChatGPT Comercial | Gemini Comercial | AIPost (TFG) |
|---|---|---|---|
| D1: Formato LinkedIn | ... | ... | ... |
| D2: Voz de Marca | ... | ... | ... |
| D3: Factualidad | ... | ... | ... |
| D4: Compliance | ... | ... | ... |
| D5: Hashtags | ... | ... | ... |

#### Hallazgos Cualitativos Clave:
- **Diferencia crítica observada**: [e.g., ChatGPT inventó que BBVA creó FrauDfense en solitario, omitiendo a CaixaBank y Santander; AIPost identificó la alianza tripartita desde el RAG y citó el servicio FrauDfense Check correctamente].
- **Veredicto cualitativo**: Por qué un gestor de comunicación publicaría la salida de AIPost y descartaría la salida comercial directa.
```
