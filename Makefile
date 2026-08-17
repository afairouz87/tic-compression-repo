# Compiler
CXX = g++

# Compiler flags
CXXFLAGS = -std=c++17 -O3

# Target executables
TARGETS = pic-v3.1 epic-v3.1

# Default target builds all executables
all: $(TARGETS)

# Rules
pic-v3.1: pic-v3.1.cpp
	$(CXX) $(CXXFLAGS) pic-v3.1.cpp -o pic-v3.1

epic-v3.1: epic-v3.1.cpp
	$(CXX) $(CXXFLAGS) epic-v3.1.cpp -o epic-v3.1

# Optional aliases
pic: pic-v3.1
epic: epic-v3.1

# Clean target
clean:
	rm -f $(TARGETS)