-- Adapter view: store_hierarchy_v1 for East of England DEV
-- Pass-through to the production canonical store hierarchy view.
CREATE OR REPLACE VIEW STORE_INSIGHT_DEV.PUBLIC.STORE_HIERARCHY_V1 AS
SELECT * FROM STORE_INSIGHT_DB.PUBLIC.STORE_HIERARCHY_V1;
