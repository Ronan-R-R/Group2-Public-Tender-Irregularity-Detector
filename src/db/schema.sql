-- Tender Risk Monitor database, PostgreSQL 17.
--
-- Loosely follows the Open Contracting Data Standard: a contracting process
-- (ocid) has one tender and any number of awards, each to one supplier.
--
-- Everything lives in the "tender" schema, not "public". Supabase publishes
-- "public" through its REST API with an anonymous key, and director data must
-- never be reachable that way. Row-level security is enabled on every table
-- with no policies, as a second barrier: only the table owner (the pipeline's
-- direct connection) can read or write.
--
-- Applied by docker compose on first start of the data volume, and by the
-- schema tests. Changes after release go in forward-only migrations.

CREATE SCHEMA IF NOT EXISTS tender;
SET search_path = tender;

-- ---------------------------------------------------------------------------
-- Procurement records (public data from the eTenders OCDS feed)
-- ---------------------------------------------------------------------------

CREATE TABLE buyers (
    buyer_id    text PRIMARY KEY,                  -- "etenders:<id>"
    name        text NOT NULL CHECK (length(name) BETWEEN 1 AND 300)
);

CREATE TABLE tenders (
    ocid                text PRIMARY KEY CHECK (ocid ~ '^ocds-[a-z0-9]+-'),
    buyer_id            text NOT NULL REFERENCES buyers ON DELETE RESTRICT,
    title               text NOT NULL DEFAULT '',
    category            text,                      -- eTenders category label
    procurement_method  text,                      -- procurementMethodDetails
    close_date          date CHECK (close_date >= DATE '2000-01-01'),
    loaded_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX tenders_buyer_close_idx ON tenders (buyer_id, close_date);
CREATE INDEX tenders_category_close_idx ON tenders (category, close_date);

-- A supplier as eTenders identifies it, enriched from CIPC where matched.
-- company_id is "etenders:<id>" or "name:<normalised name>" for suppliers
-- eTenders gives the placeholder id 0.
CREATE TABLE companies (
    company_id            text PRIMARY KEY,
    name                  text NOT NULL CHECK (length(name) BETWEEN 1 AND 300),
    registration_number   text UNIQUE,             -- CIPC, e.g. 2019/123456/07
    registration_date     date,
    status                text,                    -- CIPC status
    industry              text,                    -- CIPC industry description
    cipc_match_confidence numeric(4, 3) CHECK (cipc_match_confidence BETWEEN 0 AND 1),
    cipc_checked_at       timestamptz
);

CREATE TABLE company_annual_returns (
    company_id  text NOT NULL REFERENCES companies ON DELETE CASCADE,
    filed_on    date NOT NULL,
    PRIMARY KEY (company_id, filed_on)
);

CREATE TABLE awards (
    award_id    text PRIMARY KEY,                  -- "<ocid>/<award id>"
    ocid        text NOT NULL REFERENCES tenders ON DELETE CASCADE,
    supplier_id text NOT NULL REFERENCES companies ON DELETE RESTRICT,
    value       numeric(20, 2) CHECK (value > 0),  -- NULL when not published
    currency    char(3) NOT NULL DEFAULT 'ZAR' CHECK (currency ~ '^[A-Z]{3}$'),
    award_date  date CHECK (award_date >= DATE '2000-01-01'),
    CHECK (award_id LIKE ocid || '/%')
);
CREATE INDEX awards_ocid_idx ON awards (ocid);
CREATE INDEX awards_supplier_idx ON awards (supplier_id);

-- Bidders, where a source publishes a genuine bid list (needed by R5).
CREATE TABLE tender_bidders (
    ocid        text NOT NULL REFERENCES tenders ON DELETE CASCADE,
    company_id  text NOT NULL REFERENCES companies ON DELETE RESTRICT,
    PRIMARY KEY (ocid, company_id)
);
CREATE INDEX tender_bidders_company_idx ON tender_bidders (company_id);

-- ---------------------------------------------------------------------------
-- Personal information (POPIA). Never exported to the public site.
-- ---------------------------------------------------------------------------

-- director_id is a pseudonymous key; it is the only director field that may
-- appear in public output. No identity numbers are stored.
CREATE TABLE directors (
    director_id text PRIMARY KEY,
    full_name   text NOT NULL CHECK (length(full_name) BETWEEN 1 AND 300),
    loaded_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE company_directors (
    company_id  text NOT NULL REFERENCES companies ON DELETE CASCADE,
    director_id text NOT NULL REFERENCES directors ON DELETE CASCADE,
    appointed   date,
    resigned    date,
    PRIMARY KEY (company_id, director_id),
    CHECK (resigned IS NULL OR appointed IS NULL OR resigned >= appointed)
);
CREATE INDEX company_directors_director_idx ON company_directors (director_id);

-- Politically exposed person matches for R6; always reviewed by a person.
CREATE TABLE pep_matches (
    director_id  text NOT NULL REFERENCES directors ON DELETE CASCADE,
    source       text NOT NULL,                    -- e.g. "opensanctions"
    source_ref   text NOT NULL,
    match_score  numeric(4, 3) NOT NULL CHECK (match_score BETWEEN 0 AND 1),
    matched_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (director_id, source, source_ref)
);

-- ---------------------------------------------------------------------------
-- Resolution cache for supplier lookups (CIPC and OpenCorporates)
-- ---------------------------------------------------------------------------

CREATE TABLE resolution_cache (
    supplier_name         text PRIMARY KEY,
    matched_company_id    text,
    matched_company_name  text,
    confidence            numeric(4, 3) NOT NULL,
    status                text NOT NULL, -- exact, strong_fuzzy, needs_review, no_match
    source                text NOT NULL, -- cipc, opencorporates, sample
    directors             jsonb NOT NULL DEFAULT '[]',
    cached_at             timestamptz NOT NULL DEFAULT now(),
    expires_at            timestamptz NOT NULL
);

-- ---------------------------------------------------------------------------
-- Scoring output
-- ---------------------------------------------------------------------------

CREATE TABLE scoring_runs (
    run_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at      timestamptz NOT NULL DEFAULT now(),
    source          text NOT NULL,                 -- e.g. OCDS feed URL
    awards_scored   integer NOT NULL DEFAULT 0 CHECK (awards_scored >= 0)
);

CREATE TABLE risk_scores (
    run_id              bigint NOT NULL REFERENCES scoring_runs ON DELETE CASCADE,
    award_id            text NOT NULL REFERENCES awards ON DELETE CASCADE,
    score               smallint NOT NULL CHECK (score BETWEEN 0 AND 100),
    uncapped_score      smallint NOT NULL CHECK (uncapped_score >= score),
    level               text NOT NULL CHECK (level IN ('none', 'flag', 'alert')),
    coverage            numeric(4, 3) NOT NULL CHECK (coverage BETWEEN 0 AND 1),
    needs_review        boolean NOT NULL DEFAULT false,
    -- Isolation Forest percentile, reported beside the score, never part of it.
    anomaly_percentile  numeric(4, 1) CHECK (anomaly_percentile BETWEEN 0 AND 100),
    PRIMARY KEY (run_id, award_id),
    CHECK ((level = 'alert') = (score >= 75)),
    CHECK ((level = 'flag') = (score >= 50 AND score < 75))
);
CREATE INDEX risk_scores_award_idx ON risk_scores (award_id);
CREATE INDEX risk_scores_ranked_idx ON risk_scores (run_id, score DESC);

CREATE TABLE rule_results (
    run_id            bigint NOT NULL,
    award_id          text NOT NULL,
    rule_id           text NOT NULL CHECK (rule_id ~ '^R[0-9]{1,2}$'),
    severity          text NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    fired             boolean NOT NULL,
    evaluated         boolean NOT NULL,
    points            smallint NOT NULL CHECK (points >= 0),
    evidence          jsonb NOT NULL DEFAULT '{}',
    private_evidence  jsonb NOT NULL DEFAULT '{}', -- director names, PEP detail
    PRIMARY KEY (run_id, award_id, rule_id),
    FOREIGN KEY (run_id, award_id) REFERENCES risk_scores ON DELETE CASCADE,
    CHECK (evaluated OR NOT fired),
    CHECK (fired OR points = 0),
    CHECK (NOT fired OR points = CASE severity
        WHEN 'critical' THEN 25 WHEN 'high' THEN 15 WHEN 'medium' THEN 8 ELSE 3 END)
);

-- ---------------------------------------------------------------------------
-- Retention (privacy notice: director data is deleted 12 months after its
-- last link to an award we still hold)
-- ---------------------------------------------------------------------------

-- A director's "last link" is the latest date of any retained award won by a
-- company they direct: the award date, else the tender close date, else the
-- day the record was loaded (so an undated award still counts as recent).
-- Directors with no link at all, or whose last link is older than the
-- retention period, are deleted; their company links and PEP matches go with
-- them through ON DELETE CASCADE. Returns the number of directors deleted.
CREATE FUNCTION purge_expired_directors(
    retention interval DEFAULT interval '12 months',
    as_of date DEFAULT current_date
) RETURNS integer
LANGUAGE sql
SET search_path = tender
AS $$
    WITH last_link AS (
        SELECT cd.director_id,
               max(coalesce(a.award_date, t.close_date, t.loaded_at::date)) AS last_close
        FROM company_directors cd
        JOIN awards a ON a.supplier_id = cd.company_id
        JOIN tenders t ON t.ocid = a.ocid
        GROUP BY cd.director_id
    ),
    deleted AS (
        DELETE FROM directors d
        WHERE NOT EXISTS (
            SELECT 1 FROM last_link l
            WHERE l.director_id = d.director_id
              AND l.last_close IS NOT NULL
              AND l.last_close >= as_of - retention
        )
        RETURNING 1
    )
    SELECT count(*)::integer FROM deleted;
$$;

-- ---------------------------------------------------------------------------
-- Row-level security on every table, no policies: deny to API roles.
-- ---------------------------------------------------------------------------

DO $$
DECLARE t record;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'tender' LOOP
        EXECUTE format('ALTER TABLE tender.%I ENABLE ROW LEVEL SECURITY', t.tablename);
    END LOOP;
END $$;

RESET search_path;
