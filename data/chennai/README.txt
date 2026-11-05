Chennai website inputs
=======================

Existing ward-level analysis (retained)
---------------------------------------
chennai_final_ward_analytical_dataset.csv
    Final 155-row ward analytical dataset and priority ranking.
chennai_final_healthcare_priority.gpkg
    Final ward polygons; layer: final_ward_priority.
healthcare_facilities_beds_geocoded.csv
    Coordinate-complete healthcare facility inventory used for ward map markers.

New settlement-level analysis
-----------------------------
settlements/chennai_settlement_priority.csv
    Final 202-row settlement priority dataset, including Model C components.
settlements/chennai_settlement_priority.gpkg
    Settlement geometries and priority attributes; layer: settlement_priority.
settlements/maps/*.png
    Four supplied thematic maps.
settlements/interactive/chennai_interactive_accessibility_map.html
    Supplied interactive accessibility map.

The dashboard displays the supplied settlement scores and geometries without recalculating them.
The settlement analysis uses Model C: 0.51D + 0.34G + 0.15S. Its distance input
is nearest healthcare facility distance (any facility type), and socioeconomic
vulnerability is a district-level income proxy. See the in-dashboard notes for
additional limitations and interpretation.
