from store_insight.pipeline.pipeline._shared import project_attributed
from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name='osa_store_actionable_cost_projection',
    signal_types=['OSA_STORE_ACTIONABLE'],
    facts_keys=['cost_projection'],
    description='Attributed cost-of-inaction projection using latest-week run rate.',
)


def gather(signals):
    return {}


def extract_facts(signal, raw_result, projection_weeks=4):
    projected = project_attributed(signal.get('this_week_lsv') or {}, projection_weeks)
    return {
        'cost_projection': {
            'projection_weeks': projection_weeks,
            'store_controlled_cost_of_inaction': projected.get('store_controlled', 0.0),
            **projected,
        }
    }
