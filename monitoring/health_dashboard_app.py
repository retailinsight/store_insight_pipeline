"""Store Insight pilot health dashboard (Streamlit in Snowflake).

Live view of LATEST_SYSTEM_HEALTH: status cards, a colour-coded table and a
bar chart of alert volume vs baseline. Deployed by
scripts/deploy_health_dashboard.py; the app URL is pinned in
#store-insight-pilot-alerts so anyone can check current health on demand.
"""
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from snowflake.snowpark.context import get_active_session

DB = "STORE_INSIGHT_DB"
STAGE = f"{DB}.PUBLIC.HEALTH_DASHBOARD_STAGE"

STATUS_COLOURS = {
    "OK": "#10b981",       # green
    "WARN": "#f59e0b",     # amber
    "FAIL": "#ef4444",     # red
    "UNKNOWN": "#9ca3af",  # grey
}
STATUS_ICONS = {"OK": "\u2705", "WARN": "\u26a0\ufe0f",
                "FAIL": "\U0001f534", "UNKNOWN": "\u26aa"}

st.set_page_config(page_title="Store Insight Pilot Health", layout="wide")
session = get_active_session()

st.title("Store Insight Pilot Health")
st.caption("Live view — refreshes every time you open or reload this page. "
           "Green = good, amber = investigate, red = act now, grey = no data.")

health = session.sql(f"""
    SELECT CHECK_ID, HUMAN_NAME, DESCRIPTION, AFFECTED_PART, IMPACT,
           FIRST_RESPONSE, STATUS, COLOUR, DATA_AS_OF, LAST_CHECK_TIME,
           DETAILS, OWNER
    FROM {DB}.PUBLIC.LATEST_SYSTEM_HEALTH
    ORDER BY CHECK_ID
""").to_pandas()

if health.empty:
    st.warning("No monitoring results yet. The monitor runs daily at 07:00 UK.")
    st.stop()

# ── Overall banner ───────────────────────────────────────────────────────────
counts = health["STATUS"].value_counts()
n_fail = int(counts.get("FAIL", 0))
n_warn = int(counts.get("WARN", 0))
n_unknown = int(counts.get("UNKNOWN", 0))
n_ok = int(counts.get("OK", 0))

if n_fail:
    st.error(f"Overall: FAIL — {n_fail} check(s) need action now.")
elif n_warn or n_unknown:
    st.warning(f"Overall: WARN — {n_warn + n_unknown} check(s) need a look today.")
else:
    st.success("Overall: HEALTHY — all checks passed on the latest run.")

last_check = pd.to_datetime(health["LAST_CHECK_TIME"]).max()
now = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M:%S")
st.caption(f"Monitoring last run: {last_check} | Business date: {health['DATA_AS_OF'].max()} | "
           f"Dashboard opened: {now} UTC")

with st.expander("How this dashboard updates"):
    st.markdown("""
- The monitoring task runs **daily at 07:00 UK** and writes one row per check to `MONITORING_LOG`.
- This page is **live on every open/reload** — it re-queries `LATEST_SYSTEM_HEALTH` fresh each time.
- **To refresh:** press F5 / Ctrl+R in the browser tab.
- **"Monitoring last run"** = the last time `SP_RUN_MONITORING` completed. **"Business date"** = the data date it checked. **"Dashboard opened"** = when you loaded this page.
""")

# ── Status cards ─────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("\u2705 Healthy", n_ok)
c2.metric("\u26a0\ufe0f Warning", n_warn)
c3.metric("\U0001f534 Failed", n_fail)
c4.metric("\u26aa Unknown", n_unknown)

st.markdown("---")

# ── Action needed (only shown if something is not OK) ────────────────────────
bad = health[health["STATUS"] != "OK"]
if bad.empty:
    st.success("No action needed — all checks are healthy.")
