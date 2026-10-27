-- Director birth dates for PEP screening (R6). Read off the ID number when a
-- director is looked up on CIPC; the ID number itself is never stored.
ALTER TABLE tender.directors
    ADD COLUMN IF NOT EXISTS birth_date date CHECK (birth_date >= DATE '1900-01-01');
