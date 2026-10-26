from .cipc_registry_loader import CompanyRecord

def sample_company_registry() -> list[CompanyRecord]:
    return [
        CompanyRecord(
            company_id="sample:001",
            legal_name="Ndlovu Transport Services Pty Ltd",
            trading_name="Ndlovu Transport",
            directors=["Sibongile Ndlovu", "Thabo Ndlovu"],
        ),
        CompanyRecord(
            company_id="sample:002",
            legal_name="Mokoena Construction and Projects CC",
            trading_name="Mokoena Construction",
            directors=["Tshepo Mokoena"],
        ),
        CompanyRecord(
            company_id="sample:003",
            legal_name="Bophelo Civils Limited",
            trading_name="Bophelo Civils",
            directors=["Aisha Mokoena"],
        ),
    ]