else:
    st.subheader("Action needed")
    for _, r in bad.iterrows():
        status = r["STATUS"]
        if status == "FAIL":
            box = st.error
        else:
            box = st.warning
        box(
            f"{r['CHECK_ID']} — {r['HUMAN_NAME']}\n\n"
            f"What is wrong: {r['DETAILS']}\n"
            f"What stores may see: {r['IMPACT']}\n"
            f"First step: {r['FIRST_RESPONSE']}\n"
            f"Owner: {r['OWNER'] or 'Owner not yet agreed'}  |  "
            f"Escalate to Dave if not fixed today."
        )

st.markdown("---")
st.subheader("Source feed detail")
source_health = session.sql(f"""
    SELECT SOURCE_NAME, CHECK_DATE, ROW_COUNT, BASELINE_ROWS, STATUS, ACTION_TAKEN
    FROM {DB}.PUBLIC.DATA_QUALITY_LOG
    WHERE RUN_DATE = (SELECT MAX(RUN_DATE) FROM {DB}.PUBLIC.DATA_QUALITY_LOG)
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY SOURCE_NAME ORDER BY CREATED_AT DESC
    ) = 1
    ORDER BY SOURCE_NAME
""").to_pandas()
if source_health.empty:
    st.info("No source-quality rows for the latest run date.")
else:
    source_health["Current vs baseline"] = source_health.apply(
        lambda r: (
            f"{int(r['ROW_COUNT']):,} vs {float(r['BASELINE_ROWS']):,.0f} "
            f"({float(r['ROW_COUNT']) / float(r['BASELINE_ROWS']):.1%})"
            if pd.notna(r["ROW_COUNT"]) and pd.notna(r["BASELINE_ROWS"])
            and float(r["BASELINE_ROWS"]) > 0
            else f"{int(r['ROW_COUNT']):,}" if pd.notna(r["ROW_COUNT"]) else "No count"
        ), axis=1)
    source_health["Impact"] = source_health["SOURCE_NAME"].map({
        "osa": "Availability actions may be missing or incomplete.",
        "feedback": "Feedback analysis may be incomplete; current OSA actions are unaffected.",
        "markdown_log": "Markdown compliance output may be incomplete.",
        "markdown_sales": "Markdown sales output may be incomplete.",
        "wastage": "Waste-related output may be incomplete.",
    }).fillna("Output depending on this source may be incomplete.")
    source_health = source_health.rename(columns={
        "SOURCE_NAME": "Source", "CHECK_DATE": "Source data date",
        "STATUS": "Status", "ACTION_TAKEN": "Gate action",
    })
    st.dataframe(source_health[["Source", "Source data date", "Status",
                                "Current vs baseline", "Gate action", "Impact"]],
                 use_container_width=True)

# ── Health check table (plain English) ───────────────────────────────────────
st.subheader("Today's health checks")
display = health.copy()
display["Status"] = display["STATUS"].map(
    lambda s: f"{STATUS_ICONS.get(s, '')} {s}")
display = display.rename(columns={
    "CHECK_ID": "Code",
    "HUMAN_NAME": "What it checks",
    "AFFECTED_PART": "Affected part",
    "IMPACT": "What stores may see if it breaks",
    "FIRST_RESPONSE": "First response step",
    "DETAILS": "Latest result",
    "OWNER": "Owner",
    "DATA_AS_OF": "Data as of",
})
table = display[["Status", "Code", "What it checks", "Affected part",
                 "Latest result", "What stores may see if it breaks",
                 "First response step", "Owner", "Data as of"]]
table = table.reset_index(drop=True)
st.dataframe(table, use_container_width=True)

st.markdown("---")

# ── Charts row ───────────────────────────────────────────────────────────────
left, right = st.columns(2)

with left:
    st.subheader("Alerts sent to stores (last 14 days)")
    volume = session.sql(f"""
        SELECT RUN_DATE, COUNT(*) AS ALERTS
        FROM {DB}.PUBLIC.ALERTS_PIPELINE
        WHERE RUN_DATE >= DATEADD(day, -14, CURRENT_DATE())
        GROUP BY RUN_DATE
        ORDER BY RUN_DATE
    """).to_pandas()
    if volume.empty:
        st.info("No alert volume data in the last 14 days.")
    else:
        chart = alt.Chart(volume).mark_bar(color="#3b82f6").encode(
            x=alt.X("RUN_DATE:T", title="Day"),
            y=alt.Y("ALERTS:Q", title="Alerts"),
            tooltip=["RUN_DATE:T", "ALERTS:Q"],
        )
        st.altair_chart(chart, use_container_width=True)

