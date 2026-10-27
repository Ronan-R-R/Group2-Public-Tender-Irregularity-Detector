from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import psycopg
from psycopg.rows import dict_row


@dataclass
class CachedResolution:
    supplier_name: str
    matched_company_id: str | None
    matched_company_name: str | None
    confidence: float
    status: str
    source: str
    directors: list[str] = field(default_factory=list)
    cached_at: datetime | None = None
    expires_at: datetime | None = None


class ResolutionCacheRepository:
    def __init__(self, conninfo: str, ttl_days: int = 30):
        self.conninfo = conninfo
        self.ttl = timedelta(days=ttl_days)

    def lookup(self, supplier_name: str) -> CachedResolution | None:
        """Lookup an unexpired cached resolution for a supplier name."""
        with psycopg.connect(self.conninfo, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path = tender;")
                cur.execute("""
                    SELECT supplier_name, matched_company_id, matched_company_name,
                           confidence, status, source, directors, cached_at, expires_at
                    FROM resolution_cache
                    WHERE supplier_name = %s AND expires_at > current_timestamp
                """, (supplier_name,))
                
                row = cur.fetchone()
                if not row:
                    return None

                directors_data = row["directors"]
                if isinstance(directors_data, str):
                    directors_data = json.loads(directors_data)

                return CachedResolution(
                    supplier_name=row["supplier_name"],
                    matched_company_id=row["matched_company_id"],
                    matched_company_name=row["matched_company_name"],
                    confidence=float(row["confidence"]),
                    status=row["status"],
                    source=row["source"],
                    directors=directors_data or [],
                    cached_at=row["cached_at"],
                    expires_at=row["expires_at"],
                )

    def save(self, resolution: CachedResolution) -> None:
        """Save or upsert a resolution outcome (accepted, ambiguous, or no-match)."""
        now = datetime.now(timezone.utc)
        expires_at = resolution.expires_at or (now + self.ttl)

        with psycopg.connect(self.conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path = tender;")
                cur.execute("""
                    INSERT INTO resolution_cache (
                        supplier_name, matched_company_id, matched_company_name,
                        confidence, status, source, directors, cached_at, expires_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (supplier_name) DO UPDATE SET
                        matched_company_id = EXCLUDED.matched_company_id,
                        matched_company_name = EXCLUDED.matched_company_name,
                        confidence = EXCLUDED.confidence,
                        status = EXCLUDED.status,
                        source = EXCLUDED.source,
                        directors = EXCLUDED.directors,
                        cached_at = EXCLUDED.cached_at,
                        expires_at = EXCLUDED.expires_at
                """, (
                    resolution.supplier_name,
                    resolution.matched_company_id,
                    resolution.matched_company_name,
                    resolution.confidence,
                    resolution.status,
                    resolution.source,
                    json.dumps(resolution.directors),
                    now,
                    expires_at,
                ))

    def invalidate(self, supplier_name: str) -> None:
        """Invalidate/delete a cached entry."""
        with psycopg.connect(self.conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path = tender;")
                cur.execute("DELETE FROM resolution_cache WHERE supplier_name = %s", (supplier_name,))
