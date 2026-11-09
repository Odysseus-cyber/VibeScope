"""Recalculate review metrics from the saved real-source prediction snapshot.

This does not re-fetch mutable repositories or call a model API. The snapshot
records predictions on fetched README data; short source excerpts are included
for traceability. See dataset review_method for bias and labeling limitations.
"""
import json
from pathlib import Path

folder = Path(__file__).parent
source = json.loads((folder / 'real-agent-cases.json').read_text())
rows = source['cases']

def score(key):
    n = len(rows)
    correct_kind = sum(row[key]['kind'] == row['expected']['kind'] for row in rows)
    correct_confirmed = sum(row[key]['ai_development_confirmed'] == row['expected']['ai_development_confirmed'] for row in rows)
    tp = sum(row[key]['ai_development_confirmed'] and row['expected']['ai_development_confirmed'] for row in rows)
    fp = sum(row[key]['ai_development_confirmed'] and not row['expected']['ai_development_confirmed'] for row in rows)
    fn = sum(not row[key]['ai_development_confirmed'] and row['expected']['ai_development_confirmed'] for row in rows)
    return {'sample_count': n, 'kind_accuracy': round(correct_kind/n,4), 'author_claim_accuracy': round(correct_confirmed/n,4), 'explicit_precision': round(tp/(tp+fp),4) if tp+fp else None, 'explicit_recall': round(tp/(tp+fn),4) if tp+fn else None, 'confusion_counts': {'tp':tp,'fp':fp,'fn':fn,'tn':n-tp-fp-fn}}

result={'dataset_type':source['dataset_type'],'review_status':'agent_reviewed; human review pending','sampling_policy':source['sampling_policy'],'limitations':source['review_method'],'before_refinement':score('prediction_before_review'),'current_rule_snapshot':score('prediction'),'kind_errors':[{'repository':r['repository'],'expected':r['expected']['kind'],'actual':r['prediction']['kind']} for r in rows if r['expected']['kind']!=r['prediction']['kind']]}
(folder/'real-agent-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
