-- Whether a company's annual return history was looked up. Without it an
-- empty company_annual_returns could mean "never filed" (R3 fires) or "not
-- looked up" (R3 not evaluated), and R3 would wrongly flag every company
-- whose filings nobody checked.
ALTER TABLE tender.companies
    ADD COLUMN IF NOT EXISTS annual_returns_checked boolean NOT NULL DEFAULT false;
