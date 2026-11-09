with eligible as (
    select app_id, category from {{ ref('dwd_applications') }} where is_eligible
), totals as (
    select count(*) as total from eligible
)
select
    eligible.category,
    count(*)::bigint as count,
    round(100.0 * count(*) / nullif(totals.total, 0), 2) as percentage
from eligible
cross join totals
group by eligible.category, totals.total
