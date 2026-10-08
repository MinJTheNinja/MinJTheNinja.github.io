"""Weighted one-month transition risks, clustered uncertainty, and sensitivity.
Run after build_panel.py. Public outputs contain aggregates only.
"""
import json, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import scipy.optimize as opt
from scipy.special import softmax
from scipy.stats import norm
import statsmodels.formula.api as smf
import patsy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).parent
BINS=['0-4','5-12','13-26','27-51','52+']
STATES=['unemployed','below_ba','ba_plus','nilf','employment_unresolved']
LABELS={'unemployed':'Still unemployed','below_ba':'Below-BA occupation','ba_plus':'BA+ occupation',
        'nilf':'Out of labor force','employment_unresolved':'Employment: unresolved code'}
COLORS={0:'#315a91',1:'#c36b33'}

def clean_json(v):
    if isinstance(v,dict): return {str(k):clean_json(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [clean_json(x) for x in v]
    if isinstance(v,np.integer): return int(v)
    if isinstance(v,np.floating): return float(v) if np.isfinite(v) else None
    if isinstance(v,float) and not np.isfinite(v): return None
    return v

def risk_ci(d,y,weights='weight'):
    w=d[weights].to_numpy(); y=np.asarray(y,dtype=float); p=np.average(y,weights=w)
    scores=pd.Series(w*(y-p),index=d.index).groupby(d.person).sum().to_numpy()
    g=len(scores); se=np.sqrt(np.sum(scores**2)*g/max(g-1,1))/w.sum()
    return p,max(0,p-1.96*se),min(1,p+1.96*se),se

def export_summary(d,name):
    rows=[]
    for (f,b),g in d.groupby(['foreign','duration_bin'],observed=True):
        for outcome in ['employed']+STATES+['conditional_below']:
            h=g
            if outcome=='conditional_below':
                h=g[g.state.isin(['below_ba','ba_plus'])]; y=(h.state=='below_ba')
            elif outcome=='employed': y=h.employed
            else: y=(h.state==outcome)
            if len(h)==0: continue
            p,lo,hi,se=risk_ci(h,y)
            rows.append(dict(foreign=f,duration_bin=str(b),outcome=outcome,n=len(h),events=int(sum(y)),
                             probability=p,ci_low=lo,ci_high=hi,se=se,weight_sum=h.weight.sum()))
    a=pd.DataFrame(rows); a.to_csv(ROOT/f'{name}.csv',index=False); return a

def design_and_fit(d,y,weights=True,bin_model=False,prior=False):
    exposure='C(duration_bin)*foreign' if bin_model else 'log_duration*foreign'
    formula=f'{y} ~ {exposure} + age + I(age**2) + C(sex) + C(edu) + C(month) + C(mis)'
    if prior: formula+=' + C(last_class)'
    fit=smf.wls(formula,data=d,weights=d.weight if weights else np.ones(len(d))).fit(
        cov_type='cluster',cov_kwds={'groups':d.person})
    return fit

def contrasts(fit):
    terms=['log_duration','log_duration:foreign']
    if not all(t in fit.params for t in terms): return []
    ans=[]
    for label,c in [('U.S.-born slope',[1,0]),('Foreign-born slope',[1,1]),('Slope difference',[0,1])]:
        vec=np.zeros(len(fit.params))
        for t,val in zip(terms,c): vec[fit.params.index.get_loc(t)]=val
        tt=fit.t_test(vec); val=float(np.asarray(tt.effect).item()); se=float(np.asarray(tt.sd).item())
        ans.append(dict(term=label,estimate=val,se=se,ci_low=val-1.96*se,ci_high=val+1.96*se,p_value=float(tt.pvalue)))
    return ans

def multinomial(d):
    # Genuine mutually exclusive discrete-time competing risks. All risk-set
    # members remain in the denominator; unresolved employed is its own state.
    X=patsy.dmatrix('log_duration*foreign + age + I(age**2) + C(sex) + C(edu) + C(year) + C(month_num) + C(mis)',d,return_type='dataframe')
    columns=list(X.columns); x=X.to_numpy(); scale=np.std(x,axis=0); scale[scale==0]=1; x=x/scale
    y=pd.Categorical(d.state,categories=STATES).codes; k=len(STATES)-1; p=x.shape[1]
    w=d.weight.to_numpy(); w=w/w.mean(); n=len(d)
    targets=np.eye(k+1)[y]
    def fg(theta):
        beta=theta.reshape(p,k); eta=np.column_stack([np.zeros(n),x@beta]); probs=softmax(eta,axis=1)
        loss=-np.sum(w*np.log(np.maximum(probs[np.arange(n),y],1e-300)))/n
        grad=x.T@(w[:,None]*(probs[:,1:]-targets[:,1:]))/n
        return loss,grad.ravel()
    result=opt.minimize(fg,np.zeros(p*k),jac=True,method='L-BFGS-B',options={'maxiter':1200,'ftol':1e-12,'gtol':1e-7,'maxcor':30})
    beta=result.x.reshape(p,k); probs=softmax(np.column_stack([np.zeros(n),x@beta]),axis=1)
    h=np.zeros((p*k,p*k))
    for j in range(k):
        for l in range(k):
            a=w*probs[:,j+1]*((j==l)-probs[:,l+1])
            h[j::k,l::k]=x.T@(a[:,None]*x)
    scores=(x[:,:,None]*(w[:,None]*(targets[:,1:]-probs[:,1:]))[:,None,:]).reshape(n,p*k)
    groups=pd.factorize(d.person)[0]; g=groups.max()+1; cluster_scores=np.zeros((g,p*k)); np.add.at(cluster_scores,groups,scores)
    hinv=np.linalg.pinv(h); cov=hinv@(cluster_scores.T@cluster_scores)@hinv*g/(g-1)
    base=d.copy(); contrasts_out=[]; predictions=[]
    for f in [0,1]:
        for dur in [2,8,20,39,78]:
            base['foreign']=f; base['log_duration']=np.log2(1+dur)
            xx=np.asarray(patsy.build_design_matrices([X.design_info],base)[0])/scale
            pr=softmax(np.column_stack([np.zeros(n),xx@beta]),axis=1)
            avg=np.average(pr,axis=0,weights=w)
            predictions.append({'foreign':f,'duration':dur,**dict(zip(STATES,avg))})
        # Standardized 52 versus 13 weeks on the same pooled covariate distribution.
        gradients=[]; avgs=[]
        for dur in [13,52]:
            base['foreign']=f; base['log_duration']=np.log2(1+dur)
            xx=np.asarray(patsy.build_design_matrices([X.design_info],base)[0])/scale
            pr=softmax(np.column_stack([np.zeros(n),xx@beta]),axis=1); avgs.append(np.average(pr,axis=0,weights=w))
            grad=np.column_stack([np.sum((w*pr[:,1]*((l==0)-pr[:,l+1]))[:,None]*xx,axis=0)/w.sum() for l in range(k)])
            gradients.append(grad.ravel())
        v=gradients[1]-gradients[0]; effect=avgs[1][1]-avgs[0][1]; se=np.sqrt(v@cov@v)
        contrasts_out.append({'foreign':f,'contrast':'52 vs 13 weeks below-BA risk','estimate':effect,'se':se,
                              'ci_low':effect-1.96*se,'ci_high':effect+1.96*se,'p_value':2*norm.sf(abs(effect/se)),'gradient':v})
    v=contrasts_out[1]['gradient']-contrasts_out[0]['gradient']; effect=contrasts_out[1]['estimate']-contrasts_out[0]['estimate']; se=np.sqrt(v@cov@v)
    for c in contrasts_out: c.pop('gradient')
    contrasts_out.append({'foreign':'difference','contrast':'Foreign minus U.S.: 52 vs 13 weeks','estimate':effect,'se':se,
                         'ci_low':effect-1.96*se,'ci_high':effect+1.96*se,'p_value':2*norm.sf(abs(effect/se))})
    return {'converged':bool(result.success),'message':str(result.message),'iterations':result.nit,
            'max_gradient':float(np.max(np.abs(result.jac))),'n':n,'parameters':p*k,
            'predictions':predictions,'contrasts':contrasts_out}

def plot_rates(a):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axs=plt.subplots(1,3,figsize=(13,4.2))
    panels=[('employed','Any reemployment',0.5),('below_ba','Below-BA reemployment\nAll linked jobseekers',0.25),('conditional_below','Below-BA share\nResolved reemployed workers',0.85)]
    for ax,(out,title,top) in zip(axs,panels):
        for f,label in [(0,'U.S.-born'),(1,'Foreign-born')]:
            s=a[(a.foreign==f)&(a.outcome==out)].set_index('duration_bin').loc[BINS]; x=np.arange(5)
            ax.errorbar(x+(f-.5)*.08,s.probability*100,yerr=np.array([s.probability-s.ci_low,s.ci_high-s.probability])*100,
                        marker='o',capsize=3,label=label,color=COLORS[f],linewidth=1.7)
        ax.set_title(title,loc='left',fontweight='bold'); ax.set_xticks(range(5),BINS); ax.set_xlabel('Weeks unemployed at baseline')
        ax.set_ylabel('Percent'); ax.set_ylim(0,top*100); ax.grid(axis='y',alpha=.18)
    axs[0].legend(frameon=False); fig.tight_layout(); fig.savefig(ROOT/'transition-rates.svg',bbox_inches='tight'); plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,4.8),sharey=True)
    palette=['#dbe2ec','#c36b33','#315a91','#82848c','#d6cbbf']
    for ax,f,title in zip(axs,[0,1],['U.S.-born','Foreign-born']):
        bottom=np.zeros(5)
        for state,color in zip(STATES,palette):
            s=a[(a.foreign==f)&(a.outcome==state)].set_index('duration_bin').loc[BINS].probability.to_numpy()*100
            ax.bar(range(5),s,bottom=bottom,label=LABELS[state],color=color,width=.65); bottom+=s
        assert np.allclose(bottom,100)
        ax.set_title(title,loc='left',fontweight='bold'); ax.set_xticks(range(5),BINS); ax.set_xlabel('Weeks unemployed at baseline'); ax.set_ylim(0,100)
    axs[0].set_ylabel('Next-month outcomes (%)'); axs[1].legend(loc='upper left',bbox_to_anchor=(1.01,1),frameon=False)
    fig.tight_layout(); fig.savefig(ROOT/'competing-outcomes.svg',bbox_inches='tight'); plt.close(fig)

