with clock as (
    select coalesce(max(snapshot_date), current_date)::date as as_of
    from {{ ref('dwd_snapshots') }}
)
select
    a.app_id,
    clock.as_of,
    coalesce(today.stars, a.stars)::integer as stars,
    coalesce(today.forks, a.forks)::integer as forks,
    case when today.app_id is not null and week_ago.app_id is not null
        then today.stars::bigint - week_ago.stars::bigint end as growth_7d,
    case when today.app_id is not null and month_ago.app_id is not null
        then today.stars::bigint - month_ago.stars::bigint end as growth_30d
from {{ ref('dwd_applications') }} a
cross join clock
left join {{ ref('dwd_snapshots') }} today
    on today.app_id = a.app_id and today.snapshot_date = clock.as_of
left join {{ ref('dwd_snapshots') }} week_ago
    on week_ago.app_id = a.app_id and week_ago.snapshot_date = clock.as_of - 7
left join {{ ref('dwd_snapshots') }} month_ago
    on month_ago.app_id = a.app_id and month_ago.snapshot_date = clock.as_of - 30
