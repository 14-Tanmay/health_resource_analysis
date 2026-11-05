"""Chennai 2011 urban ward healthcare-priority dashboard."""
from pathlib import Path
import pandas as pd
import streamlit as st


def render_chennai_wards(data_root: Path, read_csv, read_geo, map_priority):
    data_dir = Path(data_root) / "chennai"
    scores_path = data_dir / "chennai_final_ward_analytical_dataset.csv"
    geo_path = data_dir / "chennai_final_healthcare_priority.gpkg"
    facilities_path = data_dir / "healthcare_facilities_beds_geocoded.csv"

    required = [scores_path, geo_path, facilities_path]
    missing = [p.name for p in required if not p.exists()]
    if missing:
        st.error("Chennai integration files are missing: " + ", ".join(missing))
        return

    try:
        scores = read_csv(str(scores_path))
        wards = read_geo(str(geo_path), layer="final_ward_priority")
        facilities = read_csv(str(facilities_path))

        if "admin_unit_id" not in scores or "admin_unit_id" not in wards:
            raise ValueError("The Chennai ward ID field 'admin_unit_id' is missing.")
        scores["admin_unit_id"] = scores["admin_unit_id"].astype(str).str.strip()
        wards["admin_unit_id"] = wards["admin_unit_id"].astype(str).str.strip()

        if scores["admin_unit_id"].duplicated().any():
            raise ValueError("Duplicate ward IDs were found in the Chennai analytical CSV.")
        if wards["admin_unit_id"].duplicated().any():
            raise ValueError("Duplicate ward IDs were found in the Chennai GeoPackage.")
        if set(scores["admin_unit_id"]) != set(wards["admin_unit_id"]):
            raise ValueError("Ward IDs in the Chennai CSV and GeoPackage do not match.")

        numeric_fields = [
            "total_population", "total_households", "area_sq_km",
            "total_healthcare_facilities", "public_facilities", "private_facilities",
            "hospital_records", "public_hospitals", "private_hospitals",
            "total_hospital_beds", "public_hospital_beds", "private_hospital_beds",
            "nearest_hospital_distance_km", "nearest_public_hospital_distance_km",
            "distance_score", "population_score", "combined_availability_gap",
            "public_gap_score", "socioeconomic_vulnerability_score",
            "priority_score", "priority_rank", "priority_percentile",
            "per_capita_income_2012_inr", "hospital_count_per_10000",
            "hospital_beds_per_10000",
        ]
        for frame in (scores, wards):
            for col in numeric_fields:
                if col in frame.columns:
                    frame[col] = pd.to_numeric(frame[col], errors="coerce")

        # Chennai's source model stores normalized scores on 0-1.
        # Convert score fields to the same 0-100 display scale used by Lucknow
        # and the other city dashboards. Distances, populations, counts and beds
        # remain in their original units.
        score_fields = [
            "distance_score",
            "population_score",
            "combined_availability_gap",
            "public_gap_score",
            "socioeconomic_vulnerability_score",
            "priority_score",
        ]
        for frame in (scores, wards):
            for col in score_fields:
                if col in frame.columns:
                    frame[col] = frame[col] * 100

        for col in ("latitude", "longitude", "beds_total"):
            if col in facilities.columns:
                facilities[col] = pd.to_numeric(facilities[col], errors="coerce")
        facilities = facilities.dropna(subset=["latitude", "longitude"]).copy()
    except Exception as exc:
        st.error("Chennai data could not be loaded or validated.")
        st.exception(exc)
        return

    tier_col, score_col, rank_col = "priority_tier", "priority_score", "priority_rank"
    st.header("Chennai healthcare access and ward priority")
    st.caption(
        "Urban analysis of 155 Census 2011 wards using the completed Chennai ward-priority "
        "dataset. The original ward scores and boundaries are displayed without recalculating the model."
    )

    f1, f2, f3 = st.columns(3)
    tier_values = ["Very High Priority", "High Priority", "Moderate Priority",
                   "Low-Moderate Priority", "Low Priority"]
    tier_options = ["All tiers"] + [t for t in tier_values if t in set(wards[tier_col].dropna())]
    selected_tier = f1.selectbox("Priority tier", tier_options, key="chennai_tier")
    zone_col = "zone_name" if "zone_name" in wards.columns else "gcc_zone_2008"
    zone_values = sorted(wards[zone_col].dropna().astype(str).unique()) if zone_col in wards.columns else []
    selected_zone = f2.selectbox("GCC zone", ["All zones"] + zone_values, key="chennai_zone")
    color_options = [
        "Model priority tier", "Model priority score",
        "Distance/accessibility score", "Population score",
        "Combined availability gap", "Public healthcare gap",
        "Socioeconomic vulnerability", "Nearest hospital distance (km)",
        "Nearest public hospital distance (km)", "Healthcare facility records",
        "Reported hospital beds", "Census 2011 population",
    ]
    selected_color = f3.selectbox("Color map by", color_options, key="chennai_color")

    show_facilities = st.checkbox(
        "Show healthcare facility markers", value=True, key="chennai_show_facilities"
    )
    facility_type = st.selectbox(
        "Facility markers", ["All facilities", "Public only", "Private only"],
        key="chennai_facility_type"
    )
    marker_data = facilities.copy()
    if facility_type != "All facilities" and "ownership" in marker_data.columns:
        wanted = "public" if facility_type == "Public only" else "private"
        marker_data = marker_data[
            marker_data["ownership"].astype(str).str.strip().str.lower().eq(wanted)
        ]

    view = wards.copy()
    if selected_tier != "All tiers":
        view = view[view[tier_col].astype(str) == selected_tier]
    if selected_zone != "All zones" and zone_col in view.columns:
        view = view[view[zone_col].astype(str) == selected_zone]

    component_map = {
        "Distance/accessibility score": "distance_score",
        "Population score": "population_score",
        "Combined availability gap": "combined_availability_gap",
        "Public healthcare gap": "public_gap_score",
        "Socioeconomic vulnerability": "socioeconomic_vulnerability_score",
        "Nearest hospital distance (km)": "nearest_hospital_distance_km",
        "Nearest public hospital distance (km)": "nearest_public_hospital_distance_km",
        "Healthcare facility records": "total_healthcare_facilities",
        "Reported hospital beds": "total_hospital_beds",
        "Census 2011 population": "total_population",
    }
    popup_fields = [
        "ward_display_name", "admin_unit_name", "ward_no", "zone_name",
        "total_population", "total_households", "area_sq_km",
        "total_healthcare_facilities", "public_facilities", "private_facilities",
        "hospital_records", "public_hospitals", "private_hospitals",
        "total_hospital_beds", "public_hospital_beds", "private_hospital_beds",
        "nearest_hospital_distance_km", "nearest_public_hospital_distance_km",
        "distance_score", "population_score", "combined_availability_gap",
        "public_gap_score", "socioeconomic_vulnerability_score",
        "priority_score", "priority_rank", "priority_tier",
    ]
    aliases = {
        "ward_display_name": "Ward",
        "admin_unit_name": "Census ward name",
        "ward_no": "Ward number",
        "zone_name": "GCC zone",
        "total_population": "Census 2011 population",
        "total_households": "Census 2011 households",
        "area_sq_km": "Area (sq. km)",
        "total_healthcare_facilities": "Healthcare facility records",
        "public_facilities": "Public facility records",
        "private_facilities": "Private facility records",
        "hospital_records": "Hospital records",
        "public_hospitals": "Public hospital records",
        "private_hospitals": "Private hospital records",
        "total_hospital_beds": "Reported hospital beds",
        "public_hospital_beds": "Public hospital beds",
        "private_hospital_beds": "Private hospital beds",
        "nearest_hospital_distance_km": "Nearest hospital distance (km; hybrid)",
        "nearest_public_hospital_distance_km": "Nearest public hospital distance (km; hybrid)",
        "distance_score": "Distance/accessibility score (0–100)",
        "population_score": "Population score (0–100)",
        "combined_availability_gap": "Combined availability gap (0–100)",
        "public_gap_score": "Public healthcare gap (0–100)",
        "socioeconomic_vulnerability_score": "Socioeconomic vulnerability (0–100)",
        "priority_score": "Priority score (0–100)",
        "priority_rank": "Priority rank",
        "priority_tier": "Priority tier",
    }

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Wards in view", f"{len(view):,} / 155")
    k2.metric("Population represented", f"{pd.to_numeric(view['total_population'], errors='coerce').sum():,.0f}")
    k3.metric("Facility records in input", f"{len(marker_data):,}")
    beds_col = "total_hospital_beds" if "total_hospital_beds" in view.columns else None
    k4.metric("Reported hospital beds", f"{pd.to_numeric(view[beds_col], errors='coerce').sum():,.0f}" if beds_col else "Not available")

    st.subheader("Ward priority map")
    map_priority(
        view, "Chennai ward priority", selected_color, tier_col, score_col,
        component_map, popup_fields, aliases, "OpenStreetMap",
        marker_data, show_facilities, False,
        "All hospitals" if facility_type == "All facilities" else facility_type,
        marker_label="healthcare facility", map_key="chennai_ward_priority_map",
    )

    st.subheader("Ward priority ranking")
    table_fields = [
        "priority_rank", "ward_display_name", "ward_no", "zone_name",
        "total_population", "total_healthcare_facilities", "public_facilities",
        "private_facilities", "total_hospital_beds",
        "nearest_hospital_distance_km", "nearest_public_hospital_distance_km",
        "distance_score", "population_score", "combined_availability_gap",
        "public_gap_score", "socioeconomic_vulnerability_score",
        "priority_score", "priority_tier",
    ]
    table_fields = [c for c in table_fields if c in view.columns]
    table = view[table_fields].sort_values(rank_col) if not view.empty else view[table_fields]
    st.dataframe(table, width="stretch", hide_index=True)
    st.download_button(
        "Download Chennai ward priority (CSV)",
        table.to_csv(index=False).encode("utf-8"),
        "chennai_ward_priority_filtered.csv",
        "text/csv",
    )

    with st.expander("Methodology and interpretation"):
        st.markdown("""
- **Geographic units:** 155 urban wards represented by the supplied Census 2011 ward boundaries.
- **Priority formula:** `0.25 × distance + 0.15 × population + 0.35 × availability gap + 0.10 × public healthcare gap + 0.15 × socioeconomic vulnerability`. All component scores and the final priority score are displayed on a 0–100 scale.
- **Score scale:** component scores and the final priority score are normalized from 0 to 100. Priority tiers divide the 155 wards into five equal, rank-based groups; they are relative screening categories, not validated clinical-need classes.
- **Distance:** the supplied nearest-hospital distance uses the road network where reachable and a straight-line fallback for disconnected wards. It is a hybrid distance measure, not travel time.
- **Public healthcare gap:** a ward with no public hospital physically inside its boundary can still have a nearby public hospital. The nearest-public-hospital distance is shown separately.
- **Facility inventory:** markers show the supplied coordinate-complete facility records. A missing local record should not be interpreted as proof that no facility exists.
- **Socioeconomic factor:** income-derived vulnerability is a proxy, not an official poverty classification.
""")
    st.caption(
        "Chennai's original analytical outputs are retained. Priority scores are intended for within-Chennai "
        "screening and should not be interpreted as directly comparable with another city's raw scores."
    )