with right:
    st.subheader("Alert mix today")
    mix = session.sql(f"""
        SELECT TYPE AS ALERT_TYPE, COUNT(*) AS ALERTS
        FROM {DB}.PUBLIC.ALERTS_PIPELINE
        WHERE RUN_DATE = (SELECT MAX(RUN_DATE) FROM {DB}.PUBLIC.ALERTS_PIPELINE)
        GROUP BY TYPE
        ORDER BY ALERTS DESC
    """).to_pandas()
    if mix.empty:
        st.info("No alerts for the latest run date.")
    else:
        chart = alt.Chart(mix).mark_bar(color="#8b5cf6").encode(
            x=alt.X("ALERTS:Q", title="Alerts"),
            y=alt.Y("ALERT_TYPE:N", title="Alert type", sort="-x"),
            tooltip=["ALERT_TYPE:N", "ALERTS:Q"],
        )
        st.altair_chart(chart, use_container_width=True)

st.markdown("---")

# ── Status history ───────────────────────────────────────────────────────────
st.subheader("Check history (last 14 days)")
history = session.sql(f"""
    SELECT TO_VARCHAR(BUSINESS_DATE, 'YYYY-MM-DD') AS DAY,
           CHECK_ID, STATUS
    FROM {DB}.PUBLIC.MONITORING_LOG
    WHERE BUSINESS_DATE >= DATEADD(day, -14, CURRENT_DATE())
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY BUSINESS_DATE, CHECK_ID ORDER BY CHECKED_AT DESC) = 1
    ORDER BY DAY, CHECK_ID
""").to_pandas()
if history.empty:
    st.info("No monitoring history yet.")
