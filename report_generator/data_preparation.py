
from pathlib import Path
import pandas as pd
import geopandas as gpd


def _find_data_directory(data_dir=None):
    if data_dir:
        path = Path(data_dir)
        if not path.exists():
            raise FileNotFoundError(f"Data directory not found: {path}")
        return path

    project_root = Path(__file__).resolve().parent.parent
    path = project_root / "data"

    if not path.exists():
        raise FileNotFoundError(f"Data directory not found: {path}")

    return path


def _read_file(path):
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Required data file not found: {path}")

    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)

    if path.suffix.lower() == ".gpkg":
        return gpd.read_file(path)

    raise ValueError(f"Unsupported file format: {path.suffix}")


def _first_existing_column(df, candidates):
    for column in candidates:
        if column in df.columns:
            return column
    return None


def _safe_number(value):
    if pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _prepare_level(
    df,
    level_name,
    source_file,
    map_file,
    name_columns,
    score_columns,
    tier_columns,
    population_columns=None,
    hospital_columns=None,
    public_hospital_columns=None,
    private_hospital_columns=None,
    bed_columns=None,
    public_bed_columns=None,
    distance_columns=None,
    availability_columns=None,
    public_gap_columns=None,
    top_n=10
):
    population_columns = population_columns or []
    hospital_columns = hospital_columns or []
    public_hospital_columns = public_hospital_columns or []
    private_hospital_columns = private_hospital_columns or []
    bed_columns = bed_columns or []
    public_bed_columns = public_bed_columns or []
    distance_columns = distance_columns or []
    availability_columns = availability_columns or []
    public_gap_columns = public_gap_columns or []

    name_col = _first_existing_column(df, name_columns)
    score_col = _first_existing_column(df, score_columns)
    tier_col = _first_existing_column(df, tier_columns)

    if not name_col:
        raise ValueError(
            f"Area name column not found for {level_name}"
        )

    if not score_col:
        raise ValueError(
            f"Priority score column not found for {level_name}"
        )

    if not tier_col:
        raise ValueError(
            f"Priority tier column not found for {level_name}"
        )

    df = df.copy()

    df[score_col] = pd.to_numeric(
        df[score_col], errors="coerce"
    )

    df = df.dropna(subset=[score_col])

    if df.empty:
        raise ValueError(
            f"No valid priority scores found for {level_name}"
        )

    tier_counts = (
        df[tier_col]
        .fillna("Unclassified")
        .astype(str)
        .value_counts()
        .to_dict()
    )

    top_areas = df.sort_values(
        score_col, ascending=False
    ).head(top_n)

    selected_columns = {
        "area_name": name_col,
        "priority_score": score_col,
        "priority_tier": tier_col,
        "population": _first_existing_column(
            df, population_columns
        ),
        "hospital_records": _first_existing_column(
            df, hospital_columns
        ),
        "public_hospitals": _first_existing_column(
            df, public_hospital_columns
        ),
        "private_hospitals": _first_existing_column(
            df, private_hospital_columns
        ),
        "total_beds": _first_existing_column(
            df, bed_columns
        ),
        "public_beds": _first_existing_column(
            df, public_bed_columns
        ),
        "nearest_hospital_distance_km": _first_existing_column(
            df, distance_columns
        ),
        "availability_gap": _first_existing_column(
            df, availability_columns
        ),
        "public_gap": _first_existing_column(
            df, public_gap_columns
        )
    }

    top_area_data = []

    for _, row in top_areas.iterrows():
        area = {
            "area_name": str(row[name_col]),
            "priority_score": _safe_number(row[score_col]),
            "priority_tier": str(row[tier_col])
        }

        for key, column in selected_columns.items():
            if key in ["area_name", "priority_score", "priority_tier"]:
                continue

            if column:
                area[key] = _safe_number(row[column])

        top_area_data.append(area)

    score_series = df[score_col]

    return {
        "level_name": level_name,
        "source_file": str(source_file),
        "map_file": str(map_file) if map_file else None,
        "total_units": int(len(df)),
        "score_statistics": {
            "mean": _safe_number(score_series.mean()),
            "median": _safe_number(score_series.median()),
            "minimum": _safe_number(score_series.min()),
            "maximum": _safe_number(score_series.max())
        },
        "priority_distribution": {
            str(k): int(v)
            for k, v in tier_counts.items()
        },
        "top_priority_areas": top_area_data,
        "available_resource_fields": {
            key: column
            for key, column in selected_columns.items()
            if column is not None
        }
    }


