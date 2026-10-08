"""Link adjacent monthly CPS files and audit eligibility/attrition.
Usage: python build_panel.py --cps-dir PATH --crosswalk PATH
Inputs read-only; writes only to --out (default: script directory).
"""
import argparse, hashlib, json, re, zipfile
from collections import defaultdict
from pathlib import Path
import pandas as pd
from bls_thresholds import THRESHOLDS

MONTHS = 'jan feb mar apr may jun jul aug sep oct nov dec'.split()
FIELDS = {'mis':(63,64),'age':(122,123),'sex':(129,130),'edu':(137,138),
          'cit':(172,173),'mlr':(180,181),'duration':(407,409),
          'weight':(613,622),'occ':(860,863)}

def iv(row,a,b):
    try: return int(row[a-1:b])
    except ValueError: return -999

def crosswalk(path,out):
    a=pd.read_excel(path,sheet_name='2018 Census Occ Code List',header=None)
    specs={int(r[2]):str(r[3]).strip() for _,r in a.iterrows() if re.fullmatch(r'\d{4}',str(r[2]))}
    titles={int(r[2]):str(r[1]).strip() for _,r in a.iterrows() if re.fullmatch(r'\d{4}',str(r[2]))}
    def expand(spec):
        if spec in THRESHOLDS: return {spec}
        if re.fullmatch(r'\d{2}-\d{4}',spec):
            # BLS sometimes publishes a combined group, e.g. 13-1020.
            for n in (1,2,3,4):
                parent=spec[:-n]+'0'*n
                if parent in THRESHOLDS: return {parent}
            prefix=spec.rstrip('0')
            return {s for s in THRESHOLDS if s.startswith(prefix)} if spec.endswith('0') else set()
        if 'X' in spec: return {s for s in THRESHOLDS if re.fullmatch(spec.replace('X','[0-9]'),s)}
        return set()
    sets={k:expand(s) for k,s in specs.items()}
    # Census uses X in residual groups. Remove occupations separately coded
    # elsewhere; never apply an unrestricted broad-SOC-major-group shortcut.
    precise=set().union(*(sets[k] for k,s in specs.items() if 'X' not in s))
    for k,s in specs.items():
        if 'X' in s: sets[k] -= precise
    new={k:{THRESHOLDS[s] for s in socs} for k,socs in sets.items()}
    old_links=defaultdict(set)
    b=pd.read_excel(path,sheet_name='2010 to 2018 Crosswalk ',header=None)
    old=None
    for _,r in b.iterrows():
        if re.fullmatch(r'\d{4}',str(r[1])): old=int(r[1])
        if old is not None and re.fullmatch(r'\d{4}',str(r[4])): old_links[old].add(int(r[4]))
    old_sets={k:set().union(*(new.get(n,set()) for n in dest)) for k,dest in old_links.items()}
    # If any destination is unresolved, do not infer unanimity from the others.
    for k,dest in old_links.items():
        if any(not new.get(n) for n in dest): old_sets[k]=set()
    rows=[]
    for vintage,mapping in [(2018,new),(2010,old_sets)]:
        for k,v in mapping.items():
            rows.append({'census_vintage':vintage,'census_code':k,
                         'below_ba':next(iter(v)) if len(v)==1 else None,
                         'status':'resolved' if len(v)==1 else ('mixed' if len(v)>1 else 'unmapped'),
                         'soc_codes':';'.join(sorted(sets.get(k,()))) if vintage==2018 else '',
                         'destination_2018_codes':';'.join(map(str,sorted(old_links[k]))) if vintage==2010 else '',
                         'title':titles.get(k,'') if vintage==2018 else ''})
    pd.DataFrame(rows).to_csv(out/'occupation_crosswalk.csv',index=False)
    return {2018:new,2010:old_sets}

