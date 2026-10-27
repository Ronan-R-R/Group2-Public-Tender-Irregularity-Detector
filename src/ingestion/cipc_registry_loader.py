from collections.abc import Iterable
from dataclasses import dataclass, field
import psycopg
from psycopg.rows import dict_row


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
    def __init__(self, conninfo: str):
        """Initialize the CIPC registry loader with a PostgreSQL connection string."""
        self.conninfo = conninfo

    def load_companies(self) -> Iterable[CompanyRecord]:
        """Load all active company records and their associated directors from the local DB."""
        with psycopg.connect(self.conninfo, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path = tender;")
                
                # Fetch all companies
                cur.execute("""
                    SELECT company_id, name, registration_number, status
                    FROM companies
                """)
                companies = cur.fetchall()

                for comp in companies:
                    c_id = comp["company_id"]
                    directors = self.load_directors_for_company(c_id)

                    yield CompanyRecord(
                        company_id=c_id,
                        legal_name=comp["name"],
                        trading_name=comp.get("registration_number"),
                        directors=directors,
                    )

    def load_directors_for_company(self, company_id: str) -> list[str]:
        """Securely fetch director full names for a given company ID using parameterized queries."""
        with psycopg.connect(self.conninfo, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path = tender;")
                cur.execute("""
                    SELECT d.full_name
                    FROM company_directors cd
                    JOIN directors d ON d.director_id = cd.director_id
                    WHERE cd.company_id = %s
                """, (company_id,))
                
                return [row["full_name"] for row in cur.fetchall()]
