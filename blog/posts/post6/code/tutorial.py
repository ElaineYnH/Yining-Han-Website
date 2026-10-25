"""SQL/Python lesson and aggregate-only publication outputs from PSID."""
from pathlib import Path
import json
import platform
import sqlite3

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def load_tables(work_dir):
    database = Path(work_dir) / 'psid.sqlite'
    if not database.exists():
        raise FileNotFoundError('Run code/run_analysis.py with your downloaded ZIP first.')
    return sqlite3.connect(database)


def match_families(con):
    # BEGIN match
    links = pd.read_sql_query('''
    WITH parent_keys AS (
      SELECT id68 AS child_family, pn AS child_pn,
             mother_id68 AS parent_family, mother_pn AS parent_pn,
             'mother' AS parent_role FROM people
      UNION ALL
      SELECT id68, pn, father_id68, father_pn, 'father' FROM people
    )
    SELECT k.child_family * 1000 + k.child_pn AS child_id,
           p.id68 * 1000 + p.pn AS parent_id,
           k.child_family AS family_id, k.parent_role
    FROM parent_keys AS k
    JOIN people AS p ON k.parent_family = p.id68 AND k.parent_pn = p.pn
    WHERE k.parent_family > 0 AND k.parent_pn BETWEEN 1 AND 399
    ORDER BY child_id, parent_role
    ''', con)
    assert not links.duplicated(['child_id', 'parent_role']).any()
    # END match
    return links


# BEGIN summarize
def summarize(con, lo, hi, target):
    averages = pd.read_sql_query('''
    SELECT id68 * 1000 + pn AS person_id,
           AVG(income) AS average, COUNT(*) AS n_years
    FROM earnings WHERE age BETWEEN ? AND ?
    GROUP BY id68, pn HAVING COUNT(*) >= 3
    ''', con, params=(lo, hi))
    rows = pd.read_sql_query('''
    SELECT id68 * 1000 + pn AS person_id, year, age, income
    FROM earnings WHERE age BETWEEN ? AND ?
    ''', con, params=(lo, hi))
    rows['distance'] = abs(rows.age - target)
    anchors = (rows.sort_values(['distance', 'year']).drop_duplicates('person_id')
               .rename(columns={'income': 'single'}))
    return averages.merge(anchors[['person_id', 'single']], on='person_id')
# END summarize


def build_sample(con, links):
    # BEGIN sample
    sample = links.copy()
    specs = [(35, 44, 40, 'p', 'parent_id'),
             (20, 29, 25, 'early', 'child_id'),
             (30, 39, 35, 'later', 'child_id')]
    for lo, hi, target, label, key in specs:
        measures = summarize(con, lo, hi, target).rename(columns={
            'person_id': key, 'average': f'{label}_average',
            'single': f'{label}_single', 'n_years': f'{label}_n'})
        sample = sample.merge(measures, on=key, validate='many_to_one')
    columns = [f'{g}_{m}' for g in ['p', 'early', 'later']
               for m in ['single', 'average']]
    sample = sample.loc[sample[columns].gt(0).all(axis=1)].copy()
    both = sample.groupby('child_id').parent_role.nunique().eq(2)
    sample = sample.loc[sample.child_id.isin(both[both].index)].copy()
    # END sample
    return sample


def estimate(sample):
    # BEGIN estimate
    estimates = []
    for role in ['mother', 'father']:
        d = sample.loc[sample.parent_role == role]
        for stage in ['early', 'later']:
            for measure in ['single', 'average']:
                x = np.log(d[f'p_{measure}'])
                y = np.log(d[f'{stage}_{measure}'])
                beta, intercept = np.polyfit(x, y, 1)
                estimates.append(dict(parent=role, stage=stage, measure=measure,
                                      ige=beta, n_children=len(d)))
    estimates = pd.DataFrame(estimates)
    print(estimates.round(3).to_string(index=False))
    # END estimate
    return estimates


