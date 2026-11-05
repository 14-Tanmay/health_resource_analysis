
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from scipy.stats import spearmanr, kendalltau


# ---------------------------------------------------------
# 1. LOAD LUCKNOW URBAN DATA
# ---------------------------------------------------------

DATA_PATH = os.path.join(
    "data",
    "lucknow_urban_healthcare_priority_scores_model_c.csv"
)

OUTPUT_DIR = "weight_sensitivity_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

df = pd.read_csv(DATA_PATH)

print("Dataset loaded successfully.")
print("Total records:", len(df))


# ---------------------------------------------------------
# 2. DEFINE REQUIRED COMPONENTS
# ---------------------------------------------------------

components = [
    "distance_score",
    "population_score",
    "combined_availability_gap",
    "public_gap_score",
    "socioeconomic_vulnerability_score"
]

required_columns = [
    "map_unit_id",
    "priority_score_model_c"
] + components

missing_columns = [
    col for col in required_columns
    if col not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Missing required columns: {missing_columns}"
    )


# Convert component columns to numeric
for col in components + ["priority_score_model_c"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")


# Remove rows with missing component scores
initial_count = len(df)

df = df.dropna(
    subset=components + ["priority_score_model_c"]
).copy()

print("Records removed due to missing scores:",
      initial_count - len(df))

if df.empty:
    raise ValueError("No complete records available for analysis.")


# ---------------------------------------------------------
# 3. DEFINE THREE WEIGHTING SCHEMES
# ---------------------------------------------------------

weights = {

    "Original_Model_C": {
        "distance_score": 0.25,
        "population_score": 0.15,
        "combined_availability_gap": 0.35,
        "public_gap_score": 0.10,
        "socioeconomic_vulnerability_score": 0.15
    },

    "Equal_Weights": {
        "distance_score": 0.20,
        "population_score": 0.20,
        "combined_availability_gap": 0.20,
        "public_gap_score": 0.20,
        "socioeconomic_vulnerability_score": 0.20
    },

    "Alternative_Model": {
        "distance_score": 0.40,
        "population_score": 0.05,
        "combined_availability_gap": 0.10,
        "public_gap_score": 0.30,
        "socioeconomic_vulnerability_score": 0.15
    }
}


# Validate weights
for model_name, model_weights in weights.items():

    if not np.isclose(sum(model_weights.values()), 1.0):
        raise ValueError(
            f"Weights for {model_name} do not sum to 1."
        )


# ---------------------------------------------------------
# 4. CALCULATE PRIORITY SCORES
# ---------------------------------------------------------

for model_name, model_weights in weights.items():

    df[model_name + "_score"] = sum(
        df[component] * weight
        for component, weight in model_weights.items()
    )


# ---------------------------------------------------------
# 5. CALCULATE RANKINGS
# ---------------------------------------------------------

df["Original_Model_C_rank"] = (
    df["priority_score_model_c"]
    .rank(ascending=False, method="min")
)

df["Equal_Weights_rank"] = (
    df["Equal_Weights_score"]
    .rank(ascending=False, method="min")
)

df["Alternative_Model_rank"] = (
    df["Alternative_Model_score"]
    .rank(ascending=False, method="min")
)


# ---------------------------------------------------------
# 6. VERIFY ORIGINAL FORMULA
# ---------------------------------------------------------

df["reconstructed_model_c_score"] = df[
    "Original_Model_C_score"
] if "Original_Model_C_score" in df.columns else (
    df["Original_Model_C_score"]
    if "Original_Model_C_score" in df.columns
    else (
        0.25 * df["distance_score"]
        + 0.15 * df["population_score"]
        + 0.35 * df["combined_availability_gap"]
        + 0.10 * df["public_gap_score"]
        + 0.15 * df["socioeconomic_vulnerability_score"]
    )
)

df["original_score_difference"] = (
    df["priority_score_model_c"]
    - df["reconstructed_model_c_score"]
)

print("\nOriginal Model C verification")
print(
    "Maximum absolute score difference:",
    df["original_score_difference"].abs().max()
)


# ---------------------------------------------------------
# 7. RANK CORRELATION ANALYSIS
# ---------------------------------------------------------

model_pairs = [
    (
        "Original vs Equal",
        "Original_Model_C_rank",
        "Equal_Weights_rank"
    ),
    (
        "Original vs Alternative",
        "Original_Model_C_rank",
        "Alternative_Model_rank"
    ),
    (
        "Equal vs Alternative",
        "Equal_Weights_rank",
        "Alternative_Model_rank"
    )
]

correlation_results = []

for comparison, rank1, rank2 in model_pairs:

    spearman_value, spearman_p = spearmanr(
        df[rank1],
        df[rank2]
    )

    kendall_value, kendall_p = kendalltau(
        df[rank1],
        df[rank2]
    )

    correlation_results.append({
        "Comparison": comparison,
        "Spearman_Correlation": spearman_value,
        "Spearman_P_Value": spearman_p,
        "Kendall_Correlation": kendall_value,
        "Kendall_P_Value": kendall_p
    })


correlation_df = pd.DataFrame(correlation_results)


# ---------------------------------------------------------
# 8. TOP 10 PRIORITY WARD OVERLAP
# ---------------------------------------------------------

top_n = min(10, len(df))

top_10 = {}

for model_name, rank_column in [
    ("Original Model C", "Original_Model_C_rank"),
    ("Equal Weights", "Equal_Weights_rank"),
    ("Alternative Model", "Alternative_Model_rank")
]:

    top_10[model_name] = set(
        df.nsmallest(top_n, rank_column)["map_unit_id"]
    )


overlap_results = []

model_names = list(top_10.keys())

for i in range(len(model_names)):

    for j in range(i + 1, len(model_names)):

        model1 = model_names[i]
        model2 = model_names[j]

        common = top_10[model1].intersection(
            top_10[model2]
        )

        overlap_results.append({
            "Comparison": f"{model1} vs {model2}",
            "Common_Top_10_Wards": len(common),
            "Overlap_Percentage": (
                len(common) / top_n
            ) * 100,
            "Common_Ward_IDs": ", ".join(
                map(str, sorted(common, key=str))
            )
        })


overlap_df = pd.DataFrame(overlap_results)


# ---------------------------------------------------------
# 9. CALCULATE RANK CHANGES
# ---------------------------------------------------------

df["Equal_Rank_Change"] = (
    df["Equal_Weights_rank"]
    - df["Original_Model_C_rank"]
)

df["Alternative_Rank_Change"] = (
    df["Alternative_Model_rank"]
    - df["Original_Model_C_rank"]
)

# Positive rank change means the ward moved down.
# Negative rank change means the ward moved up.

df["Equal_Absolute_Rank_Change"] = (
    df["Equal_Rank_Change"].abs()
)

df["Alternative_Absolute_Rank_Change"] = (
    df["Alternative_Rank_Change"].abs()
)


# ---------------------------------------------------------
# 10. IDENTIFY MOST AFFECTED WARDS
# ---------------------------------------------------------

most_changed_equal = df.nlargest(
    10,
    "Equal_Absolute_Rank_Change"
)

most_changed_alternative = df.nlargest(
    10,
    "Alternative_Absolute_Rank_Change"
)


# ---------------------------------------------------------
# 11. DISPLAY RESULTS
# ---------------------------------------------------------

print("\n========== RANK CORRELATION ==========")
print(correlation_df.to_string(index=False))

print("\n========== TOP 10 OVERLAP ==========")
print(overlap_df.to_string(index=False))

print("\n========== TOP 10: ORIGINAL MODEL C ==========")
print(
    df.nsmallest(10, "Original_Model_C_rank")[
        ["map_unit_id", "priority_score_model_c",
         "Original_Model_C_rank"]
    ].to_string(index=False)
)

print("\n========== TOP 10: EQUAL WEIGHTS ==========")
print(
    df.nsmallest(10, "Equal_Weights_rank")[
        ["map_unit_id", "Equal_Weights_score",
         "Equal_Weights_rank"]
    ].to_string(index=False)
)

print("\n========== TOP 10: ALTERNATIVE MODEL ==========")
print(
    df.nsmallest(10, "Alternative_Model_rank")[
        ["map_unit_id", "Alternative_Model_score",
         "Alternative_Model_rank"]
    ].to_string(index=False)
)

print("\n========== MOST CHANGED WARDS: EQUAL MODEL ==========")
print(
    most_changed_equal[
        ["map_unit_id", "Original_Model_C_rank",
         "Equal_Weights_rank", "Equal_Rank_Change"]
    ].to_string(index=False)
)

print("\n========== MOST CHANGED WARDS: ALTERNATIVE MODEL ==========")
print(
    most_changed_alternative[
        ["map_unit_id", "Original_Model_C_rank",
         "Alternative_Model_rank", "Alternative_Rank_Change"]
    ].to_string(index=False)
)


# ---------------------------------------------------------
# 12. SAVE OUTPUT FILES
# ---------------------------------------------------------

df.to_csv(
    os.path.join(
        OUTPUT_DIR,
        "lucknow_urban_all_model_scores_and_ranks.csv"
    ),
    index=False
)

correlation_df.to_csv(
    os.path.join(
        OUTPUT_DIR,
        "rank_correlation_results.csv"
    ),
    index=False
)

overlap_df.to_csv(
    os.path.join(
        OUTPUT_DIR,
        "top_10_overlap_results.csv"
    ),
    index=False
)

most_changed_equal.to_csv(
    os.path.join(
        OUTPUT_DIR,
        "most_changed_wards_equal_weights.csv"
    ),
    index=False
)

most_changed_alternative.to_csv(
    os.path.join(
        OUTPUT_DIR,
        "most_changed_wards_alternative_model.csv"
    ),
    index=False
)


# ---------------------------------------------------------
# 13. VISUALIZATION: RANK COMPARISON
# ---------------------------------------------------------

plt.figure(figsize=(9, 7))

plt.scatter(
    df["Original_Model_C_rank"],
    df["Equal_Weights_rank"],
    alpha=0.7
)

plt.xlabel("Original Model C Rank")
plt.ylabel("Equal Weight Model Rank")
plt.title("Original Model C vs Equal Weight Model")

plt.plot(
    [1, len(df)],
    [1, len(df)],
    linestyle="--"
)

plt.tight_layout()

plt.savefig(
    os.path.join(
        OUTPUT_DIR,
        "original_vs_equal_rank.png"
    ),
    dpi=300
)

plt.show()


plt.figure(figsize=(9, 7))

plt.scatter(
    df["Original_Model_C_rank"],
    df["Alternative_Model_rank"],
    alpha=0.7
)

plt.xlabel("Original Model C Rank")
plt.ylabel("Alternative Model Rank")
plt.title("Original Model C vs Alternative Model")

plt.plot(
    [1, len(df)],
    [1, len(df)],
    linestyle="--"
)

plt.tight_layout()

plt.savefig(
    os.path.join(
        OUTPUT_DIR,
        "original_vs_alternative_rank.png"
    ),
    dpi=300
)

plt.show()


# ---------------------------------------------------------
# 14. VISUALIZATION: RANK CHANGE DISTRIBUTION
# ---------------------------------------------------------

plt.figure(figsize=(9, 6))

plt.hist(
    df["Equal_Rank_Change"],
    bins=20,
    edgecolor="black"
)

plt.xlabel("Change in Rank")
plt.ylabel("Number of Wards")
plt.title("Rank Changes: Equal Weight Model vs Original Model")

plt.tight_layout()

plt.savefig(
    os.path.join(
        OUTPUT_DIR,
        "equal_weight_rank_change_distribution.png"
    ),
    dpi=300
)

plt.show()


plt.figure(figsize=(9, 6))

plt.hist(
    df["Alternative_Rank_Change"],
    bins=20,
    edgecolor="black"
)

plt.xlabel("Change in Rank")
plt.ylabel("Number of Wards")
plt.title("Rank Changes: Alternative Model vs Original Model")

plt.tight_layout()

plt.savefig(
    os.path.join(
        OUTPUT_DIR,
        "alternative_rank_change_distribution.png"
    ),
    dpi=300
)

plt.show()


print("\n======================================")
print("SENSITIVITY ANALYSIS COMPLETED")
print("Results saved in:", OUTPUT_DIR)
print("======================================")
