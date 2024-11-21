import csv

def process_csv(input_file, output_file):
    try:
        # Open the input CSV file
        with open(input_file, 'r') as csv_file:
            csv_reader = csv.reader(csv_file)  # Create a CSV reader object
            
            # Open the output text file
            with open(output_file, 'w') as txt_file:
                for row in csv_reader:
                    if len(row) >= 1:  # Ensure there is at least one column
                        txt_file.write(row[0] + '\n')  # Write the first column to the output file
        print(f"Processed successfully. Output written to '{output_file}'.")
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
input_csv = 'unigram_freq.csv'  # Replace with your input file path
output_txt = 'dict.txt'  # Replace with your desired output file path

process_csv(input_csv, output_txt)
