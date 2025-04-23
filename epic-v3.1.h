// Header file
// All functions declarations

#include <iostream>
#include <cstdint> // For uint8_t
#include <fstream>
#include <sstream>
#include <unordered_map>  // hash table library: (key,value) pair
#include <string>
#include <math.h>  // math library
#include <cctype> // For std::ispunct
#include <vector>
#include <bitset>
#include <iomanip>
#include <algorithm>

#include <mutex>
#include <stdexcept>

#include <chrono> // for sleep and execution time calculation
#include <thread>

using namespace std;
using namespace chrono;
namespace fs = std::filesystem;

// *** Reserved codeWords in T0: space, new line, next capital
/*
This is used to shift the codeWord by 
the reserved codeWords (space, newline, nextCapital).
*/ 
#define CODE_WORD_OFFSET 4    // number of reserved code-words

// These reserved code-words nedds to be shifted to the left by 1, and insert a zero.
#define SPACE_CODE 0x0        // represent a space
#define NEW_LINE_CODE 0x1     // represent a newline 
#define NEXT_CAPITAL_CODE 0x2 // represent an uppercase letter of the first character of the next word
#define NEXT_SPECIAL_CODE 0x3 // represent a special code word in the next bytes of the encoded file
// *******************************

// Pre-calculated offset for each code-word type (T0, T1, T2, ...)
#define TWO_BYTE_OFFSET 128 // = pow(2,7)
#define THREE_BYTE_OFFSET 16512 // = ( pow(2,7) + pow(2,14) )
#define FOUR_BYTE_OFFSET 2113664 // = ( pow(2,7) + pow(2,14) + pow(2,21) )
#define ONE_BYTE_LOWER_BOUND CODE_WORD_OFFSET
#define ONE_BYTE_BOUND 128 // = pow(2,7)
#define TWO_BYTE_BOUND 16512 // = ( pow(2,7) + pow(2,14) )
#define THREE_BYTE_BOUND 2113664 // = ( pow(2,7) + pow(2,14) + pow(2,21) )
#define FOUR_BYTE_BOUND 270549120 // = ( pow(2,7) + pow(2,14) + pow(2,21) + pow(2,28) )


uint32_t MASK_BYTE = 0x0000007f; // Mask value for the least significant byte (LSB)

uint8_t Build_Dictionary_Table_Compression();
uint8_t Build_Dictionary_Table_Decompression();
vector<uint8_t> ONE_BYTE_CODE_GENERATOR(uint32_t input);
vector<uint8_t> TWO_BYTE_CODE_GENERATOR(uint32_t input);
vector<uint8_t> THREE_BYTE_CODE_GENERATOR(uint32_t input);
vector<uint8_t> SPECIAL_CODE_WORD_GENERATOR(string input);
string SPECIAL_CODE_WORD_READER_BYTES(vector<uint8_t> bytes);
string SPECIAL_CODE_WORD_READER(ifstream *filePtr);
//vector<uint8_t> SPECIAL_CODE_WORD_GENERATOR(const string &input);

// Hello Test

uint8_t Mask_Single_Byte(uint32_t number);
uint32_t Shift_Left_with_One_Inserted(uint32_t number);
uint32_t Shift_Left_with_Zero_Inserted(uint32_t number);
uint32_t Shift_Right_Seven_Positions(uint32_t number);

uint8_t Compression_Function(const string& inputFile, streampos start, streampos end, const string& outputFile);
uint8_t Decompression_Function(const string& inputFileNameBin, streampos start, streampos end, const string& outputFileNameText);

uint32_t Lookup_Function(const string& inputFileNameBin, streampos start, streampos end, 
    string searchString, int threadIndex, vector<uint32_t>& results);

uint32_t Lookup_and_Replace_Function(const string& inputFileNameBin, streampos start, streampos end, 
    const string& outputFileNameBin, string searchString, string replaceString, int threadIndex, vector<uint32_t>& results);

// uint32_t Lookup_and_Replace_Function(const string& inputFileNameBin, streampos start, streampos end, 
//         const string& outputFileNameBin, string searchString, string replaceString, int threadIndex, vector<uint32_t>& results, char preservedDelimiter);

// Reading a plain text file functions
uint8_t processFile(const string &filePath);
vector<string> processLineChar(const string &line); // return a vector of strings
//vector<string> processLineChar(const string &line, ofstream *file); // return a vector of strings
//vector<uint8_t> processLineChar(const string &line, ofstream *file); // return a vector of strings
vector<uint8_t> convertStringToCodeWord(vector<string> word);
vector<uint8_t> convertSearchStringToCodeWord(vector<string> wordsSet);

char checkStringEndsWithPunctuation(const string &str);
void checkLinesInFile(const string &filePath);
bool endsWithNewline(const string &str);

void printBinaryFile(const string &filePath);


//*** Multi Threading Functions ****

// ** Compression **
void mergeBinaryFiles(const vector<string>& tempFiles, const string& outputFile);
uint8_t splitAndProcessTextFile(const string& inputFile, const string& outputFile, int numThreads);

// ** Decompression **
void mergeTextFiles(const vector<string>& tempFiles, const string& outputFile);
uint8_t splitAndProcessBinaryFile(const string& inputFile, const string& outputFile, int numThreads);

// ** Lookup **
uint8_t splitAndProcessBinaryFileForSearch(const string& inputFile, const string& outputFile, int numThreads, string searchString);

// ** Lookup and Replace **
uint8_t splitAndProcessBinaryFileForSearchAndReplace(const string &inputFile, const string &outputFile, int numThreads, string searchString, string replaceString);

// Version 2
//uint8_t splitAndProcessBinaryFileWithReplacement(const string &inputFile, const string &outputFile, int numThreads, const string &searchString, const string &replaceString);

//********************************** 

uint32_t readCodeWords(vector<uint8_t> bytes);
uint32_t concatenateBytes(uint32_t final, uint32_t tmp, uint8_t count);

uint32_t countLinesInFile(const string &filePath); // read the number of words in the dictionary 
