from pathlib import Path
import json
import pandas as pd
import geopandas as gpd
import streamlit as st
import folium
from folium.plugins import MarkerCluster, FastMarkerCluster, Fullscreen
from streamlit_folium import st_folium

st.set_page_config(page_title="Healthcare Access & Priority Explorer", page_icon="🏥", layout="wide")
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CSV = DATA / "lucknow_healthcare_dashboard_data.csv"
HOSPITALS = DATA / "lucknow_hospital_master_cleaned.csv"
URBAN_GPKG = DATA / "lucknow_map_boundaries_with_demographics.gpkg"
URBAN_SUMMARY = DATA / "lucknow_urban_ward_healthcare_summary.csv"
URBAN_ASSIGNMENTS = DATA / "lucknow_urban_hospital_assignments.csv"
URBAN_PRIORITY_C = DATA / "lucknow_urban_healthcare_priority_scores_model_c.csv"
DISTRICT_MODEL_C_GPKG = DATA / "lucknow_settlement_priority_model_c.gpkg"

TIER_COLORS = {"Very High": "#b2182b", "High": "#ef8a62", "Moderate": "#fddbc7", "Lower": "#67a9cf"}
CONTINUOUS_COLORS = ["#d1e5f0", "#fddbc7", "#ef8a62", "#b2182b"]
BANDS = ["Any", "0–25 (lower)", "25–50", "50–75", "75–100 (higher)"]
BAND_LIMITS = {"Any": (None, None), "0–25 (lower)": (0, 25), "25–50": (25, 50), "50–75": (50, 75), "75–100 (higher)": (75, 100)}

@st.cache_data
def read_csv(path):
    return pd.read_csv(path)

@st.cache_data
def read_geo(path, layer=None):
    g = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
    if g.crs is not None:
        g = g.to_crs("EPSG:4326")
    return g

def numeric(df, columns):
    for c in columns:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def apply_band(df, column, selected_band):
    if selected_band == "Any" or column not in df.columns:
        return df
    lo, hi = BAND_LIMITS[selected_band]
    vals = pd.to_numeric(df[column], errors="coerce")
    # Include missing values only when no filter is applied; selecting a band requires a known value.
    return df[vals.ge(lo) & vals.le(hi)]

def add_basemap(m, name):
    if name == "Esri World Street Map":
        folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", attr="Tiles © Esri", name=name, overlay=False).add_to(m)
    else:
        folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)

def continuous_color(value, low, high):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "#d9d9d9"
    if pd.isna(v):
        return "#d9d9d9"
    if high <= low:
        ratio = 0.5
    else:
        ratio = max(0.0, min(1.0, (v - low) / (high - low)))
    return "#d1e5f0" if ratio < .25 else "#fddbc7" if ratio < .5 else "#ef8a62" if ratio < .75 else "#b2182b"

def add_hospital_markers(m, hospitals, ownership_filter="All hospitals", district_only=False, marker_label="hospital"):
    """Add facility points efficiently using browser-side clustering."""
    if hospitals.empty or not {"latitude", "longitude"}.issubset(hospitals.columns):
        return

    h = hospitals.copy()
    if district_only and "inside_lucknow_district" in h.columns:
        h = h[h["inside_lucknow_district"].astype(str).str.lower().isin(["true", "1", "yes"])]

    h["latitude"] = pd.to_numeric(h["latitude"], errors="coerce")
    h["longitude"] = pd.to_numeric(h["longitude"], errors="coerce")
    h = h.dropna(subset=["latitude", "longitude"])
    h = h[
        h["latitude"].between(-90, 90) &
        h["longitude"].between(-180, 180)
    ].copy()

    if "ownership" not in h.columns:
        h["ownership"] = "unknown"
    h["ownership_norm"] = h["ownership"].astype(str).str.strip().str.lower()

    if ownership_filter == "Public only":
        h = h[h["ownership_norm"].eq("public")]
    elif ownership_filter == "Private only":
        h = h[h["ownership_norm"].eq("private")]

    groups = [
        ("Public", "public", "#2878b5"),
        ("Private", "private", "#e67e22"),
        ("Other / unspecified", "unknown", "#777777"),
    ]

    def safe_value(row, candidates, default="Not recorded"):
        for col in candidates:
            if col in row.index and pd.notna(row[col]) and str(row[col]).strip():
                return str(row[col]).strip()
        return default

    for label, ownership, color in groups:
        subset = h[h["ownership_norm"].eq(ownership)]
        if subset.empty:
            continue

        rows = []
        for _, r in subset.iterrows():
            lat = float(r["latitude"])
            lon = float(r["longitude"])
            name = safe_value(r, ["facility_name", "Establishment Name", "establishment_name"], "Healthcare facility")
            facility_type = safe_value(r, ["facility_type_group", "facility_type"], "")
            beds = safe_value(r, ["beds", "beds_total", "No. of Beds"])
            address = safe_value(r, ["address"], "")
            rows.append([lat, lon, name, facility_type, beds, address])

        # Data and popup construction are handled client-side. This keeps the
        # serialized Folium document compact even for inventories with 1,000+ points.
        callback = f"""
        function(row) {{
            function esc(value) {{
                return String(value == null ? '' : value).replace(/[&<>\"']/g, function(ch) {{
                    return {{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}}[ch];
                }});
            }}
            var marker = L.circleMarker([row[0], row[1]], {{
                radius: 5,
                color: '{color}',
                weight: 1,
                fillColor: '{color}',
                fillOpacity: 0.9
            }});
            var title = esc(row[2]);
            var type = esc(row[3]);
            var beds = esc(row[4]);
            var address = esc(row[5]);
            marker.bindTooltip(title);
            marker.bindPopup(
                '<b>' + title + '</b><br>Ownership: {ownership.title()}' +
                (type ? '<br>Type: ' + type : '') +
                '<br>Reported beds: ' + beds +
                (address ? '<br>Address: ' + address : '')
            );
            return marker;
        }}
        """
        FastMarkerCluster(
            data=rows,
            callback=callback,
            name=f"{label} {marker_label}s",
            options={"maxClusterRadius": 45}
        ).add_to(m)

    legend = (
        f'<div style="position:fixed;bottom:24px;right:24px;z-index:9999;'
        f'background:white;padding:9px 12px;border:1px solid #aaa;'
        f'border-radius:4px;color:#222;font-size:13px">'
        f'<b>Facility ownership</b><br>'
        f'<span style="color:#2878b5">●</span> Public {marker_label}<br>'
        f'<span style="color:#e67e22">●</span> Private {marker_label}</div>'
    )
    m.get_root().html.add_child(folium.Element(legend))