def render_chennai_settlements(data_root: Path, read_csv, read_geo, map_priority):
    """Render the 202-settlement Model C analysis and supplied thematic outputs."""
    import streamlit.components.v1 as components

    data_dir = Path(data_root) / "chennai" / "settlements"
    city_data_dir = Path(data_root) / "chennai"
    csv_path = data_dir / "chennai_settlement_priority.csv"
    gpkg_path = data_dir / "chennai_settlement_priority.gpkg"
    facilities_path = city_data_dir / "healthcare_facilities_beds_geocoded.csv"
    if not csv_path.exists() or not gpkg_path.exists():
        st.error("The Chennai settlement priority CSV or GeoPackage is missing.")
        return
    if not facilities_path.exists():
        st.error("The Chennai healthcare facility inventory is missing; hospital markers cannot be displayed.")
        return

    try:
        scores = read_csv(str(csv_path))
        areas = read_geo(str(gpkg_path), layer="settlement_priority")
        facilities = read_csv(str(facilities_path))
        for col in ("latitude", "longitude", "beds_total"):
            if col in facilities.columns:
                facilities[col] = pd.to_numeric(facilities[col], errors="coerce")
        facilities = facilities.dropna(subset=["latitude", "longitude"]).copy()
        facilities = facilities[
            facilities["latitude"].between(-90, 90) &
            facilities["longitude"].between(-180, 180)
        ].copy()
        if "admin_unit_id" not in scores or "admin_unit_id" not in areas:
            raise ValueError("Settlement ID field 'admin_unit_id' is missing.")
        scores["admin_unit_id"] = scores["admin_unit_id"].astype(str).str.strip()
        areas["admin_unit_id"] = areas["admin_unit_id"].astype(str).str.strip()
        if scores["admin_unit_id"].duplicated().any() or areas["admin_unit_id"].duplicated().any():
            raise ValueError("Duplicate settlement IDs were found.")
        if set(scores["admin_unit_id"]) != set(areas["admin_unit_id"]):
            raise ValueError("Settlement IDs in the CSV and GeoPackage do not match.")
        # Use the spatial layer as the authoritative geometry + attribute source.
        # The CSV is retained for direct tabular download and cross-validation.
        numeric_cols = [
            "total_population", "total_households", "area_sq_km", "total_facilities",
            "public_facilities", "private_facilities", "hospital_facilities",
            "primary_community_centres", "other_facilities", "total_beds",
            "public_beds", "private_beds", "facilities_per_10000",
            "beds_per_10000", "all_distance_km", "public_distance_km",
            "private_distance_km", "distance_score", "local_hospital_gap_score",
            "per_capita_income_constant_2011_12",
            "socioeconomic_vulnerability_score", "priority_score", "priority_rank"
        ]
        for col in numeric_cols:
            if col in areas.columns:
                areas[col] = pd.to_numeric(areas[col], errors="coerce")
            if col in scores.columns:
                scores[col] = pd.to_numeric(scores[col], errors="coerce")
        if len(areas) != 202:
            st.warning(f"Expected 202 settlement polygons; the supplied GeoPackage contains {len(areas)}.")
        if areas["priority_score"].isna().any():
            raise ValueError("Priority scores contain missing values.")
    except Exception as exc:
        st.exception(exc)
        return

    st.header("Chennai healthcare access and settlement priority")
    st.caption(
        "Settlement-level Model C analysis across the 202 supplied towns, villages and outgrowths. "
        "This is separate from the retained 155-ward analysis."
    )

    f1, f2, f3 = st.columns(3)
    districts = ["All districts"] + sorted(areas["district"].dropna().astype(str).unique())
    types = ["All settlement types"] + sorted(areas["admin_unit_type"].dropna().astype(str).unique())
    tiers = ["All tiers"] + [t for t in ["Very High", "High", "Moderate", "Lower"]
                              if t in set(areas["priority_tier"].dropna().astype(str))]
    district = f1.selectbox("District", districts, key="chn_set_district")
    unit_type = f2.selectbox("Settlement type", types, key="chn_set_type")
    tier = f3.selectbox("Priority tier", tiers, key="chn_set_tier")

    view = areas.copy()
    if district != "All districts":
        view = view[view["district"].astype(str) == district]
    if unit_type != "All settlement types":
        view = view[view["admin_unit_type"].astype(str) == unit_type]
    if tier != "All tiers":
        view = view[view["priority_tier"].astype(str) == tier]

    total_pop = pd.to_numeric(view["total_population"], errors="coerce").sum()
    total_fac = pd.to_numeric(view["total_facilities"], errors="coerce").sum()
    total_beds = pd.to_numeric(view["total_beds"], errors="coerce").sum()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Settlements in view", f"{len(view):,}")
    k2.metric("Population represented", f"{total_pop:,.0f}")
    k3.metric("Local healthcare facilities", f"{total_fac:,.0f}")
    k4.metric("Reported beds assigned locally", f"{total_beds:,.0f}")

    color_options = [
        "Model priority tier", "Model priority score",
        "Distance/accessibility score", "Local hospital gap score",
        "Socioeconomic vulnerability", "Nearest healthcare facility distance (km)",
        "Local hospital facilities", "Healthcare facilities per 10,000",
        "Reported beds", "Census 2011 population"
    ]
    component_map = {
        "Distance/accessibility score": "distance_score",
        "Local hospital gap score": "local_hospital_gap_score",
        "Socioeconomic vulnerability": "socioeconomic_vulnerability_score",
        "Nearest healthcare facility distance (km)": "all_distance_km",
        "Local hospital facilities": "hospital_facilities",
        "Healthcare facilities per 10,000": "facilities_per_10000",
        "Reported beds": "total_beds",
        "Census 2011 population": "total_population",
    }
    aliases = {
        "admin_unit_name": "Settlement", "admin_unit_type": "Settlement type",
        "district": "District", "total_population": "Census 2011 population",
        "total_households": "Households", "area_sq_km": "Area (sq. km)",
        "total_facilities": "All local healthcare facilities",
        "hospital_facilities": "Local hospital facilities",
        "primary_community_centres": "Primary/community centres",
        "total_beds": "Reported beds assigned locally",
        "all_distance_km": "Nearest healthcare facility distance (km)",
        "all_distance_method": "Distance method",
        "all_nearest_facility_name": "Nearest healthcare facility",
        "distance_score": "Distance/accessibility disadvantage (0–100)",
        "local_hospital_gap_score": "Local hospital gap (0–100)",
        "per_capita_income_constant_2011_12": "Per-capita income (2011–12 prices)",
        "socioeconomic_vulnerability_score": "Income-derived socioeconomic vulnerability (0–100)",
        "socioeconomic_factor_level": "Socioeconomic data resolution",
        "priority_score": "Model C priority score (0–100)",
        "priority_rank": "Model C rank", "priority_tier": "Priority tier",
        "public_distance_km": "Nearest public facility distance (km)",
        "private_distance_km": "Nearest private facility distance (km)",
    }
    c1, c2, c3, c4 = st.columns([1.2, 1, 1.2, 1.5])
    color = c1.selectbox("Map colour", color_options, index=0, key="chn_set_color")
    show_facilities = c2.checkbox(
        "Show hospital markers", value=True, key="chn_set_show_facilities"
    )
    facility_type = c3.selectbox(
        "Facility markers", ["All facilities", "Public only", "Private only"],
        key="chn_set_facility_type"
    )
    show_facility_note = c4.checkbox(
        "Show interpretation notes", value=True, key="chn_set_notes"
    )

    # Keep point markers consistent with the selected district. When all
    # districts are shown, display the complete coordinate-verified inventory.
    marker_data = facilities.copy()
    if district != "All districts" and "district" in marker_data.columns:
        marker_data = marker_data[
            marker_data["district"].astype(str).str.strip().str.casefold()
            == district.strip().casefold()
        ]
    if facility_type == "Public only":
        marker_data = marker_data[
            marker_data["ownership"].astype(str).str.strip().str.casefold().eq("public")
        ]
    elif facility_type == "Private only":
        marker_data = marker_data[
            marker_data["ownership"].astype(str).str.strip().str.casefold().eq("private")
        ]

    popup_fields = [
        "admin_unit_name", "admin_unit_type", "district", "total_population",
        "total_households", "total_facilities", "hospital_facilities",
        "primary_community_centres", "total_beds", "all_distance_km",
        "all_distance_method", "all_nearest_facility_name", "public_distance_km",
        "private_distance_km", "distance_score", "local_hospital_gap_score",
        "per_capita_income_constant_2011_12", "socioeconomic_vulnerability_score",
        "socioeconomic_factor_level", "priority_score", "priority_rank", "priority_tier"
    ]
    map_priority(
        view, "Chennai settlement priority", color, "priority_tier", "priority_score",
        component_map, popup_fields, aliases, "OpenStreetMap",
        marker_data, show_facilities, False,
        "All hospitals" if facility_type == "All facilities" else facility_type,
        marker_label="healthcare facility", map_key="chennai_settlement_priority_map"
    )

    st.subheader("Settlement priority ranking")
    table_cols = [
        "priority_rank", "admin_unit_name", "admin_unit_type", "district",
        "total_population", "hospital_facilities", "total_beds", "all_distance_km",
        "distance_score", "local_hospital_gap_score",
        "socioeconomic_vulnerability_score", "priority_score", "priority_tier"
    ]
    table_cols = [c for c in table_cols if c in view.columns]
    ranking = view[table_cols].sort_values("priority_rank") if not view.empty else view[table_cols]
    st.dataframe(ranking, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered settlement ranking (CSV)",
        ranking.to_csv(index=False).encode("utf-8"),
        "chennai_settlement_priority_filtered.csv", "text/csv"
    )
    st.download_button(
        "Download complete settlement dataset (CSV)",
        scores.to_csv(index=False).encode("utf-8"),
        "chennai_settlement_priority_all.csv", "text/csv"
    )

    st.subheader("Thematic maps")
    map_files = [
        ("Overall settlement priority", "chennai_overall_priority_map.png"),
        ("Healthcare distance/accessibility", "chennai_healthcare_distance_map.png"),
        ("Local hospital availability", "chennai_local_hospital_availability_map.png"),
        ("Socioeconomic vulnerability", "chennai_socioeconomic_vulnerability_map.png"),
    ]
    cols = st.columns(2)
    for i, (label, filename) in enumerate(map_files):
        path = data_dir / "maps" / filename
        with cols[i % 2]:
            st.markdown(f"**{label}**")
            if path.exists():
                st.image(str(path), use_container_width=True)
            else:
                st.warning(f"Map image not found: {filename}")

    html_path = data_dir / "interactive" / "chennai_interactive_accessibility_map.html"
    st.subheader("Full interactive accessibility map")
    if html_path.exists():
        with st.expander("Open interactive map", expanded=False):
            components.html(html_path.read_text(encoding="utf-8"), height=760, scrolling=True)
    else:
        st.warning("The supplied interactive HTML map is missing.")

    if show_facility_note:
        st.info(
            "Methodological notes: the distance input is distance to the nearest healthcare facility "
            "of any type, not exclusively a hospital. Four settlements use straight-line fallback "
            "distances where a directed road-network route was unavailable. Local facility and bed "
            "counts include coordinate-matched facilities spatially assigned within settlement "
            "polygons; facilities without coordinates cannot contribute to those local counts. "
            "Income vulnerability is a district-level proxy, so settlements in the same district "
            "share the same socioeconomic score. Priority tiers are relative screening categories, "
            "not validated clinical-need classifications."
        )


def render_chennai(data_root: Path, read_csv, read_geo, map_priority):
    st.header("Chennai healthcare analysis")
    analysis = st.radio(
        "Choose analysis level",
        ["Settlement-level (202 units)", "Ward-level (155 wards)"],
        horizontal=True, key="chennai_analysis_level_selector"
    )
    if analysis.startswith("Settlement"):
        render_chennai_settlements(data_root, read_csv, read_geo, map_priority)
    else:
        render_chennai_wards(data_root, read_csv, read_geo, map_priority)
