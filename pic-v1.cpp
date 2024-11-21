/*

Title: Enhanced PIC (EPIC) compression
Author: Abbas A. Fairouz
Version: 1.0
Created: Sep. 17, 2024
Updated: Nov. 13, 2024

Word frequency reference:
https://www.kaggle.com/datasets/rtatman/english-word-frequency?resource=download

*/


#include <iostream>
#include <cstdint>
#include <fstream>
#include <sstream>
#include <unordered_map>  // hash table library: (key,value) pair
#include <string>
#include <math.h>  // math library
#include <cctype> // For std::ispunct
#include <vector>
#include <bitset>
#include <iomanip>

using namespace std;

#define TWO_SEVEN pow(2,7)
#define TWO_FOURTEEN pow(2,14)

/*
*** Notes for the byte codes range calculations ***
- Byte Code 1: BC1
- Byte Code 2: BC2
- Byte Code 3: BC3

0, 1, 2: reserved codes for the BC1
BC1 range:       3         --> (2^7) - 1
BC2 range:     (2^7)       --> (2^7) + (2^14) - 1
BC3 range: (2^7) + (2^14)  --> (2^7) + (2^14) + (2^21) - 1

BC2 offset: (2^7)
BC3 offset: (2^7) + (2^14)

*** Comments:
Dictionary table - implementation options:
1. Create multiple hash map tables: BC1 hash map, BC2 hash map, ... etc    ??
2. ..



*/

/*
This is used to shift the codeWord by 
the reserved codeWords (space, newline, nextCapital).
*/ 
#define CODE_WORD_OFFSET 3

// Reserved codeWords: space, new line, next capital
#define SPACE_CODE 0x0
#define NEW_LINE_CODE 0x1
#define NEXT_CAPITAL_CODE 0x2 

#define TWO_BYTE_OFFSET pow(2,7)
#define THREE_BYTE_OFFSET pow(2,7) + pow(2,14)
#define ONE_BYTE_BOUND pow(2,7) - 1
#define ONE_BYTE_LOWER_BOUND 0
#define TWO_BYTE_BOUND pow(2,7) + pow(2,14) - 1
//#define TWO_BYTE_MID (pow(2,7)-1) << 7
#define THREE_BYTE_BOUND pow(2,7) + pow(2,14) + pow(2,21) - 1 

uint32_t MASK_BYTE = 0x0000007f; // Mask value for the least significant byte (LSB)

uint8_t Build_Dictionary_Table();
vector<uint8_t> ONE_BYTE_CODE_GENERATOR(uint32_t input);
vector<uint8_t> TWO_BYTE_CODE_GENERATOR(uint32_t input);
vector<uint8_t> THREE_BYTE_CODE_GENERATOR(uint32_t input);

uint8_t Mask_Single_Byte(uint32_t number);
uint32_t Shift_Left_with_One_Inserted(uint32_t number);
uint32_t Shift_Left_with_Zero_Inserted(uint32_t number);
uint32_t Shift_Right_Seven_Positions(uint32_t number);

uint8_t Compression_Function();

// Reading a plain text file functions
uint8_t processFile(const string &filePath);
//vector<string> processLineChar(const string &line, ofstream *file); // return a vector of strings
vector<uint8_t> processLineChar(const string &line, ofstream *file); // return a vector of strings
void convertStringToCodeWord(const vector<string> &strings);
uint8_t checkNumberOfCodeByte(int serial);

char checkStringEndsWithPunctuation(const string &str);
void checkLinesInFile(const string &filePath);
bool endsWithNewline(const string &str);

void writeStringToFile(const string &filePath, const string &line);

void writeBinaryFile(ofstream *file, const vector<uint8_t> &data);
void writeBinaryFileOLD(const string &filePath, const vector<uint8_t> &data);


// Declare the unordered_map to store the word and serialized integer
unordered_map<string, int> dictMapWord; // Compression Hash Table
unordered_map<int, string> dictMapCode; // Decompression Hash Table

// File path of the CSV file
//string dictFilename = "unigram_freq.csv"; 
string dictFilename = "dict.txt"; 

// input plaint text file
//string inputFilename = "input_file.txt"; 
string inputFilename = "test1.txt"; 
string outputFilePath = "outputCompressed";

