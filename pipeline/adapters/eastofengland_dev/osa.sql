-- Adapter view: osa_v1 for East of England DEV
-- Pass-through to the production canonical OSA view.
CREATE OR REPLACE VIEW STORE_INSIGHT_DEV.PUBLIC.OSA_V1 AS
SELECT * FROM STORE_INSIGHT_DB.PUBLIC.OSA_V1;
