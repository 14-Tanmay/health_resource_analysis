
import os
import re
import tempfile
from io import BytesIO
from datetime import datetime

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


# ---------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------

def safe_filename(value):
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "_", value)
    return value.strip("_")


def format_number(value, decimals=2):
    if value is None:
        return "Not available"

    try:
        if pd.isna(value):
            return "Not available"

        if isinstance(value, (int, float)):
            return f"{value:,.{decimals}f}"

        return str(value)

    except (TypeError, ValueError):
        return str(value)


def shade_cell(cell, fill):
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(shading)


def set_cell_text(cell, value, bold=False, color=None, size=9):
    cell.text = str(value)

    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.bold = bold
            run.font.name = "Arial"
            run.font.size = Pt(size)

            if color:
                run.font.color.rgb = RGBColor(*color)

    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def add_table(document, headers, rows):
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        set_cell_text(
            cell,
            header,
            bold=True,
            color=(255, 255, 255),
            size=8
        )
        shade_cell(cell, "24476B")

    for row in rows:
        cells = table.add_row().cells

        for index, value in enumerate(row):
            set_cell_text(cells[index], value, size=8)

    document.add_paragraph()
    return table


def add_bullet_list(document, items):
    if not items:
        document.add_paragraph("No information available.")
        return

    for item in items:
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(5)
        paragraph.add_run(str(item))


def add_section_heading(document, text, level=2):
    heading = document.add_heading(text, level=level)
    heading.paragraph_format.space_before = Pt(10)
    heading.paragraph_format.space_after = Pt(5)
    heading.paragraph_format.keep_with_next = True
    return heading


# ---------------------------------------------------------
# MAP GENERATION
# ---------------------------------------------------------

def find_column(columns, candidates):
    column_lookup = {
        str(column).lower(): column
        for column in columns
    }

    for candidate in candidates:
        if candidate.lower() in column_lookup:
            return column_lookup[candidate.lower()]

    for column in columns:
        column_lower = str(column).lower()

        for candidate in candidates:
            if candidate.lower() in column_lower:
                return column

    return None


def generate_priority_map(map_path, level_name):
    if not map_path or not os.path.exists(map_path):
        print(f"Map file not found: {map_path}")
        return None

    try:
        gdf = gpd.read_file(map_path)

        if gdf.empty:
            return None

        gdf = gdf[gdf.geometry.notna()].copy()

        if gdf.empty:
            return None

        tier_column = find_column(
            gdf.columns,
            [
                "priority_tier",
                "priority_tier_model_c",
                "priority_category",
                "priority_level",
                "priority_class",
                "priority",
                "healthcare_priority",
                "tier"
            ]
        )

        score_column = find_column(
            gdf.columns,
            [
                "priority_score",
                "priority_score_model_c",
                "healthcare_priority_score",
                "final_priority_score",
                "composite_score",
                "priority_index",
                "final_score",
                "score"
            ]
        )

        fig, ax = plt.subplots(figsize=(9, 7))

        if tier_column:
            gdf.plot(
                column=tier_column,
                categorical=True,
                legend=True,
                ax=ax,
                edgecolor="black",
                linewidth=0.25,
                missing_kwds={
                    "color": "lightgrey",
                    "label": "Missing"
                },
                legend_kwds={
                    "loc": "best",
                    "fontsize": 8
                }
            )

        elif score_column:
            gdf[score_column] = pd.to_numeric(
                gdf[score_column],
                errors="coerce"
            )

            gdf.plot(
                column=score_column,
                cmap="RdYlGn_r",
                legend=True,
                ax=ax,
                edgecolor="black",
                linewidth=0.25,
                missing_kwds={
                    "color": "lightgrey",
                    "label": "Missing"
                },
                legend_kwds={
                    "label": "Priority Score",
                    "shrink": 0.65
                }
            )

        else:
            gdf.plot(
                ax=ax,
                color="lightblue",
                edgecolor="black",
                linewidth=0.3
            )

        ax.set_title(
            f"{level_name} Healthcare Priority Map",
            fontsize=13,
            fontweight="bold",
            pad=12
        )

        ax.set_axis_off()
        plt.tight_layout()

        image_buffer = BytesIO()

        fig.savefig(
            image_buffer,
            format="png",
            dpi=220,
            bbox_inches="tight"
        )

        image_buffer.seek(0)
        plt.close(fig)

        return image_buffer

    except Exception as error:
        print(f"Could not generate map for {level_name}: {error}")
        plt.close("all")
        return None


