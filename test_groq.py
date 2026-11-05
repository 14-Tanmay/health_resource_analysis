import json

from report_generator.data_preparation import prepare_city_report_data
from report_generator.groq_analysis import generate_city_analysis

city_data = prepare_city_report_data("chennai")

analysis = generate_city_analysis(city_data)

print(json.dumps(analysis, indent=4, ensure_ascii=False))

