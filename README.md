# GB electricity carbon scheduling and forecast risk

**Decision:** Can an operations team move a flexible two-hour, 100 kWh job away from a fixed 17:00 UTC start and lower its estimated grid emissions?

This portfolio study uses official NESO half-hourly national carbon intensity for calendar 2025. It distinguishes a forecast-led retrospective policy from an actual-intensity hindsight lower bound, measures downside days and tests scheduling flexibility. It demonstrates time-series cleaning, SQL window functions, constrained optimisation, uncertainty and decision reporting.

**Source:** https://api.carbonintensity.org.uk/ (CC BY 4.0; National Energy System Operator). **Scope:** Great Britain, not all UK electricity. **Run:** Runtime → Run all on a free CPU runtime. No keys, Drive mounting or paid services are required. Outputs are written under the runtime project folder; download the bundle before resetting the runtime.

**Scenario, not achieved business impact:** Energy per job, permitted start times and baseline are explicit assumptions. Grid-average intensity is not marginal emissions, does not include all lifecycle emissions and is not a price signal. The historical forecast field is not an archived forecast vintage; the policy is retrospective and is not a leakage-free live trading backtest.

## Verified results


Analysed 17,520 unique half-hour records for 2025; 361 complete days support the scenario and 4 days were excluded. Under a 100 kWh two-hour job assumption, moving from 17:00 UTC to a forecast-selected start in 06:00–20:00 UTC changes modelled emissions by 2,046.1 kg CO2 (35.35% reduction) across eligible days. This is a retrospective scenario, not delivered business impact.

The seven-day block bootstrap interval for historical reduction is 31.51% to 39.04%. The policy was worse than baseline on 1 days. Actual-intensity hindsight is a lower bound, not an implementable policy.

Recommendation: review flexibility_sensitivity.csv and daily downside before proposing a small operational pilot. Store timestamped forecast vintages and measured kWh in the pilot. No tariff or marginal-emissions claim is supported. The historical API forecast may have been revised; this limits causal and prospective interpretation.

Source: National Energy System Operator, Carbon Intensity API, https://api.carbonintensity.org.uk/ , CC BY 4.0. Raw response hashes are in source_manifest.json.


## Repository contents

- Executed notebook with saved charts and tables
- analysis.py and analysis.sql
- exports/ with analysis and Power BI input tables
- reports/ with executive summary, three PNG figures and an offline interactive HTML chart
- DATA_DICTIONARY.md and POWER_BI.md
- source_manifest.json with source hashes and environment.json
- data/raw/ with cached source snapshots (excluded by .gitignore)

## Reproduce

Open the notebook in Google Colab and choose Runtime → Run all on a free CPU runtime. No authentication to data APIs or paid services is required. Download outputs before resetting a temporary runtime. Alternatively install requirements.txt and run analysis.py from the parent portfolio directory.