def kinship_clusters(sample):
    """Keep shared people and original family lineages together, including both parents."""
    roots = {}

    def root(x):
        roots.setdefault(x, x)
        while roots[x] != x:
            roots[x] = roots[roots[x]]
            x = roots[x]
        return x

    def union(a, b):
        ra, rb = root(a), root(b)
        if ra != rb:
            roots[rb] = ra

    for r in sample.itertuples():
        child, parent = ('p', r.child_id), ('p', r.parent_id)
        union(child, parent)
        union(child, ('f', r.family_id))
        union(parent, ('f', r.parent_id // 1000))
    return pd.Series([str(root(('p', c))) for c in sample.child_id], index=sample.index)


def family_bootstrap(sample, estimates, draws=2000, seed=20261026):
    sample = sample.copy()
    sample['cluster'] = kinship_clusters(sample)
    clusters = sorted(sample.cluster.unique())
    index = {c:i for i,c in enumerate(clusters)}
    g = len(clusters)
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(g, np.full(g, 1/g), size=draws)
    boot = []
    for r in estimates.itertuples():
        d = sample.loc[sample.parent_role == r.parent]
        inverse = d.cluster.map(index).to_numpy()
        x, y = np.log(d[f'p_{r.measure}']), np.log(d[f'{r.stage}_{r.measure}'])
        moments = np.column_stack([np.bincount(inverse, weights=z, minlength=g)
                                   for z in [np.ones(len(d)), x, y, x*x, x*y]])
        n, sx, sy, sxx, sxy = (counts @ moments).T
        slopes = (sxy-sx*sy/n)/(sxx-sx*sx/n)
        if not np.isfinite(slopes).all():
            raise ValueError('Degenerate bootstrap draw; inspect sample/cluster coverage.')
        boot.append(slopes)
    boot = np.column_stack(boot)
    estimates = estimates.copy()
    estimates['ci_low'], estimates['ci_high'] = np.quantile(boot,[.025,.975],axis=0)
    return estimates, boot, sample


def plot_results(estimates):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,
                         'axes.spines.top':False,'axes.spines.right':False})
    # Stack panels so labels remain readable on a phone.
    fig, axes = plt.subplots(2, 1, figsize=(8, 8), sharex=True, sharey=True,
                             constrained_layout=True)
    colors = {'single':'#B35D45','average':'#287F8E'}
    for ax, role in zip(axes,['mother','father']):
        for j, measure in enumerate(['single','average']):
            d = estimates.loc[(estimates.parent==role)&(estimates.measure==measure)]
            d = d.set_index('stage').loc[['early','later']]
            x = np.array([0.,1.]) + (-.12 if j==0 else .12)
            ax.errorbar(x,d.ige,yerr=[d.ige-d.ci_low,d.ci_high-d.ige],fmt='o',
                        color=colors[measure],markersize=8,linewidth=2,capsize=4,
                        label='One observed year' if j==0 else 'Mean of 3+ observed years')
            for xx, val in zip(x,d.ige):
                ax.annotate(f'{val:.3f}',(xx,val),xytext=(-12 if j==0 else 12,8),
                            textcoords='offset points',ha='right' if j==0 else 'left',
                            color=colors[measure],fontweight='bold')
        ax.axhline(0,color='#9CA3A5',linewidth=1)
        ax.grid(axis='y',alpha=.2)
        ax.set_axisbelow(True)
        ax.set_ylabel('Intergenerational elasticity (IGE)')
        ax.set_title(f'{role.capitalize()} and child',loc='left',fontweight='bold',fontsize=14)
        ax.tick_params(labelbottom=True)
    axes[0].legend(loc='upper left',frameon=False,ncol=2,fontsize=10)
    axes[-1].set_xticks([0,1],['Child income at ages 20–29','Child income at ages 30–39'])
    axes[-1].set_xlim(-.48,1.48)
    axes[-1].set_ylim(min(0,estimates.ci_low.min()-.065),estimates.ci_high.max()+.16)
    fig.suptitle('The same children, different income windows',fontsize=16,fontweight='bold')
    (ROOT/'results/figures').mkdir(parents=True,exist_ok=True)
    fig.savefig(ROOT/'results/figures/income_timing.png',dpi=180)
    plt.close(fig)


