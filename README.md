---------------------------------------------------
Plaint-text Incremental Compression (PIC) Technique
---------------------------------------------------

Description:
------------
It is a dictionary-based compresssion technique. 
In this technique, it generates a hash-map of all words in the dictionary and generates a code-word (encoding) 
based on the frequency of words/letter/punctuations. 

Main Files:
-----------
1. dict.txt:
2. pic-v1.cpp: old PIC compression C++ file 
3. epic-v3.1.cpp epic-v3.1.h: new enhanced PIC compression C++ file (Multi-threading version)
3. epic-v1.cpp: new enhanced PIC compression C++ file (Single thread version)

Complementary Files:
--------------------
1. measureTime.py: measuring the process time
2. pre-process-dict.py: pre-process and clean the dictionary file

Complementary Directories:
--------------------------
1. test-code: includes all the test C++ files for testing functions.

