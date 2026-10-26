from dataclasses import dataclass
from typing import Iterable, List, Optional

@dataclass
class CompanyRecord:
    company_id: str
    legal_name: str
    trading_name: Optional[str] = None
    directors: List[str] = None

    def __post_init__(self):
        if self.directors is None:
            self.directors = []

class CIPCRegistryLoader:
    def __init__(self, source: str):
        self.source = source

    def load_companies(self) -> Iterable[CompanyRecord]:
        raise NotImplementedError

    def load_directors_for_company(self, company_id: str) -> List[str]:
        raise NotImplementedError