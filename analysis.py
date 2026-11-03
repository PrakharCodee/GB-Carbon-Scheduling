PROJECT = '01_GB_Carbon_Scheduling'

from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, io, sqlite3, math, sys, platform, shutil
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
from IPython.display import display, Markdown

BASE = Path.cwd() / PROJECT
RAW, EXPORT, FIG = [BASE / p for p in ('data/raw','exports','reports/figures')]
for p in (RAW, EXPORT, FIG): p.mkdir(parents=True, exist_ok=True)
manifest = []
session = requests.Session()
session.headers.update({'User-Agent':'Prakhar-Analytics-Portfolio/1.0','Accept':'application/json'})
session.mount('https://', HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504])))

def fetch(url, name, headers=None, params=None):
    p = RAW / name
    if p.exists():
        payload = p.read_bytes()
        cached = True
    else:
        r = session.get(url, headers=headers, params=params, timeout=(15,90))
        r.raise_for_status()
        payload = r.content
        if not payload: raise ValueError('Empty source response: '+url)
        p.write_bytes(payload)
        cached = False
    manifest.append({'url':url,'params':params,'file':name,'sha256':hashlib.sha256(payload).hexdigest(),
                     'bytes':len(payload),'cached':cached,'observed_at_utc':datetime.now(timezone.utc).isoformat()})
    return payload

def save_table(df, name):
    df.to_csv(EXPORT / (name+'.csv'),index=False)

def chart(name):
    plt.tight_layout()
    plt.savefig(FIG/(name+'.png'),dpi=160,bbox_inches='tight')
    plt.show()

def finish(summary, dictionary, dax):
    (BASE/'reports'/'executive_summary.md').write_text(summary,encoding='utf-8')
    (BASE/'DATA_DICTIONARY.md').write_text(dictionary,encoding='utf-8')
    (BASE/'POWER_BI.md').write_text(dax,encoding='utf-8')
    (BASE/'source_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (BASE/'environment.json').write_text(json.dumps({'python':sys.version,'pandas':pd.__version__,
        'numpy':np.__version__,'requests':requests.__version__,'platform':platform.platform()},indent=2),encoding='utf-8')
    display(Markdown(summary))
    print('OUTPUT_DIRECTORY:',BASE)

plt.rcParams.update({'figure.figsize':(11,5),'axes.spines.top':False,'axes.spines.right':False,
                     'axes.grid':True,'grid.alpha':0.18})
pd.set_option('display.max_columns',20)
print('Project:',PROJECT,'| Run UTC:',datetime.now(timezone.utc).isoformat())

START, END = pd.Timestamp('2025-01-01',tz='UTC'), pd.Timestamp('2026-01-01',tz='UTC')
pieces=[]
for a in pd.date_range(START,END,freq='7D',inclusive='left'):
    b=min(a+pd.Timedelta(days=7),END)
    fmt=lambda x:x.strftime('%Y-%m-%dT%H:%MZ')
    payload=json.loads(fetch(f'https://api.carbonintensity.org.uk/intensity/{fmt(a)}/{fmt(b)}',a.strftime('%Y%m%d')+'.json'))
    if not isinstance(payload.get('data'),list): raise ValueError(str(payload)[:300])
    pieces.extend(payload['data'])
raw=pd.json_normalize(pieces)
df=raw.rename(columns={'from':'timestamp','to':'interval_end','intensity.actual':'actual','intensity.forecast':'forecast'})
df['timestamp']=pd.to_datetime(df['timestamp'],utc=True)
df['interval_end']=pd.to_datetime(df['interval_end'],utc=True)
df=df.loc[df.timestamp.ge(START)&df.timestamp.lt(END),['timestamp','interval_end','actual','forecast']].copy()
for c in ['actual','forecast']: df[c]=pd.to_numeric(df[c],errors='coerce')
duplicate_rows=int(df.timestamp.duplicated().sum())
conflicts=df.groupby('timestamp')[['actual','forecast']].nunique().gt(1).any().any()
assert not conflicts,'Conflicting source records at the same timestamp'
df=df.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
expected=pd.date_range(START,END,freq='30min',inclusive='left')
missing_intervals=len(expected.difference(df.timestamp))
assert ((df.interval_end-df.timestamp)==pd.Timedelta(minutes=30)).all()
assert df[['actual','forecast']].dropna().ge(0).all().all()
df['date']=df.timestamp.dt.strftime('%Y-%m-%d')
df['month']=df.timestamp.dt.strftime('%Y-%m')
df['hour_utc']=df.timestamp.dt.hour+df.timestamp.dt.minute/60
audit=pd.DataFrame({'check':['expected intervals','observed unique intervals','overlap duplicates removed','missing timestamps','missing actual','missing forecast'],
                    'value':[len(expected),len(df),duplicate_rows,missing_intervals,int(df.actual.isna().sum()),int(df.forecast.isna().sum())]})