int main() {

    // **** TESTs ****
    // int TMP_NUM = ONE_BYTE_BOUND-1;
    // const int TWO_BYTE_MID = TMP_NUM << 7;
    // cout << "Two byte mid = " << TWO_BYTE_MID << "bits = " << bitset<14> (TWO_BYTE_MID) << endl;
    // ****************

    // Compression
    // Building the dictionary hash table
    cout << "Building the dictionary hash table.." << endl;
    if(Build_Dictionary_Table()==0)
        cout << "The dictionary hash table has been built successfully." << endl;
    else
        cout << "Error in building the dictionary hash table!" << endl;

    if(Compression_Function()==0)
        cout << "The compression function is successful." << endl;
    else
        cout << "Error in running the compression function!" << endl;


    return 0;
} // main function



/* OTHER FUNCTIONS */


uint8_t Build_Dictionary_Table(){
    // Variables to store each line and word
    string line, word;
    int serial = 0; // Start serializing from 0
    int tmpSerial;

    // Open the Text file
    ifstream file(dictFilename);

    // Check if the file is open
    if (!file.is_open()) {
        cerr << "Error opening file: " << dictFilename << endl;
        return 1;
    }

    // Read the file line by line
    while (getline(file, line)) {
        stringstream ss(line); // Use a stringstream to parse the line
        string temp; // To hold the "count" column which we will ignore
        
        // Get the word from the line
        // getline(ss, word, ','); 
        // getline(ss, temp, ','); // Ignore the second column (count)
        getline(ss, word, '\n'); 
        
        dictMapWord[word] = serial;
        serial++;
    }

    // Close the file after reading
    file.close();

    cout << "\nTotal words = " << serial-1 << "\n";
    cout << "The hash map has been generated successfully!\n\n";

    // Test the hash map
    cout << "Test the hash map:\n";
    string tmp_word = "wild";
    cout << "Word (" << tmp_word << ") has an order of: " << dictMapWord[tmp_word] << "\n";
    cout << "\n\n";

    return 0;
}


// Function to read a file line by line and process each line
uint8_t Compression_Function() {
    ifstream inFile(inputFilename); // Open the file
    if (!inFile) {
        cerr << "Error opening file: " << inputFilename << endl;
        return -1;
    }

    ofstream outFile(inputFilename, ios::binary | ios::app);
    if (!outFile) {
        cerr << "Error: Could not open the file." << endl;
        return 1;
    }

    string line;
    while (getline(inFile, line)) { // Read each line
        //vector<string> tokens = processLineChar(line, &outFile); // Process the line
        vector<uint8_t> tokens = processLineChar(line, &outFile); // Process the line
        //convertStringToCodeWord(tokens); // generate the codeWord and print it to the output binary file

        outFile.write(reinterpret_cast<const char*>(tokens.data()), tokens.size());

        // // ** Output the processed tokens **
        // // for (const auto &token : tokens) {
        // for (size_t i = 0; i < tokens.size(); ++i) {
        //     cout << tokens[i] << endl;
        // }
        // cout << endl;
    }

    inFile.close(); // Close the input file
    outFile.close(); // Close the output file

    return 0;
}


/* 
Abbas reached here.. 
You need to think on how to call byte generator 
based on the serial from wordMap, or special cases,
such as new line, space, next Capital, and puctuation.
*/
//vector<string> processLineChar(const string &line, ofstream *file) {
vector<uint8_t> processLineChar(const string &line, ofstream *file) {
    vector<string> result;
    vector<uint8_t> lineCodeWords;
    vector<uint8_t> codeWords;
    string word;
    bool startsWithUppercase = false; // Flag to indicate if the word starts with an uppercase letter

    uint8_t byteCode;
    uint8_t byteCode1, byteCode2, byteCode3;
    int serial;
    uint8_t codeRange;

    for (size_t i = 0; i < line.size(); ++i) {
        char ch = line[i];

        if (isalnum(ch)) { // If the character is alphanumeric, build the word
            if (word.empty() && isupper(ch)) {
                startsWithUppercase = true; // Set the flag if the first character is uppercase
                //cout << "Uppercase character..\n"; // for testing... 
            }
            word += ch;
        } 
        //else if (ch == '\'') { // Handle apostrophes
        else if (ch == '\'' || (i + 2 <= line.size() && line.substr(i, 3) == "’")) {
            if (!word.empty()) {
                result.push_back(word);
                serial = dictMapWord[word] + CODE_WORD_OFFSET;
                codeWords.clear();
                word.clear();
            }
            result.push_back("'");
            codeWords.clear();

            // Check for 's' after the apostrophe
            if (i + 1 < line.size() && line[i + 1] == 's') {
                result.push_back("s");
                codeWords.clear();
                ++i; // Skip the 's'
            }
        } else if (ispunct(ch)) { // Handle punctuation
            if (!word.empty()) {
                result.push_back(word);
                codeWords.clear();
                word.clear();
            }
            result.push_back(string(1, ch)); // Add punctuation as a separate string
        } else if (isspace(ch)) { // Handle spaces
            if (!word.empty()) {
                result.push_back(word);
                serial = dictMapWord[word] + CODE_WORD_OFFSET;
                codeRange = checkNumberOfCodeByte(serial);
                codeWords.clear();
                word.clear();
            }

            //result.push_back(string(1, 127)); // Add 127 as a separate string -- SPACE
        }

        startsWithUppercase = false;
    }

    // Add the last word if there is any
    if (!word.empty()) {
        result.push_back(word);
        codeWords.clear();
    }

    //return result;
    return codeWords;
}

