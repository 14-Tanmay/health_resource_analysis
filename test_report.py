
from report_generator.data_preparation import prepare_city_report_data
from report_generator.groq_analysis import generate_city_analysis
from report_generator.document_generator import generate_city_report


city = "chennai"

print("Preparing city data...")
city_data = prepare_city_report_data(city)

print("Generating AI analysis...")
analysis = generate_city_analysis(city_data)

print("Generating Word report...")
output_path = generate_city_report(
    city_data,
    analysis,
    output_path=f"{city}_healthcare_analysis_report.docx"
)

print("\nReport generated successfully!")
print("File:", output_path)
