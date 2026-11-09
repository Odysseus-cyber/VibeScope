# VibeScope API contract
Base `/api/v1`. All dates ISO, counts numeric, unavailable growth is null. History stars/forks may be null when observation is missing; coverage_days counts actually observed distinct dates, not span. JSON has no envelope unless described below. Mode `demo` or `live`.

App fields: `id` integer repository id, `name`, `full_name`, `description`, `summary`, `url`, `homepage` nullable, `category`, `tools` string[], `language` nullable, `kind` (`application`/`developer_tool`/`resource`), `evidence_level` (`explicit`/`weak`/`unknown`), `stars`, `forks`, `growth_7d`, `growth_30d`, `created_at`, `first_seen_at`, `last_observed_at`, `method` (`rules`/`llm`/`manual`/`demo`), `evidence` [{quote,url}], `manual_override` boolean.

- GET `/meta`: `{mode,as_of,last_updated,llm_enabled,categories:string[],tools:string[],languages:string[]}`.
- GET `/overview?window=7|30|90`: `{meta,kpis:{tracked,eligible,new_created,new_discovered,stars,growth_7d,classified,coverage_days,growth_7d_eligible},categories:[{name,count,percentage}],tools:[{name,count,percentage}],daily:[{date,stars,apps,growth}],leaders:App[]}`. Distribution denominator is eligible apps, tools multi-label. UTC window includes as_of and previous window-1 dates.
- GET `/apps?q=&category=&tool=&language=&kind=&evidence_level=&created_after=&sort=growth_7d|stars|newest&page=1&page_size=12&eligible_only=true`: `{items:App[],total,page,page_size,meta}`. eligible_only defaults true. Use false for review candidates.
- GET `/apps/export.csv`: same filters; returns CSV attachment.
- GET `/apps/{id}`: `{app:App,history:[{date,stars,forks,growth}],discussions:[{id,title,url,score,comments,posted_at}],classification:{method,model,prompt_version,classified_at,manual_override,evidence}}`.
- PATCH `/apps/{id}/classification`: `{category,kind,evidence_level,tools,summary,evidence:[{quote,url}]}`; returns App, retains manual override.
- GET `/trends?window=...`: same structure as overview.
- GET `/reports`: `{items:Report[]}`. Report fields `{id,title,period_start,period_end,body,method,created_at,facts,sources:[{title,url}],mode}`. body Markdown.
- GET `/reports/{id}`: Report.
- POST `/reports`: optional `{}` -> Job, status 202.
- GET `/jobs`: `{items:Job[]}`. Job `{id,kind,status,progress,processed,errors,error,created_at,started_at,finished_at,summary}`. status queued/running/succeeded/partial/failed. kind sync/github/hn/classify/warehouse/report.
- POST `/jobs`: `{kind}` -> Job status 202.
- POST `/jobs/{id}/retry`: -> new Job status 202.
- GET `/quality`: `{meta,checks:[{name,status,value,detail}],layers:[{name,rows}],coverage:[{source,observed_at,status,detail}]}`. status pass/warn/fail.
- GET `/health`: `{status,mode}`.
Errors `{detail:string}` with appropriate status.
