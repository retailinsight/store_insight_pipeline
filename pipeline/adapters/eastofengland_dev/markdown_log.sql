-- Adapter view: markdown_log_v1 for East of England DEV
-- Pass-through to the production canonical markdown log view.
CREATE OR REPLACE VIEW STORE_INSIGHT_DEV.PUBLIC.MARKDOWN_LOG_V1 AS
SELECT * FROM STORE_INSIGHT_DB.PUBLIC.MARKDOWN_LOG_V1;
