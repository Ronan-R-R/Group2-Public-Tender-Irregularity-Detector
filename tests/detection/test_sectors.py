import pytest

from detection.sectors import TRADE, company_sectors, is_generic, normalise, tender_sectors

# Every category label in the eTenders OCDS feed, 2017-2026 (awards with a value).
ETENDERS_CATEGORIES = [
    "Services: Professional", "Construction", "Services: General", "Supplies: General",
    "Other service activities",
    "Services: Functional (Including Cleaning and Security Services)", "Civil engineering",
    "Construction of buildings", "Services: Electrical", "Supplies: Medical",
    "Information and communication", "Supplies: Computer Equipment", "Services: Building",
    "Professional, scientific and technical activities", "Supplies: Electrical Equipment",
    "Accommodation", "Rental and leasing activities",
    "Electricity, gas, steam and air conditioning", "Security and investigation activities",
    "Supplies: Stationery/Printing", "Computer programming, consultancy and related activities",
    "Administrative and support activities", "Information service activities",
    "Supplies: Clothing/Textiles/Footwear", "Food and beverage service activities",
    "Other professional, scientific and technical activities", "Services: Civil", "Education",
    "Repair and installation of machinery and equipment", "Legal and accounting activities",
    "Travel agency, tour operator, reservation service and related activities",
    "Transportation and storage", "Manufacture of furniture",
    "Specialised construction activities", "Telecommunications",
    "Waste collection, treatment and disposal activities; materials recovery",
    "Financial service activities, except insurance and pension funding",
    "Services to buildings and landscape activities", "Financial and insurance activities",
    "Activities of head offices; management consultancy activities",
    "Advertising and market research", "Disposals: General",
    "Water supply; sewerage, waste management and remediation activities",
    "Other personal service activities",
    "Office administrative, office support and other business support activities",
    "Printing and reproduction of recorded media", "Water collection, treatment and supply",
    "Supplies: Perishable Provisions", "Other manufacturing", "Scientific research and development",
    "Human health activities", "Sewerage", "Manufacturing", "Employment activities",
    "Manufacture of machinery and equipment n.e.c.",
    "Architectural and engineering activities; technical testing and analysis",
    "Manufacture of electrical equipment", "Manufacture of chemicals and chemical products",
    "Real estate activities", "Manufacture of computer, electronic and optical products",
    "Remediation activities and other waste management services",
    "Activities auxiliary to financial service and insurance activities.",
    "Manufacture of motor vehicles, trailers and semi-trailers", "Manufacture of textiles",
    "Wholesale and retail trade and repair of motor vehicles and motorcycles",
    "Creative, arts and entertainment activities", "Publishing activities",
    "Arts, entertainment and recreation", "Human health and social work activities",
    "Libraries, archives, museums and other cultural activities", "Manufacture of basic metals",
    "Manufacture of fabricated metal products, except machinery and equipment", "Air transport",
    "Sports activities and amusement and recreation activities", "Water transport",
    "Warehousing and support activities for transportation", "Postal and courier activities",
    "Land transport and transport via pipelines",
    "Manufacture of coke and refined petroleum products",
    "Insurance, reinsurance and pension funding, except compulsory social security",
    "Agricultural Products and Services",
    "Activities of households as employers of domestic personnel",
    "Manufacture of rubber and plastics products",
    "Motion picture, video and television programme production, sound recording and music "
    "publishing activities",
    "Mining and quarrying", "Manufacture of paper and paper products",
    "Mining support service activities", "Residential care activities",
    "Mining of coal and lignite", "Programming and broadcasting activities",
    "goods", "services", "works",
]  # fmt: skip


@pytest.mark.parametrize("category", ETENDERS_CATEGORIES)
def test_every_observed_category_is_mapped_or_generic(category: str) -> None:
    assert is_generic(category) or tender_sectors(category) is not None


def test_normalise_collapses_whitespace_and_case() -> None:
    assert normalise("  Supplies:   MEDICAL ") == "supplies: medical"


def test_supplies_categories_accept_trade() -> None:
    sectors = tender_sectors("Supplies: Medical")

    assert sectors is not None
    assert TRADE in sectors
    assert "health" in sectors


def test_non_supply_categories_do_not_accept_trade() -> None:
    sectors = tender_sectors("Construction")

    assert sectors is not None
    assert TRADE not in sectors


def test_multi_group_label() -> None:
    sectors = tender_sectors("Services: Functional (Including Cleaning and Security Services)")

    assert sectors == frozenset({"security", "facilities"})


@pytest.mark.parametrize("label", ["Services: General", "goods", "Other service activities"])
def test_generic_labels_map_to_none(label: str) -> None:
    assert tender_sectors(label) is None
    assert company_sectors(label) is None


def test_unknown_label_maps_to_none() -> None:
    assert tender_sectors("Underwater basket weaving") is None
    assert company_sectors("Underwater basket weaving") is None


def test_company_side_trade_label() -> None:
    assert company_sectors("Wholesale and retail trade") == frozenset({TRADE})
