# Power BI handover
Import fact_intensity.csv and daily_scheduling_scenario.csv as separate facts. Create a unique Date dimension and one-to-many relationships using date. Do not directly join the two facts.

Baseline kg = SUM(daily_scheduling_scenario[baseline_kg])
Policy kg = SUM(daily_scheduling_scenario[forecast_policy_kg])
Avoided kg = [Baseline kg] - [Policy kg]
Reduction % = DIVIDE([Avoided kg], [Baseline kg])

Format Reduction % as a percentage; it is a ratio, not a pre-multiplied percent. Page 1: scenario totals and monthly policy comparison. Page 2: downside distribution and forecast MAE. Slicers: month and chosen start hour. Clearly label all savings as modelled scenarios.
