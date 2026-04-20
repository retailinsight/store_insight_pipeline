"""
Cortex usage / cost report.

Queries ``SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY`` and prints a
summary of Cortex LLM token spend over a rolling window.

Usage
-----
    python -m store_insight.alerts.monitoring.cortex_usage            # last 7 days
    python -m store_insight.alerts.monitoring.cortex_usage --days 30
    python -m store_insight.alerts.monitoring.cortex_usage --days 7 --credit-price 3.0

Notes
-----
* ``ACCOUNT_USAGE`` views require a role with the relevant grants (typically
  ACCOUNTADMIN, or a custom role granted ``IMPORTED PRIVILEGES`` on the
  SNOWFLAKE database).  If your default role cannot see the view, override
  via the ``SNOWFLAKE_ROLE`` env var before running.
* ``ACCOUNT_USAGE`` has a 45-minute to 2-hour latency.
"""

from __future__ import annotations

import argparse

from store_insight.api.app.snowflake_session import get_session


_SQL = """
SELECT
    function_name,
    model_name,
    SUM(tokens)        AS total_tokens,
    SUM(token_credits) AS total_credits,
    COUNT(*)           AS calls
FROM   snowflake.account_usage.cortex_functions_usage_history
WHERE  start_time >= DATEADD('day', -{days}, CURRENT_TIMESTAMP())
GROUP  BY 1, 2
ORDER  BY total_credits DESC
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Report Snowflake Cortex usage.")
    parser.add_argument('--days', type=int, default=7, help='Lookback window in days (default: 7).')
    parser.add_argument(
        '--credit-price', type=float, default=3.0,
        help='USD per Snowflake credit for rough cost estimate (default: 3.0).',
    )
    args = parser.parse_args()

    session = get_session()
    rows = session.sql(_SQL.format(days=args.days)).collect()

    if not rows:
        print(f"No Cortex usage in the last {args.days} day(s).")
        return

    header = f"Cortex usage — last {args.days} day(s)   (credit price = ${args.credit_price:.2f})"
    print(header)
    print('=' * len(header))
    fmt = "{function:<18} {model:<28} {calls:>8} {tokens:>14} {credits:>12} {usd:>12}"
    print(fmt.format(
        function='FUNCTION', model='MODEL', calls='CALLS',
        tokens='TOKENS', credits='CREDITS', usd='EST USD',
    ))
    print('-' * len(header))

    total_credits = 0.0
    total_tokens  = 0
    total_calls   = 0
    for r in rows:
        credits = float(r['TOTAL_CREDITS'] or 0)
        tokens  = int(r['TOTAL_TOKENS'] or 0)
        calls   = int(r['CALLS'] or 0)
        total_credits += credits
        total_tokens  += tokens
        total_calls   += calls
        print(fmt.format(
            function=str(r['FUNCTION_NAME'])[:18],
            model=str(r['MODEL_NAME'])[:28],
            calls=f"{calls:,}",
            tokens=f"{tokens:,}",
            credits=f"{credits:,.4f}",
            usd=f"${credits * args.credit_price:,.2f}",
        ))

    print('-' * len(header))
    print(fmt.format(
        function='TOTAL', model='',
        calls=f"{total_calls:,}",
        tokens=f"{total_tokens:,}",
        credits=f"{total_credits:,.4f}",
        usd=f"${total_credits * args.credit_price:,.2f}",
    ))


if __name__ == '__main__':
    main()
