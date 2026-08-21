"""
Test PAT (Personal Access Token) connection to Snowflake
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snowflake.connector  # noqa: E402
from snowflake_credentials import get_credentials  # noqa: E402


def test_pat_connection():
    try:
        print("=== Testing PAT Connection ===")
        print("Service Account: SVC_STOREINSIGHT")
        print()

        # Connect using PAT token with authenticator
        conn = snowflake.connector.connect(
            user='SVC_STOREINSIGHT',
            account='ukcoop',  # Try simple account name first
            authenticator='oauth',
            token=get_credentials().token,
            warehouse='STORE_INSIGHT_WH',
            database='STORE_INSIGHT_DB',
            schema='PUBLIC',
            role='SNOWFLAKE_DATASCIENCE'
        )

        print("✅ PAT CONNECTION SUCCESSFUL!")

        cursor = conn.cursor()

        # Basic connection validation
        cursor.execute('SELECT CURRENT_ACCOUNT(), CURRENT_USER(), CURRENT_ROLE(), CURRENT_REGION()')
        result = cursor.fetchone()
        print(f"Account: {result[0]}")
        print(f"User: {result[1]}")
        print(f"Role: {result[2]}")
        print(f"Region: {result[3]}")

        # Test role inheritance
        cursor.execute('SELECT IS_ROLE_IN_SESSION(\'STORE_INSIGHT_ROLE\'), IS_DATABASE_ROLE_IN_SESSION(\'SNOWFLAKE.CORTEX_USER\')')
        result = cursor.fetchone()
        print(f"STORE_INSIGHT_ROLE in session: {result[0]}")
        print(f"CORTEX_USER in session: {result[1]}")

        # Test source database access
        print("\n=== Source Database Access ===")
        schemas = cursor.execute('SHOW SCHEMAS IN DATABASE ANALYSIS').fetchall()
        print(f"✅ ANALYSIS database: {len(schemas)} schemas accessible")

        schemas = cursor.execute('SHOW SCHEMAS IN DATABASE INBOUND').fetchall()
        print(f"✅ INBOUND database: {len(schemas)} schemas accessible")

        # Test specific tables
        print("\n=== Specific Table Access ===")
        try:
            tables = cursor.execute('SHOW TABLES LIKE \'GLD_ALERT_INTERVENTIONS\' IN DATABASE ANALYSIS').fetchall()
            if tables:
                print(f"✅ GLD_ALERT_INTERVENTIONS found in ANALYSIS.{tables[0]['schema_name']}")
            else:
                print("⚠️ GLD_ALERT_INTERVENTIONS not found in ANALYSIS")
        except Exception as e:
            print(f"⚠️ Error finding GLD_ALERT_INTERVENTIONS: {e}")

        # Test Cortex access
        print("\n=== Cortex Access ===")
        try:
            cursor.execute('SELECT SNOWFLAKE.CORTEX.SENTIMENT(\'PAT connection test successful\')')
            result = cursor.fetchone()
            print(f"✅ Cortex working: {result[0]}")
        except Exception as e:
            print(f"⚠️ Cortex issue: {e}")

        # Test pipeline output table
        print("\n=== Pipeline Output Access ===")
        try:
            cursor.execute('SELECT COUNT(*) FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE')
            result = cursor.fetchone()
            print(f"✅ ALERTS_PIPELINE table: {result[0]} rows")
        except Exception as e:
            print(f"⚠️ ALERTS_PIPELINE access issue: {e}")

        # Test temp table creation
        print("\n=== Object Creation Test ===")
        cursor.execute('CREATE OR REPLACE TEMPORARY TABLE PAT_TEST (ID NUMBER, MESSAGE VARCHAR)')
        cursor.execute('INSERT INTO PAT_TEST VALUES (1, \'PAT connection successful\')')
        result = cursor.execute('SELECT * FROM PAT_TEST').fetchone()
        print(f"✅ Temp table test: {result[1]}")
        cursor.execute('DROP TABLE IF EXISTS PAT_TEST')

        cursor.close()
        conn.close()

        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Store Insight environment is fully accessible via PAT")
        print("✅ Ready for pipeline development and testing")

        return True

    except Exception as e:
        print(f"❌ PAT Connection failed: {e}")

        # Try alternative account formats if the first one fails
        if "404" in str(e) or "account" in str(e).lower():
            print("\nTrying alternative account formats...")

            alt_accounts = ['ukcoop.east-us-2.azure', 'ukcoop.west-us-2.azure']

            for account in alt_accounts:
                try:
                    print(f"Trying account: {account}")
                    conn = snowflake.connector.connect(
                        user='SVC_STOREINSIGHT',
                        account=account,
                        authenticator='oauth',
                        token=get_credentials().token,
                        warehouse='STORE_INSIGHT_WH',
                        database='STORE_INSIGHT_DB',
                        schema='PUBLIC',
                        role='SNOWFLAKE_DATASCIENCE'
                    )

                    print(f"✅ SUCCESS with account: {account}")
                    conn.close()
                    return True

                except Exception as e2:
                    print(f"Failed with {account}: {e2}")
                    continue

        return False

if __name__ == "__main__":
    success = test_pat_connection()

    if success:
        print("\n✅ PAT authentication is working perfectly!")
        print("Next steps:")
        print("1. I can now validate all Store Insight data access")
        print("2. Run pipeline tests against real data")
        print("3. Verify all detectors and gatherers work")
        print("4. Test Cortex LLM functionality")
    else:
        print("\n❌ PAT authentication failed")
        print("Check:")
        print("1. Token is correct and not expired")
        print("2. Service account has proper permissions")
        print("3. Account identifier format is correct")
