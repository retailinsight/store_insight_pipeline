# Store Insight Snowflake Context for Claude

## Purpose

Use this context when working with the Store Insight Snowflake environment. The goal is to query the required datasets, use the Store Insight warehouse and database, create application objects where permitted, and use Snowflake Cortex safely.

Do not assume administrative access. The user is not an `ACCOUNTADMIN` and should not need that role for normal development or validation.

## Confirmed Snowflake session information

- **Snowflake account name:** `UKCOOP`
- **Region:** `AZURE_UKSOUTH`
- **User:** `ELAHEH.K@RETAILINSIGHT.IO`
- **Usable account role:** `SNOWFLAKE_DATASCIENCE`
- **Target application role:** `STORE_INSIGHT_ROLE`
- **Snowflake-provided Cortex database role:** `SNOWFLAKE.CORTEX_USER`
- **Warehouse:** `STORE_INSIGHT_WH`
- **Application database:** `STORE_INSIGHT_DB`
- **Default application schema:** `STORE_INSIGHT_DB.PUBLIC`
- **Required source databases:** `ANALYSIS` and `INBOUND`
- **Known service account:** `SVC_STOREINSIGHT`

The user previously confirmed that `STORE_INSIGHT_ROLE` was not directly listed in `CURRENT_AVAILABLE_ROLES()`. Therefore, use `SNOWFLAKE_DATASCIENCE` as the active role unless a later session check proves that `STORE_INSIGHT_ROLE` is directly available.

The intended role hierarchy is that the active role inherits the required Store Insight and Cortex permissions. Validate this with session functions rather than trying to activate a database role directly.

## Important Snowflake role rules

1. `SNOWFLAKE.CORTEX_USER` is a **database role**, not an account role.
2. Never run:

```sql
USE ROLE SNOWFLAKE.CORTEX_USER;
```

3. A database role cannot be activated directly with `USE ROLE`.
4. Use an account role such as `SNOWFLAKE_DATASCIENCE`.
5. Validate inherited roles with:

```sql
IS_ROLE_IN_SESSION('STORE_INSIGHT_ROLE')
IS_DATABASE_ROLE_IN_SESSION('SNOWFLAKE.CORTEX_USER')
```

6. Do not request or depend on `ACCOUNTADMIN` for ordinary querying, object creation, or Cortex use.
7. Do not create a new role named `CORTEX_USER`. The correct built-in database role is `SNOWFLAKE.CORTEX_USER`.

## Required session bootstrap

Run this at the start of a session:

```sql
USE ROLE SNOWFLAKE_DATASCIENCE;

SELECT
    CURRENT_ACCOUNT_NAME() AS ACCOUNT_NAME,
    CURRENT_USER()         AS CURRENT_USER,
    CURRENT_ROLE()         AS CURRENT_ROLE,
    CURRENT_REGION()       AS CURRENT_REGION,
    CURRENT_AVAILABLE_ROLES() AS AVAILABLE_ROLES,
    IS_ROLE_IN_SESSION('STORE_INSIGHT_ROLE')
        AS STORE_INSIGHT_ROLE_IN_SESSION,
    IS_DATABASE_ROLE_IN_SESSION('SNOWFLAKE.CORTEX_USER')
        AS CORTEX_USER_IN_SESSION;
```

Expected environment:

- `ACCOUNT_NAME` should be `UKCOOP`
- `CURRENT_ROLE` should be `SNOWFLAKE_DATASCIENCE`
- `STORE_INSIGHT_ROLE_IN_SESSION` should ideally be `TRUE`
- `CORTEX_USER_IN_SESSION` should ideally be `TRUE`

If either inherited-role check is `FALSE`, do not guess. Report the missing access clearly.

Then set the working context:

```sql
USE ROLE SNOWFLAKE_DATASCIENCE;
USE WAREHOUSE STORE_INSIGHT_WH;
USE DATABASE STORE_INSIGHT_DB;
USE SCHEMA PUBLIC;

SELECT
    CURRENT_ACCOUNT_NAME() AS ACCOUNT_NAME,
    CURRENT_USER()         AS CURRENT_USER,
    CURRENT_ROLE()         AS CURRENT_ROLE,
    CURRENT_WAREHOUSE()    AS CURRENT_WAREHOUSE,
    CURRENT_DATABASE()     AS CURRENT_DATABASE,
    CURRENT_SCHEMA()       AS CURRENT_SCHEMA;
```

Expected values:

- Account: `UKCOOP`
- Role: `SNOWFLAKE_DATASCIENCE`
- Warehouse: `STORE_INSIGHT_WH`
- Database: `STORE_INSIGHT_DB`
- Schema: `PUBLIC`

## Non-destructive access validation

Prefer a temporary table for validation so that no permanent object remains:

```sql
USE ROLE SNOWFLAKE_DATASCIENCE;
USE WAREHOUSE STORE_INSIGHT_WH;
USE DATABASE STORE_INSIGHT_DB;
USE SCHEMA PUBLIC;

CREATE OR REPLACE TEMPORARY TABLE STORE_INSIGHT_VALIDATION_TEST (
    TEST_ID NUMBER,
    TEST_MESSAGE VARCHAR
);

INSERT INTO STORE_INSIGHT_VALIDATION_TEST
VALUES (1, 'Validation successful');

SELECT *
FROM STORE_INSIGHT_VALIDATION_TEST;

DROP TABLE IF EXISTS STORE_INSIGHT_VALIDATION_TEST;
```

