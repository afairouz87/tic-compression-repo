# Compiler
CXX = g++
# Compiler flags
CXXFLAGS = -std=c++11
# Target executables
TARGETS = pic-v1 epic-v1 epic-v2
# Source files
SOURCES = pic-v1.cpp epic-v1.cpp epic-v2.cpp

# Default target builds all executables
all: $(TARGETS)

# Rule to build each target from its corresponding source
pic: pic-v1.cpp
	$(CXX) $(CXXFLAGS) pic-v1.cpp -o pic-v1

epic: epic-v1.cpp
	$(CXX) $(CXXFLAGS) epic-v1.cpp -o epic-v1

epic2: epic-v2.cpp
	$(CXX) $(CXXFLAGS) epic-v2.cpp -o epic-v2

# Clean target to remove all executables
clean:
	rm -f $(TARGETS)