def parse(path):
    records={}; duplicates=set()
    with zipfile.ZipFile(path) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.dat')]
        assert len(names)==1,(path,names)
        with z.open(names[0]) as f:
            for row in f:
                age=iv(row,122,123)
                if not 24<=age<=65: continue
                key=(row[:15],row[70:75],row[146:148])
                if key in records: duplicates.add(key)
                rec={k:iv(row,*pos) for k,pos in FIELDS.items()}
                records[key]=rec
    for k in duplicates: records.pop(k,None)
    return records,len(duplicates)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--cps-dir',type=Path,required=True)
    ap.add_argument('--crosswalk',type=Path,required=True); ap.add_argument('--out',type=Path,default=Path(__file__).parent)
    args=ap.parse_args(); out=args.out; out.mkdir(exist_ok=True,parents=True)
    maps=crosswalk(args.crosswalk,out); rows=[]; prev=None; prev_period=None; manifest=[]; missing=[]
    for y in range(2011,2026):
        for m,month in enumerate(MONTHS,1):
            p=args.cps_dir/f'{month}{y%100:02d}pub.zip'; period=f'{y}-{m:02d}'
            if not p.exists(): missing.append(period); prev=None; continue
            cur,dup=parse(p)
            with zipfile.ZipFile(p) as z:
                entries=[{'name':n.filename,'size':n.file_size,'crc':n.CRC} for n in z.infolist()]
            manifest.append({'period':period,'file':p.name,'bytes':p.stat().st_size,'zip_entries':entries,'duplicate_keys':dup})
            if prev is not None:
                py,pm=prev_period
                for key,a in prev.items():
                    if not (25<=a['age']<=64 and a['edu'] in (43,44,45,46) and a['cit'] in (1,4,5)
                            and a['mlr']==4 and 0<=a['duration']<=999 and a['weight']>0): continue
                    b=cur.get(key); eligible=a['mis'] in (1,2,3,5,6,7)
                    linked=bool(eligible and b and b['mis']==a['mis']+1 and b['sex']==a['sex']
                                and a['age']<=b['age']<=a['age']+1 and b['cit'] in (1,4,5)
                                and (b['cit']==1)==(a['cit']==1) and b['mlr'] in range(1,8))
                    person_hash=hashlib.sha256(b'|'.join(key)).hexdigest()[:24]
                    rec={'person':person_hash,'month':f'{py}-{pm:02d}','next_month':period,'year':py,'month_num':pm,
                         'foreign':int(a['cit'] in (4,5)),'age':a['age'],'sex':a['sex'],'edu':a['edu'],
                         'duration':a['duration'],'weight':a['weight']/10000,'mis':a['mis'],
                         'eligible':int(eligible),'linked':int(linked),'last_occ':a['occ']}
                    if linked:
                        employed=b['mlr'] in (1,2); statuses=maps[2018 if y>=2020 else 2010].get(b['occ'],set())
                        resolved=employed and len(statuses)==1
                        rec.update({'next_mlr':b['mlr'],'next_occ':b['occ'],'employed':int(employed),
                                    'below_ba':next(iter(statuses)) if resolved else None,
                                    'mapping':'resolved' if resolved else ('mixed' if len(statuses)>1 else 'unmapped')})
                        rec['state']=('below_ba' if rec['below_ba']==1 else 'ba_plus') if resolved else (
                            'employment_unresolved' if employed else ('unemployed' if b['mlr'] in (3,4) else 'nilf'))
                    rows.append(rec)
            prev=cur; prev_period=(y,m)
        print(y,len(rows),flush=True)
        pd.DataFrame(rows).to_csv(out/'panel.csv.gz',index=False)
    df=pd.DataFrame(rows); df.to_csv(out/'panel.csv.gz',index=False)
    (out/'input_manifest.json').write_text(json.dumps({'missing_months':missing,'files':manifest},indent=2))
    print(df.groupby('foreign')[['eligible','linked','employed']].sum().to_string(),flush=True)
    print(df.groupby(['foreign','state']).size().to_string(),flush=True)

if __name__=='__main__': main()
