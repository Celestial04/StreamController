import os

def prepend_to_files(directory, prepend_string):
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            new_filename = prepend_string + filename
            os.rename(file_path, os.path.join(directory, new_filename))
            print(f"Renamed {filename} to {new_filename}")
        elif os.path.isdir(file_path):
            # It's a directory, recurse into it
            prepend_to_files(file_path, prepend_string)

# Usage
directory_path = 'flatpak/icons/'  # Replace with your directory path
prepend_string = 'com.core447.StreamController:'  # Replace with the string you want to prepend
prepend_to_files(directory_path, prepend_string)