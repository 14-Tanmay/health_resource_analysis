# Healthcare Access & Priority Explorer

An interactive, GIS-based decision-support application for exploring healthcare accessibility and identifying potentially underserved geographic areas. The application currently integrates analyses for **Lucknow, Delhi, Mumbai, and Chennai**.

Users can explore healthcare-priority maps at the geographic levels available for each city, inspect facility and demographic indicators, filter areas, view ranked tables, and download CSV outputs. The application also includes a city-specific Word report generator that combines quantitative summaries and maps with AI-generated findings and planning recommendations.

> **Important:** Priority scores and tiers are model-based screening indicators intended to support geographic planning. They are not official government classifications, clinical risk scores, or proof that an area has no access to healthcare. The models, source years, geographic units, and distance definitions differ between cities; scores should not be compared directly across cities without harmonizing those inputs and methods.

---

## 1. Features

- **Four-city selection:** Choose Lucknow, Delhi, Mumbai, or Chennai from the opening city selector.
- **Interactive GIS maps:** Explore geographic priority outputs with Folium maps and OpenStreetMap basemaps.
- **Priority visualization:** Display priority tiers, final scores, and available component indicators through map coloring and popups.
- **Filters:** Filter by the geographic and analytical attributes supported by each city dashboard, such as priority tier, district, tehsil, ward type, zone, settlement type, and component-score bands.
- **Healthcare facility markers:** Display mapped facility records, with public/private filters where supported. Markers are limited to records with usable coordinates.
- **Ranked tables and KPIs:** Inspect area rankings and summary statistics for the selected view.
- **CSV exports:** Download filtered or city-level priority tables from the dashboards.
- **Word report generation:** Generate a city-specific `.docx` report containing maps, quantitative summaries, priority-area information, AI-generated findings, and planning recommendations.
- **Extensible city structure:** City-specific data and rendering logic are kept separate where separate modules are used, while the city selector is configured through `cities.json`.

## 2. Cities and available analysis

| City | Geographic analysis available in the dashboard | Notes |
|---|---|---|
| **Lucknow** | District settlements and urban wards | Includes the district settlement model and the urban ward-level model. |
| **Delhi** | Districts and wards | Uses historical Census 2011 district boundaries. District and ward analyses use income-derived socioeconomic vulnerability based on 2012 per-capita income estimates. |
| **Mumbai** | Districts and wards | District polygons are dissolved from the 97 target ward polygons using the supplied ward-to-district crosswalk. The district comparison is relative to Mumbai and Mumbai Suburban. |
| **Chennai** | Settlements and wards | Includes a settlement-level view with 202 analysis units and a ward-level view with 155 wards. The supplied model outputs are displayed without recalculating the Chennai scores in the website. |

### City-specific interpretation notes

#### Lucknow

The Lucknow dashboard contains two separate models:

**District settlement model**

\[
P_{district}=0.51D+0.34G+0.15S
\]

- `D`: distance/accessibility score.
- `G`: local hospital-gap score.
- `S`: tehsil-level socioeconomic vulnerability proxy.

**Urban ward model**

\[
P_{urban}=0.25D+0.15P+0.35A+0.10G+0.15S
\]

- `D`: distance/accessibility score.
- `P`: population score.
- `A`: combined healthcare availability-gap component.
- `G`: public healthcare-gap score.
- `S`: income-derived socioeconomic vulnerability score.

The weights are explicit modelling choices for a planning-oriented composite indicator; they are not learned causal effects. Lucknow's socioeconomic vulnerability component uses an income-derived proxy, not an official poverty measure. The district and urban models are distinct and their scores should not be compared directly.

#### Delhi

- The district analysis uses nine historical Census 2011 district polygons.
- District-level scoring follows the district weighting structure used for Lucknow: 51% distance/accessibility, 34% local hospital gap, and 15% socioeconomic vulnerability.
- District income is aggregated from ward-level per-capita income estimates (2012 INR), weighted by population.
- The ward-level dashboard uses the supplied ward priority outputs and the urban model structure.
- The socioeconomic component is income-derived; lower per-capita income corresponds to higher vulnerability.
- Facility inputs are curated records and should not be treated as a verified exhaustive inventory. Bed values may combine different source years and confidence levels.
- The historical district boundaries should not be interpreted as current administrative boundaries.

#### Mumbai

- The dashboard provides district-level and ward-level views.
- The ward analysis covers 97 target Census wards; district polygons are derived from those wards using the supplied crosswalk.
- The supplied Model C outputs use the urban weighting structure, with per-capita income as the socioeconomic factor.
- Income-to-ward assignments are candidate matches based on population similarity and are provisional.
- Distances displayed in this dashboard are straight-line estimates, not travel times.

#### Chennai

