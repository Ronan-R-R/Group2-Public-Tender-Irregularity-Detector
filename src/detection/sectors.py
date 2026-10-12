"""Maps tender categories and company industries onto shared sector groups.

eTenders mixes two vocabularies in one field: its own labels ("Services:
Professional", "Supplies: Medical") and ISIC section/division names
("Civil engineering", "Human health activities"). CIPC industries are
SIC descriptions, which follow ISIC. Both sides go through the same table, so
a match means "these share a sector group", not exact label equality.

A label may belong to several groups ("Services: Functional" covers cleaning
and security). Labels that say nothing about the work ("Services: General",
plain "goods") are listed as generic and never compared.

Coverage is the 90 category labels seen in the eTenders OCDS feed,
2017-2026. Unknown labels return None so callers can report "not evaluated"
instead of guessing.
"""

from __future__ import annotations

TRADE = "trade"

GENERIC_LABELS: frozenset[str] = frozenset(
    {
        "goods",
        "services",
        "services: general",
        "supplies: general",
        "other service activities",
        "disposals: general",
        "other manufacturing",
        "manufacturing",
        "other personal service activities",
    }
)

_GROUPS: dict[str, frozenset[str]] = {
    group: frozenset(labels)
    for group, labels in {
        "construction": {
            "works",
            "construction",
            "civil engineering",
            "construction of buildings",
            "specialised construction activities",
            "services: building",
            "services: civil",
            "architectural and engineering activities; technical testing and analysis",
            "mining support service activities",
        },
        "professional": {
            "services: professional",
            "professional, scientific and technical activities",
            "other professional, scientific and technical activities",
            "legal and accounting activities",
            "activities of head offices; management consultancy activities",
            "architectural and engineering activities; technical testing and analysis",
            "scientific research and development",
            "advertising and market research",
            "employment activities",
        },
        "ict": {
            "information and communication",
            "computer programming, consultancy and related activities",
            "information service activities",
            "telecommunications",
            "supplies: computer equipment",
            "manufacture of computer, electronic and optical products",
            "publishing activities",
            "programming and broadcasting activities",
        },
        "health": {
            "supplies: medical",
            "human health activities",
            "human health and social work activities",
            "residential care activities",
        },
        "security": {
            "security and investigation activities",
            "services: functional (including cleaning and security services)",
        },
        "facilities": {
            "services: functional (including cleaning and security services)",
            "services to buildings and landscape activities",
            "administrative and support activities",
            "office administrative, office support and other business support activities",
            "rental and leasing activities",
            "real estate activities",
        },
        "electrical": {
            "services: electrical",
            "supplies: electrical equipment",
            "electricity, gas, steam and air conditioning",
            "manufacture of electrical equipment",
            "repair and installation of machinery and equipment",
        },
        "hospitality": {
            "accommodation",
            "food and beverage service activities",
            "supplies: perishable provisions",
            "travel agency, tour operator, reservation service and related activities",
        },
        "transport": {
            "transportation and storage",
            "air transport",
            "water transport",
            "land transport and transport via pipelines",
            "warehousing and support activities for transportation",
            "postal and courier activities",
            "manufacture of motor vehicles, trailers and semi-trailers",
            "wholesale and retail trade and repair of motor vehicles and motorcycles",
        },
        "water_waste": {
            "water supply; sewerage, waste management and remediation activities",
            "water collection, treatment and supply",
            "sewerage",
            "waste collection, treatment and disposal activities; materials recovery",
            "remediation activities and other waste management services",
        },
        "finance": {
            "financial and insurance activities",
            "financial service activities, except insurance and pension funding",
            "insurance, reinsurance and pension funding, except compulsory social security",
            "activities auxiliary to financial service and insurance activities.",
            "legal and accounting activities",
        },
        "education": {"education", "libraries, archives, museums and other cultural activities"},
        "media_arts": {
            "creative, arts and entertainment activities",
            "arts, entertainment and recreation",
            "sports activities and amusement and recreation activities",
            "motion picture, video and television programme production, sound recording and "
            "music publishing activities",
            "advertising and market research",
        },
        "printing": {
            "supplies: stationery/printing",
            "printing and reproduction of recorded media",
            "manufacture of paper and paper products",
        },
        "clothing": {"supplies: clothing/textiles/footwear", "manufacture of textiles"},
        "industrial": {
            "manufacture of machinery and equipment n.e.c.",
            "manufacture of basic metals",
            "manufacture of fabricated metal products, except machinery and equipment",
            "manufacture of chemicals and chemical products",
            "manufacture of rubber and plastics products",
            "manufacture of coke and refined petroleum products",
            "mining and quarrying",
            "mining of coal and lignite",
        },
        "furniture": {"manufacture of furniture"},
        "agriculture": {"agricultural products and services"},
        "domestic": {"activities of households as employers of domestic personnel"},
        TRADE: {"wholesale and retail trade", "wholesale trade", "retail trade"},
    }.items()
}

_LABEL_TO_GROUPS: dict[str, frozenset[str]] = {}
for _group, _labels in _GROUPS.items():
    for _label in _labels:
        _LABEL_TO_GROUPS[_label] = _LABEL_TO_GROUPS.get(_label, frozenset()) | {_group}


def normalise(label: str) -> str:
    return " ".join(label.split()).casefold()


def is_generic(label: str) -> bool:
    return normalise(label) in GENERIC_LABELS


def tender_sectors(category: str) -> frozenset[str] | None:
    """Sector groups a tender category belongs to, or None if unmapped/generic.

    Any "Supplies: ..." category also accepts the trade group, because a
    wholesaler or retailer legitimately supplies goods it does not make.
    """
    key = normalise(category)
    if key in GENERIC_LABELS:
        return None
    groups = _LABEL_TO_GROUPS.get(key)
    if groups is None:
        return None
    if key.startswith("supplies:"):
        groups = groups | {TRADE}
    return groups


def company_sectors(industry: str) -> frozenset[str] | None:
    key = normalise(industry)
    if key in GENERIC_LABELS:
        return None
    return _LABEL_TO_GROUPS.get(key)
