-- Adapter view: wastage_v1 for East of England DEV
-- Pass-through to the production canonical wastage view.
CREATE OR REPLACE VIEW STORE_INSIGHT_DEV.PUBLIC.WASTAGE_V1 AS
SELECT * FROM STORE_INSIGHT_DB.PUBLIC.WASTAGE_V1;