def map_priority(gdf, layer_name, color_mode, tier_col, score_col, component_map, popup_fields, aliases, basemap, hospital_data=None, show_hospitals=False, district_hospitals_only=False, hospital_ownership_filter="All hospitals", marker_label="hospital", map_key=None):
    if gdf.empty:
        st.info("No areas match the selected filters.")
        return
    g = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    if g.empty:
        st.info("No mapped polygons remain after filtering.")
        return
    center = g.geometry.union_all().centroid
    m = folium.Map(location=[center.y, center.x], zoom_start=9 if len(g) > 150 else 11, tiles=None, control_scale=True, prefer_canvas=True)

    # Add a full-screen control inside the map's top-right corner.
    # Users can exit full screen with Esc or the same control.
    Fullscreen(
        position="topright",
        title="Enter full screen",
        title_cancel="Exit full screen",
        force_separate_button=True
    ).add_to(m)

    add_basemap(m, basemap)
    component_col = component_map.get(color_mode)
    active_col = tier_col if color_mode.endswith("priority tier") else score_col if color_mode.endswith("priority score") else component_col
    vals = pd.to_numeric(g[active_col], errors="coerce") if active_col and active_col in g.columns else pd.Series(dtype=float)
    lo = float(vals.min()) if vals.notna().any() else 0
    hi = float(vals.max()) if vals.notna().any() else 100
    def style(feature):
        props = feature["properties"]
        if color_mode.endswith("priority tier"):
            tier_palette = {
                **TIER_COLORS,
                "Very High Priority": "#b2182b",
                "High Priority": "#ef8a62",
                "Moderate Priority": "#fddbc7",
                "Low-Moderate Priority": "#67a9cf",
                "Low Priority": "#2166ac",
            }
            fill = tier_palette.get(str(props.get(tier_col)), "#d9d9d9")
        else:
            fill = continuous_color(props.get(active_col), lo, hi)
        return {"fillColor": fill, "color": "#ffffff" if len(g) > 200 else "#4a4a4a", "weight": .35 if len(g) > 200 else .8, "fillOpacity": .78}
    fields = [c for c in popup_fields if c in g.columns]
    folium.GeoJson(g[fields + ["geometry"]].to_json(), name=layer_name, style_function=style,
        tooltip=folium.GeoJsonTooltip(fields=fields[:3] if fields else [], aliases=[aliases.get(c,c) for c in fields[:3]] if fields else []),
        popup=folium.GeoJsonPopup(fields=fields, aliases=[aliases.get(c,c) for c in fields], localize=True, max_width=430)).add_to(m)
    if color_mode.endswith("priority tier"):
        legend = '<div style="position:fixed;bottom:24px;left:24px;z-index:9999;background:white;padding:10px 12px;border:1px solid #aaa;border-radius:4px;color:#222;font-size:13px"><b>Relative priority</b><br>'
        for tier, color in TIER_COLORS.items():
            legend += f'<span style="color:{color}">■</span> {tier}<br>'
        legend += '</div>'
        m.get_root().html.add_child(folium.Element(legend))
    elif vals.notna().any():
        folium.LinearColormap(CONTINUOUS_COLORS, vmin=lo, vmax=hi if hi > lo else lo + 1, caption=color_mode).add_to(m)
    if show_hospitals and hospital_data is not None:
        add_hospital_markers(m, hospital_data, ownership_filter=hospital_ownership_filter, district_only=district_hospitals_only, marker_label=marker_label)
    folium.LayerControl(collapsed=True).add_to(m)
    # A stable, city-specific key prevents Streamlit component identity collisions
    # when switching between city dashboards that share this renderer.
    component_key = map_key or f"priority_map_{layer_name.lower().replace(' ', '_')}"
    st_folium(m, key=component_key, use_container_width=True, height=660, returned_objects=[])

