"""
Genera (o regenera) los 3 templates base de CV, uno por arquetipo de rol (AI Engineer,
Forward Deployed Engineer, QA Automation Mid-level), usando el mismo loop generador-revisor
de siempre contra una JD genérica por arquetipo (no una vacante real). Correr una sola vez, o
cuando el perfil (master_profile.json) cambie mucho:

    py generate_archetype_templates.py

tailor_agent.py después parte de estos templates para cada vacante real, en vez de regenerar
el CV completo desde cero cada vez — ver archetypes.py y cv_tailoring.py.
"""
import asyncio
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import profile_paths
import llm_chain
from archetypes import ARCHETYPES, ARCHETYPE_LABELS, ARCHETYPE_GENERIC_JD, ARCHETYPE_POSITIONING, save_template
from cv_tailoring import generate_full


async def main():
    print("====================================================")
    print(" Generando templates base por arquetipo")
    print("====================================================\n")

    with open(profile_paths.resolve("master_profile.json"), "r", encoding="utf-8") as f:
        master_json_str = f.read()
        master_profile = json.loads(master_json_str)

    llm_chain.print_budget_status()

    # py generate_archetype_templates.py ai_engineer forward_deployed_engineer -> solo esos
    selected = [a for a in sys.argv[1:] if a in ARCHETYPES] or ARCHETYPES

    for archetype in selected:
        label = ARCHETYPE_LABELS[archetype]
        print(f"\n>>> Arquetipo: {label}")
        try:
            result, approved = await generate_full(
                job_title=label,
                job_company="(template genérico — no es una vacante real)",
                job_desc=(f"{ARCHETYPE_GENERIC_JD[archetype]}\n\n"
                          f"CANDIDATE POSITIONING (applies to this CV): {ARCHETYPE_POSITIONING[archetype]}"),
                gap_analysis="",
                master_json_str=master_json_str,
                master_profile=master_profile,
            )
        except llm_chain.AllProvidersExhausted:
            print(f"   [CUOTA AGOTADA] No se pudo generar el template de {label} — probá de nuevo "
                  f"más tarde con cupo fresco.")
            continue

        profile_dict = result.model_dump()
        del profile_dict["target_role_title"]  # se recalcula por vacante real, no hace falta guardarlo
        save_template(archetype, profile_dict)
        print(f"   Guardado en archetype_templates/{archetype}.json (revisado: {approved})")

    print("\n====================================================")
    print(" Listo. Revisá los .json en archetype_templates/ antes de correr tailor_agent.py")
    print(" a gran escala con esto — son la base de TODOS los CVs de ese arquetipo.")
    print("====================================================")


if __name__ == "__main__":
    asyncio.run(main())
