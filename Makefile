# Compiler
CXX = g++
# Compiler flags
CXXFLAGS = -std=c++17
# Target executables
TARGETS = pic-v3.1 epic-v3.1
# Source files
SOURCES = pic-v3.1.cpp epic-v3.1.cpp

# Default target builds all executables
all: $(TARGETS)

# Rule to build each target from its corresponding source
pic: pic-v3.1.cpp
	$(CXX) $(CXXFLAGS) pic-v3.1.cpp -o pic-v3.1

epic: epic-v3.1.cpp
	$(CXX) $(CXXFLAGS) epic-v3.1.cpp -o epic-v3.1

# Clean target to remove all executables
clean:
	rm -f $(TARGETS)