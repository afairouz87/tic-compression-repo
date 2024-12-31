/*

Title: Enhanced PIC (EPIC) compression
Author: Abbas A. Fairouz
Version: 1.0
Created: Sep. 17, 2024
Updated: Nov. 25, 2024

Word frequency reference:
https://www.kaggle.com/datasets/rtatman/english-word-frequency?resource=download

*/


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

#include <chrono> // for sleep
#include <thread>

using namespace std;

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

*** Generate T0 ***
    Have reserved values:
    1) Space                => 0x0
    2) New line             => 0x1 --> in EPIC format, shift left by 1 => 0x2
    3) Next Capital letter  => 0x2 --> in EPIC format, shift left by 1 => 0x4
    4) Special codeWord     => 0x3 --> in EPIC format, shift left by 1 => 0x6


*** Comments ***
To-Do:
1. Implement the special codeWord encoding scheme.
** For the special code word, if a word is not found in the dictionary hash table,
then it will be considerd as a special codeWord.
The encoding of the special codeWord will be as follows:
Byte-1: represents the number of characters to hold the ASCII encodeing of the special codeWord
Byte-2:
...
Byte-n: last ASCII byte code

** We can add a reserved codeWord for indicating that the next word is a special codeWord.


Test Mac Pro

*/

/*
This is used to shift the codeWord by 
the reserved codeWords (space, newline, nextCapital).
*/ 
#define CODE_WORD_OFFSET 4

// Reserved codeWords: space, new line, next capital
#define SPACE_CODE 0x0
#define NEW_LINE_CODE 0x1
#define NEXT_CAPITAL_CODE 0x2
#define NEXT_SPECIAL_CODE 0x3

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

uint8_t Mask_Single_Byte(uint32_t number);
uint32_t Shift_Left_with_One_Inserted(uint32_t number);
uint32_t Shift_Left_with_Zero_Inserted(uint32_t number);
uint32_t Shift_Right_Seven_Positions(uint32_t number);

uint8_t Compression_Function();
uint8_t Decompression_Function();

// Reading a plain text file functions
uint8_t processFile(const string &filePath);
vector<string> processLineChar(const string &line); // return a vector of strings
//vector<string> processLineChar(const string &line, ofstream *file); // return a vector of strings
//vector<uint8_t> processLineChar(const string &line, ofstream *file); // return a vector of strings
vector<uint8_t> convertStringToCodeWord(vector<string> word);

char checkStringEndsWithPunctuation(const string &str);
void checkLinesInFile(const string &filePath);
bool endsWithNewline(const string &str);

void printBinaryFile(const string &filePath);

uint32_t readCodeWords(vector<uint8_t> bytes);
uint32_t concatenateBytes(uint32_t final, uint32_t tmp, uint8_t count);

uint32_t countLinesInFile(const string &filePath); // read the number of words in the dictionary 

// Declare the unordered_map to store the word and serialized integer
unordered_map<string, uint32_t> dictMapWord; // Compression Hash Table
unordered_map<uint32_t, string> dictMapCode; // Decompression Hash Table
string *dictMapCodeArray = nullptr; // Decompression Consecutive Array of rank of codeWords

// File path of the CSV file
//string dictFilename = "unigram_freq.csv"; 
string dictFilename = "dict.txt"; 

// input plaint text file
//string inputFileNameText = "input_file.txt"; 
// Compression
string inputFileNameText = "test1.txt"; 
string outputFileNameBin = "output.bin";

// Decompression
string inputFileNameBin = "output.bin"; 
string outputFileNameText = "output.txt";

