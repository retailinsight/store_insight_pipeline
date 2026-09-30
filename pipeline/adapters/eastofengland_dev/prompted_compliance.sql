-- Adapter view: prompted_compliance_v1 for East of England DEV
-- Pass-through to the production canonical prompted compliance view.
CREATE OR REPLACE VIEW STORE_INSIGHT_DEV.PUBLIC.PROMPTED_COMPLIANCE_V1 AS
SELECT * FROM STORE_INSIGHT_DB.PUBLIC.PROMPTED_COMPLIANCE_V1;