- The ward dashboard contains 155 wards.
- The settlement dashboard contains 202 analysis units and uses the supplied settlement priority dataset, thematic maps, and interactive accessibility map.
- The website displays the supplied Chennai model scores and geometries as provided; it does not recalculate the Chennai model.
- The settlement analysis uses the supplied Model C structure: `0.51D + 0.34G + 0.15S`.
- Its distance input is nearest healthcare-facility distance, including any facility type, and its socioeconomic vulnerability input is a district-level income proxy.
- The supplied nearest-facility distance is a hybrid road-network/straight-line-fallback distance, not travel time.

### Distance and score interpretation

Distance fields must be interpreted according to the source and method used by the relevant city model. A distance in kilometres is not a travel-time estimate. Some city datasets use straight-line distance, while others use road-network or hybrid distance methods. Refer to the relevant in-dashboard notes and source data before comparing values.

Priority tiers are relative categories within the relevant city's analysis and should not be treated as externally validated clinical-need thresholds.

---

## 3. Technology stack

- **Python** – application and data-processing language.
- **Streamlit** – interactive web application framework.
- **Pandas** – tabular data loading, cleaning, filtering, and summaries.
- **GeoPandas** – geospatial data handling and spatial operations.
- **Shapely** – geometric operations.
- **Folium** – interactive maps and facility markers.
- **streamlit-folium** – Folium map integration in Streamlit.
- **Plotly** – visualization dependency.
- **Matplotlib** – map rendering for generated reports.
- **python-docx** – Word document generation.
- **Groq API** – AI-generated qualitative analysis for reports, using the `openai/gpt-oss-120b` model configured in the application.

The project uses CSV files for tabular inputs and outputs and GeoPackage (`.gpkg`) files for spatial datasets. The city dashboards load prepared model outputs; they are primarily for exploration and presentation rather than running the full upstream modelling pipeline each time the app starts.

---

## 4. Project structure

```text
lucknow_healthcare_website/
│
├── app.py                         # Main Streamlit application and city dispatch
├── cities.json                    # City selector registry
├── requirements.txt               # Core application dependencies
│
├── cities/
│   ├── __init__.py
│   ├── delhi.py                   # Delhi district- and ward-level dashboard
│   ├── chennai.py                 # Chennai settlement- and ward-level dashboard
│   └── README.md                  # Guidance for adding city modules
│
├── data/
│   ├── lucknow_*                  # Lucknow model outputs and facility data
│   ├── delhi/                     # Delhi datasets and spatial outputs
│   ├── mumbai/                    # Mumbai datasets and spatial outputs
│   └── chennai/                   # Chennai datasets and spatial outputs
│       └── settlements/           # Chennai settlement outputs, maps, and HTML map
│
├── report_generator/
│   ├── __init__.py
│   ├── data_preparation.py        # City-specific report data preparation
│   ├── groq_analysis.py           # Groq API analysis and response validation
│   └── document_generator.py      # Word report and map generation
│
├── notebooks/                     # Project analysis and modelling notebooks
├── scripts/                       # Supporting data/model scripts
├── test_groq.py                   # Groq connectivity/test script
├── test_report.py                 # Report-generation test script
└── README.md
```

The Mumbai dashboard logic is currently implemented directly in `app.py`; Delhi and Chennai have separate modules under `cities/`.

---

## 5. Installation and local setup

### Prerequisites

- Python 3.10 or later is recommended.
- `pip`
- A Groq API key is required only if you want to generate AI-assisted Word reports.

### Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd lucknow_healthcare_website
```

Replace `<YOUR_REPOSITORY_URL>` with the URL of your repository.

### Install dependencies

Install the core dashboard dependencies:

```bash
pip install -r requirements.txt
```

Install the additional packages used by the Word report generator:

```bash
pip install groq python-docx matplotlib pillow
```

If you only want to run the interactive dashboards and do not need Word report generation, the additional report-generation packages and Groq API key are not required for the normal dashboard views.

### Configure the Groq API key

The report generator reads the API key from the `GROQ_API_KEY` environment variable or Streamlit secrets.

**Option A – environment variable**

Windows PowerShell:

```powershell
$env:GROQ_API_KEY="your_groq_api_key"
```

macOS/Linux:

```bash
export GROQ_API_KEY="your_groq_api_key"
```

**Option B – Streamlit secrets**

Create `.streamlit/secrets.toml` in the project root:

```toml
GROQ_API_KEY = "your_groq_api_key"
```

Do not commit API keys, `.streamlit/secrets.toml`, or other credentials to a public repository. Keep the secrets file excluded through `.gitignore`.

### Run the application

From the project root:

```bash
streamlit run app.py
```

Streamlit will display a local URL in the terminal, usually `http://localhost:8501`.

Select a city from the opening dropdown to load its dashboard.

---

## 6. Generating a Word healthcare analysis report

The application includes a **Download Healthcare Analysis Report** section after a city is selected.