display(audit)
save_table(audit,'quality_audit'); save_table(df,'fact_intensity')

con=sqlite3.connect(BASE/'analytics.sqlite')
df.assign(timestamp=df.timestamp.astype(str),interval_end=df.interval_end.astype(str)).to_sql('intensity',con,if_exists='replace',index=False)
SQL = '''
WITH paired AS (
 SELECT *, actual-forecast AS error FROM intensity
 WHERE actual IS NOT NULL AND forecast IS NOT NULL
), monthly AS (
 SELECT month, COUNT(*) AS paired_intervals, AVG(actual) AS mean_actual_g_kwh,
 AVG(ABS(error)) AS mae_g_kwh, AVG(error) AS bias_g_kwh
 FROM paired GROUP BY month
)
SELECT *, mean_actual_g_kwh-LAG(mean_actual_g_kwh) OVER(ORDER BY month) AS change_g_kwh
FROM monthly ORDER BY month;
'''
(BASE/'analysis.sql').write_text(SQL,encoding='utf-8')
monthly=pd.read_sql_query(SQL,con)
assert np.isclose(monthly.paired_intervals.sum(),df[['actual','forecast']].notna().all(axis=1).sum())
save_table(monthly,'monthly_forecast_quality'); display(monthly)

KWH, SLOTS, BASELINE_START = 100.0, 4, 17.0
rows=[]; skipped=[]
for date,g in df.groupby('date'):
    g=g.sort_values('timestamp').reset_index(drop=True)
    if len(g)!=48 or g[['actual','forecast']].isna().any().any() or not g.timestamp.diff().iloc[1:].eq(pd.Timedelta(minutes=30)).all():
        skipped.append(date); continue
    candidates=[]
    for i in range(len(g)-SLOTS+1):
        if 6 <= g.loc[i,'hour_utc'] <= 20:
            w=g.iloc[i:i+SLOTS]
            candidates.append({'start':g.loc[i,'hour_utc'],'forecast_mean':w.forecast.mean(),'actual_mean':w.actual.mean()})
    c=pd.DataFrame(candidates)
    base=c.loc[c.start.eq(BASELINE_START)].iloc[0]
    chosen=c.sort_values(['forecast_mean','start']).iloc[0]
    oracle=c.sort_values(['actual_mean','start']).iloc[0]
    rows.append({'date':date,'month':date[:7],'baseline_kg':base.actual_mean*KWH/1000,
      'forecast_policy_kg':chosen.actual_mean*KWH/1000,'hindsight_kg':oracle.actual_mean*KWH/1000,
      'chosen_start_utc':chosen.start,'baseline_start_utc':BASELINE_START,
      'baseline_intensity':base.actual_mean,'chosen_actual_intensity':chosen.actual_mean})
policy=pd.DataFrame(rows)
assert len(policy)>=300, 'Too few complete days for an annual comparison'
policy['avoided_kg']=policy.baseline_kg-policy.forecast_policy_kg
policy['hindsight_gap_kg']=policy.forecast_policy_kg-policy.hindsight_kg
assert (policy.hindsight_kg<=policy.forecast_policy_kg+1e-9).all()
policy['daily_saving_pct']=100*policy.avoided_kg/policy.baseline_kg.replace(0,np.nan)
baseline=policy.baseline_kg.sum(); avoided=policy.avoided_kg.sum()
total_saving_pct=100*avoided/baseline
downside_days=int(policy.avoided_kg.lt(0).sum())
display(policy.head())
print(f'Eligible days: {len(policy)} | Excluded days: {len(skipped)} | Scenario reduction: {total_saving_pct:.2f}% | Worse-than-baseline days: {downside_days}')
save_table(policy,'daily_scheduling_scenario')

rng=np.random.default_rng(42)
vals=policy[['baseline_kg','avoided_kg']].to_numpy(); n=len(vals); sims=[]
for _ in range(1000):
    starts=rng.integers(0,n,size=math.ceil(n/7))
    ids=np.concatenate([(np.arange(s,s+7)%n) for s in starts])[:n]
    sampled=vals[ids]; sims.append(100*sampled[:,1].sum()/sampled[:,0].sum())
