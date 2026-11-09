select snapshot_date
from {{ ref('dws_daily_metrics') }}
where growth is not null
  and (expected_apps = 0 or growth_eligible_apps <> expected_apps or apps <> expected_apps)
