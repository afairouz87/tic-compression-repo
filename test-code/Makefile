# Compiler
CXX = g++
# Compiler flags
CXXFLAGS = -std=c++11
# Target executables
TARGETS = test_generate_file test
# Source files
SOURCES = test_generate_file.cpp test.cpp

# Default target builds all executables
all: $(TARGETS)

# Rule to build each target from its corresponding source
test_generate_file: test_generate_file.cpp
	$(CXX) $(CXXFLAGS) test_generate_file.cpp -o test_generate_file

test: test.cpp
	$(CXX) $(CXXFLAGS) test.cpp -o test

# Clean target to remove all executables
clean:
	rm -f $(TARGETS)