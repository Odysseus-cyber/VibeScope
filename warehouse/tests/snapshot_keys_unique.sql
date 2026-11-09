select app_id, snapshot_date
from {{ ref('dwd_snapshots') }}
group by app_id, snapshot_date
having count(*) > 1