// *********************************************
//            Main Function
// *********************************************
//int main(int argc, char * argv[]) {
int main() {

    uint32_t numberOfWords = countLinesInFile(dictFilename);
    cout << "Number of lines in the dictionary file: " << numberOfWords << endl;

    dictMapCodeArray = new string[numberOfWords+10]; // add an extra spaces

    // **** TESTs ****
    // int TMP_NUM = ONE_BYTE_BOUND-1;
    // const int TWO_BYTE_MID = TMP_NUM << 7;
    // cout << "Two byte mid = " << TWO_BYTE_MID << "bits = " << bitset<14> (TWO_BYTE_MID) << endl;
    // ****************

    // Compression
    // Building the dictionary hash table for compression
    cout << "Building the dictionary hash table for compression.." << endl;
    if(Build_Dictionary_Table_Compression()==0)
        cout << "The dictionary hash table for compression has been built successfully." << endl;
    else
        cout << "Error in building the dictionary hash table!" << endl;

    if(Compression_Function()==0)
        cout << "The compression function is successful." << endl;
    else
        cout << "Error in running the compression function!" << endl;

    // For testing ...
    //printBinaryFile(outputFileNameBin);

    cout << "Sleep for one second..\n";




    this_thread::sleep_for(chrono::seconds(1));



    // Decompression
    // Building the dictionary hash table for decompression
    cout << "Building the dictionary hash table for decompression.." << endl;
    if(Build_Dictionary_Table_Decompression()==0)
        cout << "The dictionary hash table for decompression has been built successfully." << endl;
    else
        cout << "Error in building the dictionary hash table!" << endl;

    if(Decompression_Function()==0)
        cout << "The decompression function is successful." << endl;
    else
        cout << "Error in running the decompression function!" << endl;


    delete[] dictMapCodeArray;
    dictMapCodeArray = nullptr;

    return 0;
} // main function



/* 
--------------------------
    OTHER FUNCTIONS 
--------------------------
*/

// *** Consecutive Array for Decompression ***
uint8_t Build_Dictionary_Table_Decompression(){
    // Variables to store each line and word
    string line, word;
    uint32_t serial = CODE_WORD_OFFSET; // Start serializing after the the serialized number of all reserved codeWords

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
        
        dictMapCodeArray[serial] = word;
        serial++;
    }

    // Close the file after reading
    file.close();

    // ** for testing ... **
    cout << "\nTotal words = " << serial-1 << "\n";
    cout << "The hash map for decompresssion has been generated successfully!\n\n";

    // // Test the hash map
    // cout << "Test the hash map:\n";
    // uint32_t tmpSerial = 127;
    // cout << "Serial (" << tmpSerial << ") has a word of: " << dictMapCode[tmpSerial] << "\n";
    // cout << "\n\n";

    return 0;
}

// *** Hash Table for Decompression ***
// uint8_t Build_Dictionary_Table_Decompression(){
//     // Variables to store each line and word
//     string line, word;
//     uint32_t serial = CODE_WORD_OFFSET; // Start serializing from 0

//     // Open the Text file
//     ifstream file(dictFilename);

//     // Check if the file is open
//     if (!file.is_open()) {
//         cerr << "Error opening file: " << dictFilename << endl;
//         return 1;
//     }

//     // Read the file line by line
//     while (getline(file, line)) {
//         stringstream ss(line); // Use a stringstream to parse the line
//         string temp; // To hold the "count" column which we will ignore
        
//         // Get the word from the line
//         // getline(ss, word, ','); 
//         // getline(ss, temp, ','); // Ignore the second column (count)
//         getline(ss, word, '\n'); 
        
//         dictMapCode[serial] = word;
//         serial++;
//     }

//     // Close the file after reading
//     file.close();

//     // ** for testing ... **
//     cout << "\nTotal words = " << serial-1 << "\n";
//     cout << "The hash map for decompresssion has been generated successfully!\n\n";

//     // // Test the hash map
//     // cout << "Test the hash map:\n";
//     // uint32_t tmpSerial = 127;
//     // cout << "Serial (" << tmpSerial << ") has a word of: " << dictMapCode[tmpSerial] << "\n";
//     // cout << "\n\n";

//     return 0;
// }


uint8_t Build_Dictionary_Table_Compression(){
    // Variables to store each line and word
    string line, word;
    uint32_t serial = CODE_WORD_OFFSET; // Start serializing from 3

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

    //** for testing ... **
    cout << "\nTotal words = " << serial-1 << "\n";
    cout << "The hash map for compression has been generated successfully!\n\n";

    // // Test the hash map
    // cout << "Test the hash map:\n";
    // string tmp_word = "wild";
    // cout << "Word (" << tmp_word << ") has an order of: " << dictMapWord[tmp_word] << "\n";
    // cout << "\n\n";

    return 0;
}


