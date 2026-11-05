"""Regenerate Delhi's district-level screening outputs from data/delhi source files."""
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "delhi"


def main():
    boundary = gpd.read_file(DATA / "delhi_district_boundary.gpkg").to_crs("EPSG:4326")
    demographics = pd.read_csv(DATA / "admin_unit_demographics_delhi.csv", dtype={"admin_unit_id": str})
    socioeconomic = pd.read_csv(DATA / "admin_unit_socioeconomic_delhi.csv", dtype={"admin_unit_id": str})
    facilities = pd.read_csv(DATA / "healthcare_facilities_delhi.csv")
    for col in ["latitude", "longitude", "beds_total"]:
        facilities[col] = pd.to_numeric(facilities[col], errors="coerce")
    facilities = facilities.dropna(subset=["latitude", "longitude"]).copy()
    points = gpd.GeoDataFrame(facilities, geometry=gpd.points_from_xy(facilities.longitude, facilities.latitude), crs="EPSG:4326")
    assigned = gpd.sjoin(points, boundary[["admin_unit_id", "admin_unit_name", "geometry"]], how="left", predicate="within")
    # Use intersects for points on district boundaries, resolving only unambiguous matches.
    missing = assigned["admin_unit_id"].isna()
    if missing.any():
        fallback = gpd.sjoin(points.loc[missing], boundary[["admin_unit_id", "admin_unit_name", "geometry"]], how="left", predicate="intersects")
        for idx in fallback.index.unique():
            matches = fallback.loc[idx, "admin_unit_id"]
            if isinstance(matches, pd.Series):
                matches = matches.dropna().unique()
                value = matches[0] if len(matches) == 1 else np.nan
            else:
                value = matches
            if pd.notna(value):
                assigned.loc[idx, "admin_unit_id"] = value

    counts = assigned.dropna(subset=["admin_unit_id"]).groupby("admin_unit_id").agg(
        hospital_records=("facility_id", "nunique"),
        public_hospitals=("ownership", lambda x: int(x.astype(str).str.lower().eq("public").sum())),
        private_hospitals=("ownership", lambda x: int(x.astype(str).str.lower().eq("private").sum())),
        beds_total=("beds_total", "sum"),
    ).reset_index()

    base = boundary.drop(columns="geometry").merge(demographics, on=["admin_unit_id", "admin_unit_name", "district", "state", "census_year"], how="left", suffixes=("", "_demo"))
    base = base.merge(socioeconomic[["admin_unit_id", "socioeconomic_indicator", "indicator_value", "indicator_unit", "reference_year"]], on="admin_unit_id", how="left", suffixes=("", "_socio"))
    base = base.merge(counts, on="admin_unit_id", how="left")
    for col in ["hospital_records", "public_hospitals", "private_hospitals", "beds_total"]:
        base[col] = base[col].fillna(0)

    projected_boundary = boundary.to_crs("EPSG:32643")
    projected_points = points.to_crs("EPSG:32643")
    coords = np.array([(p.x, p.y) for p in projected_points.geometry])
    distances, nearest = [], []
    for polygon in projected_boundary.geometry:
        point = polygon.representative_point()
        d = np.sqrt(((coords - np.array([point.x, point.y])) ** 2).sum(axis=1))
        i = int(d.argmin())
        distances.append(float(d[i] / 1000))
        nearest.append(str(facilities.iloc[i]["facility_name"]))
    base["nearest_hospital_distance_km"] = distances
    base["nearest_hospital_name"] = nearest
    max_distance = float(base["nearest_hospital_distance_km"].max())
    base["distance_score"] = 100 * base["nearest_hospital_distance_km"] / max_distance if max_distance else 0
    base["local_hospital_gap_score"] = np.where(base["hospital_records"] > 0, 0, 100)
    base["socioeconomic_vulnerability_score"] = pd.to_numeric(base["indicator_value"], errors="coerce").clip(0, 100)
    base["priority_score_model_c"] = 0.51 * base["distance_score"] + 0.34 * base["local_hospital_gap_score"] + 0.15 * base["socioeconomic_vulnerability_score"]
    base = base.sort_values("priority_score_model_c", ascending=False).reset_index(drop=True)
    base["priority_rank_model_c"] = np.arange(1, len(base) + 1)
    base["priority_tier_model_c"] = pd.cut(base["priority_score_model_c"], [-np.inf, 25, 50, 75, np.inf], labels=["Lower", "Moderate", "High", "Very High"], right=False).astype(str)
    base["priority_model_version"] = "Delhi district screening adaptation of Lucknow district model; 2011 geography"
    base["socioeconomic_data_status"] = "Adult illiteracy proxy (Census 2011); not income or poverty"
    base["distance_method"] = "Straight-line from district representative point to nearest facility coordinate"
    base["hospital_dataset_note"] = "50-record curated facility input; not independently exhaustive/verified"

    base.to_csv(DATA / "delhi_district_priority_scores.csv", index=False)
    output = boundary.merge(base, on=["admin_unit_id", "admin_unit_name", "district", "state", "census_year"], how="left", suffixes=("", "_model"))
    output.to_file(DATA / "delhi_district_priority_model.gpkg", layer="delhi_district_priority_model", driver="GPKG")
    assigned_out = points.copy()
    assigned_out["admin_unit_id"] = assigned["admin_unit_id"].values
    name_lookup = boundary.set_index("admin_unit_id")["admin_unit_name"]
    assigned_out["admin_unit_name"] = assigned_out["admin_unit_id"].map(name_lookup)
    assigned_out.to_file(DATA / "delhi_facility_assignments.gpkg", layer="delhi_facility_assignments", driver="GPKG")
    print(f"Wrote {DATA / 'delhi_district_priority_scores.csv'}")
    print(base[["admin_unit_id", "admin_unit_name", "hospital_records", "nearest_hospital_distance_km", "priority_score_model_c", "priority_rank_model_c", "priority_tier_model_c"]].to_string(index=False))
    print(f"Facility points assigned to a 2011 district: {assigned['admin_unit_id'].notna().sum()}/{len(assigned)}")


if __name__ == "__main__":
    main()
