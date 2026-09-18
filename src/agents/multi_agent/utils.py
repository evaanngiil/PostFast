"""
Utilidades compartidas de los nodos del pipeline multi-agente.

- slim_company_profile: versión compacta del perfil corporativo para inyectar en
  prompts. El perfil completo incluye `recent_posts_analysis` (decenas de posts
  analizados), que infla el contexto en decenas de miles de tokens sin aportar
  a la redacción: ese conocimiento ya llega destilado vía brand_persona y
  engagement_analysis.
- parse_post_text: parseo DETERMINISTA del texto libre del writer/editor a la
  estructura DraftPost (sin segunda llamada LLM). La generación en texto libre
  preserva la calidad de redacción que el structured output JSON degrada
  (saltos de línea, emojis, hashtags integrados en el post).
"""
import re

# Campos ligeros del perfil que sí aportan a la redacción.
_SLIM_PROFILE_KEYS = (
    "name",
    "urn",
    "vanity_name",
    "industry",
    "company_size",
    "company_type",
    "founded",
    "headquarters",
    "specialties",
    "followers",
    "website",
)

_HASHTAG_RE = re.compile(r"#[\wÀ-ÿ]+")
_HASHTAG_LINE_RE = re.compile(r"^(?:#[\wÀ-ÿ]+[\s,.]*)+$")
_PREAMBLE_RE = re.compile(
    r"^(aquí tienes|aqui tienes|claro[,!]|por supuesto|borrador|post de linkedin|aquí está|aqui esta)",
    re.IGNORECASE,
)


def slim_company_profile(profile: dict | None, about_us_max_chars: int = 1200) -> dict:
    """Devuelve una copia compacta del perfil corporativo apta para prompts."""
    if not profile:
        return {}
    slim = {k: profile[k] for k in _SLIM_PROFILE_KEYS if profile.get(k)}
    about = profile.get("about_us_content")
    if about:
        slim["about_us_content"] = str(about)[:about_us_max_chars]
    return slim


def parse_post_text(raw: str) -> dict:
    """
    Convierte el texto libre generado por el LLM en la estructura DraftPost.

    Limpieza aplicada:
    - Elimina fences de código accidentales.
    - Elimina una primera línea de preámbulo conversacional si la hubiera.
    - Extrae hashtags del propio texto (quedan también dentro de `content`).
    - Deduce la llamada a la acción como la última línea sustantiva.
    """
    text = (raw or "").strip()
    text = re.sub(r"^```(?:\w+)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    text = text.replace("\\n", "\n")

    lines = text.splitlines()
    if lines:
        first = lines[0].strip()
        # Preámbulo típico: línea corta conversacional, a menudo terminada en ':'
        if len(first) < 100 and _PREAMBLE_RE.match(first) and (first.endswith(":") or len(lines) > 1):
            text = "\n".join(lines[1:]).strip()

    hashtags = list(dict.fromkeys(_HASHTAG_RE.findall(text)))

    call_to_action = ""
    for line in reversed([ln.strip() for ln in text.splitlines() if ln.strip()]):
        if not _HASHTAG_LINE_RE.fullmatch(line):
            call_to_action = line
            break

    return {
        "content": text,
        "hashtags": hashtags,
        "call_to_action": call_to_action,
    }
