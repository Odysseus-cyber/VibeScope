with eligible as (
    select app_id from {{ ref('dwd_applications') }} where is_eligible
), eligible_count as (
    select count(*)::bigint as expected_apps from eligible
), observed as (
    select s.*
    from {{ ref('dwd_snapshots') }} s
    inner join eligible e on e.app_id = s.app_id
), daily as (
    select
        snapshot_date,
        sum(stars)::bigint as stars,
        count(*)::bigint as apps
    from observed
    group by snapshot_date
), pairs as (
    select
        current_day.snapshot_date,
        count(*)::bigint as growth_eligible_apps,
        sum(current_day.stars::bigint - previous_day.stars::bigint)::bigint as matched_growth
    from observed current_day
    inner join observed previous_day
        on current_day.app_id = previous_day.app_id
        and previous_day.snapshot_date = current_day.snapshot_date - 1
    group by current_day.snapshot_date
)
select
    daily.snapshot_date,
    daily.stars,
    daily.apps,
    eligible_count.expected_apps,
    coalesce(pairs.growth_eligible_apps, 0)::bigint as growth_eligible_apps,
    case
        when eligible_count.expected_apps > 0
          and pairs.growth_eligible_apps = eligible_count.expected_apps
        then pairs.matched_growth
        else null
    end::bigint as growth,
    round(daily.apps::numeric / nullif(eligible_count.expected_apps, 0), 4) as coverage_ratio
from daily
cross join eligible_count
left join pairs on daily.snapshot_date = pairs.snapshot_date