def add_map_to_document(document, map_path, level_name):
    add_section_heading(document, "Healthcare Priority Map")

    map_image = generate_priority_map(map_path, level_name)

    if map_image is None:
        document.add_paragraph(
            "The priority map could not be generated from "
            "the available geographic data."
        )
        return

    # Preserve the map's aspect ratio while limiting its size.
    image = Image.open(map_image)
    image_width, image_height = image.size

    max_width = 6.2
    max_height = 4.7

    aspect_ratio = image_width / image_height

    display_width = min(max_width, max_height * aspect_ratio)
    display_height = display_width / aspect_ratio

    map_image.seek(0)

    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.keep_together = True

    paragraph.add_run().add_picture(
        map_image,
        width=Inches(display_width),
        height=Inches(display_height)
    )

    caption = document.add_paragraph(
        f"Figure: Healthcare priority distribution across "
        f"{level_name.lower()} units."
    )

    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for run in caption.runs:
        run.italic = True
        run.font.size = Pt(8)


# ---------------------------------------------------------
# REPORT CONTENT
# ---------------------------------------------------------

def add_city_overview(document, city_data):
    city = city_data.get("city", "Unknown City")

    title = document.add_heading(
        f"{city} Healthcare Accessibility and Priority Analysis",
        level=0
    )

    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    subtitle = document.add_paragraph(
        "Geographic assessment of healthcare accessibility "
        "and priority areas for resource allocation"
    )

    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for run in subtitle.runs:
        run.italic = True
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(90, 90, 90)

    document.add_paragraph()

    date_paragraph = document.add_paragraph(
        f"Report generated on: {datetime.now().strftime('%d %B %Y')}"
    )
    date_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    document.add_paragraph()

    intro = document.add_paragraph(
        f"This report presents the geographic healthcare priority "
        f"analysis for {city}. It includes priority maps, quantitative "
        f"summaries, key findings, and area-specific planning "
        f"recommendations for the geographic units covered."
    )

    intro.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    document.add_page_break()


def add_statistics(document, level_data):
    stats = level_data.get("score_statistics", {})
    distribution = level_data.get("priority_distribution", {})

    add_section_heading(document, "Analysis Summary")

    summary_rows = [
        [
            "Total geographic units",
            format_number(level_data.get("total_units"), 0)
        ],
        [
            "Mean priority score",
            format_number(stats.get("mean"))
        ],
        [
            "Median priority score",
            format_number(stats.get("median"))
        ],
        [
            "Minimum priority score",
            format_number(stats.get("minimum"))
        ],
        [
            "Maximum priority score",
            format_number(stats.get("maximum"))
        ]
    ]

    add_table(
        document,
        ["Indicator", "Value"],
        summary_rows
    )

    if distribution:
        add_section_heading(document, "Priority Distribution")

        distribution_rows = [
            [str(priority), format_number(count, 0)]
            for priority, count in distribution.items()
        ]

        add_table(
            document,
            ["Priority Category", "Number of Units"],
            distribution_rows
        )


def add_top_areas(document, level_data):
    areas = level_data.get("top_priority_areas", [])

    if not areas:
        return

    add_section_heading(
        document,
        "Highest-Priority Geographic Units"
    )

    # These keys match the actual output of data_preparation.py.
    field_config = [
        ("area_name", "Area"),
        ("priority_score", "Priority Score"),
        ("priority_tier", "Priority Tier"),
        ("population", "Population"),
        ("hospital_records", "Hospitals"),
        ("public_hospitals", "Public Hospitals"),
        ("private_hospitals", "Private Hospitals"),
        ("total_beds", "Total Beds"),
        (
            "nearest_hospital_distance_km",
            "Nearest Hospital (km)"
        ),
        ("availability_gap", "Availability Gap")
    ]

    available_fields = [
        (key, label)
        for key, label in field_config
        if any(key in area for area in areas)
    ]

    rows = []

    for area in areas:
        row = []

        for key, label in available_fields:
            value = area.get(key)

            if isinstance(value, (int, float)):
                if key == "population":
                    value = format_number(value, 0)
                else:
                    value = format_number(value, 2)

            elif value is None:
                value = "Not available"

            row.append(str(value))

        rows.append(row)

    headers = [
        label
        for key, label in available_fields
    ]

    add_table(document, headers, rows)


