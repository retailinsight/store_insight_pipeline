-- Adapter view: wmd_hierarchy_v1 for East of England DEV
-- Pass-through to the production canonical item hierarchy view.
CREATE OR REPLACE VIEW STORE_INSIGHT_DEV.PUBLIC.WMD_HIERARCHY_V1 AS
SELECT * FROM STORE_INSIGHT_DB.PUBLIC.WMD_HIERARCHY_V1;