If a permanent object is explicitly required, use the fully qualified name:

```sql
CREATE OR REPLACE TABLE STORE_INSIGHT_DB.PUBLIC.STORE_INSIGHT_VALIDATION_TEST (
    TEST_ID NUMBER,
    TEST_MESSAGE VARCHAR
);

INSERT INTO STORE_INSIGHT_DB.PUBLIC.STORE_INSIGHT_VALIDATION_TEST
VALUES (1, 'Validation successful');

SELECT *
FROM STORE_INSIGHT_DB.PUBLIC.STORE_INSIGHT_VALIDATION_TEST;

DROP TABLE IF EXISTS STORE_INSIGHT_DB.PUBLIC.STORE_INSIGHT_VALIDATION_TEST;
```

Do not create or replace permanent tables unless the user explicitly approves it.

## Cortex validation

Run:

```sql
USE ROLE SNOWFLAKE_DATASCIENCE;
USE WAREHOUSE STORE_INSIGHT_WH;

SELECT SNOWFLAKE.CORTEX.SENTIMENT(
    'The Store Insight Cortex validation completed successfully.'
) AS CORTEX_TEST_RESULT;
```

A numeric result indicates that Cortex access is working.

If this fails:

- Do not try to create `CORTEX_USER`.
- Re-run the session-role checks.
- Report the exact Snowflake error.
- Ask a system engineer to verify that `SNOWFLAKE.CORTEX_USER` is granted into the active role hierarchy and that any required AI-function privilege is present.

## Discovering accessible datasets

### ANALYSIS database

```sql
SHOW SCHEMAS IN DATABASE ANALYSIS;
SHOW TABLES IN DATABASE ANALYSIS;
SHOW VIEWS IN DATABASE ANALYSIS;
```

### INBOUND database

```sql
SHOW SCHEMAS IN DATABASE INBOUND;
SHOW TABLES IN DATABASE INBOUND;
SHOW VIEWS IN DATABASE INBOUND;
```

Use the returned schema and object names to build fully qualified queries:

```sql
SELECT *
FROM ANALYSIS.<SCHEMA_NAME>.<TABLE_OR_VIEW_NAME>
LIMIT 100;
```

```sql
SELECT *
FROM INBOUND.<SCHEMA_NAME>.<TABLE_OR_VIEW_NAME>
LIMIT 100;
```

Always use three-part object names for source databases:

```text
DATABASE.SCHEMA.OBJECT
```

Do not assume that `ANALYSIS.GLD_ALERT_INTERVENTIONS` is a complete reference. In Snowflake, a two-part name is normally interpreted as `SCHEMA.OBJECT` within the current database.

First locate the object:

```sql
SHOW TABLES LIKE 'GLD_ALERT_INTERVENTIONS' IN DATABASE ANALYSIS;
SHOW VIEWS LIKE 'GLD_ALERT_INTERVENTIONS' IN DATABASE ANALYSIS;
```

Then query it using the schema returned by `SHOW`:

```sql
SELECT *
FROM ANALYSIS.<RETURNED_SCHEMA_NAME>.GLD_ALERT_INTERVENTIONS
LIMIT 1;
```

If the object is not found in `ANALYSIS`, search `INBOUND`:

```sql
SHOW TABLES LIKE 'GLD_ALERT_INTERVENTIONS' IN DATABASE INBOUND;
SHOW VIEWS LIKE 'GLD_ALERT_INTERVENTIONS' IN DATABASE INBOUND;
```

## Recommended full validation script

Run each section separately so that failures are easy to diagnose.