# City selection / extensible city registry
CITY_REGISTRY_PATH = ROOT / "cities.json"
DEFAULT_CITY_REGISTRY = {
    "cities": [
        {"id": "lucknow", "name": "Lucknow", "status": "ready", "description": "District settlements and urban wards"},
        {"id": "delhi", "name": "Delhi", "status": "setup", "description": "District-level healthcare access analysis"}
    ]
}
if CITY_REGISTRY_PATH.exists():
    try:
        city_registry = json.loads(CITY_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        city_registry = DEFAULT_CITY_REGISTRY
else:
    city_registry = DEFAULT_CITY_REGISTRY

cities = city_registry.get("cities", DEFAULT_CITY_REGISTRY["cities"])
city_names = {city["name"]: city for city in cities}
CITY_PLACEHOLDER = "— Select a city —"
st.title("Healthcare Access & Priority Explorer")
st.caption("Select a city to explore healthcare access and underserved-area priorities. More cities can be added through the city registry and a city-specific data module.")
selected_city = st.selectbox("Choose a city to continue", [CITY_PLACEHOLDER] + list(city_names.keys()), index=0, key="selected_city")

if selected_city == CITY_PLACEHOLDER:
    st.stop()


# ---------------------------------------------------------
# CITY-WISE WORD REPORT DOWNLOAD
# ---------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def build_city_report_bytes(city_id, data_directory):
    """Generate and cache a city-specific healthcare analysis report."""
    import tempfile

    from report_generator.data_preparation import prepare_city_report_data
    from report_generator.groq_analysis import generate_city_analysis
    from report_generator.document_generator import generate_city_report

    city_data = prepare_city_report_data(
        city_id,
        data_dir=data_directory
    )

    analysis = generate_city_analysis(city_data)

    with tempfile.TemporaryDirectory() as temp_directory:
        output_path = Path(temp_directory) / f"{city_id}_healthcare_analysis_report.docx"

        generate_city_report(
            city_data,
            analysis,
            output_path=str(output_path)
        )

        return output_path.read_bytes()


selected_city_id = city_names[selected_city].get("id", "").strip().lower()
report_session_key = f"healthcare_report_bytes_{selected_city_id}"
report_filename = f"{selected_city_id}_healthcare_analysis_report.docx"

st.divider()

with st.expander("Download Healthcare Analysis Report", expanded=False):
    st.write(
        f"Generate a city-specific Word report for **{selected_city}**, "
        "including priority maps, quantitative summaries, key findings, "
        "planning recommendations and final interpretations."
    )

    if st.button(
        "Generate Report",
        key=f"generate_healthcare_report_{selected_city_id}",
        type="primary"
    ):
        try:
            with st.spinner(
                f"Generating the {selected_city} healthcare analysis report. "
                "This may take a little time..."
            ):
                report_bytes = build_city_report_bytes(
                    selected_city_id,
                    str(DATA)
                )

            st.session_state[report_session_key] = report_bytes
            st.success("Your report has been generated successfully.")

        except Exception as error:
            st.error("The report could not be generated.")
            st.exception(error)

    if report_session_key in st.session_state:
        st.download_button(
            label="Download Word Report (.docx)",
            data=st.session_state[report_session_key],
            file_name=report_filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f"download_healthcare_report_{selected_city_id}"
        )

st.divider()

if city_names[selected_city].get("id") == "delhi":
    from cities.delhi import render_delhi
    render_delhi(DATA, read_csv, read_geo, map_priority)
    st.stop()

if city_names[selected_city].get("id") == "chennai":
    from cities.chennai import render_chennai
    render_chennai(DATA, read_csv, read_geo, map_priority)
    st.stop()

if city_names[selected_city].get("id") == "mumbai":
    st.header("Mumbai healthcare access and priority")
    st.caption("District-level and ward-level screening using Model C weights; per-capita income is the socioeconomic factor.")
    md = DATA / "mumbai"
    try:
        mumbai = read_geo(str(md / "mumbai_ward_priority.gpkg"), layer="mumbai_ward_priority")
        mumbai_districts = read_geo(str(md / "mumbai_district_priority.gpkg"), layer="mumbai_district_priority")
        mhosp = read_csv(str(md / "mumbai_healthcare_facilities.csv"))
        for frame in [mumbai, mumbai_districts]:
            for c in ["total_population", "district_population", "hospital_records", "public_hospitals", "private_hospitals", "beds_total", "nearest_hospital_distance_km", "distance_score", "population_score", "combined_availability_gap", "public_gap_score", "socioeconomic_vulnerability_score", "priority_score_model_c", "priority_rank_model_c", "per_capita_income_2012_inr"]:
                if c in frame.columns:
                    frame[c] = pd.to_numeric(frame[c], errors="coerce")
        for c in ["latitude", "longitude", "beds_total"]:
            if c in mhosp.columns:
                mhosp[c] = pd.to_numeric(mhosp[c], errors="coerce")
    except Exception as e:
        st.exception(e)
        st.stop()
    analysis_level = st.radio("Analysis level", ["District-level priority", "Ward-level priority"], horizontal=True, key="mumbai_analysis_level")
    m_color_options = ["Model priority tier", "Model priority score", "Distance/accessibility score", "Population score", "Combined availability gap", "Public healthcare gap", "Socioeconomic vulnerability", "Per-capita income (2012 INR)", "Nearest hospital distance (km)", "Hospital records", "Reported beds"]
    component_map = {"Distance/accessibility score":"distance_score", "Population score":"population_score", "Combined availability gap":"combined_availability_gap", "Public healthcare gap":"public_gap_score", "Socioeconomic vulnerability":"socioeconomic_vulnerability_score", "Per-capita income (2012 INR)":"per_capita_income_2012_inr", "Nearest hospital distance (km)":"nearest_hospital_distance_km", "Hospital records":"hospital_records", "Reported beds":"beds_total", "Census 2011 population":"total_population", "District population":"district_population"}
    aliases = {"district_name":"District", "NAME2":"Census ward name", "ward_code":"Ward code", "TOT_POP":"Census 2011 population", "district_population":"Population represented", "total_population":"Census 2011 population", "per_capita_income_2012_inr":"Per-capita income (2012 INR)", "hospital_records":"Healthcare records", "public_hospitals":"Public healthcare records", "private_hospitals":"Private healthcare records", "beds_total":"Reported beds", "nearest_hospital_distance_km":"Nearest hospital distance (km; straight-line)", "distance_score":"Distance/accessibility score", "population_score":"Population score", "combined_availability_gap":"Combined availability gap", "public_gap_score":"Public healthcare gap", "socioeconomic_vulnerability_score":"Income-derived socioeconomic vulnerability", "priority_score_model_c":"Model C priority score", "priority_rank_model_c":"Priority rank", "priority_tier_model_c":"Priority tier", "ward_count":"Ward count"}
    mshow = st.checkbox("Show healthcare facility markers (records with coordinates only)", value=True, key="m_show_hospitals")
    mtype = st.selectbox("Facility markers", ["All facilities", "Public only", "Private only"], key="m_hospital_type")
    if mtype != "All facilities" and "ownership" in mhosp.columns:
        mhosp = mhosp[mhosp["ownership"].astype(str).str.lower().eq("public" if mtype == "Public only" else "private")]
    if analysis_level == "District-level priority":
        st.subheader("District-level priority map")
        st.caption("District polygons are dissolved from the 97 target ward polygons using the supplied Census ward-to-district crosswalk. The two-district priority comparison is relative to Mumbai and Mumbai Suburban.")
        f1, f2 = st.columns(2)
        tier_opts = ["All tiers"] + [t for t in ["Very High", "High", "Moderate", "Lower"] if t in set(mumbai_districts["priority_tier_model_c"].dropna())]
        m_tier = f1.selectbox("Priority tier", tier_opts, key="mumbai_d_tier")
        m_color = f2.selectbox("Color map by", m_color_options, key="mumbai_d_color")
        view = mumbai_districts.copy()
        if m_tier != "All tiers":
            view = view[view["priority_tier_model_c"] == m_tier]
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Districts in view", f"{len(view):,}")
        k2.metric("Population represented", f"{pd.to_numeric(view['district_population'], errors='coerce').sum():,.0f}")
        k3.metric("Healthcare records", f"{pd.to_numeric(view['hospital_records'], errors='coerce').sum():,.0f}")
        k4.metric("Reported beds", f"{pd.to_numeric(view['beds_total'], errors='coerce').sum():,.0f}")
        popup = ["district_name", "district_population", "ward_count", "hospital_records", "public_hospitals", "private_hospitals", "beds_total", "per_capita_income_2012_inr", "nearest_hospital_distance_km", "distance_score", "population_score", "combined_availability_gap", "public_gap_score", "socioeconomic_vulnerability_score", "priority_score_model_c", "priority_rank_model_c", "priority_tier_model_c"]
        map_priority(view, "Mumbai district priority", m_color, "priority_tier_model_c", "priority_score_model_c", component_map, popup, aliases, "OpenStreetMap", mhosp, mshow, hospital_ownership_filter=("All hospitals" if mtype == "All facilities" else mtype))
        st.subheader("District priority ranking")
        table_cols = [c for c in popup if c in view.columns]
        table = view[table_cols].sort_values("priority_rank_model_c") if not view.empty else view[table_cols]
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.download_button("Download Mumbai district priority (CSV)", table.to_csv(index=False).encode("utf-8"), "mumbai_district_priority.csv", "text/csv")
    else:
        st.subheader("Ward-level priority map")
        f1, f2, f3 = st.columns(3)
        tier_opts = ["All tiers"] + [t for t in ["Very High", "High", "Moderate", "Lower"] if t in set(mumbai["priority_tier_model_c"].dropna())]
        m_tier = f1.selectbox("Priority tier", tier_opts, key="mumbai_w_tier")
        district_opts = ["All districts"] + sorted(mumbai["DISTRICT"].dropna().astype(str).unique())
        m_district = f2.selectbox("District", district_opts, key="mumbai_w_district")
        m_color = f3.selectbox("Color map by", m_color_options + ["Census 2011 population"], key="mumbai_w_color")
        view = mumbai.copy()
        if m_tier != "All tiers":
            view = view[view["priority_tier_model_c"] == m_tier]
        if m_district != "All districts":
            view = view[view["DISTRICT"].astype(str) == m_district]
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Wards in view", f"{len(view):,}")
        k2.metric("Population represented", f"{pd.to_numeric(view.get('TOT_POP'), errors='coerce').sum():,.0f}")
        k3.metric("Healthcare records", f"{pd.to_numeric(view.get('hospital_records'), errors='coerce').sum():,.0f}")
        k4.metric("Reported beds", f"{pd.to_numeric(view.get('beds_total'), errors='coerce').sum():,.0f}")
        popup = ["NAME2", "ward_code", "DISTRICT", "TOT_POP", "per_capita_income_2012_inr", "hospital_records", "public_hospitals", "private_hospitals", "beds_total", "nearest_hospital_distance_km", "distance_score", "population_score", "combined_availability_gap", "public_gap_score", "socioeconomic_vulnerability_score", "priority_score_model_c", "priority_rank_model_c", "priority_tier_model_c"]
        map_priority(view, "Mumbai ward priority", m_color, "priority_tier_model_c", "priority_score_model_c", component_map, popup, aliases, "OpenStreetMap", mhosp, mshow, hospital_ownership_filter=("All hospitals" if mtype == "All facilities" else mtype))
        st.subheader("Ward priority ranking")
        table_cols = [c for c in popup if c in view.columns]
        table = view[table_cols].sort_values("priority_rank_model_c") if not view.empty else view[table_cols]
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.download_button("Download Mumbai ward priority (CSV)", table.to_csv(index=False).encode("utf-8"), "mumbai_ward_priority.csv", "text/csv")
    st.divider()
    st.caption("Priority tiers are relative screening categories, not validated clinical-need classes. Per-capita income is from 2012. Distances are straight-line estimates, not travel times. Facility markers show only records with usable coordinates.")
    st.stop()

if city_names[selected_city].get("id") != "lucknow":
    st.header(f"{selected_city} analysis")
    st.info("This city is registered but does not yet have a city-specific analysis module. Add its data and module to enable the dashboard.")
    st.stop()

# Validate core data inputs
required = [CSV, HOSPITALS, URBAN_GPKG, URBAN_SUMMARY, URBAN_PRIORITY_C]
missing = [p for p in required if not p.exists()]
if not DISTRICT_MODEL_C_GPKG.exists():
    missing.append(DISTRICT_MODEL_C_GPKG)
if missing:
    st.error("Some required data files are missing. Place the following files in the website's data/ folder:")
    for p in missing:
        st.code(p.name)
    st.stop()

try:
    settlements = read_csv(str(CSV))
    hospitals = read_csv(str(HOSPITALS))
    district = read_geo(str(DISTRICT_MODEL_C_GPKG), layer="settlement_priority_model_c")
    district = numeric(district, ["priority_score_model_c", "priority_rank_model_c", "distance_score", "local_hospital_gap_score", "socioeconomic_vulnerability_score", "population_corrected", "nearest_hospital_distance_km", "hospital_record_count", "public_hospital_records", "private_hospital_records", "total_reported_beds", "estimated_per_capita_income_2012_inr"])
    if "is_town" in district.columns:
        district["settlement_kind"] = district["is_town"].map({True: "Town", False: "Village"}).fillna("Unknown")
    urban = read_geo(str(URBAN_GPKG), layer="ward_demographics")
    urban_summary = read_csv(str(URBAN_SUMMARY))
    urban_c = read_csv(str(URBAN_PRIORITY_C))
    for frame in [urban, urban_summary, urban_c]:
        if "map_unit_id" in frame.columns:
            frame["map_unit_id"] = frame["map_unit_id"].astype(str).str.strip()
    urban = urban.merge(urban_summary, on="map_unit_id", how="left", suffixes=("", "_summary"))
    urban = urban.loc[:, ~urban.columns.duplicated()].copy()
    cols_c = [c for c in urban_c.columns if c == "map_unit_id" or c not in urban.columns]
    urban = urban.merge(urban_c[cols_c], on="map_unit_id", how="left", suffixes=("", "_c"))
    urban = urban.loc[:, ~urban.columns.duplicated()].copy()
    # The final Model CSV is authoritative for model fields, including the manually added Cantonment income.
    model_fields = ["map_unit_type", "per_capita_income_2012_inr", "socioeconomic_vulnerability_score", "priority_score_model_c", "priority_rank_model_c", "priority_tier_model_c", "socioeconomic_data_status", "socioeconomic_factor_level", "priority_model_version"]
    if "map_unit_id" in urban_c.columns:
        model_lookup = urban_c.set_index("map_unit_id")
        for field in model_fields:
            if field in model_lookup.columns:
                urban[field] = urban["map_unit_id"].map(model_lookup[field])
    urban = numeric(urban, ["total_population", "hospital_records", "public_hospitals", "private_hospitals", "beds_total", "nearest_hospital_distance_km", "distance_score", "population_score", "combined_availability_gap", "public_gap_score", "socioeconomic_vulnerability_score", "priority_score_model_c", "priority_rank_model_c", "per_capita_income_2012_inr"])
except Exception as e:
    st.exception(e)
    st.stop()

st.header("Lucknow Healthcare Priority Maps")
st.caption("Explore district-wide settlement priorities and urban ward priorities on two dedicated map pages. Both use the final Model. Filters apply to the map and table.")
page = st.radio("Analysis page", ["District-level analysis", "Urban ward-level analysis"], horizontal=True, label_visibility="collapsed")
st.divider()

if page == "District-level analysis":
    st.header("District-level healthcare priority")
    st.caption("Model combines distance/accessibility (51%), local hospital gap (34%) and tehsil-level socioeconomic vulnerability (15%). The socioeconomic value is a tehsil-level proxy shared by settlements in the same tehsil.")
    # Inline filters: discrete controls instead of red range sliders.
    f1, f2, f3 = st.columns(3)
    tier_opts = ["All tiers"] + [t for t in ["Very High", "High", "Moderate", "Lower"] if t in set(district["priority_tier_model_c"].dropna())]
    d_tier = f1.selectbox("Final priority tier", tier_opts, key="d_tier")
    tehsil_opts = ["All tehsils"] + sorted(district["tehsil_name"].dropna().astype(str).unique())
    d_tehsil = f2.selectbox("Tehsil", tehsil_opts, key="d_tehsil")
    d_type = f3.selectbox("Settlement type", ["All types", "Village", "Town"], key="d_type")
    st.markdown("**Filter by Model formula components**")
    b1, b2, b3 = st.columns(3)
    d_dist_band = b1.selectbox("Distance/accessibility score", BANDS, key="d_dist_band", help="Choose a score band from 0 to 100. This replaces the range slider.")
    d_gap_band = b2.selectbox("Local hospital-gap score", BANDS, key="d_gap_band")
    d_socio_band = b3.selectbox("Socioeconomic vulnerability", BANDS, key="d_socio_band")
    d_color = st.selectbox("Color map by", ["Model priority tier", "Model priority score", "Distance/accessibility score", "Local hospital-gap score", "Socioeconomic vulnerability"], key="d_color")
    view = district.copy()
    if d_tier != "All tiers": view = view[view["priority_tier_model_c"] == d_tier]
    if d_tehsil != "All tehsils": view = view[view["tehsil_name"].astype(str) == d_tehsil]
    if d_type != "All types": view = view[view["settlement_kind"] == d_type]
    for col, band in [("distance_score", d_dist_band), ("local_hospital_gap_score", d_gap_band), ("socioeconomic_vulnerability_score", d_socio_band)]:
        view = apply_band(view, col, band)
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    k1.metric("Settlements in view", f"{len(view):,}")
    k2.metric("Population represented", f"{pd.to_numeric(view.get('population_corrected'), errors='coerce').sum():,.0f}")
    k3.metric("Mean nearest-hospital distance", f"{pd.to_numeric(view.get('nearest_hospital_distance_km'), errors='coerce').mean():.2f} km" if len(view) else "—")
    k4.metric("Reported beds", f"{pd.to_numeric(view.get('total_reported_beds'), errors='coerce').sum():,.0f}")
    k5.metric("Public hospital records", f"{pd.to_numeric(view.get('public_hospital_records'), errors='coerce').sum():,.0f}")
    k6.metric("Private hospital records", f"{pd.to_numeric(view.get('private_hospital_records'), errors='coerce').sum():,.0f}")
    components = {"Distance/accessibility score":"distance_score", "Local hospital-gap score":"local_hospital_gap_score", "Socioeconomic vulnerability":"socioeconomic_vulnerability_score"}
    popup = ["tv_name", "tehsil_name", "settlement_kind", "population_corrected", "estimated_per_capita_income_2012_inr", "nearest_hospital_name", "nearest_hospital_distance_km", "total_reported_beds", "public_hospital_records", "private_hospital_records", "distance_score", "local_hospital_gap_score", "socioeconomic_vulnerability_score", "priority_score_model_c", "priority_rank_model_c", "priority_tier_model_c"]
    aliases = {"tv_name":"Settlement", "tehsil_name":"Tehsil", "settlement_kind":"Settlement type", "population_corrected":"Population used in model", "estimated_per_capita_income_2012_inr":"Estimated per-capita income (2012 INR; tehsil proxy)", "nearest_hospital_name":"Nearest hospital (recorded by model)", "nearest_hospital_distance_km":"Nearest hospital distance (km)", "total_reported_beds":"Reported beds in local hospital records", "public_hospital_records":"Public hospital records", "private_hospital_records":"Private hospital records", "distance_score":"Distance/accessibility score", "local_hospital_gap_score":"Local hospital-gap score", "socioeconomic_vulnerability_score":"Tehsil-level socioeconomic vulnerability", "priority_score_model_c":"Final Model score", "priority_rank_model_c":"Model rank", "priority_tier_model_c":"Final Model tier"}
    show_district_hospitals = st.checkbox("Show hospital markers", value=True, key="d_show_hospitals")
    d_hospital_type = st.selectbox("Hospital markers", ["All hospitals", "Public only", "Private only"], key="d_hospital_type")
    map_priority(view, "District settlements", d_color, "priority_tier_model_c", "priority_score_model_c", components, popup, aliases, "OpenStreetMap", hospitals, show_district_hospitals, district_hospitals_only=True, hospital_ownership_filter=d_hospital_type)
    st.subheader("Filtered settlement priority list")
    table_cols = [c for c in popup + ["pc11_tv_id"] if c in view.columns]
    table = view[table_cols].sort_values("priority_rank_model_c") if not view.empty else view[table_cols]
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.download_button("Download filtered district settlements (CSV)", table.to_csv(index=False).encode("utf-8"), "lucknow_district_model_c_filtered.csv", "text/csv")
else:
    st.header("Urban ward-level healthcare priority")
    st.caption("The final Model includes 110 Municipal Corporation wards and one aggregated Cantonment unit. Cantonment uses a manually sourced per-capita-income estimate of ₹80,072, scaled against the LMC ward income range; its source should be documented in the project methodology.")
    tier_col = "priority_tier_model_c"
    score_col = "priority_score_model_c"
    rank_col = "priority_rank_model_c"
    st.markdown("**Filters**")
    f1,f2,f3 = st.columns(3)
    unit_opts = ["All urban units", "LMC wards only", "Cantonment only"]
    u_type = f1.selectbox("Urban unit type", unit_opts, key="u_type")
    u_tier_opts = ["All tiers"] + [t for t in ["Very High", "High", "Moderate", "Lower"] if t in set(urban[tier_col].dropna())]
    u_tier = f2.selectbox("Final priority tier", u_tier_opts, key="u_tier")
    u_zone_options = ["All zones"] + sorted(urban["Zone"].dropna().astype(str).unique()) if "Zone" in urban.columns else ["All zones"]
    u_zone = f3.selectbox("Zone", u_zone_options, key="u_zone")
    st.markdown("**Filter by Model formula components**")
    uf1,uf2,uf3 = st.columns(3)
    u_dist_band = uf1.selectbox("Distance/accessibility score", BANDS, key="u_dist_band")
    u_pop_band = uf2.selectbox("Population score", BANDS, key="u_pop_band")
    u_avail_band = uf3.selectbox("Combined availability gap", BANDS, key="u_avail_band")
    uf4,uf5 = st.columns(2)
    u_public_band = uf4.selectbox("Public healthcare gap", BANDS, key="u_public_band")
    u_socio_band = uf5.selectbox("Socioeconomic vulnerability", BANDS, key="u_socio_band", help="LMC wards use ward-level income estimates; Cantonment uses a manually sourced estimate scaled to the same LMC reference range.")
    map_opts = ["Model priority tier", "Model priority score", "Distance/accessibility score", "Population score", "Combined availability gap", "Public healthcare gap", "Socioeconomic vulnerability", "Nearest hospital distance (km)", "Hospital records", "Reported beds", "Census 2011 population"]
    u_color = st.selectbox("Color map by", map_opts, key="u_color")
    show_hospitals = st.checkbox("Show hospital markers", value=True, key="u_show_hospitals")
    u_hospital_type = st.selectbox("Hospital markers", ["All hospitals", "Public only", "Private only"], key="u_hospital_type")
    view_u = urban.copy()
    if u_type == "LMC wards only": view_u = view_u[view_u["map_unit_type"] == "LMC_WARD"]
    elif u_type == "Cantonment only": view_u = view_u[view_u["map_unit_type"] == "CANTONMENT_AGGREGATE"]
    if u_tier != "All tiers": view_u = view_u[view_u[tier_col] == u_tier]
    if u_zone != "All zones" and "Zone" in view_u.columns: view_u = view_u[view_u["Zone"].astype(str) == u_zone]
    for col, band in [("distance_score",u_dist_band),("population_score",u_pop_band),("combined_availability_gap",u_avail_band),("public_gap_score",u_public_band),("socioeconomic_vulnerability_score",u_socio_band)]:
        view_u = apply_band(view_u, col, band)
    # Label each urban polygon with its closest hospital by straight-line centroid distance.
    # This is a display label only; the existing Model distance score is not recalculated.
    if not urban.empty and not hospitals.empty and {"latitude", "longitude", "facility_name"}.issubset(hospitals.columns):
        try:
            hcopy = hospitals.copy()
            hcopy["latitude"] = pd.to_numeric(hcopy["latitude"], errors="coerce")
            hcopy["longitude"] = pd.to_numeric(hcopy["longitude"], errors="coerce")
            hcopy = hcopy.dropna(subset=["latitude", "longitude"])
            hgeo = gpd.GeoDataFrame(hcopy, geometry=gpd.points_from_xy(hcopy["longitude"], hcopy["latitude"]), crs="EPSG:4326").to_crs("EPSG:32644")
            centroids_m = urban[["map_unit_id", "geometry"]].to_crs("EPSG:32644").copy()
            centroids_m["geometry"] = centroids_m.geometry.centroid
            if not hgeo.empty:
                lookup = {}
                for _, row in centroids_m.iterrows():
                    distances = hgeo.geometry.distance(row.geometry)
                    idx = distances.idxmin()
                    lookup[row["map_unit_id"]] = hgeo.loc[idx, "facility_name"]
                urban["nearest_hospital_name"] = urban["map_unit_id"].map(lookup)
                view_u["nearest_hospital_name"] = view_u["map_unit_id"].map(lookup)
        except Exception:
            urban["nearest_hospital_name"] = urban.get("nearest_hospital_name", "Not available")
            view_u["nearest_hospital_name"] = view_u["map_unit_id"].map(urban.set_index("map_unit_id")["nearest_hospital_name"])
    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Units in view", f"{len(view_u):,}")
    k2.metric("Population", f"{pd.to_numeric(view_u.get('total_population'), errors='coerce').sum():,.0f}")
    k3.metric("Hospital records", f"{pd.to_numeric(view_u.get('hospital_records'), errors='coerce').sum():,.0f}")
    k4.metric("Reported beds", f"{pd.to_numeric(view_u.get('beds_total'), errors='coerce').sum():,.0f}")
    metric_map = {"Distance/accessibility score":"distance_score", "Population score":"population_score", "Combined availability gap":"combined_availability_gap", "Public healthcare gap":"public_gap_score", "Socioeconomic vulnerability":"socioeconomic_vulnerability_score", "Nearest hospital distance (km)":"nearest_hospital_distance_km", "Hospital records":"hospital_records", "Reported beds":"beds_total", "Census 2011 population":"total_population"}
    popup = ["map_unit_name", "map_unit_type", "total_population", "per_capita_income_2012_inr", "nearest_hospital_name", "hospital_records", "public_hospitals", "private_hospitals", "beds_total", "nearest_hospital_distance_km", "distance_score", "population_score", "combined_availability_gap", "public_gap_score", "socioeconomic_vulnerability_score", "socioeconomic_data_status", "priority_score_model_c", "priority_rank_model_c", "priority_tier_model_c"]
    aliases = {"socioeconomic_data_status":"Socioeconomic data status", "map_unit_name":"Urban unit", "map_unit_type":"Unit type", "total_population":"Census 2011 population", "per_capita_income_2012_inr":"Estimated per-capita income (2012 INR; source varies by unit)", "nearest_hospital_name":"Nearest hospital (centroid-nearest; straight-line)", "hospital_records":"Hospital records", "public_hospitals":"Public hospital records", "private_hospitals":"Private hospital records", "beds_total":"Reported beds", "nearest_hospital_distance_km":"Nearest hospital distance (km)", "distance_score":"Distance/accessibility score", "population_score":"Population score", "combined_availability_gap":"Combined availability gap", "public_gap_score":"Public healthcare gap", "socioeconomic_vulnerability_score":"Socioeconomic vulnerability (income-derived proxy)", "priority_score_model_c":"Final Model score", "priority_rank_model_c":"Model rank", "priority_tier_model_c":"Final Model tier"}
    map_priority(view_u, "Urban ward priority", u_color, tier_col, score_col, metric_map, popup, aliases, "OpenStreetMap", hospitals, show_hospitals, hospital_ownership_filter=u_hospital_type)
    st.subheader("Filtered urban ward priority list")
    table_cols = [c for c in popup if c in view_u.columns]
    table_u = view_u[table_cols].sort_values(rank_col) if not view_u.empty and rank_col in view_u.columns else view_u[table_cols]
    st.dataframe(table_u, use_container_width=True, hide_index=True)
    st.download_button("Download filtered urban units (CSV)", table_u.to_csv(index=False).encode("utf-8"), "lucknow_urban_priority_filtered.csv", "text/csv")

st.divider()
st.caption("Interpretation: priority tiers are relative screening categories, not validated clinical-need classes. A settlement or ward without a local hospital record may still use nearby facilities. Distance is not travel time. Socioeconomic vulnerability is income-derived and differs in geographic resolution between district and ward analyses.")
