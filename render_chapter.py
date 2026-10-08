"""Generate the public chapter from computed aggregate results."""
import html,json,platform,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import scipy,statsmodels,matplotlib

ROOT=Path(__file__).parent

def pp(x): return f'{x*100:+.2f}'
def pct(x): return f'{x*100:.1f}%'
def pv(x): return '&lt;0.001' if x<.001 else f'{x:.3f}'
def ci(c): return f'[{c["ci_low"]*100:+.2f}, {c["ci_high"]*100:+.2f}]'
def table(head,rows):
    return '<table><thead><tr>'+''.join(f'<th>{h}</th>' for h in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{x}</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
def main():
    r=json.loads((ROOT/'results.json').read_text()); rates=pd.read_csv(ROOT/'duration_rates.csv'); total={x['foreign']:x for x in r['totals']}
    main_c=r['models']['below_ba']['contrasts']; native,foreign,diff=main_c
    cond_c=r['models']['conditional_below']['contrasts']; emp_c=r['models']['employed']['contrasts']
    snippets={}
    def stat(value,label): return f'<div class="stat"><strong>{value}</strong><span>{label}</span></div>'
    snippets['STAT_CARDS']=stat(f'{sum(x["linked_n"] for x in total.values()):,}','linked unemployment person-months')+stat(f'{sum(x["reemployed_n"] for x in total.values()):,}','observed next-month reemployment transitions')+stat(f'{sum(x["resolved_reemployed_n"] for x in total.values()):,}','reemployment transitions with resolved BA threshold')
    if native['ci_high']<0 and foreign['ci_high']<0:
        snippets['FINDING']='<strong>Longer unemployment predicts a lower next-month risk of below-BA reemployment in both groups.</strong> The probability of finding any job also falls. A different pattern among those who find jobs should not be read as a higher entry risk for all jobseekers.'
    elif native['estimate']<0 and foreign['estimate']<0:
        snippets['FINDING']='<strong>The estimated next-month risk of below-BA reemployment falls with duration in both groups.</strong> Uncertainty and the difference between conditional job quality and overall entry risk matter for the interpretation.'
    else:
        snippets['FINDING']='<strong>Duration relates differently to jobfinding and occupational job quality.</strong> The main question must be evaluated using all linked jobseekers, alongside competing outcomes and uncertainty.'
    group_statement=('The duration slopes differ at the nominal 5% level.' if diff['p_value']<.05 else 'The interaction does not establish a difference between the birth groups at the nominal 5% level.')
    snippets['ABSTRACT']=f'Across the 2011–2025 window, weighted below-BA entry averages {pct(total[0]["weighted_below_ba_risk"])} per linked unemployment month for U.S.-born graduates and {pct(total[1]["weighted_below_ba_risk"])} for foreign-born graduates. In the main adjusted model, a doubling of 1 + elapsed weeks is associated with {pp(native["estimate"])} percentage points for U.S.-born and {pp(foreign["estimate"])} for foreign-born respondents. {group_statement} The estimated slope difference is {pp(diff["estimate"])} points (95% interval {ci(diff)}; p = {pv(diff["p_value"])}).'
    snippets['SAMPLE_TABLE']=table(['Sample stage','U.S.-born','Foreign-born'],[
        ['Eligible age/degree/search baseline observations',f'{total[0]["baseline_n"]:,}',f'{total[1]["baseline_n"]:,}'],
        ['Scheduled for an adjacent-month interview',f'{total[0]["eligible_n"]:,}',f'{total[1]["eligible_n"]:,}'],
        ['Valid linked risk-set observations',f'{total[0]["linked_n"]:,}',f'{total[1]["linked_n"]:,}'],
        ['Unique person identifiers in linked risk set',f'{total[0]["unique_linked_people"]:,}',f'{total[1]["unique_linked_people"]:,}'],
        ['Reemployed next month',f'{total[0]["reemployed_n"]:,}',f'{total[1]["reemployed_n"]:,}'],
        ['BA threshold resolved',f'{total[0]["resolved_reemployed_n"]:,}',f'{total[1]["resolved_reemployed_n"]:,}'],
        ['Reemployed, threshold unresolved',f'{total[0]["unresolved_reemployed_n"]:,}',f'{total[1]["unresolved_reemployed_n"]:,}'],
        ['Weighted link rate among scheduled interviews',pct(total[0]['weighted_link_rate_eligible']),pct(total[1]['weighted_link_rate_eligible'])]])
    snippets['SAMPLE_RECONCILIATION']='The reconstruction checks that age does not decline and keeps baseline eligibility fixed when respondents turn 65 or their reported degree changes. Consequently, its event counts can differ from the earlier pilot, which allowed a one-year decline and reapplied the age/degree screen at follow-up. These are separately documented samples, not additional observations appended to the pilot.'
    def rate(f,b,out):return rates[(rates.foreign==f)&(rates.duration_bin==b)&(rates.outcome==out)].iloc[0].probability
    snippets['PATTERN_TEXT']=f'For U.S.-born respondents, any-job entry is {pct(rate(0,"0-4","employed"))} at 0–4 weeks and {pct(rate(0,"52+","employed"))} at 52+ weeks; below-BA entry is {pct(rate(0,"0-4","below_ba"))} and {pct(rate(0,"52+","below_ba"))}, respectively. For foreign-born respondents, those corresponding pairs are {pct(rate(1,"0-4","employed"))} versus {pct(rate(1,"52+","employed"))} for any job and {pct(rate(1,"0-4","below_ba"))} versus {pct(rate(1,"52+","below_ba"))} for below-BA entry. These unadjusted comparisons pool different people and survey dates.'
    model_names={'employed':'Any reemployment / all linked','below_ba':'Below-BA entry / all linked','ba_plus':'BA+ entry / all linked','conditional_below':'Below-BA share / resolved reemployed'}
    rows=[]
    for key,label in model_names.items():
        for c in r['models'][key]['contrasts']:
            rows.append([label,c['term'],pp(c['estimate']),ci(c),pv(c['p_value'])])
    snippets['MODEL_TABLE']=table(['Outcome','Duration effect','pp per doubling','95% interval','p'],rows)
    snippets['MODEL_TEXT']=f'The main below-BA duration slopes are {pp(native["estimate"])} and {pp(foreign["estimate"])} points, compared with {pp(emp_c[0]["estimate"])} and {pp(emp_c[1]["estimate"])} for any-job entry. Among resolved reemployment events, the corresponding below-BA-share slopes are {pp(cond_c[0]["estimate"])} and {pp(cond_c[1]["estimate"])} points. Conditioning on employment answers a different question and selects workers who successfully found jobs.'
    mc=r['multinomial']['contrasts']; names={0:'U.S.-born',1:'Foreign-born','difference':'Difference between groups'}
    snippets['MULTINOMIAL_TABLE']=table(['Standardized change: 52 vs 13 weeks','Below-BA risk change (pp)','95% interval','p'],[[names[c['foreign']],pp(c['estimate']),ci(c),pv(c['p_value'])] for c in mc])
    snippets['MULTINOMIAL_TEXT']=f'The multinomial estimates imply {pp(mc[0]["estimate"])} points for U.S.-born and {pp(mc[1]["estimate"])} points for foreign-born respondents when comparing 52 with 13 elapsed weeks. The difference between these changes is {pp(mc[2]["estimate"])} points (p = {pv(mc[2]["p_value"])}). Optimization {"converged" if r["multinomial"]["converged"] else "did not meet the convergence criterion"}; {r["multinomial"]["iterations"]} iterations, maximum scaled score component {r["multinomial"]["max_gradient"]:.2g}.'
    snippets['BINNED_TABLE']=table(['Birth group','Weeks vs 0–4','Adjusted difference (pp)','95% interval','p'],[[names[c['foreign']],c['bin'],pp(c['estimate']),ci(c),pv(c['p_value'])] for c in r['binned_model']])
    labels={'unweighted':'Unweighted','exclude_2020_2021':'Exclude 2020–2021','2011_2019':'Baseline 2011–2019','2020_2025':'Baseline 2020–2025','exclude_2025':'Exclude 2025 baseline months','control_prior_occupation':'Control last-job BA class','unresolved_all_ba_plus':'Unresolved jobs all BA+','unresolved_all_below_ba':'Unresolved jobs all below-BA'}
    snippets['SENSITIVITY_TABLE']=table(['Specification','n','U.S. slope (pp)','Foreign slope (pp)','Slope difference [95% interval]','Interaction p'],[[labels[k],f'{v["n"]:,}',pp(v['contrasts'][0]['estimate']),pp(v['contrasts'][1]['estimate']),f'{pp(v["contrasts"][2]["estimate"])} {ci(v["contrasts"][2])}',pv(v['contrasts'][2]['p_value'])] for k,v in r['sensitivities'].items()])
    negative_count=sum(v['contrasts'][0]['estimate']<0 and v['contrasts'][1]['estimate']<0 for v in r['sensitivities'].values())
    snippets['SENSITIVITY_TEXT']=f'Both groups have negative below-BA entry slopes in {negative_count} of the {len(r["sensitivities"])} reported alternatives. These are specified measurement and sample checks, not a search for a favorable specification. Interaction p-values can vary by period and coding choice; conclusions should reflect that variation. The two extreme recodings bracket overall event classification but do not identify individual unresolved occupations.'
    snippets['LINKAGE_TABLE']=table(['Group · weeks','Scheduled n','Linked n','Weighted link %','Mean age: scheduled → linked','Female share: scheduled → linked'],[[f'{names[c["foreign"]]} · {c["duration_bin"]}',f'{c["eligible_n"]:,}',f'{c["linked_n"]:,}',pct(c['link_rate_eligible']),f'{c["eligible_mean_age"]:.1f} → {c["linked_mean_age"]:.1f}',f'{pct(c["eligible_female_share"])} → {pct(c["linked_female_share"])}'] for c in r['diagnostics']])
    snippets['ATTRITION_TEXT']=f'Overall, {pct(total[0]["weighted_link_rate_eligible"])} of scheduled U.S.-born observations and {pct(total[1]["weighted_link_rate_eligible"])} of scheduled foreign-born observations link successfully. Duration-specific retention and demographic shifts are reported above rather than treating all missing follow-ups as unemployment.'
    snippets['CONCLUSION']=f'<p><strong>Answer to the main question:</strong> {"The data do not support a higher next-month below-BA entry risk with longer unemployment: both main adjusted duration slopes are negative." if native["estimate"]<0 and foreign["estimate"]<0 else "The direction and uncertainty of the main all-jobseeker estimates are reported above; a conditional mismatch share is insufficient to answer the question."}</p><p><strong>Difference by birthplace:</strong> {group_statement} The foreign-minus-U.S. slope difference is {pp(diff["estimate"])} percentage points per doubling of 1 + weeks, with interval {ci(diff)}. A nonsignificant interaction is not proof that the groups have identical relationships.</p><p><strong>Economic interpretation:</strong> The fall in jobfinding means a greater below-BA share among successful entrants can coexist with a smaller below-BA entry hazard among all jobseekers. Differences in this share may be consistent with occupational concessions or constrained offers, but duration-dependent selection into unemployment and employment can generate similar patterns. The study documents transitions; it does not isolate credential recognition, discrimination, visa constraints, or changing reservation standards.</p><p><strong>Next research step:</strong> Replicate the mapping with historical education vintages and richer occupation bridges, implement calibrated longitudinal weights and full survey-design inference, and test whether the pattern persists within clearly identified unemployment spells and prior occupation groups.</p>'
    template=(ROOT/'chapter.template.html').read_text(encoding='utf-8')
    for k,v in snippets.items(): template=template.replace('{{'+k+'}}',v)
    assert '{{' not in template
    (ROOT/'index.html').write_text(template,encoding='utf-8')
    payload={'weighted':rates.to_dict('records'),'unweighted':pd.read_csv(ROOT/'duration_rates_unweighted.csv').to_dict('records')}
    (ROOT/'data.js').write_text('window.CPS_ESTIMATES = '+json.dumps(payload,allow_nan=False)+';',encoding='utf-8')
    versions={'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'scipy':scipy.__version__,'statsmodels':statsmodels.__version__,'matplotlib':matplotlib.__version__}
    (ROOT/'versions.json').write_text(json.dumps(versions,indent=2))
    with zipfile.ZipFile(ROOT/'reproduction.zip','w',zipfile.ZIP_DEFLATED) as z:
        for f in ['README.md','requirements.txt','build_panel.py','bls_thresholds.py','analyze.py','render_chapter.py','chapter.template.html','style.css','explorer.js',
                  'occupation_crosswalk.csv','duration_rates.csv','duration_rates_unweighted.csv','linkage_diagnostics.csv','results.json','input_manifest.json','versions.json','transition-rates.svg','competing-outcomes.svg']:
            z.write(ROOT/f,f)
    print('Chapter and reproduction package generated.',flush=True)

if __name__=='__main__':main()
