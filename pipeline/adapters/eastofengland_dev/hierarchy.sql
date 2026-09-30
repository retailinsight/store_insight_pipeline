-- Adapter view: hierarchy_v1 for East of England DEV
-- Pass-through to the production canonical hierarchy view.
CREATE OR REPLACE VIEW STORE_INSIGHT_DEV.PUBLIC.HIERARCHY_V1 AS
SELECT * FROM STORE_INSIGHT_DB.PUBLIC.HIERARCHY_V1;