```sql
-- ============================================================
-- 1. Session and inherited-role checks
-- ============================================================

USE ROLE SNOWFLAKE_DATASCIENCE;

SELECT
    CURRENT_ACCOUNT_NAME() AS ACCOUNT_NAME,
    CURRENT_USER()         AS CURRENT_USER,
    CURRENT_ROLE()         AS CURRENT_ROLE,
    CURRENT_REGION()       AS CURRENT_REGION,
    CURRENT_AVAILABLE_ROLES() AS AVAILABLE_ROLES,
    IS_ROLE_IN_SESSION('STORE_INSIGHT_ROLE')
        AS STORE_INSIGHT_ROLE_IN_SESSION,
    IS_DATABASE_ROLE_IN_SESSION('SNOWFLAKE.CORTEX_USER')
        AS CORTEX_USER_IN_SESSION;

-- ============================================================
-- 2. Set Store Insight context
-- ============================================================

USE ROLE SNOWFLAKE_DATASCIENCE;
USE WAREHOUSE STORE_INSIGHT_WH;
USE DATABASE STORE_INSIGHT_DB;
USE SCHEMA PUBLIC;

SELECT
    CURRENT_ROLE()      AS CURRENT_ROLE,
    CURRENT_WAREHOUSE() AS CURRENT_WAREHOUSE,
    CURRENT_DATABASE()  AS CURRENT_DATABASE,
    CURRENT_SCHEMA()    AS CURRENT_SCHEMA;

-- ============================================================
-- 3. Safe object-creation test
-- ============================================================

CREATE OR REPLACE TEMPORARY TABLE STORE_INSIGHT_VALIDATION_TEST (
    TEST_ID NUMBER,
    TEST_MESSAGE VARCHAR
);

INSERT INTO STORE_INSIGHT_VALIDATION_TEST
VALUES (1, 'Validation successful');

SELECT *
FROM STORE_INSIGHT_VALIDATION_TEST;

DROP TABLE IF EXISTS STORE_INSIGHT_VALIDATION_TEST;

-- ============================================================
-- 4. Cortex test
-- ============================================================

SELECT SNOWFLAKE.CORTEX.SENTIMENT(
    'The Store Insight Cortex validation completed successfully.'
) AS CORTEX_TEST_RESULT;

-- ============================================================
-- 5. Source-database discovery
-- ============================================================

SHOW SCHEMAS IN DATABASE ANALYSIS;
SHOW TABLES IN DATABASE ANALYSIS;
SHOW VIEWS IN DATABASE ANALYSIS;

SHOW SCHEMAS IN DATABASE INBOUND;
SHOW TABLES IN DATABASE INBOUND;
SHOW VIEWS IN DATABASE INBOUND;

-- ============================================================
-- 6. Locate the known object safely
-- ============================================================

SHOW TABLES LIKE 'GLD_ALERT_INTERVENTIONS' IN DATABASE ANALYSIS;
SHOW VIEWS LIKE 'GLD_ALERT_INTERVENTIONS' IN DATABASE ANALYSIS;

SHOW TABLES LIKE 'GLD_ALERT_INTERVENTIONS' IN DATABASE INBOUND;
SHOW VIEWS LIKE 'GLD_ALERT_INTERVENTIONS' IN DATABASE INBOUND;

-- After identifying the correct database and schema:
-- SELECT *
-- FROM ANALYSIS.<SCHEMA_NAME>.GLD_ALERT_INTERVENTIONS
-- LIMIT 1;
```

## How Claude should behave

When helping with this environment:

- Use `SNOWFLAKE_DATASCIENCE` as the active role unless current session output shows a better valid role.
- Never suggest activating `SNOWFLAKE.CORTEX_USER` directly.
- Never suggest creating a replacement `CORTEX_USER` account role.
- Prefer read-only queries and temporary objects.
- Fully qualify source objects with `DATABASE.SCHEMA.OBJECT`.
- Use `LIMIT` for exploratory queries.
- Before joins or transformations, inspect schemas and columns first.
- Preserve the current Store Insight context: `STORE_INSIGHT_WH`, `STORE_INSIGHT_DB`, and `PUBLIC`.
- Treat `ANALYSIS` and `INBOUND` as source databases with read access.
- Do not assume access exists merely because an object name is known.
- When a query fails, explain whether it is a wrong account, inactive or missing role, missing warehouse access, missing database/schema usage, missing object privilege, missing Cortex inheritance, or an incorrectly qualified object name.
- Ask for exact Snowflake error text before proposing administrative changes.
- Do not recommend `ACCOUNTADMIN` unless an administrator is explicitly performing a grant or ownership task.

## Access escalation messages

If `STORE_INSIGHT_ROLE_IN_SESSION` is `FALSE`:

> I am connected to the UKCOOP account using `SNOWFLAKE_DATASCIENCE`, but `STORE_INSIGHT_ROLE` is not inherited in my current session. Please grant it into the role hierarchy used by `SNOWFLAKE_DATASCIENCE`, or confirm the approved role I should use for Store Insight development.

If `CORTEX_USER_IN_SESSION` is `FALSE`:

> I can access the Store Insight environment, but `SNOWFLAKE.CORTEX_USER` is not inherited in my current session. Please verify that the Snowflake database role `SNOWFLAKE.CORTEX_USER` is granted to `STORE_INSIGHT_ROLE` and that `STORE_INSIGHT_ROLE` is inherited by my active account role.

If the service account must be verified:

> Please also confirm that `STORE_INSIGHT_ROLE` has been granted to the service account `SVC_STOREINSIGHT`, as this may require administrator-level metadata visibility.

## Success criteria

The environment is ready when all of the following are true:

- The active account is `UKCOOP`.
- `SNOWFLAKE_DATASCIENCE` can activate successfully.
- `STORE_INSIGHT_WH` can be used.
- `STORE_INSIGHT_DB.PUBLIC` can be used.
- A temporary table can be created, queried, and dropped.
- `SNOWFLAKE.CORTEX.SENTIMENT` executes successfully.
- Schemas, tables, and views can be listed in `ANALYSIS`.
- Schemas, tables, and views can be listed in `INBOUND`.
- Required source objects can be queried using fully qualified names.
- An administrator confirms `STORE_INSIGHT_ROLE` is granted to `SVC_STOREINSIGHT`.
