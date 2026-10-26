from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass
class CompanyRecord:
    company_id: str
    legal_name: str
    trading_name: str | None = None
    directors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.directors is None:
            self.directors = []


class CIPCRegistryLoader:
    def __init__(self, source: str):
        self.source = source

    def load_companies(self) -> Iterable[CompanyRecord]:
        raise NotImplementedError

    def load_directors_for_company(self, company_id: str) -> list[str]:
        raise NotImplementedError