// Function to read a file line by line and process each line
uint8_t Compression_Function() {
    ifstream inFile(inputFileNameText); // Open the file
    if (!inFile) {
        cerr << "Error opening file: " << inputFileNameText << endl;
        return -1;
    }

    // Open the output file in binary mode and in append mode
    ofstream outFile(outputFileNameBin, ios::binary | ios::app); 
    if (!outFile) {
        cerr << "Error: Could not open the file." << endl;
        return 1;
    }

    vector<string> tokens;
    vector<uint8_t> lineCodeWords;
    const char* buffer;
    size_t bufferSize;
    string line;


    //*** Method 1 ***
    string currentLine, nextLine;

    // Read the first line before entering the loop
    if (getline(inFile, currentLine)) {
        while (true) {
            // Peek ahead to check for the next line
            if (getline(inFile, nextLine)) {
                // Process the current line
                tokens = processLineChar(currentLine); // Process the line
                lineCodeWords = convertStringToCodeWord(tokens); // Generate the code words

                buffer = reinterpret_cast<const char*>(lineCodeWords.data());
                bufferSize = lineCodeWords.size();
                outFile.write(buffer, bufferSize);

                // Move to the next line
                currentLine = nextLine;
            } else {
                // Handle the last line (no next line available)
                tokens = processLineChar(currentLine); // Process the line
                lineCodeWords = convertStringToCodeWord(tokens); // Generate the code words

                lineCodeWords.pop_back(); // remove the last new line at the end of file
                buffer = reinterpret_cast<const char*>(lineCodeWords.data());
                bufferSize = lineCodeWords.size();
                outFile.write(buffer, bufferSize);

                // Break out of the loop after processing the last line
                break;
            }
        }
    }

    inFile.close(); // Close the input file
    outFile.close(); // Close the output file

    return 0;
}

/*
-- Compression Function --
A function used to process each line read from a plain text file separately.
It will recognize between words, characters, uppercase, and puctuation characters.
*/
vector<string> processLineChar(const string &line) {
    vector<string> result;
    vector<uint8_t> lineCodeWords;
    string word;
    bool startsWithUppercase = false; // Flag to indicate if the word starts with an uppercase letter

    for (size_t i = 0; i < line.size(); ++i) {
        char ch = line[i];

        if (isalnum(ch)) { // If the character is alphanumeric, build the word
            if (word.empty() && isupper(ch)) {
                result.push_back(string(1, 0xff)); // '0xff' represents that the next word starts with an uppercase character. 
                startsWithUppercase = true; // Set the flag if the first character is uppercase
                //cout << "Uppercase character..\n"; // for testing... 
            }
            ch = tolower(ch); // set the uppercase character to lowercase character.
            word += ch;
        } 
        else if (ch == '\'' || (i + 2 <= line.size() && line.substr(i, 3) == "’")) {
            if (!word.empty()) {
                result.push_back(word);
                word.clear();
            }
            result.push_back("'");

            // Check for 's' after the apostrophe
            if (i + 1 < line.size() && line[i + 1] == 's') {
                result.push_back("s");
                ++i; // Skip the 's'
            }
        } else if (ispunct(ch)) { // Handle punctuation
            if (!word.empty()) {
                result.push_back(word);
                word.clear();
            }
            result.push_back(string(1, ch)); // Add punctuation as a separate string
        } else if (isspace(ch)) { // Handle spaces
            if (!word.empty()) {
                result.push_back(word);
                word.clear();
            }
            result.push_back(string(1, ' ')); // Add space as a separate string -- SPACE
        }

        startsWithUppercase = false;
    }

    // Add the last word if there is any
    if (!word.empty()) {
        result.push_back(word);
    }

    return result; // return a vector of separate strings
}