def prepare_city_report_data(city, data_dir=None):
    data_path = _find_data_directory(data_dir)

    city = city.strip().lower()

    configurations = {
        "lucknow": [
            {
                "level": "District Settlement Analysis",
                "source": "lucknow_settlement_priority_model_c.gpkg",
                "map": "lucknow_settlement_priority_model_c.gpkg",
                "name": ["tv_name_priority", "tv_name"],
                "score": ["priority_score_model_c"],
                "tier": ["priority_tier_model_c"],
                "population": ["pop2011_villagept_priority", "pop2011_villagept"],
                "hospitals": ["hospital_record_count"],
                "public_hospitals": ["public_hospital_records"],
                "private_hospitals": ["private_hospital_records"],
                "beds": ["total_reported_beds"],
                "public_beds": ["public_reported_beds"],
                "distance": ["nearest_hospital_distance_km"],
                "availability": ["local_hospital_gap_score"],
                "public_gap": ["public_hospital_gap_score"]
            },
            {
                "level": "Urban Ward Analysis",
                "source": "lucknow_urban_healthcare_priority_scores_model_c.csv",
                "map": "lucknow_map_boundaries_with_demographics.gpkg",
                "name": ["map_unit_name"],
                "score": ["priority_score_model_c"],
                "tier": ["priority_tier_model_c"],
                "population": ["total_population"],
                "hospitals": ["hospital_records"],
                "public_hospitals": ["public_hospitals"],
                "private_hospitals": ["private_hospitals"],
                "beds": ["beds_total"],
                "distance": ["nearest_hospital_distance_km"],
                "availability": ["combined_availability_gap"],
                "public_gap": ["public_gap_score"]
            }
        ],

        "delhi": [
            {
                "level": "District Analysis",
                "source": "delhi/delhi_district_priority_model.gpkg",
                "map": "delhi/delhi_district_priority_model.gpkg",
                "name": ["admin_unit_name"],
                "score": ["priority_score_model_c"],
                "tier": ["priority_tier_model_c"],
                "population": ["total_population"],
                "hospitals": ["hospital_records"],
                "public_hospitals": ["public_hospitals"],
                "private_hospitals": ["private_hospitals"],
                "beds": ["beds_total"],
                "distance": ["nearest_hospital_distance_km"],
                "availability": ["local_hospital_gap_score"]
            },
            {
                "level": "Ward Analysis",
                "source": "delhi/delhi_ward_priority_model.gpkg",
                "map": "delhi/delhi_ward_priority_model.gpkg",
                "name": ["map_unit_name", "Ward_Name"],
                "score": ["priority_score_model_c"],
                "tier": ["priority_tier_model_c"],
                "population": ["total_population", "population"],
                "hospitals": ["hospital_records", "facility_count"],
                "public_hospitals": ["public_hospitals"],
                "private_hospitals": ["private_hospitals"],
                "beds": ["beds_total"],
                "distance": ["nearest_hospital_distance_km", "nearest_facility_km"],
                "availability": ["combined_availability_gap"],
                "public_gap": ["public_gap_score"]
            }
        ],

        "mumbai": [
            {
                "level": "District Analysis",
                "source": "mumbai/mumbai_district_priority.gpkg",
                "map": "mumbai/mumbai_district_priority.gpkg",
                "name": ["district_name"],
                "score": ["priority_score_model_c"],
                "tier": ["priority_tier_model_c"],
                "population": ["district_population"],
                "hospitals": ["hospital_records"],
                "public_hospitals": ["public_hospitals"],
                "private_hospitals": ["private_hospitals"],
                "beds": ["beds_total"],
                "distance": ["nearest_hospital_distance_km"],
                "availability": ["combined_availability_gap"],
                "public_gap": ["public_gap_score"]
            },
            {
                "level": "Ward Analysis",
                "source": "mumbai/mumbai_ward_priority.gpkg",
                "map": "mumbai/mumbai_ward_priority.gpkg",
                "name": ["map_unit_name"],
                "score": ["priority_score_model_c"],
                "tier": ["priority_tier_model_c"],
                "population": ["total_population"],
                "hospitals": ["hospital_records"],
                "public_hospitals": ["public_hospitals"],
                "private_hospitals": ["private_hospitals"],
                "beds": ["beds_total"],
                "distance": ["nearest_hospital_distance_km"],
                "availability": ["combined_availability_gap"],
                "public_gap": ["public_gap_score"]
            }
        ],

        "chennai": [
            {
                "level": "Ward Analysis",
                "source": "chennai/chennai_final_healthcare_priority.gpkg",
                "map": "chennai/chennai_final_healthcare_priority.gpkg",
                "name": ["ward_display_name", "admin_unit_name"],
                "score": ["priority_score"],
                "tier": ["priority_tier"],
                "population": ["total_population"],
                "hospitals": ["hospital_records"],
                "public_hospitals": ["public_hospitals"],
                "private_hospitals": ["private_hospitals"],
                "beds": ["total_hospital_beds"],
                "public_beds": ["public_hospital_beds"],
                "distance": ["nearest_hospital_distance_km"],
                "availability": ["combined_availability_gap"],
                "public_gap": ["public_gap_score"]
            },
            {
                "level": "Settlement Analysis",
                "source": "chennai/settlements/chennai_settlement_priority.gpkg",
                "map": "chennai/settlements/chennai_settlement_priority.gpkg",
                "name": ["admin_unit_name"],
                "score": ["priority_score"],
                "tier": ["priority_tier"],
                "population": ["total_population"],
                "hospitals": ["hospital_facilities"],
                "public_hospitals": ["public_facilities"],
                "private_hospitals": ["private_facilities"],
                "beds": ["total_beds"],
                "public_beds": ["public_beds"],
                "distance": ["all_distance_km"],
                "availability": ["local_hospital_gap_score"]
            }
        ]
    }

    if city not in configurations:
        raise ValueError(
            "Unsupported city. Choose Lucknow, Delhi, Mumbai or Chennai."
        )

    city_data = {
        "city": city.title(),
        "analysis_levels": []
    }

    for config in configurations[city]:
        source_path = data_path / config["source"]
        map_path = data_path / config["map"]

        df = _read_file(source_path)

        level_data = _prepare_level(
            df=df,
            level_name=config["level"],
            source_file=source_path,
            map_file=map_path,
            name_columns=config["name"],
            score_columns=config["score"],
            tier_columns=config["tier"],
            population_columns=config.get("population"),
            hospital_columns=config.get("hospitals"),
            public_hospital_columns=config.get("public_hospitals"),
            private_hospital_columns=config.get("private_hospitals"),
            bed_columns=config.get("beds"),
            public_bed_columns=config.get("public_beds"),
            distance_columns=config.get("distance"),
            availability_columns=config.get("availability"),
            public_gap_columns=config.get("public_gap")
        )

        city_data["analysis_levels"].append(level_data)

    return city_data
