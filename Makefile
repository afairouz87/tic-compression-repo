# Compiler
CXX = g++
# Compiler flags
CXXFLAGS = -std=c++11
# Target executables
<<<<<<< HEAD
TARGETS = epic-v3.1
# Source files
SOURCES = epic-v3.1.cpp
=======
TARGETS = pic-v3.1 epic-v3.1
# Source files
SOURCES = pic-v3.1.cpp epic-v3.1.cpp
>>>>>>> d26d2008968ff2dfa2223e144344dd686fb6bc61

# Default target builds all executables
all: $(TARGETS)

# Rule to build each target from its corresponding source
<<<<<<< HEAD
# pic: pic-v1.cpp
# 	$(CXX) $(CXXFLAGS) pic-v1.cpp -o pic-v1

# epic: epic-v1.cpp
# 	$(CXX) $(CXXFLAGS) epic-v1.cpp -o epic-v1

# epic2: epic-v2.cpp
# 	$(CXX) $(CXXFLAGS) epic-v2.cpp -o epic-v2

# epic3: epic-v3.cpp
# 	$(CXX) $(CXXFLAGS) epic-v3.cpp -o epic-v3

epic31: epic-v3.1.cpp
=======
pic: pic-v3.1.cpp
	$(CXX) $(CXXFLAGS) pic-v3.1.cpp -o pic-v3.1

epic: epic-v3.1.cpp
>>>>>>> d26d2008968ff2dfa2223e144344dd686fb6bc61
	$(CXX) $(CXXFLAGS) epic-v3.1.cpp -o epic-v3.1

# Clean target to remove all executables
clean:
	rm -f $(TARGETS)