vector<uint8_t> convertStringToCodeWord(vector<string> wordsSet) {

    vector<uint8_t> lineCodeWords;
    vector<uint8_t> byteCodes;
    // uint8_t byteCode;
    // uint8_t byteCode1, byteCode2, byteCode3;
    uint32_t serial = 0, inputNumber = 0;
    string word;

    /* 
    *** Open the output file in appen mode **
    WARNING: 
    Since the output file is in an append mode,
    you need to delete the output file after each run.
    
    *** Generate T0 ***
    Have reserved values:
    1) Space                => 0x0
    2) New line             => 0x1 --> in EPIC format, shift left by 1 => 0x2
    3) Next Capital letter  => 0x2 --> in EPIC format, shift left by 1 => 0x4
    */


    for (size_t i = 0; i < wordsSet.size(); ++i) {
        word = wordsSet[i];

        //serial = dictMapWord[word];
        if(!word.empty() && static_cast<uint8_t>(word[0]) == 0x20){ // compare with SPACE in ASCII
            lineCodeWords.push_back(SPACE_CODE); // SPACE codeWord
        }
        else if(!word.empty() && static_cast<uint8_t>(word[0]) == 0xFF){ // compare with Next Uppercase character code (0xFF)
            lineCodeWords.push_back(Shift_Left_with_Zero_Inserted(NEXT_CAPITAL_CODE)); // next uppercase letter codeWord
        }
        else{
            
            /*
            NOTE:
            - In the 'unordered_map', the returned value of 'not found' hash key is zero '0'.
            */
            serial = dictMapWord[word]; // read th evalue of the word in the dictionary hash table
            

            if(serial >= ONE_BYTE_LOWER_BOUND && serial < ONE_BYTE_BOUND){ // ONE BYTE encoding
                inputNumber = serial; // add the offset if the reserved codeWords (i.e. space, newline, ..)
                byteCodes = ONE_BYTE_CODE_GENERATOR(inputNumber); // generate a single byte codeWord
            }
            else if(serial >= TWO_BYTE_OFFSET && serial < TWO_BYTE_BOUND){ // TWO BYTE encoding
                inputNumber = serial - TWO_BYTE_OFFSET;
                byteCodes = TWO_BYTE_CODE_GENERATOR(inputNumber); // generate a two bytes codeWord
            }
            else if(serial >= THREE_BYTE_OFFSET && serial < THREE_BYTE_BOUND){
                inputNumber = serial - (THREE_BYTE_OFFSET);
                byteCodes = THREE_BYTE_CODE_GENERATOR(inputNumber); // generate a three bytes codeWord
            }
            else{
                // Add word to the map with the current serial number
                //dictMapWord[word] = serial;
            }

            // Push the byteCodes to the lineCodeWords vector
            lineCodeWords.insert(lineCodeWords.end(), byteCodes.begin(), byteCodes.end());
            byteCodes.clear();

        } // end of else for special codeWords
        
    } // end of the for loop    
    
    lineCodeWords.push_back(Shift_Left_with_Zero_Inserted(NEW_LINE_CODE)); // new line codeWord

    return lineCodeWords;
}

uint8_t Decompression_Function(){
    vector<uint8_t> byteCodes;
    uint32_t tmpSerial = 0, finalSerial = 0;
    string word;

    // Open the file in binary mode
    ifstream inFile(inputFileNameBin, ios::binary);
    if (!inFile) {
        cerr << "Error: Could not open file " << outputFileNameBin << " for reading." << endl;
        return -1;
    }
    
    ofstream outFile(outputFileNameText, ios::app); // Open in append mode
    if (!outFile) {
        cerr << "Error: Could not open file " << outputFileNameText << " for appending." << endl;
        return -1;
    }

    uint8_t nextByte; // Variable to store each byte
    size_t byteIndex = 0; // Optional: Index of the byte being read
    bool NEXT_CAP = false;
    int serial = 0;
    uint32_t count = 0;

    char byte;
    cout << "Reading file byte by byte:" << endl;

    // Read the file byte by byte
    //while (inFile.read(reinterpret_cast<char*>(&byte), sizeof(byte))) {
    while (inFile.read(&byte, 1)) {
        tmpSerial = static_cast<uint8_t>(byte);
        
        /* 
        ----------
        To check the LSb of the byte: 
        '1' --> there is a next byte. 
        '0' --> last byte in the codeWord sequence
        ----------
        */
        nextByte = tmpSerial % 2; 
        
        tmpSerial = tmpSerial >> 1; // ignore the LSb after reading it
        
        if(nextByte==0){
            // Finalize the concatenated serial number
            finalSerial = static_cast<uint32_t>(concatenateBytes(finalSerial, tmpSerial, count));
            
            /*
            ----------
            Note:
            The variable "count" is used to count the number of ones 
            realized in the codeWord while reading each byte separately.
            ----------
            */
            if(count == 1) // TWO CODE
                finalSerial += TWO_BYTE_OFFSET;
            else if(count == 2) // THREE CODE
                finalSerial += THREE_BYTE_OFFSET;
            
            if(finalSerial == 0){ // space
                outFile << " ";
            }
            else if (finalSerial == 1){ // newline
                //cout << "NEW LINE\n";
                outFile << "\n";
            }
            else if (finalSerial == 2){ // next uppercase character
                //cout << "NEXT CAP\n";
                NEXT_CAP = true;
            }
            else{ // check the dictionary hash table
                
                // Check the word in the dictionary hash table
                //word = dictMapCode[finalSerial];

                // Check the word in the dictionary array of words
                word = dictMapCodeArray[finalSerial];
                
                if(NEXT_CAP){
                    // Change the first letter of the word to uppercase character
                    word[0] = toupper(word[0]);

                    // reset the NEXT_CAP to false
                    NEXT_CAP = false;
                }

                outFile << word;
            } // end of else 'check the dictionary hash table'

            // reset both finalSerial and tmpSerial
            tmpSerial = 0;
            finalSerial = 0;
            count = 0;

        } // if (nextByte==0)
        else{ // if (nextByte==1)
            //finalSerial = (finalSerial << 7) | tmpSerial;
            finalSerial = concatenateBytes(finalSerial, tmpSerial, count);
            count++;
        }
        
        byteIndex++;
    }

    if (inFile.eof()) {
        cout << "End of file reached." << endl;
    } else if (inFile.fail()) {
        cerr << "Error: Failed to read the file." << endl;
    }

    inFile.close();
    outFile.close();

    return 0;
}

