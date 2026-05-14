"""
Snowflake Session Factory
==========================
Creates a Snowpark session from a combination of config values and
environment variables.

Preferred usage (with config system)
------------------------------------
    from store_insight.pipeline.config.loader import load_config
    from store_insight.pipeline.pipeline.session import create_session

    cfg     = load_config('eastofengland')   # loads .env + merges YAML
    session = create_session(cfg)

Legacy usage (env vars only)
----------------------------
    from store_insight.pipeline.pipeline.session import load_env, create_session

    load_env()            # reads alerts/.env into os.environ
    session = create_session()

Resolution order for each connection param:
    1. ``cfg.connection.key``  (if a config is passed)
    2. ``os.environ['SNOWFLAKE_<KEY>']``

Secrets (account, user, password) always come from environment variables,
which are loaded from the client's ``.env`` by ``config.loader``.
"""

import os


def load_env(env_path=None):
    """
    Load environment variables from a .env file.

    Parameters
    ----------
    env_path : str | None — path to .env file; defaults to store_insight/pipeline/.env
               (one level above this module's directory)
    """
    if env_path is None:
        here     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(here, '.env')

    if not os.path.exists(env_path):
        raise FileNotFoundError(f'.env file not found: {env_path}')

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                os.environ.setdefault(key.strip(), val.strip())


def create_session(cfg=None):
    """
    Create and return a Snowpark Session.

    Parameters
    ----------
    cfg : PipelineConfig or None
        Merged config from ``config.loader.load_config``.  If provided,
        non-secret connection params (warehouse, database, schema, role) are
        read from ``cfg.connection`` with env-var fallback.  Secrets
        (account, user, password) always come from env vars.

    Returns
    -------
    snowflake.snowpark.Session
    """
    from snowflake.snowpark import Session

    conn = cfg.connection if cfg else {}

    password = os.environ.get('SNOWFLAKE_PASSWORD')

    params = {
        'account':   os.environ['SNOWFLAKE_ACCOUNT'],
        'user':      os.environ['SNOWFLAKE_USER'],
        'role':      conn.role or os.environ.get('SNOWFLAKE_ROLE'),
        'warehouse': conn.warehouse or os.environ.get('SNOWFLAKE_WAREHOUSE'),
        'database':  conn.database or os.environ.get('SNOWFLAKE_DATABASE'),
        'schema':    conn.schema_name or os.environ.get('SNOWFLAKE_SCHEMA'),
    }

    if password:
        params['password'] = password
    else:
        params['authenticator'] = 'externalbrowser'

    session = Session.builder.configs(params).create()

    warehouse = params.get('warehouse')
    if warehouse:
        session.use_warehouse(warehouse)

    print('Snowflake session created.')
    return session
