"""
Script que construye el dataset oficial de Ground Truth de BBVA (`evaluation/bbva_ground_truth.json`)
a partir de las publicaciones reales extraídas en Supabase para `urn:li:organization:136115687`.
"""
import re
import json
from pathlib import Path
from src.services.supabase_client import get_supabase

BBVA_URN = "urn:li:organization:136115687"

# Metadata analítica y prompts inversos para cada uno de los 22 posts reales
METADATA_MAP = {
    1: {
        "title": "Premios Fronteras del Conocimiento y rigor científico",
        "casuistica": "C3",
        "complexity": "alta",
        "context_level": "bajo",
        "category": "thought_leadership",
        "prompt": "Escribe una publicación institucional para LinkedIn que celebre el rigor científico, la evidencia y la cooperación frente a la simplificación y el prejuicio, con motivo de los Premios Fronteras del Conocimiento de la Fundación BBVA.",
        "expected_key_facts": ["Premios Fronteras del Conocimiento", "Fundación BBVA", "curiosidad frente al conformismo", "evidencia frente al prejuicio"],
        "compliance_notes": "Código de Conducta: difusión cultural y científica sin fines comerciales agresivos."
    },
    2: {
        "title": "Yellow Day: bienestar y personas en BBVA",
        "casuistica": "C1",
        "complexity": "baja",
        "context_level": "bajo",
        "category": "engagement",
        "prompt": "Escribe un post distendido para LinkedIn con motivo del Yellow Day (el día más feliz del año), reflexionando sobre el optimismo y la actitud del equipo.",
        "expected_key_facts": ["Yellow Day", "día más feliz del año", "equipo y actitud"],
        "compliance_notes": "Tono humano, cercano, sin menciones financieras."
    },
    3: {
        "title": "Acción interna deportiva: El pase más largo del mundo",
        "casuistica": "C1",
        "complexity": "baja",
        "context_level": "alto",
        "category": "cultura",
        "prompt": "Escribe un post corporativo para LinkedIn sobre una iniciativa interna donde un balón viaja de oficina en oficina por 25 países uniendo a los empleados bajo el lema Campeones en todos los campos.",
        "expected_key_facts": ["25 países", "pase más largo del mundo", "un solo equipo"],
        "compliance_notes": "Código de Conducta 4.20: reforzar el orgullo de pertenencia y trabajo en equipo."
    },
    4: {
        "title": "Mujeres en ingeniería e IA con criterio",
        "casuistica": "C3",
        "complexity": "alta",
        "context_level": "bajo",
        "category": "educativo",
        "prompt": "Redacta un post para el Día de la Mujer Ingeniera destacando cómo la próxima generación de ingenieras usa la IA con criterio, ética y curiosidad a través de iniciativas como Technovation Girls.",
        "expected_key_facts": ["Technovation Girls", "Día de la Mujer Ingeniera", "uso crítico de la IA", "talento femenino en STEM"],
        "compliance_notes": "Alineado con los objetivos de diversidad e igualdad de oportunidades de BBVA."
    },
    5: {
        "title": "La empatía como habilidad activa en la banca",
        "casuistica": "C1",
        "complexity": "baja",
        "context_level": "bajo",
        "category": "educativo",
        "prompt": "Escribe una reflexión para LinkedIn sobre cómo la empatía no es solo una intención sino una habilidad que requiere trabajo diario para acompañar a los clientes y entender sus necesidades reales.",
        "expected_key_facts": ["empatía activa", "acompañamiento al cliente", "Campus BBVA"],
        "compliance_notes": "Principio de poner al cliente en primer lugar (Código de Conducta)."
    },
    6: {
        "title": "Inclusión laboral y formación con Colegio Areteia",
        "casuistica": "C2",
        "complexity": "baja",
        "context_level": "alto",
        "category": "rrhh",
        "prompt": "Escribe un post de agradecimiento y orgullo sobre la experiencia de acoger a estudiantes en prácticas del Colegio Areteia en nuestro equipo, destacando el aprendizaje mutuo.",
        "expected_key_facts": ["Colegio Areteia", "aprendizaje mutuo", "entornos inclusivos"],
        "compliance_notes": "GDPR: no publicar datos sensibles de menores o estudiantes; tono de respeto mutuo."
    },
    7: {
        "title": "FrauDfense: Alianza interbancaria contra el fraude financiero",
        "casuistica": "C4",
        "complexity": "alta",
        "context_level": "alto",
        "category": "producto",
        "prompt": "Redacta un post informativo y riguroso anunciando FrauDfense Check, la iniciativa colaborativa de BBVA junto a Santander y CaixaBank para compartir inteligencia y prevenir el fraude en transferencias Bizum, tarjetas y altas.",
        "expected_key_facts": ["FrauDfense", "FrauDfense Check", "Santander", "CaixaBank", "Bizum", "prevención de fraude financiero"],
        "compliance_notes": "Política de Comunicación Publicitaria: citar competidores solo en el marco de la alianza oficial; datos exactos."
    },
    8: {
        "title": "Programa Polaris para desarrollo de mánagers en Campus BBVA",
        "casuistica": "C2",
        "complexity": "baja",
        "context_level": "alto",
        "category": "rrhh",
        "prompt": "Escribe un post sobre el programa de liderazgo Polaris de Campus BBVA, recogiendo el testimonio de mánagers que terminan la formación con ganas de repetir por el valor humano y profesional aportado.",
        "expected_key_facts": ["Polaris", "Campus BBVA", "desarrollo de mánagers", "liderazgo"],
        "compliance_notes": "Employer branding fiel a la oferta formativa real de BBVA."
    },
    9: {
        "title": "Inclusión LGTBIQ+ y red de empleados Be Yourself",
        "casuistica": "C2",
        "complexity": "baja",
        "context_level": "alto",
        "category": "cultura",
        "prompt": "Publica una reflexión sobre si apostar por la diversidad es compromiso o valentía corporativa, presentando la labor de la red de empleados Be Yourself de BBVA para garantizar un entorno de trabajo seguro y auténtico.",
        "expected_key_facts": ["Be Yourself", "espacios seguros", "autenticidad en el trabajo", "diversidad e inclusión"],
        "compliance_notes": "Código de Conducta: respeto a la identidad y no discriminación."
    },
    10: {
        "title": "Día del Orgullo de la Neurodiversidad en el trabajo",
        "casuistica": "C2",
        "complexity": "baja",
        "context_level": "alto",
        "category": "rrhh",
        "prompt": "Escribe un post educativo y de sensibilización con motivo del Día del Orgullo de la Neurodiversidad, explicando que el 20% de la población es neurodivergente y cómo BBVA adapta sus procesos de selección para atraer talento con diferentes formas de procesar la información.",
        "expected_key_facts": ["20% población neurodivergente", "Neurodiversity Pride", "adaptación de selección", "entornos accesibles"],
        "compliance_notes": "Tratamiento respetuoso y riguroso de la diversidad cognitiva."
    },
    11: {
        "title": "Comunicado de apoyo y solidaridad ante el sismo (BBVA Provincial)",
        "casuistica": "C4",
        "complexity": "alta",
        "context_level": "alto",
        "category": "compliance",
        "prompt": "Redacta un comunicado institucional de emergencia y solidaridad de BBVA Provincial tras el sismo en el país, informando de la operatividad de los servicios y del compromiso con clientes y comunidades afectadas.",
        "expected_key_facts": ["BBVA Provincial", "solidaridad y apoyo", "operatividad de canales", "atención prioritaria"],
        "compliance_notes": "Comunicación en situación de crisis: máxima sobriedad, sin mensajes comerciales, información fidedigna."
    },
    12: {
        "title": "Reconocimiento como Top Líder en inclusión por REDI",
        "casuistica": "C2",
        "complexity": "baja",
        "context_level": "alto",
        "category": "thought_leadership",
        "prompt": "Escribe un post anunciando el reconocimiento de BBVA por segundo año consecutivo como Top Líder en inclusión por parte de REDI y Actualidad Económica, enfatizando que la inclusión es una convicción permanente.",
        "expected_key_facts": ["REDI", "Actualidad Económica", "Top Líderes", "segundo año consecutivo"],
        "compliance_notes": "Política Publicitaria: datos de premios exactos y verificables sin auto-elogios exagerados."
    },
    13: {
        "title": "Formación masiva en IA y Premio Cegos al Talento",
        "casuistica": "C4",
        "complexity": "alta",
        "context_level": "alto",
        "category": "datos",
        "prompt": "Publica un post con cifras sobre la adopción de IA en BBVA, destacando que más de 105.000 empleados se han formado y la consecución del Premio Cegos por aplicar tecnología con visión centrada en las personas.",
        "expected_key_facts": ["105.000 personas formadas", "Premio Cegos", "Champions de IA", "IA centrada en las personas"],
        "compliance_notes": "Factualidad estricta: verificación de la cifra de 105.000 y del galardón otorgado."
    },
    14: {
        "title": "Respuesta humanitaria y canal de ayuda tras el terremoto en Venezuela",
        "casuistica": "C4",
        "complexity": "alta",
        "context_level": "alto",
        "category": "compliance",
        "prompt": "Redacta un post sobre la ayuda humanitaria desplegada por BBVA para asistir a los afectados por los terremotos en Venezuela, facilitando canales seguros de colaboración junto a Cruz Roja y ACNUR.",
        "expected_key_facts": ["Cruz Roja", "ACNUR", "ayuda humanitaria", "canales de donación seguros"],
        "compliance_notes": "Rigurosidad en organizaciones colaboradoras y protocolos de donación."
    },
    15: {
        "title": "Historias humanas detrás de la transición sostenible",
        "casuistica": "C2",
        "complexity": "baja",
        "context_level": "alto",
        "category": "storytelling",
        "prompt": "Escribe un post en tono narrativo sobre cómo la sostenibilidad en BBVA se construye persona a persona, contando la labor de los gestores que ayudan a pymes y empresas en su transición ecológica.",
        "expected_key_facts": ["transición ecológica", "acompañamiento a pymes", "sostenibilidad real"],
        "compliance_notes": "Política General de Sostenibilidad: evitar greenwashing; foco en soluciones concretas."
    },
    16: {
        "title": "BBVA Quantum: Computación cuántica aplicada a finanzas y riesgos",
        "casuistica": "C4",
        "complexity": "alta",
        "context_level": "alto",
        "category": "producto",
        "prompt": "Escribe un post de divulgación tecnológica sobre el equipo de BBVA Quantum, explicando cómo colaboran con gigantes como IBM o D-Wave y aplican algoritmos cuánticos para optimizar carteras y riesgos financieros.",
        "expected_key_facts": ["BBVA Quantum", "IBM", "D-Wave", "Top 10 Quantum Innovation Index", "Mercados Globales"],
        "compliance_notes": "Citar socios tecnológicos reales; precisión técnica en computación cuántica."
    },
    17: {
        "title": "Presencia internacional: Visita a la oficina CIB de BBVA en Shanghái",
        "casuistica": "C2",
        "complexity": "baja",
        "context_level": "alto",
        "category": "cultura",
        "prompt": "Redacta un post de employer branding internacional mostrando la oficina de Corporate & Investment Banking de BBVA en Shanghái a través de la experiencia de Lin Li, destacando la conexión cultural entre España y Asia.",
        "expected_key_facts": ["BBVA CIB Shanghái", "Lin Li", "puente cultural y financiero", "equipo global"],
        "compliance_notes": "Identidad global de BBVA sin revelar información sensible de clientes asiáticos."
    },
    18: {
        "title": "Sustainability Global Awards 2026: 6 operaciones de impacto real",
        "casuistica": "C4",
        "complexity": "alta",
        "context_level": "alto",
        "category": "datos",
        "prompt": "Publica un post institucional detallando los 6 deals sostenibles premiados en los Sustainability Global Awards 2026, citando los proyectos con Bloom Energy (EE.UU.), Sabesp (Brasil) y Ternium (México).",
        "expected_key_facts": ["Sustainability Global Awards 2026", "Bloom Energy", "Sabesp", "Ternium", "descarbonización", "economía circular"],
        "compliance_notes": "GDPR y confidencialidad comercial: solo operaciones públicas y autorizadas por los clientes corporativos."
    },
    19: {
        "title": "Celebración global del Orgullo LGTBIQ+ en BBVA",
        "casuistica": "C2",
        "complexity": "baja",
        "context_level": "alto",
        "category": "cultura",
        "prompt": "Escribe un post de celebración de la semana del Orgullo LGTBIQ+ en las diferentes geografías de BBVA, destacando la creación de espacios seguros y el compromiso colectivo con la diversidad.",
        "expected_key_facts": ["Orgullo global", "espacios seguros", "autenticidad y respeto"],
        "compliance_notes": "Inclusión y valores de marca sin fines partidistas o políticos."
    },
    20: {
        "title": "Jurado de los Premios ViVa 2026 y evaluación a ciegas",
        "casuistica": "C2",
        "complexity": "baja",
        "context_level": "alto",
        "category": "cultura",
        "prompt": "Escribe un post sobre el jurado de los Premios ViVa 2026 de BBVA, explicando cómo pasaron de más de 127.000 candidatos a 34 finalistas evaluando historias mediante una fase 'a ciegas' sin nombres ni países.",
        "expected_key_facts": ["Premios ViVa", "+127.000 candidatos", "34 finalistas", "evaluación a ciegas", "12 ganadores"],
        "compliance_notes": "Cifras oficiales exactas del certamen interno de cultura."
    },
    21: {
        "title": "Datathon BeTalent BBVA 2026: 40 promesas del Data Science",
        "casuistica": "C4",
        "complexity": "alta",
        "context_level": "alto",
        "category": "rrhh",
        "prompt": "Redacta un post para LinkedIn sobre la jornada final del Datathon BeTalent BBVA 2026, donde 40 candidatos de Data Science resolvieron retos técnicos durante 8 horas, invitando a futuros profesionales a postular.",
        "expected_key_facts": ["Datathon BeTalent BBVA 2026", "40 candidatos", "Data Science", "8 horas", "enlace bbva.info"],
        "compliance_notes": "Llamada a la acción con enlace verídico de selección."
    },
    22: {
        "title": "Criptografía cuántica y aleatoriedad QRNG en ciberseguridad financiera",
        "casuistica": "C4",
        "complexity": "alta",
        "context_level": "alto",
        "category": "producto",
        "prompt": "Escribe un post divulgativo de alta tecnología sobre cómo BBVA investiga la aleatoriedad cuántica mediante Generadores Cuánticos de Números Aleatorios (QRNG) para blindar claves criptográficas y simulaciones de riesgo Montecarlo.",
        "expected_key_facts": ["Generadores Cuánticos de Números Aleatorios", "QRNG", "simulaciones Montecarlo", "ciberseguridad financiera", "enlace bbva.info"],
        "compliance_notes": "Máxima precisión en conceptos de física y criptografía; no prometer sistemas 100% invulnerables."
    }
}