1. Select a city from the opening selector.
2. Expand **Download Healthcare Analysis Report**.
3. Select **Generate Report**.
4. Wait while the application prepares the city data, requests the AI-generated analysis, and builds the Word document.
5. Select **Download Word Report (.docx)** when the report is ready.

The report-generation workflow is divided into three modules:

### `report_generator/data_preparation.py`

- Loads the selected city's prepared analytical datasets.
- Identifies the available analysis levels and relevant columns.
- Calculates descriptive summaries and priority-tier distributions from the supplied scores.
- Extracts high-priority areas and relevant geographic indicators for the report.

### `report_generator/groq_analysis.py`

- Sends the prepared city analysis data to the Groq API.
- Uses the configured `openai/gpt-oss-120b` model to generate qualitative findings and planning recommendations.
- Validates the structured response before it is passed to the document generator.
- The prompt instructs the model not to invent or recalculate population, facility, bed, distance, score, or geographic values.

### `report_generator/document_generator.py`

- Creates the `.docx` report using `python-docx`.
- Generates priority maps from the relevant spatial data where supported.
- Adds city overview information, quantitative statistics, priority distributions, high-priority areas, findings, and recommendations.

The report generator depends on the input datasets being present and correctly structured. AI-generated narrative is an interpretation of the supplied data, not an independent validation of the underlying model or recommendations.

---

## 7. Data organization

Keep city-specific data in separate folders under `data/`:

```text
data/
├── lucknow files...
├── delhi/
├── mumbai/
└── chennai/
```

The current application expects the prepared files and layer names used by its city-specific loading code. In particular, GeoPackage layer names matter: a file may exist but fail to load if the requested layer name does not match the layer stored in that file.

Do not replace a city's data with another city's files merely because the column names look similar. Before integrating new data, check:

- Geographic unit and boundary vintage.
- Coordinate reference system (CRS).
- Stable geographic identifiers and join coverage.
- Population and socioeconomic source years.
- Facility definitions, ownership classifications, coordinates, and bed-count coverage.
- Distance definition (straight-line, road-network, or hybrid) and units.
- Score direction, normalization, weights, and priority-tier definitions.
- Missing values, duplicates, and unmatched geographic records.

---

## 8. Adding another city

The city selector is driven by `cities.json`. A new city should have its own data folder and city-specific loading and rendering logic.

1. **Prepare and validate the data.** Keep raw inputs, cleaned tables, spatial outputs, and model outputs clearly distinguished.
2. **Create a data folder.** For example, `data/<city_id>/`.
3. **Create a city module.** Add `cities/<city_id>.py` with a rendering function that loads the city's own files and checks the required schema.
4. **Register the city.** Add a unique city entry to `cities.json`, including its `id`, `name`, `status`, and description.
5. **Add dispatch logic.** Update `app.py` to call the new module when that city is selected.
6. **Document the methodology.** Explain the geographic unit, source years, score formula, normalization, distance method, and limitations.
7. **Test independently.** Confirm that the new city works and that switching between cities does not change existing city outputs.

Reuse an existing scoring structure only when the component definitions, direction, normalization, and geographic scale are genuinely comparable. Do not silently apply a ward-level formula to a district-level dataset or assume that all cities have equivalent facility inventories.

---

## 9. Limitations and responsible interpretation

- **Data coverage:** Facility inventories may be curated or incomplete. A missing facility record does not necessarily mean that no facility exists in that area.
- **Bed counts:** Reported beds are not necessarily staffed, available, unoccupied, or appropriate for every type of care.
- **Source years:** Census, income, facility, and boundary datasets may refer to different years. Historical boundaries and estimates should be identified clearly.
- **Distance is not travel time:** Straight-line and road-network distances do not automatically represent actual travel time, traffic, affordability, service quality, or patient choice.
- **Proxy variables:** Income-derived or other socioeconomic indicators are proxies and should not be described as direct measurements of poverty or health outcomes.
- **Model assumptions:** Composite scores depend on selected variables, normalization procedures, and weights. The weights are planning assumptions unless independently validated.
- **Relative tiers:** Priority tiers are based on the relevant model's ranking or supplied classification and are not clinical or statutory categories.
- **Cross-city comparison:** Differences in geographic units, data coverage, source years, and distance methods prevent straightforward comparison of raw scores across cities.
- **AI-generated reports:** Generated findings and recommendations should be reviewed by domain experts and local authorities before operational use.

The application is intended as a prototype decision-support tool to help explore spatial patterns and support further investigation. It should complement, not replace, field verification, public-health expertise, and official planning processes.

---

## 10. License and attribution

Add the project's selected software license and the required attribution for the underlying datasets before public distribution. Follow the terms of each source dataset, including OpenStreetMap attribution and applicable data-use conditions.

---

## 11. Acknowledgements

This project brings together geospatial analysis, demographic and socioeconomic indicators, healthcare-facility records, and interactive visualization to support evidence-informed public-health resource planning.
