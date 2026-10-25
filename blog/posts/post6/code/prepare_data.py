"""Read a user's PSID extract locally; write individual records outside the repo."""
from pathlib import Path
import hashlib
import io
import json
import re
import sqlite3
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def validate_work_dir(work_dir):
    work_dir = Path(work_dir).expanduser().resolve()
    protected = [ROOT]
    protected.extend(p for p in ROOT.parents
                     if (p / '_quarto.yml').exists() or (p / '_quarto.yaml').exists())
    if any(work_dir == p or p in work_dir.parents for p in protected):
        raise ValueError('Choose --work-dir outside the website repository.')
    return work_dir


def read_extract(input_zip, manifest):
    with zipfile.ZipFile(input_zip) as archive:
        candidates = [n for n in archive.namelist()
                      if n.lower().endswith('.do') and not n.lower().endswith('_formats.do')]
        if len(candidates) != 1:
            raise ValueError('Expected one Stata import .do file in the extract ZIP.')
        do_name = candidates[0]
        text = archive.read(do_name).decode('utf-8-sig')
        infix = text.split('infix', 1)[1].split('using', 1)[0]
        layout = [(v, int(a)-1, int(b))
                  for v, a, b in re.findall(r'(ER\d+)\s+(\d+)\s*-\s*(\d+)', infix)]
        columns = {v: (a, b) for v, a, b in layout}
        required = manifest['required_variables']
        missing = sorted(set(required) - set(columns))
        if missing:
            raise ValueError(f'Extract is missing required variables: {missing}')
        data_names = [n for n in archive.namelist()
                      if Path(n).name.lower() == Path(do_name).with_suffix('.txt').name.lower()]
        if len(data_names) != 1:
            raise ValueError('Could not identify the fixed-width data file.')
        raw = pd.read_fwf(io.BytesIO(archive.read(data_names[0])),
                          colspecs=[columns[v] for v in required], names=required,
                          header=None, dtype='float64')
    if raw[['ER30001', 'ER30002']].duplicated().any():
        raise ValueError('Individual identifiers are not unique.')
    if raw[['ER30001', 'ER30002']].isna().any().any():
        raise ValueError('Missing individual identifiers.')
    return raw, hashlib.sha256(Path(input_zip).read_bytes()).hexdigest()


def prepare(input_zip, work_dir):
    work_dir = validate_work_dir(work_dir)
    # Publishing the Quarto folder must never accidentally include microdata.
    work_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'data/variable_manifest.json').read_text())
    raw, digest = read_extract(input_zip, manifest)
    # Later waves incorporate corrections. Take the latest valid reported birth year.
    birth_vars = [w['birth_year'] for w in reversed(manifest['waves'])]
    by = raw[birth_vars].where(raw[birth_vars].ge(1870) & raw[birth_vars].le(2023))
    birth_year = by.bfill(axis=1).iloc[:, 0]
    people = pd.DataFrame({
        'id68': raw.ER30001.astype(int), 'pn': raw.ER30002.astype(int),
        'sex': raw.ER32000.astype(int), 'birth_year': birth_year,
        'mother_id68': raw.ER32009.astype(int), 'mother_pn': raw.ER32010.astype(int),
        'father_id68': raw.ER32016.astype(int), 'father_pn': raw.ER32017.astype(int)})
    cpi = pd.read_csv(ROOT / 'data/cpi.csv').set_index('year').cpi
    observations = []
    audits = []
    for w in manifest['waves']:
        reference = raw[w['sequence']].eq(1) & raw[w['relationship']].eq(10)
        spouse = raw[w['sequence']].eq(2) & raw[w['relationship']].isin([20, 22])
        responding = raw[w['interview_id']].gt(0)
        eligible = (reference | spouse) & responding
        nominal = pd.Series(np.nan, index=raw.index)
        source = pd.Series('', index=raw.index)
        for mask, variable, ceiling, role in [
            (reference, w['reference_income'], w['reference_max_valid'], 'reference'),
            (spouse, w['spouse_income'], w['spouse_max_valid'], 'spouse')]:
            amount = raw[variable]
            valid = mask & responding & amount.between(0, ceiling)
            nominal.loc[valid] = amount.loc[valid]
            source.loc[valid] = role
        d = people[['id68', 'pn', 'birth_year']].copy()
        d['year'] = w['income_year']
        d['age'] = d.year - d.birth_year
        d['nominal_income'] = nominal
        d['income'] = nominal * float(cpi.loc[2020]) / float(cpi.loc[w['income_year']])
        d['survey_role'] = source
        d = d.loc[d.income.notna() & d.birth_year.notna()].copy()
        observations.append(d)
        audits.append({'survey_year': w['survey_year'], 'income_year': w['income_year'],
                       'eligible_reference_or_spouse': int(eligible.sum()),
                       'valid_income_and_birth_year': len(d),
                       'zero_income_observations': int(d.income.eq(0).sum()),
                       'invalid_income_codes_excluded': int((eligible & nominal.isna()).sum())})
    earnings = pd.concat(observations, ignore_index=True)
    earnings['age'] = earnings.age.astype(int)
    assert not earnings.duplicated(['id68', 'pn', 'year']).any()
    assert earnings.income.ge(0).all()
    database = work_dir / 'psid.sqlite'
    with sqlite3.connect(database) as con:
        people.to_sql('people', con, index=False, if_exists='replace')
        earnings.to_sql('earnings', con, index=False, if_exists='replace')
        con.execute('CREATE UNIQUE INDEX people_id ON people(id68,pn)')
        con.execute('CREATE UNIQUE INDEX earnings_id ON earnings(id68,pn,year)')
    audit = {
        'extract_sha256': digest, 'individuals': len(people),
        'income_records': len(earnings), 'zero_income_records': int(earnings.income.eq(0).sum()),
        'birth_year_disagreement_across_waves': int(by.nunique(axis=1).gt(1).sum()),
        'income_years': [int(earnings.year.min()), int(earnings.year.max())],
        'cpi_base_year': 2020, 'waves': audits}
    (work_dir / 'preparation_audit.json').write_text(json.dumps(audit, indent=2)+'\n')
    return database, audit
