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

# Tercer filtro: la descripción restringe a otro país aunque LinkedIn no traiga ubicación (frases reales de jobs.db, 2026-10-15)
from job_filters import country_only_reason as only
for desc in [
    "Work Model This position is **fully remote within the United States** , providing the flexibility",  # Cognizant
    "**AI Testing Engineer** Location: Remote – US **About Us** Trillium Digital Services",
    "**Role Location:** Fully remote, US-based **The Company** Our client",                              # Signify
    "Qualified applicants must be willing and able to work on a w2 basis.",                                # Eliassen
    "Remote (USA). Competitive salary.", "Remote - United States", "Location: Remote, UK",
    "Remote in the U.S. only", "100% remote within the USA.", "This role is remote within Canada.",
    "Candidates must be eligible to work in the United States.", "Must be authorized to work in the U.S.",
    "Must be legally permitted to work for the UK", "Must be a U.S. citizen.", "US citizenship required",
    "Active security clearance required", "Green card holders welcome", "W-2 only, no C2C",
    "Must reside in the United States", "must be located in the US", "US-based candidates only",
    "Remote within the EU", "Remote | India",
]:
    assert only(desc), desc
for desc in [
    "",
    "Remote, Latin America. Overlap live US hours or this does not work.",                                 # Bold Business
    "Work remotely with a US-based team with clear collaboration hours",
    "Traffic Control Advertising is a US-based performance marketing agency",
    "Full-time | 40 hours per week | USA-based client | PST time zone",                                    # BruntWork
    "benefits package, which is available to all eligible US based employees.",                            # Waymo: beneficios, no requisito
    "California Fair Chance Act, for US-based candidates.",                                                # OpenAI: texto legal
    "Applicants must be permanently authorized to work in their country of residence",                     # AspenView: le sirve
    "working for a US-based client. Remote, full-time job - Latin America preferred",                     # HKR.TEAM
    "Fully remote within the United States or anywhere in LATAM",                                          # dice que contrata en LATAM
    "Remote, using Python and AWS", "Remote: work with us from Colombia", "Our customers across the US love us",
    "Join us! Remote - flexible hours", "Remote within Uruguay and Colombia", "We use AWS EU regions",
]:
    assert only(desc) is None, desc

# Áreas metropolitanas de LinkedIn sin país (corrida real 2026-10-15: Bogotá salía como extranjera). home_country = colombia
from job_filters import with_search_country as tag
assert tag("Bogotá D.C. Metropolitan Area", "Colombia") == "Bogotá D.C. Metropolitan Area, Colombia"
assert location_reason(tag("Bogotá D.C. Metropolitan Area", "Colombia"), "Remote role") is None
assert tag("Greater Medellín Area", "Colombia") == "Greater Medellín Area, Colombia"
assert tag("Lima Metropolitan Area", "Latin America") == "Lima Metropolitan Area"         # otra búsqueda: no se toca
assert location_reason(tag("Lima Metropolitan Area", "Latin America"), "Remote role")
assert tag("United States", "Colombia") == "United States"                                 # nombra otro país: no se toca
assert tag("Medellín, Antioquia, Colombia", "Colombia") == "Medellín, Antioquia, Colombia"
assert tag("", "Colombia") == ""
print("ok")
