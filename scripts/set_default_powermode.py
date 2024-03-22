import sys
import re

# Retrieve file path and replacement number from command line arguments
nvpmodel_conf_file_path = sys.argv[1]
power_mode = sys.argv[2]

# Define a regular expression pattern to match lines with < PM_CONFIG DEFAULT= >
pattern = re.compile(r'< PM_CONFIG DEFAULT=\d+ >')

# Read the content of the file
with open(nvpmodel_conf_file_path, 'r') as file:
    lines = file.readlines()

# Modify the specific line
with open(nvpmodel_conf_file_path, 'w') as file:
    for line in lines:
        if pattern.match(line.strip()):
            # Replace the number after DEFAULT= with the new number
            file.write(f'< PM_CONFIG DEFAULT={power_mode} >\n')
        else:
            file.write(line)