select
    id as discussion_id,
    app_id,
    title,
    url,
    score,
    comments,
    posted_at,
    observed_at
from {{ source('operational', 'discussions') }}
