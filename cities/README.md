# City modules

Create one module per additional city. Keep data loading, schema checks, scoring inputs, and map/table rendering inside the city module. The main app should dispatch based on the selected city ID. Reuse the existing scoring methodology only where the input definitions and geographic scale are comparable.