ci=np.quantile(sims,[.025,.975])
sens=[]
for flex in [0,1,3,20]:
    bsum=csum=0
    for _,g in df[df.date.isin(policy.date)].groupby('date'):
        g=g.sort_values('timestamp').reset_index(drop=True)
        c=[]
        for i in range(45):
            h=g.loc[i,'hour_utc']
            if 6<=h<=20 and abs(h-17)<=flex:
                c.append((g.iloc[i:i+4].forecast.mean(),h,g.iloc[i:i+4].actual.mean()))
        pick=min(c,key=lambda x:(x[0],x[1])); csum+=pick[2]*KWH/1000
        bsum+=g.iloc[34:38].actual.mean()*KWH/1000
    sens.append({'flexibility_hours':flex,'baseline_kg':bsum,'policy_kg':csum,'reduction_pct':100*(bsum-csum)/bsum})
sensitivity=pd.DataFrame(sens); display(sensitivity)
save_table(sensitivity,'flexibility_sensitivity')
print('Moving-block bootstrap historical interval (%):',ci.round(2))

agg=policy.groupby('month')[['baseline_kg','forecast_policy_kg','hindsight_kg']].sum()
agg.rename(columns={'baseline_kg':'Fixed 17:00 start','forecast_policy_kg':'Forecast-selected start','hindsight_kg':'Hindsight lower bound'}).plot(kind='bar',color=['#64748b','#0891b2','#a7f3d0'])
plt.ylabel('Modelled kg CO2 per monthly set of jobs'); plt.title('One 100 kWh job per eligible day | 2025 | UTC'); chart('01_policy_comparison')
plt.figure(); plt.hist(policy.avoided_kg,bins=30,color='#0891b2'); plt.axvline(0,color='#dc2626'); plt.xlabel('Baseline minus forecast-policy emissions (kg/job)'); plt.ylabel('Days'); plt.title('Daily benefit and downside'); chart('02_daily_downside')
plt.figure(); plt.plot(monthly.month,monthly.mae_g_kwh,marker='o'); plt.xticks(rotation=45); plt.ylabel('Forecast MAE (g CO2/kWh)'); plt.title('Forecast reliability by month'); chart('03_forecast_error')
fig=px.scatter(policy,x='baseline_kg',y='forecast_policy_kg',color='month',hover_data=['date','chosen_start_utc'],
               title='Explore daily scheduling outcomes',labels={'baseline_kg':'Baseline kg CO2','forecast_policy_kg':'Forecast policy kg CO2'})
fig.write_html(FIG/'interactive_daily_outcomes.html',include_plotlyjs=True); fig.show()

summary=f'''# GB carbon scheduling decision brief

Analysed {len(df):,} unique half-hour records for 2025; {len(policy)} complete days support the scenario and {len(skipped)} days were excluded. Under a 100 kWh two-hour job assumption, moving from 17:00 UTC to a forecast-selected start in 06:00–20:00 UTC changes modelled emissions by {avoided:,.1f} kg CO2 ({total_saving_pct:.2f}% reduction) across eligible days. This is a retrospective scenario, not delivered business impact.

The seven-day block bootstrap interval for historical reduction is {ci[0]:.2f}% to {ci[1]:.2f}%. The policy was worse than baseline on {downside_days} days. Actual-intensity hindsight is a lower bound, not an implementable policy.

Recommendation: review flexibility_sensitivity.csv and daily downside before proposing a small operational pilot. Store timestamped forecast vintages and measured kWh in the pilot. No tariff or marginal-emissions claim is supported. The historical API forecast may have been revised; this limits causal and prospective interpretation.

Source: National Energy System Operator, Carbon Intensity API, https://api.carbonintensity.org.uk/ , CC BY 4.0. Raw response hashes are in source_manifest.json.
'''
finish(summary,
'''# Data dictionary
fact_intensity: one half-hour in UTC; actual and forecast are g CO2/kWh. Nulls are not imputed.
daily_scheduling_scenario: one eligible complete day; kg values assume 100 kWh/job. avoided_kg=baseline_kg-forecast_policy_kg. chosen_start_utc is decimal UTC hour.
monthly_forecast_quality: paired observation counts, MAE and signed actual-minus-forecast bias.
flexibility_sensitivity: modelled policy by permitted hours from baseline; 20 represents the full candidate window.
''',
'''# Power BI handover
Import fact_intensity.csv and daily_scheduling_scenario.csv as separate facts. Create a unique Date dimension and one-to-many relationships using date. Do not directly join the two facts.

Baseline kg = SUM(daily_scheduling_scenario[baseline_kg])
Policy kg = SUM(daily_scheduling_scenario[forecast_policy_kg])
Avoided kg = [Baseline kg] - [Policy kg]
Reduction % = DIVIDE([Avoided kg], [Baseline kg])

Format Reduction % as a percentage; it is a ratio, not a pre-multiplied percent. Page 1: scenario totals and monthly policy comparison. Page 2: downside distribution and forecast MAE. Slicers: month and chosen start hour. Clearly label all savings as modelled scenarios.
''')
con.close()