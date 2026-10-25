"""Fill article code and numerical statements from actual analysis outputs."""
from pathlib import Path
import json
import re
import textwrap

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    lesson=(ROOT/'code/tutorial.py').read_text(encoding='utf-8')
    text=(ROOT/'code/article_template.txt').read_text(encoding='utf-8')
    summary=json.loads((ROOT/'results/analysis_summary.json').read_text())
    estimates=pd.read_csv(ROOT/'results/ige_estimates.csv').set_index(['parent','stage','measure'])
    values={name.upper():f'{summary[name]:,}' for name in
            ['input_individuals','children','mothers','fathers','kinship_clusters']}
    for role in ['mother','father']:
        for stage in ['early','later']:
            for measure in ['single','average']:
                values[f'{role}_{stage}_{measure}'.upper()]=f'{estimates.loc[(role,stage,measure),"ige"]:.3f}'
        change=summary['age_change_average'][role]
        values[f'{role}_AGE_CHANGE'.upper()]=f"{change['later_minus_early']:+.3f}"
        values[f'{role}_AGE_CI'.upper()]=f"[{change['ci'][0]:.3f}, {change['ci'][1]:.3f}]"
    for name in ['match','summarize','sample','estimate']:
        block=re.search(rf'^ *# BEGIN {name}\n(.*?)^ *# END {name}',lesson,flags=re.M|re.S)
        assert block,name
        values[name.upper()]=textwrap.dedent(block.group(1)).strip()
    for key,value in values.items():
        text=text.replace('{{'+key+'}}',value)
    assert not re.search(r'\{\{[A-Z_]+\}\}',text)
    (ROOT/'blog6.qmd').write_text(text,encoding='utf-8')
    prose=re.sub(r'```.*?```','',text,flags=re.S)
    prose=re.sub(r'^---.*?---','',prose,count=1,flags=re.S)
    prose=re.sub(r'\$\$.*?\$\$','',prose,flags=re.S)
    print('Approximate article prose/labels word count:',len(re.findall(r"\b[\w'-]+\b",prose)))


if __name__=='__main__':
    main()
