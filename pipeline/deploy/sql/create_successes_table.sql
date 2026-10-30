-- snowflake_Changes item 8 (Cornelious approved 13 Aug): create a SUCCESSES
-- table so success data can be retrieved from Snowflake. Seeded from the API
-- mock fixture app/fixtures/successes.json (one row per success, replicated
-- for every store in KPI_AVAILABILITY_SUMMARY so each store has data).
-- Idempotent: table created IF NOT EXISTS, seed only runs when empty.
-- The pipeline will populate real successes later.

CREATE TABLE IF NOT EXISTS SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.SUCCESSES (
    SUCCESS_ID      VARCHAR      NOT NULL,
    STORE_ID        NUMBER       NOT NULL,
    RUN_DATE        DATE         NOT NULL,
    TITLE           VARCHAR      NOT NULL,
    TRIGGER_TYPES   VARCHAR,
    TYPE            VARCHAR,
    VALUE           VARCHAR,
    TREND_DIRECTION VARCHAR,
    TREND           VARCHAR,
    IMPACT          VARCHAR,
    CREATED_AT      TIMESTAMP_NTZ DEFAULT SYSDATE()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.SUCCESSES TO ROLE STOREINSIGHT;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.SUCCESSES TO ROLE STORE_INSIGHT_ROLE;

INSERT INTO SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.SUCCESSES
    (SUCCESS_ID, STORE_ID, RUN_DATE, TITLE, TRIGGER_TYPES, TYPE, VALUE, TREND_DIRECTION, TREND, IMPACT)
SELECT s.STORE_ID || '-' || f.ID,
       s.STORE_ID,
       CURRENT_DATE(),
       f.TITLE, f.TRIGGER_TYPES, f.TYPE, f.VALUE, f.TREND_DIRECTION, f.TREND, f.IMPACT
FROM (SELECT DISTINCT STORE_ID
      FROM SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.KPI_AVAILABILITY_SUMMARY) s
CROSS JOIN (
    SELECT 's1' AS ID,
           'Food to go sales have increased this week!' AS TITLE,
           'WOW' AS TRIGGER_TYPES, 'Sales' AS TYPE, '$4,343' AS VALUE,
           'up' AS TREND_DIRECTION, '+2.3% vs LW' AS TREND,
           'This is driven by the smart action from last week, where you focussed additional replenishment efforts in Food to go on Mon, Tue and Wed' AS IMPACT
    UNION ALL
    SELECT 's2',
           'Beer, Wine & Spirits sales increased on Saturday!',
           'WOW', 'Sales', '$7,920',
           'up', '+1.8% vs LW',
           'Following your team''s improved evening replenishment, sales in Beers, Wines and Spirits improved significantly on Saturday'
    UNION ALL
    SELECT 's3',
           'Sell through increased in Ready Meals this week!',
           'VS_CHAIN', 'Waste', '+8%',
           'up', '+2% vs Cluster Avg',
           'Sell through increase in Ready Meals increased due to smart markdown compliance increasing from 40% to 98% WoW'
) f
WHERE NOT EXISTS (SELECT 1 FROM SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.SUCCESSES);

-- Verify
SELECT COUNT(*) AS TOTAL, COUNT(DISTINCT STORE_ID) AS STORES
FROM SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.SUCCESSES;

SELECT * FROM SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.SUCCESSES LIMIT 3;