uint8_t checkNumberOfCodeByte(int serial){
    uint8_t codeRange=0;

    if(serial >= ONE_BYTE_LOWER_BOUND && serial < ONE_BYTE_BOUND){ // ONE BYTE encoding 
        codeRange = 1;
    }
    else if(serial >= TWO_BYTE_OFFSET && serial < TWO_BYTE_BOUND){ // TWO BYTE encoding
        codeRange = 2;
    }
    else if(serial >= THREE_BYTE_OFFSET && serial < THREE_BYTE_BOUND){ // THREE BYTE encoding
        codeRange = 3;
    }

    return codeRange;
}

void convertStringToCodeWord(vector<string> word) {

    uint8_t byteCode;
    uint8_t byteCode1, byteCode2, byteCode3;
    int serial;

    //serial += CODE_WORD_OFFSET + dictMapWord[word];
    /* 
    *** Open the output file in appen mode **
    WARNING: 
    Since the output file is in an append mode,
    you need to delete the output file after each run.
    */
    //ofstream file(outputFilePath, ios::binary | ios::app); // open the output file

    
    /*
    *** Generate T0 ***
    Have reserved values:
    1) Space                => 0x0
    2) New line             => 0x1
    3) Next Capital letter  => 0x2
    */

    //serial = dictMapWord[word];
    if(serial >= ONE_BYTE_LOWER_BOUND && serial < ONE_BYTE_BOUND){ // ONE BYTE encoding 
        
        
    }
    else if(serial >= TWO_BYTE_OFFSET && serial < TWO_BYTE_BOUND){ // TWO BYTE encoding
        //input = serial - TWO_BYTE_OFFSET;

    }
    else if(serial >= THREE_BYTE_OFFSET && serial < THREE_BYTE_BOUND){
        //input = serial - THREE_BYTE_OFFSET;
    }
    //else{
        // Add word to the map with the current serial number
        //dictMapWord[word] = serial;
    //}

    
}

/*
'OBE_BYTE_CODE_GENERATOR' function:
Generate a 1-byte code of EPIC algorithm
*/
vector<uint8_t> ONE_BYTE_CODE_GENERATOR(uint32_t input)
{
    vector<uint8_t> codeWord;

    uint8_t byte1 = Mask_Single_Byte(input); // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte1 = Shift_Left_with_Zero_Inserted(byte1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte1);
    
    return codeWord;
}


/*
'TWO_BYTE_CODE_GENERATOR' function:
Generate a 2-byte code of EPIC algorithm
*/
vector<uint8_t> TWO_BYTE_CODE_GENERATOR(uint32_t input)
{
    vector<uint8_t> codeWord;

    uint8_t byte1 = Mask_Single_Byte(input); // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte1 = Shift_Left_with_One_Inserted(byte1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte1);

    uint8_t byte2 = Shift_Right_Seven_Positions(input); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    byte2 = Shift_Left_with_Zero_Inserted(byte2); // shift 'DICT_ORDER_NUM_shift' to the left by 1 position
    codeWord.push_back(byte2);

    return codeWord;
}


