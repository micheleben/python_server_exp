import re
from datetime import datetime

def sort_files_by_datetime(file_list):
    # Define a regex pattern to extract the datetime part
    # This looks for a pattern of 8 digits followed by underscore and 4 digits at the end of the string
    pattern = r'.*_(\d{8}_\d{4})$'
    
    # Function to extract datetime from filename and convert to sortable datetime object
    def extract_datetime(filename):
        match = re.match(pattern, filename)
        if match:
            datetime_str = match.group(1)  # Get the captured group (yyyymmdd_HHMM)
            try:
                # Parse the datetime string into a datetime object
                dt = datetime.strptime(datetime_str, '%Y%m%d_%H%M')
                return dt
            except ValueError:
                # If parsing fails, return the minimum datetime to sort it first
                return datetime.min
        # If the pattern doesn't match, return the minimum datetime
        return datetime.min
    
    # Sort the list based on the extracted datetime
    sorted_files = sorted(file_list, key=extract_datetime)
    
    return sorted_files

# Example usage
files = [
    "data_report_20230415_1430",
    "experiment_results_20220310_0945",
    "lab_notes_20230101_0000",
    "analysis_output_20230415_0800"
]

sorted_files = sort_files_by_datetime(files)
for file in sorted_files:
    print(file)