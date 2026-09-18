# Documentos públicos de BBVA para RAG (TFG - AIPost)

Empresa modelo: **BBVA** (Banco Bilbao Vizcaya Argentaria, S.A.)

## Documentos ya extraídos en esta carpeta (texto completo o extracto, listos para ingestión)

| Archivo | Contenido | Relevancia para redacción/RAG |
|---|---|---|
| `01_Codigo_de_Conducta_Grupo_BBVA.txt` | Código de Conducta completo (aprobado 30/07/2024) | Alta. Incluye sección 4.20 "Presencia en redes sociales" con pautas de tono, confidencialidad y buenas prácticas |
| `02_Politica_General_Sostenibilidad_BBVA.txt` | Política General de Sostenibilidad completa (2022) | Alta. Valores, compromisos y lenguaje institucional que aparece recurrentemente en los posts de LinkedIn |
| `03_Politica_Comunicacion_Publicitaria_BBVA.txt` | Extracto de la Política de Comunicación Publicitaria (marzo 2026): principios de redacción (transparencia, claridad, responsabilidad), tono, reglas de estilo | Muy alta. Son las reglas de estilo/redacción explícitas de BBVA |

Nota: estos ficheros son transcripciones de texto extraídas directamente de los PDF oficiales (no son PDFs con maquetación), pensadas para ingestión directa en un pipeline de RAG (chunking + embeddings).

## Enlaces oficiales adicionales (descarga directa recomendada desde tu navegador)

No pude descargar automáticamente los siguientes documentos por su gran tamaño (informes de cientos de páginas) o por restricciones de red del entorno. Son 100% oficiales y públicos; te recomiendo descargarlos tú directamente para conservar el PDF original (útil si tu pipeline de RAG procesa PDFs con su maquetación, tablas, etc.):

### Informes anuales y gobierno corporativo
- Informe Anual BBVA 2025 (español): https://accionistaseinversores.bbva.com/wp-content/uploads/2026/03/Informe-Anual-BBVA-2025_esp.pdf
- Annual Report BBVA 2025 (inglés): https://shareholdersandinvestors.bbva.com/wp-content/uploads/2026/03/Annual-Report-BBVA-2025_ENG.pdf
- Informe Anual de Gobierno Corporativo 2025: https://accionistaseinversores.bbva.com/wp-content/uploads/2026/02/17_Informe_Anual_de_Gobierno_Corporativo_2025.pdf

### Comunicación y accionistas
- Política General de Comunicación y Contactos con Accionistas e Inversores: https://accionistaseinversores.bbva.com/wp-content/uploads/2025/02/Politica-de-comunicacion-y-contactos-con-accionistas-e-inversores_esp.pdf

### Código de conducta (versiones locales, por si te interesa comparar registros/países)
- Código de Conducta BBVA México: https://www.bbva.mx/content/dam/public-web/mexico/documents/landing/footer-y-prefooter/codigo-de-conducta.pdf
- Código de Conducta BBVA Colombia: https://www.bbva.com.co/content/dam/public-web/colombia/documents/home/body/inversionista/espanol/gobierno-corporativo/codigo-de-conducta/Codigo-de-conducta-bbva-2.pdf
- Código de Conducta BBVA Argentina: https://www.bbva.com.ar/tablas/CodCond_AR.pdf
- Código de Conducta Fundación BBVA: https://www.fbbva.es/wp-content/uploads/2023/02/Codigo_de_conducta_Fundacion_BBVA.pdf

### Identidad de marca / brand book
BBVA no publica su manual de identidad de marca completo como PDF de acceso público (está en la plataforma interna "BBVA Brand Experience", brand.bbvaexperience.com, con acceso restringido a empleados/agencias autorizadas). Como referencia pública indirecta sobre su sistema de marca (colores, tipografía, tono), puedes consultar:
- BBVA — rediseño de identidad 2019 (artículo oficial): https://www.bbva.com/en/2019-rebrand-designing-the-new-identity/
- Sala de prensa / recursos de marca: https://www.bbva.com/es/sala-de-prensa/

## Cómo continuar

1. Descarga los PDFs de la sección "Enlaces oficiales adicionales" en tu navegador y guárdalos en esta misma carpeta si quieres tenerlo todo junto.
2. Los 3 archivos .txt ya están listos para trocear (chunking) e indexar en tu pipeline de RAG.
3. Para los posts reales de LinkedIn de BBVA (necesarios como "ground truth"), al ser contenido de una plataforma con restricciones de scraping, te recomiendo recopilarlos manualmente navegando a https://www.linkedin.com/company/bbva/posts/ o usando la extensión Claude en Chrome si quieres que te ayude a extraer texto de publicaciones concretas mientras navegas por la página (puedo ayudarte con eso si me confirmas que quieres proceder así).
