# Compiler
CXX = g++
# Compiler flags
CXXFLAGS = -std=c++11
# Target executable name
TARGET = test_generate_file
# Source file
SRC = test_generate_file.cpp

# Default target
all: $(TARGET)

# Build target
$(TARGET): $(SRC)
	$(CXX) $(CXXFLAGS) $(SRC) -o $(TARGET)

# Clean target to remove the executable
clean:
	rm -f $(TARGET)

