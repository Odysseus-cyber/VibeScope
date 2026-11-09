select app_id, snapshot_date
from {{ ref('dwd_snapshots') }}
where stars < 0 or forks < 0 or stars is null or forks is null
