"""Chequeo sin red del filtro de ubicación del scout: py test_location_filter.py"""
from job_filters import location_reason

assert location_reason("", "Remote role") is None                                   # sin país: decide el LLM
assert location_reason("Bogotá, Colombia", "Remote") is None
assert location_reason("Latin America", "Remote") is None
assert location_reason("Bengaluru, Karnataka, India", "Hybrid role in our Bangalore office")
assert location_reason("Paris, France", "Poste en remote")
assert location_reason("Austin, TX", "Remote within the US")
assert location_reason("São Paulo, Brazil", "We hire across LATAM, fully remote") is None  # dice que contrata en LATAM
assert location_reason("Toronto, ON, Canada", "Open to candidates anywhere in the world") is None
# texto corporativo que NO significa que contraten desde Colombia (casos reales del 2026-10-01)
assert location_reason("Pune, India", "Build AI products used by customers worldwide.")
assert location_reason("Pune, India", "100% remote working, from anywhere in India")
assert location_reason("London, United Kingdom", "We deploy anywhere as a Docker image.")
assert location_reason("Chennai, India", "Phone: * Chile+56 * Colombia+57 * Comoros+269")
assert location_reason("London, United Kingdom", "from the style capitals of Europe, to the energy of the Americas")
assert location_reason("Mexico City, Mexico", "Remote role open to candidates across Latin America") is None
assert location_reason("Toronto, Canada", "Fully remote - work from anywhere in the world") is None
# contractor con empresa extranjera, sin papeles
assert location_reason("Austin, TX", "This is a contract role; we hire international contractors via Deel.") is None
assert location_reason("New York, NY", "Independent contractor position open to talent in LATAM time zones") is None
assert location_reason("San Francisco, CA", "Contractor role. Must be authorized to work in the US.")
assert location_reason("Chicago, IL", "Full-time W2 position, remote within the US")
assert location_reason("Bengaluru, India", "Contract role for 6 months")                    # contractor local, no internacional
print("ok")
