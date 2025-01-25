import subprocess
import time

def measure_execution_time(binary_path, *args):
    """
    Measures the execution time of a C++ binary program.
    
    Parameters:
    - binary_path (str): Path to the compiled C++ binary program.
    - *args: Command-line arguments to pass to the binary program.
    
    Returns:
    - execution_time (float): Execution time in seconds.
    """
    try:
        # Record the start time
        start_time = time.perf_counter()

        # Run the C++ binary program
        subprocess.run([binary_path, *args], check=True)

        # Record the end time
        end_time = time.perf_counter()

        # Calculate the execution time
        execution_time = end_time - start_time

        return execution_time

    except subprocess.CalledProcessError as e:
        print(f"Error: The binary program exited with a non-zero status. {e}")
    except FileNotFoundError:
        print("Error: Binary program not found. Check the path.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# Example usage
if __name__ == "__main__":
    binary_path = "./pic-v1"  # Replace with the path to your binary
    args = ["arg1", "arg2"]  # Add any required arguments for your C++ binary

    execution_time = measure_execution_time(binary_path, *args)
    if execution_time is not None:
        print(f"Execution time: {execution_time:.6f} seconds")
