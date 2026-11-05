"""Delhi district and ward priority maps using income-derived socioeconomic vulnerability."""
from pathlib import Path
import pandas as pd
import streamlit as st


def render_delhi(data_dir: Path, read_csv, read_geo, map_priority):
    data_dir = Path(data_dir) / "delhi"
    district_csv = data_dir / "delhi_district_priority_scores.csv"
    district_gpkg = data_dir / "delhi_district_priority_model.gpkg"
    ward_csv = data_dir / "delhi_ward_priority_scores.csv"
    ward_gpkg = data_dir / "delhi_ward_priority_model.gpkg"
    facilities_csv = data_dir / "healthcare_facilities_delhi.csv"
    missing = [p.name for p in [district_csv, district_gpkg, ward_csv, ward_gpkg, facilities_csv] if not p.exists()]
    if missing:
        st.error("Delhi integration files are missing: " + ", ".join(missing))
        return
    page = st.radio("Delhi analysis", ["District-level priority", "Ward-level priority"], horizontal=True, key="delhi_analysis_page")
    facilities = read_csv(str(facilities_csv))
    if page == "District-level priority":
        scores = read_csv(str(district_csv))
        areas = read_geo(str(district_gpkg), layer="delhi_district_priority_model")
        unit_name, tier_col, score_col, rank_col = "admin_unit_name", "priority_tier_model_c", "priority_score_model_c", "priority_rank_model_c"
        title = "Delhi district-level healthcare priority"
        st.caption("Historical Census 2011 district boundaries. Uses the same district-level weights as Lucknow: 51% distance/access, 34% local hospital gap, 15% income-derived socioeconomic vulnerability.")
        st.info("District income is a population-weighted aggregation of ward-level per-capita income estimates (2012 INR). Lower income maps to higher vulnerability. District boundaries are historical 2011 units.")
        filter_col = st.columns(2)
        tier_options = ["All tiers"] + [x for x in ["Very High", "High", "Moderate", "Lower"] if x in set(areas[tier_col].astype(str))]
        selected_tier = filter_col[0].selectbox("Priority tier", tier_options, key="delhi_d_tier")
        color_by = filter_col[1].selectbox("Color map by", ["Model priority tier", "Model priority score", "Distance/accessibility score", "Local hospital-gap score", "Socioeconomic vulnerability", "Per-capita income (2012 INR)"], key="delhi_d_color")
        component_map = {"Distance/accessibility score":"distance_score", "Local hospital-gap score":"local_hospital_gap_score", "Socioeconomic vulnerability":"socioeconomic_vulnerability_score", "Per-capita income (2012 INR)":"per_capita_income_2012_inr"}
        popup = ["admin_unit_name", "total_population", "per_capita_income_2012_inr", "ward_count", "hospital_records", "public_hospitals", "private_hospitals", "beds_total", "nearest_hospital_name", "nearest_hospital_distance_km", "distance_score", "local_hospital_gap_score", "socioeconomic_vulnerability_score", "priority_score_model_c", "priority_rank_model_c", "priority_tier_model_c"]
        aliases = {"admin_unit_name":"2011 district", "total_population":"Census 2011 population", "per_capita_income_2012_inr":"Estimated per-capita income (2012 INR; population-weighted ward aggregation)", "ward_count":"Wards contributing to income aggregation", "hospital_records":"Recorded facilities", "public_hospitals":"Public records", "private_hospitals":"Private records", "beds_total":"Reported beds", "nearest_hospital_name":"Nearest recorded facility", "nearest_hospital_distance_km":"Straight-line distance (km)", "distance_score":"Distance/accessibility score (0–100)", "local_hospital_gap_score":"Local hospital-gap score (0–100)", "socioeconomic_vulnerability_score":"Income-derived vulnerability (0–100)", "priority_score_model_c":"Priority score (0–100)", "priority_rank_model_c":"Priority rank", "priority_tier_model_c":"Priority tier"}
        view = areas.copy()
        if selected_tier != "All tiers": view = view[view[tier_col].astype(str) == selected_tier]
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Districts shown", f"{len(view)} / 9")
        c2.metric("Population (2011)", f"{pd.to_numeric(view['total_population'], errors='coerce').sum():,.0f}")
        c3.metric("Facility records", f"{pd.to_numeric(view['hospital_records'], errors='coerce').sum():,.0f}")
        c4.metric("Highest score in view", f"{pd.to_numeric(view[score_col], errors='coerce').max():.1f}/100" if len(view) else "—")
        map_priority(view, "Delhi district priority", color_by, tier_col, score_col, component_map, popup, aliases, "OpenStreetMap", facilities, True, False, "All hospitals")
        st.subheader("District ranking")
        table_cols = [c for c in [rank_col, unit_name, "total_population", "per_capita_income_2012_inr", "ward_count", "hospital_records", "beds_total", "bed_reporting_facilities", "nearest_hospital_distance_km", "distance_score", "local_hospital_gap_score", "socioeconomic_vulnerability_score", score_col, tier_col] if c in scores.columns]
        table = scores[table_cols].sort_values(rank_col).rename(columns={rank_col:"Rank",unit_name:"District", "total_population":"Population (2011)", "per_capita_income_2012_inr":"Per-capita income (2012 INR)", "ward_count":"Wards contributing", "hospital_records":"Facility records", "nearest_hospital_distance_km":"Nearest facility (km)", "distance_score":"Distance score", "local_hospital_gap_score":"Hospital gap", "socioeconomic_vulnerability_score":"Income vulnerability", score_col:"Priority score", tier_col:"Priority tier"})
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.download_button("Download Delhi district priority CSV", scores.to_csv(index=False).encode("utf-8"), "delhi_district_priority_scores.csv", "text/csv")
    else:
        scores = read_csv(str(ward_csv))
        areas = read_geo(str(ward_gpkg), layer="delhi_ward_priority_model")
        tier_col, score_col, rank_col = "priority_tier_model_c", "priority_score_model_c", "priority_rank_model_c"
        st.caption("Ward-level priorities use the existing Delhi ward scores and the same urban weighting structure as the project. Socioeconomic vulnerability is derived from per-capita income (2012 INR), with lower income indicating greater vulnerability.")
        filters = st.columns(3)
        tier_options = ["All tiers"] + [x for x in ["Very High", "High", "Moderate", "Lower"] if x in set(areas[tier_col].astype(str))]
        selected_tier = filters[0].selectbox("Priority tier", tier_options, key="delhi_w_tier")
        color_by = filters[1].selectbox("Color map by", ["Model priority tier", "Model priority score", "Distance/accessibility score", "Population score", "Combined availability gap", "Public healthcare gap", "Socioeconomic vulnerability", "Per-capita income (2012 INR)", "Nearest hospital distance (km)", "Recorded facilities", "Reported beds"], key="delhi_w_color")
        show_hospitals = filters[2].checkbox("Show hospital markers", value=True, key="delhi_w_hospitals")
        component_map = {"Distance/accessibility score":"distance_score", "Population score":"population_score", "Combined availability gap":"combined_availability_gap", "Public healthcare gap":"public_gap_score", "Socioeconomic vulnerability":"socioeconomic_vulnerability_score", "Per-capita income (2012 INR)":"per_capita_income_2012_inr", "Nearest hospital distance (km)":"nearest_hospital_distance_km", "Recorded facilities":"hospital_records", "Reported beds":"beds_total"}
        popup = ["Ward_Name", "Ward_No", "total_population", "per_capita_income_2012_inr", "hospital_records", "beds_total", "bed_reporting_facilities", "nearest_hospital_distance_km", "distance_score", "population_score", "combined_availability_gap", "public_gap_score", "socioeconomic_vulnerability_score", score_col, rank_col, tier_col]
        aliases = {"Ward_Name":"Ward", "Ward_No":"Ward ID", "total_population":"Population (some values estimated)", "per_capita_income_2012_inr":"Per-capita income (2012 INR)", "hospital_records":"Recorded facilities", "beds_total":"Reported beds", "bed_reporting_facilities":"Facilities reporting beds", "nearest_hospital_distance_km":"Nearest facility distance (km; straight-line)", "distance_score":"Distance/accessibility score", "population_score":"Population score", "combined_availability_gap":"Combined availability gap", "public_gap_score":"Public healthcare gap", "socioeconomic_vulnerability_score":"Income-derived vulnerability (0–100)", score_col:"Priority score (0–100)", rank_col:"Priority rank", tier_col:"Priority tier"}
        view = areas.copy()
        if selected_tier != "All tiers": view = view[view[tier_col].astype(str) == selected_tier]
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Wards shown", f"{len(view):,}")
        c2.metric("Population represented", f"{pd.to_numeric(view['total_population'], errors='coerce').sum():,.0f}")
        c3.metric("Recorded facilities", f"{pd.to_numeric(view['hospital_records'], errors='coerce').sum():,.0f}")
        c4.metric("Reported beds", f"{pd.to_numeric(view['beds_total'], errors='coerce').sum():,.0f}")
        c5.metric("Highest score in view", f"{pd.to_numeric(view[score_col], errors='coerce').max():.1f}/100" if len(view) else "—")
        map_priority(view, "Delhi ward priority", color_by, tier_col, score_col, component_map, popup, aliases, "OpenStreetMap", facilities, show_hospitals, False, "All hospitals")
        st.subheader("Ward ranking")
        table_cols = [c for c in [rank_col, "Ward_Name", "Ward_No", "total_population", "per_capita_income_2012_inr", "hospital_records", "beds_total", "bed_reporting_facilities", "nearest_hospital_distance_km", "distance_score", "population_score", "combined_availability_gap", "public_gap_score", "socioeconomic_vulnerability_score", score_col, tier_col] if c in scores.columns]
        table = scores[table_cols].sort_values(rank_col).rename(columns={rank_col:"Rank", "Ward_Name":"Ward", "Ward_No":"Ward ID", "total_population":"Population", "per_capita_income_2012_inr":"Per-capita income (2012 INR)", "hospital_records":"Recorded facilities", "beds_total":"Reported beds", "bed_reporting_facilities":"Facilities reporting beds", "nearest_hospital_distance_km":"Nearest facility (km)", "distance_score":"Distance score", "population_score":"Population score", "combined_availability_gap":"Availability gap", "public_gap_score":"Public gap", "socioeconomic_vulnerability_score":"Income vulnerability", score_col:"Priority score", tier_col:"Priority tier"})
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.download_button("Download Delhi ward priority CSV", scores.to_csv(index=False).encode("utf-8"), "delhi_ward_priority_scores.csv", "text/csv")
    with st.expander("Methodology and interpretation"):
        st.markdown("""- Socioeconomic factor: per-capita income in 2012 INR; lower income produces higher vulnerability. District income is aggregated from ward estimates using population weights.
- District geography uses historical Census 2011 boundaries.
- Ward priority scores and component weights are retained from the existing Delhi accessibility output.
- Facility inventory contains 50 selected records and is not exhaustive. Ward reported-bed totals sum the bed capacities in this mapped inventory; zero means no facility from this inventory was assigned to that ward, not necessarily no beds in reality.
- Reported bed capacities are historical sanctioned-capacity records (DGHS Annual Report 2022–23), not verified current operational bed counts.
- Distance is straight-line distance, not road travel time.
- Population figures include estimates where source values were unavailable.""")
