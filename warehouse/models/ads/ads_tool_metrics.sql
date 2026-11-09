with eligible as (
    select app_id, tools from {{ ref('dwd_applications') }} where is_eligible
), expanded as (
    select distinct
        e.app_id,
        coalesce(nullif(trim(t.tool), ''), '未知') as tool
    from eligible e
    left join lateral jsonb_array_elements_text(e.tools) as t(tool) on true
), totals as (
    select count(*) as total from eligible
)
select
    expanded.tool,
    count(*)::bigint as count,
    round(100.0 * count(*) / nullif(totals.total, 0), 2) as percentage
from expanded
cross join totals
group by expanded.tool, totals.total
