select metrics.app_id
from {{ ref('ads_app_metrics') }} metrics
left join {{ ref('dwd_snapshots') }} current_day
    on current_day.app_id = metrics.app_id and current_day.snapshot_date = metrics.as_of
left join {{ ref('dwd_snapshots') }} week_ago
    on week_ago.app_id = metrics.app_id and week_ago.snapshot_date = metrics.as_of - 7
left join {{ ref('dwd_snapshots') }} month_ago
    on month_ago.app_id = metrics.app_id and month_ago.snapshot_date = metrics.as_of - 30
where (metrics.growth_7d is not null and (current_day.app_id is null or week_ago.app_id is null))
   or (metrics.growth_30d is not null and (current_day.app_id is null or month_ago.app_id is null))
   or (current_day.app_id is not null and week_ago.app_id is not null
       and metrics.growth_7d is distinct from current_day.stars::bigint - week_ago.stars::bigint)
   or (current_day.app_id is not null and month_ago.app_id is not null
       and metrics.growth_30d is distinct from current_day.stars::bigint - month_ago.stars::bigint)