/*
'THREE_BYTE_CODE_GENERATOR' function:
Generate a 3-byte code of EPIC algorithm
*/
vector<uint8_t> THREE_BYTE_CODE_GENERATOR(uint32_t input)
{
    vector<uint8_t> codeWord;

    uint16_t byte1 = Mask_Single_Byte(input); // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte1 = Shift_Left_with_One_Inserted(byte1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte1);

    uint32_t input_shitf1 = Shift_Right_Seven_Positions(input); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    uint8_t byte2 = Mask_Single_Byte(input_shitf1); // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte2 = Shift_Left_with_One_Inserted(byte2); // shift 'byte2' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte2);

    uint8_t byte3 = Shift_Right_Seven_Positions(input_shitf1); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    byte3 = byte3 << 1; // shift 'DICT_ORDER_NUM_shift' to the left by 1 position
    codeWord.push_back(byte3);
}

// To mask the least significant byte
uint8_t Mask_Single_Byte(uint32_t number){
    return MASK_BYTE & number;
}

// Shift a number to the left by one position,
// and insert '1' as the LSbit.
uint32_t Shift_Left_with_One_Inserted(uint32_t number){
    return number << 1 | (0x1);
}

// Shift a number to the left by one position,
// and insert '0' as the LSbit.
uint32_t Shift_Left_with_Zero_Inserted(uint32_t number){
    return number << 1;
}

uint32_t Shift_Right_Seven_Positions(uint32_t number){
    return number >> 7;
}


// Check if the least significant bit (LSb) is one.
// If LSb is '1', then there is another byte code in the sequence.
// This function is used in the decompression process.
uint8_t Next_Byte_Available(uint8_t number){
    //return number % 2; // return one or zero.
    return number & (0x1); // return one or zero: mask it with the LSb
}


/*
A function to check ending of strings with Punctuation characters
'\0' --> represenets a null character
*/
char checkStringEndsWithPunctuation(const string &str) {
    // Check if the string is empty
    if (str.empty()) {
        return '\0'; // Null character for empty string
    }

    // Get the last character of the string
    char lastChar = str.back();

    // Check if the last character is a punctuation character
    if (ispunct(static_cast<unsigned char>(lastChar))) {
        return lastChar;
    }

    // Return '\0' if not a punctuation character
    return '\0';
}

/*
A funxtion that checks a newline character in a string
*/
bool endsWithNewline(const string &str) {
    // Check if the string is empty
    if (str.empty()) {
        return false;
    }

    // Check if the last character is a newline
    return str.back() == '\n';
}

/*
Reads lines from a file.
Use "endsWithNewline" function to check if lines 
end with a newline character.
*/
void checkLinesInFile(const string &filePath) {
    ifstream file(filePath); // Open the file
    if (!file) {
        cerr << "Error opening file: " << filePath << endl;
        return;
    }

    string line;
    int lineNumber = 1;

    // Read the file line by line
    while (getline(file, line)) {
        cout << "Line " << lineNumber << ": " 
             << (endsWithNewline(line) ? "Ends with newline" : "Does not end with newline") 
             << endl;
        lineNumber++;
    }

    file.close(); // Close the file
}

/*
"Probably will not use it".
A function to write a single string to a text file.
Then append the string with a newline character 
at the end of the string in the text file.
*/
void writeStringToFile(const string &filePath, const string &line) {
    ofstream file(filePath, ios::app); // Open the file in append mode
    if (!file) {
        cerr << "Error opening file: " << filePath << endl;
        return;
    }

    // Write the string to the file and append a newline
    file << line << endl;

    file.close(); // Close the file after writing
}



void writeBinaryFile(ofstream *file, const vector<uint8_t> &data) {
    if (!file || !file->is_open()) {
        cerr << "Error: File pointer is null or file is not open." << endl;
        return;
    }

    // Write bytes to the binary file
    file->write(reinterpret_cast<const char *>(data.data()), data.size());
    cout << "Bytes written successfully." << endl;
}

void writeBinaryFileOLD(const string &filePath, const vector<uint8_t> &data) {
    ofstream file(filePath, ios::binary | ios::app);
    if (!file) {
        cerr << "Error opening file for writing: " << filePath << endl;
        return;
    }

    // Write the data to the binary file
    file.write(reinterpret_cast<const char*>(data.data()), data.size());
    file.close();

    cout << "Data written to " << filePath << " successfully." << endl;
}

