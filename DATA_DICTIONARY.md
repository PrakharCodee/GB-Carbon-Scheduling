# Data dictionary
fact_intensity: one half-hour in UTC; actual and forecast are g CO2/kWh. Nulls are not imputed.
daily_scheduling_scenario: one eligible complete day; kg values assume 100 kWh/job. avoided_kg=baseline_kg-forecast_policy_kg. chosen_start_utc is decimal UTC hour.
monthly_forecast_quality: paired observation counts, MAE and signed actual-minus-forecast bias.
flexibility_sensitivity: modelled policy by permitted hours from baseline; 20 represents the full candidate window.
