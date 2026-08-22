# Build for the TIC/PIC artifact.
#
# Portability notes:
#  - CXX is overridable:  make CXX=g++-14        (defaults to g++)
#  - -pthread is required on Linux/GCC because both binaries use std::thread.
#    It is harmless on macOS/Apple clang.
#  - Header dependencies are declared, so editing a .h triggers a rebuild.
#    (Previously it did not, and the binary silently went stale.)
#
# Verify the toolchain first with:  python3 check_environment.py

# Compiler. `?=` is not usable here: make predefines CXX=c++, so `?=` would
# never fire. Overriding only when the value came from make's built-in default
# keeps `make CXX=g++-14` and an exported $CXX working.
ifeq ($(origin CXX),default)
CXX = g++
endif

# Compiler flags
CXXFLAGS ?= -std=c++17 -O3 -pthread

# Extra flags for the warning audit: make warnings
WARNFLAGS = -Wall -Wextra

# Target executables
TARGETS = pic-v3.1 epic-v3.1

# Default target builds all executables
all: $(TARGETS)

# Rules
pic-v3.1: pic-v3.1.cpp pic-v3.1.h
	$(CXX) $(CXXFLAGS) pic-v3.1.cpp -o pic-v3.1

epic-v3.1: epic-v3.1.cpp epic-v3.1.h
	$(CXX) $(CXXFLAGS) epic-v3.1.cpp -o epic-v3.1

# Optional aliases
pic: pic-v3.1
epic: epic-v3.1

# Compile-only warning audit; writes no binaries.
# See docs/environment.md for the documented, accepted warnings.
warnings:
	@echo "== epic-v3.1.cpp =="
	-@$(CXX) $(CXXFLAGS) $(WARNFLAGS) -fsyntax-only epic-v3.1.cpp
	@echo "== pic-v3.1.cpp =="
	-@$(CXX) $(CXXFLAGS) $(WARNFLAGS) -fsyntax-only pic-v3.1.cpp

# Clean target
clean:
	rm -f $(TARGETS)

.PHONY: all pic epic warnings clean
