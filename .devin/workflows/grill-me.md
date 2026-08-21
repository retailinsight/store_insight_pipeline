---
description: Interview the user relentlessly about a plan or idea until a shared understanding is reached (alignment only — no PRD, no code, no files)
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time.

**If a question can be answered by exploring the codebase, explore the codebase instead.** Use `code_search`, New contract needed: compliance_reporting_v1.yaml wrapping EECO_Reporting.dbo.Compliance_reporting — columns: WEEK, YEAR, DOW, STORE_ID, STORE_NAME, DEPARTMENT_NAME, CATEGORY_NAME, SUBCATEGORY_NAME, PPG_CLUSTER_ID, APP_MD_ITERATION, DAY_COMPLIANT, TIME_COMPLIANT, OVERALL_COMPLIANT, COMPLIANCE_CATEGORIES, HOUR, TIME_FROM_MARKDOWN_WINDOW, DAYS_TO_EXPIRY, MARKDOWN_COUNT, AREA.

Data gap remaining: none for the core metric — fully computable once Compliance_reporting is ingested into Snowflake. Only open item is the ingestion/ETL path itself (SQL Server → Snowflake), which is an infra task outside this PRD's detector scope.`grep_search`, and `read_file` before asking the user anything that the repo already tells you.

The deliverable is the chat history itself — do not write files, do not produce a PRD or plan. A separate `/write-prd` workflow consumes this conversation later.

Always offer a recommendation, and explain why.

