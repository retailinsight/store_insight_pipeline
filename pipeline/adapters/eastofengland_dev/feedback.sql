-- Adapter view: feedback_v1 for East of England DEV
-- Pass-through to the production canonical feedback view.
CREATE OR REPLACE VIEW STORE_INSIGHT_DEV.PUBLIC.FEEDBACK_V1 AS
SELECT * FROM STORE_INSIGHT_DB.PUBLIC.FEEDBACK_V1;