uint32_t concatenateBytes(uint32_t final, uint32_t tmp, uint8_t count){
    // if (count == 0)
    //     return tmp;
    // else
    return final | (tmp << (7*count));
}

/*
'ONE_BYTE_CODE_GENERATOR' function:
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
vector<uint8_t> SPECIAL_CODE_WORD_GENERATOR(string input)
{
    vector<uint8_t> codeWord;
    uint8_t byte1, byte2, byte3;


    return codeWord;
}

/*
'THREE_BYTE_CODE_GENERATOR' function:
Generate a 3-byte code of EPIC algorithm
*/
vector<uint8_t> THREE_BYTE_CODE_GENERATOR(uint32_t input)
{
    vector<uint8_t> codeWord;
    uint8_t byte1, byte2, byte3;
    uint32_t input_shitf1;

    byte1 = Mask_Single_Byte(input); // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte1 = Shift_Left_with_One_Inserted(byte1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte1);

    input_shitf1 = Shift_Right_Seven_Positions(input); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    byte2 = Mask_Single_Byte(input_shitf1); // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte2 = Shift_Left_with_One_Inserted(byte2); // shift 'byte2' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte2);

    byte3 = Shift_Right_Seven_Positions(input_shitf1); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    byte3 = Shift_Left_with_Zero_Inserted(byte3); // shift 'DICT_ORDER_NUM_shift' to the left by 1 position
    codeWord.push_back(byte3);

    return codeWord;
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

// Print the hex code of the binary file for testing.
void printBinaryFile(const string &filePath) {
    ifstream file(filePath, ios::binary);  // Open the file in binary mode
    if (!file) {
        cerr << "Error opening file: " << filePath << endl;
        return;
    }

    // Read the file contents into a vector of uint8_t
    vector<uint8_t> buffer((istreambuf_iterator<char>(file)), istreambuf_iterator<char>());
    file.close();  // Close the file after reading

    cout << "Binary contents of " << filePath << ":" << endl;
    for (size_t i = 0; i < buffer.size(); ++i) {
        //cout << bitset<8>(buffer[i]) << " ";  // Print each byte as an 8-bit binary number
        cout << hex << static_cast<int>(buffer[i]) << " ";  // Print each byte as HEX number
    }
    cout << endl;
}

/*
NOTE:
It returns the number of lines-1.
Because there is no newline character '\n' at the ennd of file.
*/ 
uint32_t countLinesInFile(const string &filePath) {
    ifstream file(filePath);
    if (!file) {
        cerr << "Error: Could not open file " << filePath << endl;
        return 0;
    }

    // Count newline characters using std::count and istreambuf_iterator
    size_t lineCount = count(istreambuf_iterator<char>(file),
                             istreambuf_iterator<char>(), '\n');

    file.close();
    return lineCount;
}