else:
    heat = alt.Chart(history).mark_rect(stroke="white", strokeWidth=2).encode(
        x=alt.X("DAY:O", title="Day", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("CHECK_ID:N", title="Check"),
        color=alt.Color(
            "STATUS:N",
            scale=alt.Scale(
                domain=["OK", "WARN", "FAIL", "UNKNOWN"],
                range=["#10b981", "#f59e0b", "#ef4444", "#9ca3af"],
            ),
            legend=alt.Legend(title="Status"),
        ),
        tooltip=["DAY:O", "CHECK_ID:N", "STATUS:N"],
    ).properties(height=260)
    st.altair_chart(heat, use_container_width=True)
    st.caption("One square per check per day — green is healthy, "
               "amber needs a look, red needed action, grey had no data.")

st.markdown("---")

# ── Open incidents ───────────────────────────────────────────────────────────
st.subheader("Open incidents")
incidents = session.sql(f"""
    SELECT CHECK_ID, SEVERITY, OPENED_AT, LAST_OBSERVED_AT
    FROM {DB}.PUBLIC.MONITORING_INCIDENT
    WHERE STATUS = 'OPEN'
    ORDER BY OPENED_AT DESC
""").to_pandas()
if incidents.empty:
    st.success("No open incidents.")
else:
    st.dataframe(incidents.reset_index(drop=True), use_container_width=True)

# ── Reference documents ──────────────────────────────────────────────────────
with st.expander("Essential guides and reference documents"):
    st.write("Start with the essential guides. Technical documents are included for deeper investigation.")
    try:
        rows = session.sql(f"LIST @{STAGE}").collect()
    except Exception as e:
        st.error(f"Could not list documents: {e}")
        rows = []
    available = {Path(str(row[0])).name for row in rows}
    documents = {
        "Essential guides": [
            ("CHANNEL_GUIDE.md", "How to read alerts, status words, ownership and urgency."),
            ("PILOT_MONITORING_ONE_PAGER.md", "The current monitoring and support model at a glance."),
            ("RUNBOOK.md", "Safe validation and response steps for each C-code."),
            ("SCHEDULE_AND_GAPS.md", "Daily task schedule, rerun process and unresolved ownership gaps."),
        ],
        "Technical reference": [
            ("prd-pilot-monitoring-and-stability.md", "Full monitoring design, decisions and acceptance criteria."),
            ("RISK_VALIDATION.md", "Detailed validation evidence and incident history."),
        ],
    }
    if not rows:
        st.info("No documents in the stage yet.")
    else:
        for heading, items in documents.items():
            st.markdown(f"**{heading}**")
            for name, description in items:
                if name not in available:
                    st.write(f"{name} — not currently available")
                    continue
                try:
                    url_row = session.sql(
                        f"SELECT GET_PRESIGNED_URL('@{STAGE}', '{name}')"
                    ).collect()
                    url = url_row[0][0]
                    st.markdown(f"- [{name}]({url}) — {description}")
                except Exception as e:
                    st.write(f"{name} — link unavailable ({e})")

st.markdown("---")

# ── Support model ────────────────────────────────────────────────────────────
with st.expander("Support model: who does what"):
    st.markdown("""
| Check / component | Owner | Escalate if not fixed today |
|---|---|---|
| C1 — source feeds | Source/feed owner (TBC — Dan chasing) | Dave |
| C2/C3/C4/C7 — alerts pipeline, output, volume, gate | Dan (C4 with Bryan) | Dave |
| C5/C6 — KPI batch and output | Elaheh | Dave |
| C9 — monitor itself | Elaheh | Dave |
| C8 — .NET API / Azure uptime | Cornelious / DevOps | Dave |
| UI / app availability | Imran / BitLogix (TBC with Engineering) | Dave |

Component owners do not contact stores directly. Store-facing messages go through the pilot contact route once confirmed.
""")

# ── Diagnostic details ───────────────────────────────────────────────────────
with st.expander("Source and gate details (C1 / C7)"):
    dq = session.sql(f"""
        SELECT RUN_DATE, SOURCE_NAME, STATUS, ACTION_TAKEN,
               ROW_COUNT, BASELINE_ROWS
        FROM {DB}.PUBLIC.DATA_QUALITY_LOG
        WHERE RUN_DATE = (SELECT MAX(RUN_DATE) FROM {DB}.PUBLIC.DATA_QUALITY_LOG)
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY SOURCE_NAME ORDER BY CREATED_AT DESC
        ) = 1
        ORDER BY SOURCE_NAME
    """).to_pandas()
    if dq.empty:
        st.info("No data quality log rows today.")
    else:
        st.dataframe(dq.reset_index(drop=True), use_container_width=True)

with st.expander("Task history (C2 / C5 / C9)"):
    tasks = session.sql(f"""
        SELECT NAME, STATE, SCHEDULED_TIME, COMPLETED_TIME, ERROR_MESSAGE
        FROM TABLE({DB}.INFORMATION_SCHEMA.TASK_HISTORY(
            SCHEDULED_TIME_RANGE_START => DATEADD('hour', -168, CURRENT_TIMESTAMP())))
        WHERE NAME IN ('RUN_ALERTS_PIPELINE_TASK', 'KPI_AVAILABILITY_BATCH_TASK',
                       'KPI_AVAILABILITY_REFRESH_TASK', 'MONITORING_TASK')
        ORDER BY SCHEDULED_TIME DESC
    """).to_pandas()
    if tasks.empty:
        st.info("No task history for the last 7 days.")
    else:
        st.dataframe(tasks.reset_index(drop=True), use_container_width=True)

# ── Glossary ─────────────────────────────────────────────────────────────────
with st.expander("What do the codes and statuses mean?"):
    st.markdown("""
| Status | Meaning |
|---|---|
| ✅ **OK** | Check passed — nothing to do. |
| ⚠️ **WARN** | Something is off but stores are not misled. Owner investigates today. |
| 🔴 **FAIL** | Stores could see wrong or missing data. Owner acts now. |
| ⚪ **UNKNOWN** | The check had no data to judge. Treat like a warning. |

Each **C-code** is one health check — its plain-English name, impact and
first response step are in the table above. Full troubleshooting steps are in
the pinned guide in #store-insight-pilot-alerts and monitoring/RUNBOOK.md.
""")
