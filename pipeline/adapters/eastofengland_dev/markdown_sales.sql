-- Adapter view: markdown_sales_v1 for East of England DEV
-- Pass-through to the production canonical markdown sales view.
CREATE OR REPLACE VIEW STORE_INSIGHT_DEV.PUBLIC.MARKDOWN_SALES_V1 AS
SELECT * FROM STORE_INSIGHT_DB.PUBLIC.MARKDOWN_SALES_V1;