def clean_li_text(text: str) -> str:
    text = re.sub(r'\{hashtag\|\\\#\|(\w+)\}', r'#\1', text)
    text = text.replace('\\(', '(').replace('\\)', ')')
    return text.strip()


def extract_hashtags(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r'#\w+', text)))


def build_dataset():
    sb = get_supabase()
    res = sb.table('company_profiles').select('raw_batch_data').eq('org_urn', BBVA_URN).execute()
    if not res.data or not res.data[0].get('raw_batch_data'):
        raise RuntimeError("No se pudieron cargar los posts crudos de BBVA desde Supabase")

    raw_posts = res.data[0]['raw_batch_data']['posts']
    cases = []

    for i, p in enumerate(raw_posts, 1):
        clean_text = clean_li_text(p.get('commentary', ''))
        meta = METADATA_MAP.get(i, {})
        extracted_tags = extract_hashtags(clean_text)

        case = {
            "id": f"bbva_{i:02d}",
            "post_index": i,
            "title": meta.get("title", f"Publicación BBVA {i}"),
            "casuistica": meta.get("casuistica", "C2"),
            "complexity": meta.get("complexity", "media"),
            "context_level": meta.get("context_level", "alto"),
            "category": meta.get("category", "general"),
            "kb_dependent": meta.get("context_level") == "alto",
            "prompt": meta.get("prompt", clean_text[:200]),
            "ground_truth_post": clean_text,
            "official_hashtags": extracted_tags,
            "expected_key_facts": meta.get("expected_key_facts", []),
            "compliance_notes": meta.get("compliance_notes", ""),
            "org_urn": BBVA_URN,
        }
        cases.append(case)

    output_path = Path(__file__).parent.parent / "evaluation" / "bbva_ground_truth.json"
    data = {
        "description": "Dataset Ground Truth de publicaciones reales de LinkedIn de BBVA (Banco Bilbao Vizcaya Argentaria) para evaluación empírica cualitativa y cuantitativa del TFG.",
        "org_urn": BBVA_URN,
        "total_cases": len(cases),
        "casuisticas_summary": {
            "C1_baja_complejidad_bajo_contexto": len([c for c in cases if c['casuistica'] == 'C1']),
            "C2_baja_complejidad_alto_contexto": len([c for c in cases if c['casuistica'] == 'C2']),
            "C3_alta_complejidad_bajo_contexto": len([c for c in cases if c['casuistica'] == 'C3']),
            "C4_alta_complejidad_alto_contexto": len([c for c in cases if c['casuistica'] == 'C4']),
        },
        "cases": cases,
    }

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)

    print(f"✅ Dataset guardado exitosamente en: {output_path}")
    print(f"Total casos procesados: {len(cases)}")
    print("Distribución por casuística:", data["casuisticas_summary"])


if __name__ == "__main__":
    build_dataset()