def main():
    allrows=pd.read_csv(ROOT/'panel.csv.gz')
    allrows['duration_bin']=pd.cut(allrows.duration,[-1,4,12,26,51,np.inf],labels=BINS)
    allrows['log_duration']=np.log2(1+allrows.duration)
    allrows['unit_weight']=1.
    d=allrows[allrows.linked==1].copy()
    for state in STATES: d[state]=(d.state==state).astype(int)
    d['employed']=d.state.isin(['below_ba','ba_plus','employment_unresolved']).astype(int)
    d['last_class']='unresolved'
    cw=pd.read_csv(ROOT/'occupation_crosswalk.csv')
    for vintage in [2010,2018]:
        mapping=cw[(cw.census_vintage==vintage)&(cw.status=='resolved')].set_index('census_code').below_ba.to_dict()
        mask=(d.year<2020) if vintage==2010 else (d.year>=2020)
        d.loc[mask,'last_class']=d.loc[mask,'last_occ'].map(mapping).map({0.:'ba_plus',1.:'below_ba'}).fillna('unresolved')
    a=export_summary(d,'duration_rates'); plot_rates(a)
    unweighted=d.copy(); unweighted.weight=1; export_summary(unweighted,'duration_rates_unweighted')
    diagnostics=[]
    for (f,b),g in allrows.groupby(['foreign','duration_bin'],observed=True):
        e=g[g.eligible==1]; l=e[e.linked==1]
        diagnostics.append({'foreign':f,'duration_bin':str(b),'baseline_n':len(g),'eligible_n':len(e),'linked_n':len(l),
                            'link_rate_eligible':np.average(e.linked,weights=e.weight),
                            'eligible_mean_age':np.average(e.age,weights=e.weight),'linked_mean_age':np.average(l.age,weights=l.weight),
                            'eligible_female_share':np.average(e.sex==2,weights=e.weight),'linked_female_share':np.average(l.sex==2,weights=l.weight)})
    pd.DataFrame(diagnostics).to_csv(ROOT/'linkage_diagnostics.csv',index=False)
    totals=[]
    for f,g in allrows.groupby('foreign'):
        e=g[g.eligible==1]; l=d[d.foreign==f]; emp=l[l.employed==1]; resolved=emp[emp.state.isin(['below_ba','ba_plus'])]
        totals.append({'foreign':f,'baseline_n':len(g),'eligible_n':len(e),'linked_n':len(l),'reemployed_n':len(emp),
                       'resolved_reemployed_n':len(resolved),'unresolved_reemployed_n':len(emp)-len(resolved),
                       'unique_linked_people':l.person.nunique(),'weighted_reemployment_rate':np.average(l.employed,weights=l.weight),
                       'weighted_below_ba_risk':np.average(l.below_ba,weights=l.weight),
                       'weighted_below_ba_share':np.average(resolved.state=='below_ba',weights=resolved.weight),
                       'weighted_link_rate_eligible':np.average(e.linked,weights=e.weight)})
    results={'totals':totals,'diagnostics':diagnostics,'models':{},'sensitivities':{}}
    for outcome in ['employed','below_ba','ba_plus','unemployed','nilf','employment_unresolved']:
        print('Fitting',outcome,flush=True); fit=design_and_fit(d,outcome)
        results['models'][outcome]={'n':int(fit.nobs),'contrasts':contrasts(fit),'r2':fit.rsquared}
    cond=d[d.state.isin(['below_ba','ba_plus'])].copy()
    results['models']['conditional_below']={'n':len(cond),'contrasts':contrasts(design_and_fit(cond,'below_ba'))}
    # Binned controlled contrasts test nonlinearity independently of log slope.
    fit=design_and_fit(d,'below_ba',bin_model=True); binned=[]
    for f in [0,1]:
        for b in BINS[1:]:
            term=f'C(duration_bin)[T.{b}]'; interaction=term+':foreign'; vec=np.zeros(len(fit.params))
            vec[fit.params.index.get_loc(term)]=1
            if f: vec[fit.params.index.get_loc(interaction)]=1
            tt=fit.t_test(vec); val=float(np.asarray(tt.effect).item()); se=float(np.asarray(tt.sd).item())
            binned.append({'foreign':f,'bin':b,'estimate':val,'ci_low':val-1.96*se,'ci_high':val+1.96*se,'p_value':float(tt.pvalue)})
    results['binned_model']=binned
    scenarios={'unweighted':(d,False,False),'exclude_2020_2021':(d[~d.year.isin([2020,2021])],True,False),
               '2011_2019':(d[d.year<2020],True,False),'2020_2025':(d[d.year>=2020],True,False),
               'exclude_2025':(d[d.year<2025],True,False),'control_prior_occupation':(d,True,True)}
    for name,(h,w,prior) in scenarios.items():
        print('Sensitivity',name,flush=True)
        results['sensitivities'][name]={'n':len(h),'contrasts':contrasts(design_and_fit(h,'below_ba',weights=w,prior=prior))}
    # Mapping bounds: classify every unresolved job as either below-BA or BA+.
    for name,unknown_below in [('unresolved_all_ba_plus',False),('unresolved_all_below_ba',True)]:
        h=d.copy(); h['bound_y']=h.below_ba+h.employment_unresolved*unknown_below
        results['sensitivities'][name]={'n':len(h),'contrasts':contrasts(design_and_fit(h,'bound_y'))}
    print('Multinomial competing risks',flush=True); results['multinomial']=multinomial(d)
    (ROOT/'results.json').write_text(json.dumps(clean_json(results),indent=2),encoding='utf-8')
    print(json.dumps(clean_json({'totals':totals,'main':results['models']['below_ba'],'multinomial':results['multinomial']}),indent=2),flush=True)

if __name__=='__main__': main()