def run(work_dir, audit):
    out = ROOT/'results'
    out.mkdir(exist_ok=True)
    con = load_tables(work_dir)
    links = match_families(con)
    sample = build_sample(con,links)
    assert len(sample) > 0
    assert sample.groupby('child_id').size().eq(2).all()
    assert sample[['p_n','early_n','later_n']].ge(3).all().all()
    estimates,boot,sample = family_bootstrap(sample,estimate(sample))
    # This file is deliberately private. Only aggregate statistics go into results/.
    sample.to_csv(Path(work_dir)/'matched_incomes.csv',index=False,float_format='%.10g')
    estimates.to_csv(out/'ige_estimates.csv',index=False,float_format='%.10g')
    flow = []
    a = links.copy()
    def add_flow(label, d):
        flow.append(dict(step=label,children=int(d.child_id.nunique()),
                         mother_links=int(d.parent_role.eq('mother').sum()),
                         father_links=int(d.parent_role.eq('father').sum())))
    add_flow('Documented parent-child links with parent in individual file',a)
    for lo,hi,target,label,key in [(35,44,40,'Parent ages 35-44','parent_id'),
                                  (20,29,25,'Add child ages 20-29','child_id'),
                                  (30,39,35,'Add child ages 30-39','child_id')]:
        d=summarize(con,lo,hi,target)
        a=a.merge(d[['person_id']].rename(columns={'person_id':key}),on=key,validate='many_to_one')
        add_flow(label+'; at least 3 observed amounts',a)
    add_flow('All log inputs positive; both parents; common children',sample)
    pd.DataFrame(flow).to_csv(out/'sample_flow.csv',index=False)
    pd.DataFrame(audit['waves']).to_csv(out/'preparation_counts.csv',index=False)
    by=pd.read_sql_query('SELECT id68*1000+pn AS person_id,birth_year FROM people',con).set_index('person_id').birth_year
    births=by.loc[sample.child_id.unique()]
    differences={}
    for role in ['mother','father']:
        idx1=estimates.index[(estimates.parent==role)&(estimates.stage=='early')&(estimates.measure=='average')][0]
        idx2=estimates.index[(estimates.parent==role)&(estimates.stage=='later')&(estimates.measure=='average')][0]
        differences[role]=dict(later_minus_early=float(estimates.loc[idx2,'ige']-estimates.loc[idx1,'ige']),
                               ci=np.quantile(boot[:,idx2]-boot[:,idx1],[.025,.975]).tolist())
    summary=dict(children=int(sample.child_id.nunique()),parent_child_pairs=len(sample),
                 mothers=int(sample.loc[sample.parent_role=='mother','parent_id'].nunique()),
                 fathers=int(sample.loc[sample.parent_role=='father','parent_id'].nunique()),
                 original_child_families=int(sample.family_id.nunique()),kinship_clusters=int(sample.cluster.nunique()),
                 largest_cluster_children=int(sample.drop_duplicates('child_id').groupby('cluster').size().max()),
                 child_birth_min=int(births.min()),child_birth_max=int(births.max()),
                 income_years=audit['income_years'],input_individuals=audit['individuals'],
                 income_records=audit['income_records'],zero_income_records=audit['zero_income_records'],
                 observation_counts={k:[int(sample[k].min()),int(sample[k].max())]
                                     for k in ['p_n','early_n','later_n']},
                 age_change_average=differences,bootstrap_draws=2000,bootstrap_seed=20261026,
                 source_extract_sha256=audit['extract_sha256'])
    (out/'analysis_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (out/'sessionInfo.txt').write_text(
        f'Python {platform.python_version()}\nNumPy {np.__version__}\npandas {pd.__version__}\n'
        f'Matplotlib {matplotlib.__version__}\nSQLite {sqlite3.sqlite_version}\n')
    plot_results(estimates)
    con.close()
    print(estimates.to_string(index=False))
    print(json.dumps(summary,indent=2))
    return summary
