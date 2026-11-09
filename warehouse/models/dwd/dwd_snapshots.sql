select
    id as snapshot_id,
    app_id,
    snapshot_date::date as snapshot_date,
    stars,
    forks,
    observed_at
from {{ source('operational', 'snapshots') }}
