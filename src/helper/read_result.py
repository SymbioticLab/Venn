import re
import pandas as pd

# Define a regular expression pattern to extract relevant information
pattern = r"\[.*\]: fig/\['(.*?)', '.*', '.*', '.*'\]_(.*?)\.yml_Req\. comp\. rate: (.*?); Avg\. RCT: (.*?);"

# Initialize lists to store extracted data
schedulers = []
yaml_files = []
avg_rcts = []

# Read log entries from the file
with open('logging.txt', 'r') as file:
    log_entries = file.readlines()

# Extract data from log entries
for entry in log_entries:
    match = re.search(pattern, entry)
    if match:
        schedulers.append(match.group(1))
        yaml_files.append(match.group(2))
        avg_rcts.append(float(match.group(4)))  # Convert Avg. RCT to float

# Create a DataFrame to organize the extracted data
data = {
    "Scheduler": schedulers,
    "YAML File": yaml_files,
    "Avg. RCT": avg_rcts
}

df = pd.DataFrame(data)

# Display the DataFrame
print(df)
