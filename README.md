---------------------------------------------------
Plaint-text Incremental Compression (PIC) Technique
---------------------------------------------------

Description:
------------
It is a dictionary-based compresssion technique. 
In this technique, it generates a hash-map of all words in the dictionary and generates a code-word (encoding) 
based on the frequency of words/letter/punctuations. 

NOTE: This README is out of date and is scheduled for a rewrite. It describes an
earlier PIC-only version and does not yet document TIC. For current, accurate
documentation see docs/environment.md, docs/datasets.md and docs/licensing.md.

Main Files:
-----------
1. dict.txt:
2. epic-v3.1.cpp epic-v3.1.h: new enhanced PIC compression C++ file (Multi-threading version)
3. pic-v3.1.cpp pic-v3.1.h: PIC compression C++ file (the comparison scheme)

Complementary Files:
--------------------
1. measureTime.py: measuring the process time
2. pre-process-dict.py: pre-process and clean the dictionary file

Removed from the release artifact:
----------------------------------
The following are no longer part of this repository. Their historical state is
preserved at the Git tag pre-artifact-cleanup
(git checkout pre-artifact-cleanup -- <path>):

1. old_versions/    superseded C++ sources, including pic-v1.cpp and epic-v1.cpp
2. backup_versions/ manual .bk snapshots
3. search_outputs/  captured search run output
4. debug_pic_tic_outputs/ captured debug run output
5. test-code/       development-only C++ test files (removed earlier, in 33d95fb)