def add_analysis_text(document, analysis_level):
    add_section_heading(document, "Key Findings")

    findings = analysis_level.get("key_findings", [])
    add_bullet_list(document, findings)

    add_section_heading(document, "Planning Recommendations")

    recommendations = analysis_level.get(
        "planning_recommendations",
        []
    )

    add_bullet_list(document, recommendations)

    add_section_heading(document, "Final Interpretation")

    interpretation = analysis_level.get(
        "final_interpretation",
        "No final interpretation was generated."
    )

    paragraph = document.add_paragraph(str(interpretation))
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.paragraph_format.space_after = Pt(8)


# ---------------------------------------------------------
# MAIN DOCUMENT GENERATOR
# ---------------------------------------------------------

def generate_city_report(city_data, analysis, output_path=None):

    city = city_data.get("city", "Unknown City")

    if not output_path:
        filename = (
            f"{safe_filename(city)}_healthcare_analysis_report.docx"
        )

        output_path = os.path.join(
            tempfile.gettempdir(),
            filename
        )

    output_directory = os.path.dirname(
        os.path.abspath(output_path)
    )

    os.makedirs(output_directory, exist_ok=True)

    document = Document()

    # -----------------------------------------------------
    # PAGE FORMATTING
    # -----------------------------------------------------

    section = document.sections[0]

    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.65)
    section.right_margin = Inches(0.65)

    normal_style = document.styles["Normal"]
    normal_style.font.name = "Arial"
    normal_style.font.size = Pt(9)
    normal_style.font.color.rgb = RGBColor(45, 45, 45)

    for style_name in ["Heading 1", "Heading 2", "Heading 3"]:
        style = document.styles[style_name]
        style.font.name = "Arial"
        style.font.color.rgb = RGBColor(36, 71, 107)

    # -----------------------------------------------------
    # HEADER AND FOOTER
    # -----------------------------------------------------

    header = section.header.paragraphs[0]
    header.text = "HEALTHCARE ACCESSIBILITY ANALYSIS"
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    for run in header.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(110, 110, 110)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

    footer_run = footer.add_run(
        f"{city} | Healthcare Priority Analysis"
    )

    footer_run.font.size = Pt(8)
    footer_run.font.color.rgb = RGBColor(110, 110, 110)

    # -----------------------------------------------------
    # MATCH ANALYSIS LEVELS
    # -----------------------------------------------------

    city_levels = city_data.get("analysis_levels", [])
    generated_levels = analysis.get("analysis_levels", [])

    analysis_lookup = {
        str(level.get("level_name", "")).strip().lower(): level
        for level in generated_levels
    }

    # -----------------------------------------------------
    # INTRODUCTION
    # -----------------------------------------------------

    add_city_overview(document, city_data)

    # -----------------------------------------------------
    # GEOGRAPHIC ANALYSIS LEVELS
    # -----------------------------------------------------

    for index, level_data in enumerate(city_levels):

        level_name = level_data.get(
            "level_name",
            f"Analysis Level {index + 1}"
        )

        matching_analysis = analysis_lookup.get(
            str(level_name).strip().lower(),
            {}
        )

        if index > 0:
            document.add_page_break()

        document.add_heading(
            f"{level_name}",
            level=1
        )

        # Priority map
        add_map_to_document(
            document,
            level_data.get("map_file"),
            level_name
        )

        # Source-derived statistics
        add_statistics(document, level_data)

        # Top priority areas
        add_top_areas(document, level_data)

        # AI-generated qualitative analysis
        add_analysis_text(document, matching_analysis)

    # -----------------------------------------------------
    # SAVE DOCUMENT
    # -----------------------------------------------------

    document.save(output_path)

    return output_path
