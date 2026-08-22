/*

Title: Enhanced PIC (PIC) compression
Author: Abbas A. Fairouz
Version: 3.1
Note: multi-threaded version
Created: Apr. 8, 2025
Updated: Aug. 8, 2025

Description:
* In this version:
1) we will modify the special codeWord (T_s) to include 8-bit for each ASCII character.
The T_s special codeWord starts by an extra two bytes:
    a. Byte1: reserved code which indicates that the next word in a special codeWord.alignas
    b. Byte2: represent the number of ASCII characters in the special codeWord.

2) we will add passing arguments to choose one of the operations:
    a. Compression
    b. Decompression
    c. Lookup
    d. Lookup and Replace

Word frequency reference:
https://www.kaggle.com/datasets/rtatman/english-word-frequency?resource=download

*/



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
    2) New line             => 0x1 --> in PIC format, shift left by 1 => 0x2
    3) Next Capital letter  => 0x2 --> in PIC format, shift left by 1 => 0x4
    4) Special codeWord     => 0x3 --> in PIC format, shift left by 1 => 0x6


*** Comments ***

** For the special code word, if a word is not found in the dictionary hash table,
then it will be considerd as a special codeWord.
The encoding of the special codeWord will be as follows:
Byte-1: represents the number of characters to hold the ASCII encodeing of the special codeWord
Byte-2: first ASCII byte code
...
Byte-n: last ASCII byte code

** We can add a reserved codeWord for indicating that the next word is a special codeWord.

*/


#include "pic-v3.1.h"

// Declare the unordered_map to store the word and serialized integer
unordered_map<string, uint32_t> dictMapWord; // Compression Hash Table
// unordered_map<uint32_t, string> dictMapCode; // Decompression Hash Table (UNUSED)
string *dictMapCodeArray = nullptr; // Decompression Consecutive Array of rank of codeWords

// File path of the CSV file
// string dictFilename = "unigram_freq.csv";
string dictFilename = "dict.txt";

// input plaint text file
// string inputFileNameText = "input_file.txt";
// Compression
string inputFileNameText = "test1.txt";
string outputFileNameBin = "output.bin";

// Decompression
string inputFileNameBin = "output.bin";
string outputFileNameText = "output.txt";

// Counters for debugging
int specialCodeWordCounter = 0;
int lineNumber = 1;

//
mutex fileMutex;

// For debug
int decodedLineCounter = 0;

// *** For debug and histograms
uint32_t T1_FREQ = 0, T2_FREQ = 0, T3_FREQ = 0, T4_FREQ = 0, T5_FREQ = 0;

const uint8_t SPACE_BYTE       = Shift_Left_with_Zero_Inserted(SPACE_CODE);
const uint8_t NEWLINE_BYTE     = Shift_Left_with_Zero_Inserted(NEW_LINE_CODE);
const uint8_t END_SPECIAL_BYTE = Shift_Left_with_Zero_Inserted(END_SPECIAL_CODE);
const uint8_t NEXT_SPECIAL_BYTE = Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE);

uint32_t NUMBER_OF_WORDS_DICT = 0;

// *********************************************
//            Main Function
// *********************************************
int main(int argc, char *argv[])
{
    // int main() {

    /*
    argv[0]: binary file
    argv[1]: mode flag (-c, -d, -l, -r)
    argv[2]: thread flag (-t)
    argv[3]: number of thread 
    argv[4]: input file
    argv[5]: output file (dummy for -l)
    argv[6]: search string (for -l and -r)
    argv[7]: replace string (for -r)
    */

    if (!(argc == 6 || argc == 7 || argc == 8) ||
        !(string(argv[1]) == "-c" || string(argv[1]) == "-d" || string(argv[1]) == "-l" || string(argv[1]) == "-r") ||
        string(argv[2]) != "-t")
    {
        cerr << "Main Error:\nFlags:\n-c: compression\n-d: decompression\n-l: Lookup (Search)\n-r: Lookup-and-Replace (Search and Replace)\n"
             << "Usage: " << argv[0] << " -[c,d,l,r] -t <num_threads> <input_file> <output_file> [\"<search_string>\"] [\"<replace_string>\"]\n"
             << "Notes:\n"
             << "** For -l and -r flags: <search_string> is used.\n"
             << "** For -l flag: <output_file> is ignored\n"
             << "** For -r flag: <replace_string> is used\n"
             << "** For <search_string> and <replace_string>: You need to allocate them between double quotes \"\" \n"
             << endl;

        return 1;
    }

    if(string(argv[1]) == "-l" && argc != 7)
    {
        cerr << "Main Error: For -l flag, you need to add the search string.\n";

        return 1;
    }
    if(string(argv[1]) == "-r" && argc != 8)
    {
        cerr << "Main Error: For -r flag, you need to add the search string and the replace string.\n";

        return 1;
    }

    string operationMode = argv[1];
    string inputFileName = argv[4];
    string outputFileName = argv[5];
    string searchString = "", replaceString = "";

    if (argc == 7 || argc == 8)
        searchString = argv[6];

    if (argc == 8)
        replaceString = argv[7];

    int numThreads = 0;

    try
    {
        numThreads = stoi(argv[3]);
        if (numThreads <= 0)
            throw invalid_argument("Main Error: Number of threads must be positive");
    }
    catch (const invalid_argument &e)
    {
        cerr << "Main Error: Invalid thread count in " << argv[3] << endl;
        return 1;
    }

    // Record the start time
    auto start = high_resolution_clock::now();

    NUMBER_OF_WORDS_DICT = countLinesInFile(dictFilename);
    cout << "Number of lines in the dictionary file: " << NUMBER_OF_WORDS_DICT << endl;

    dictMapCodeArray = new string[NUMBER_OF_WORDS_DICT + 10]; // add an extra spaces

    // **** TESTs ****
    // int TMP_NUM = ONE_BYTE_BOUND-1;
    // const int TWO_BYTE_MID = TMP_NUM << 7;
    // cout << "Two byte mid = " << TWO_BYTE_MID << "bits = " << bitset<14> (TWO_BYTE_MID) << endl;
    // ****************

    if (operationMode == "-c") // compression operation flag
    { 
        // *** Compression ***
        // Building the dictionary hash table for compression
        cout << "Building the dictionary hash table for compression.." << endl;
        if (Build_Dictionary_Table_Compression() == 0)
            cout << "The dictionary hash table for compression has been built successfully." << endl;
        else
            cout << "Error in building the dictionary hash table!" << endl;

        // Send the text file to multiple compression threads
        if (splitAndProcessTextFile(inputFileName, outputFileName, numThreads) == 0)
        {
            cout << "The compression function is successful." << endl;
            
            cout << "T1_FREQ = " << T1_FREQ << endl;
            cout << "T2_FREQ = " << T2_FREQ << endl;
            cout << "T3_FREQ = " << T3_FREQ << endl;
            cout << "T4_FREQ = " << T4_FREQ << endl;
            cout << "T5_FREQ = " << T5_FREQ << endl;
        }
        else
            cout << "Error in running the compression function!" << endl;
    } // compression operation flag
    else if (operationMode == "-d") // decompression operation flag
    { 
        // *** Decompression ***
        // Building the dictionary hash table for decompression
        cout << "Building the dictionary hash table for decompression.." << endl;
        if (Build_Dictionary_Table_Decompression() == 0)
            cout << "The dictionary hash table for decompression has been built successfully." << endl;
        else
            cout << "Error in building the dictionary hash table!" << endl;

        if (splitAndProcessBinaryFile(inputFileName, outputFileName, numThreads) == 0){
            cout << "The decompression function is successful." << endl;
            cout << "Decoded lines: " << decodedLineCounter << endl;
        }
        else
            cout << "Error in running the decompression function!" << endl;
    } // decompression operation flag
    else if (operationMode == "-l") // lookup operation flag
    { 
        // Building the dictionary hash table for compressing the search string
        cout << "Building the dictionary hash table for compression.." << endl;
        if (Build_Dictionary_Table_Compression() == 0)
            cout << "The dictionary hash table for compression has been built successfully." << endl;
        else
            cout << "Error in building the dictionary hash table!" << endl;

        if (splitAndProcessBinaryFileForSearch(inputFileName, outputFileName, numThreads, searchString) == 0)
            cout << "The lookup function is successful." << endl;
        else
            cout << "Error in running the lookup function!" << endl;
    } // lookup operation flag
    else if (operationMode == "-r") // lookup and replace operation flag
    { 
        // Building the dictionary hash table for compressing the search string
        cout << "Building the dictionary hash table for compression.." << endl;
        if (Build_Dictionary_Table_Compression() == 0)
            cout << "The dictionary hash table for compression has been built successfully." << endl;
        else
            cout << "Error in building the dictionary hash table!" << endl;

        if (splitAndProcessBinaryFileForSearchAndReplace(inputFileName, outputFileName, numThreads, searchString, replaceString) == 0)
        //if (splitAndProcessBinaryFileWithReplacement(inputFileName, outputFileName, numThreads, searchString, replaceString) == 0)
            cout << "The lookup function is successful." << endl;
        else
            cout << "Error in running the lookup function!" << endl;

    } // lookup and replace operation flag
    else
    { // error
        cerr << "Invalid operation: " << argv[2] << endl;
        return 1;
    }

    // For testing ...
    // printBinaryFile(outputFileNameBin);

    // cout << "Sleep for one second..\n";
    // this_thread::sleep_for(chrono::seconds(1));

    delete[] dictMapCodeArray;
    dictMapWord.clear();
    dictMapCodeArray = nullptr;

    // Record the end time
    auto end = high_resolution_clock::now();

    // Calculate the duration in microseconds (or other units)
    auto duration = duration_cast<milliseconds>(end - start);

    cout << "Total execution time: " << duration.count() << " milliseconds" << endl;
    // cout << "Number of special codeWords = " << specialCodeWordCounter << endl;

    return 0;
} // main function

/*
--------------------------
***  OTHER FUNCTIONS  ***
--------------------------
*/


// ------------------------------------------------------
// ***** Lookup_and_Replace_Function ***********

// Version 6
uint32_t Lookup_and_Replace_Function(
    const string &inputFileNameBin,
    streampos start,
    streampos end,
    const string &outputFileNameBin,
    string searchString,
    string replaceString,
    int threadIndex,
    vector<uint32_t> &results)
{
    ifstream inFile(inputFileNameBin, ios::binary);
    ofstream outFile(outputFileNameBin, ios::binary | ios::app);

    if (!inFile || !outFile)
    {
        cerr << "Error: Could not open file(s) in thread " << threadIndex << endl;
        return -1;
    }

    inFile.seekg(start);

    const size_t bufferSize = 4096;
    char buffer[bufferSize];

    streamoff currentPos = static_cast<streamoff>(start);

    vector<uint8_t> lineCodeWords = convertSearchStringToCodeWord(processLineChar(searchString));
    vector<uint8_t> replaceCodeWords = convertSearchStringToCodeWord(processLineChar(replaceString));

    uint16_t lineCodeWordsSize = static_cast<uint16_t>(lineCodeWords.size());
    uint32_t matchCount = 0;
    uint16_t byteIndex = 0;

    vector<uint8_t> tmpCodeWord;

    while (currentPos < end && inFile)
    {
        inFile.clear();
        inFile.seekg(currentPos);

        size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - currentPos));
        inFile.read(buffer, bytesToRead);
        size_t bytesRead = static_cast<size_t>(inFile.gcount());

        if (bytesRead == 0)
            break;

        size_t i = 0;
        size_t lastSafePosInBuffer = 0;

        tmpCodeWord.clear();

        while (i < bytesRead)
        {
            uint8_t byte = static_cast<uint8_t>(buffer[i]);
            uint16_t nextByteCode = byte & 1;

            if (byteIndex < lineCodeWordsSize && byte == lineCodeWords[byteIndex])
            {
                tmpCodeWord.push_back(byte);

                /*
                 * Matching path for a special token.
                 * If the first matched byte is NEXT_SPECIAL_CODE, verify the full
                 * special-token structure using SPECIAL_CODE_WORD_READER().
                 */
                if (byte == Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE))
                {
                    size_t specialPos = i;
                    string specialWord = SPECIAL_CODE_WORD_READER(buffer, specialPos, bytesRead);

                    if (specialWord.empty())
                    {
                        break; // incomplete special token in current buffer
                    }

                    ++byteIndex;
                    ++i;

                    while (i <= specialPos && byteIndex < lineCodeWordsSize)
                    {
                        uint8_t cur = static_cast<uint8_t>(buffer[i]);
                        tmpCodeWord.push_back(cur);

                        if (cur == lineCodeWords[byteIndex])
                        {
                            ++byteIndex;
                            ++i;
                        }
                        else
                        {
                            break;
                        }
                    }

                    if (byteIndex == lineCodeWordsSize)
                    {
                        outFile.write(
                            reinterpret_cast<const char *>(replaceCodeWords.data()),
                            static_cast<streamsize>(replaceCodeWords.size())
                        );
                        ++matchCount;
                    }
                    else
                    {
                        outFile.write(
                            reinterpret_cast<const char *>(tmpCodeWord.data()),
                            static_cast<streamsize>(tmpCodeWord.size())
                        );
                    }

                    tmpCodeWord.clear();
                    byteIndex = 0;
                    lastSafePosInBuffer = i;
                    continue;
                }

                ++byteIndex;
                ++i;

                if (byteIndex == lineCodeWordsSize)
                {
                    outFile.write(
                        reinterpret_cast<const char *>(replaceCodeWords.data()),
                        static_cast<streamsize>(replaceCodeWords.size())
                    );
                    ++matchCount;

                    tmpCodeWord.clear();
                    byteIndex = 0;
                }

                lastSafePosInBuffer = i;
            }
            else
            {
                /*
                 * Non-matching path.
                 * First flush any partial match accumulated so far.
                 */
                if (!tmpCodeWord.empty())
                {
                    outFile.write(
                        reinterpret_cast<const char *>(tmpCodeWord.data()),
                        static_cast<streamsize>(tmpCodeWord.size())
                    );
                    tmpCodeWord.clear();
                }

                /*
                 * If current byte starts a special token, copy the complete special
                 * token as-is. Do not manually compute the special-token length.
                 */
                if (byte == Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE))
                {
                    size_t specialPos = i;
                    string specialWord = SPECIAL_CODE_WORD_READER(buffer, specialPos, bytesRead);

                    if (specialWord.empty())
                    {
                        break; // incomplete special token
                    }

                    outFile.write(
                        &buffer[i],
                        static_cast<streamsize>(specialPos - i + 1)
                    );

                    i = specialPos + 1;
                    lastSafePosInBuffer = i;
                    byteIndex = 0;
                    continue;
                }

                /*
                 * Copy the remainder of the current normal codeword.
                 */
                size_t startPos = i;

                if (nextByteCode == 1)
                {
                    do
                    {
                        ++i;

                        if (i >= bytesRead)
                            break;

                        nextByteCode = static_cast<uint16_t>(
                            static_cast<uint8_t>(buffer[i]) & 1
                        );

                    } while (nextByteCode == 1);

                    if (i >= bytesRead)
                        break;

                    ++i; // consume final byte with LSB = 0
                }
                else
                {
                    ++i;
                }

                outFile.write(
                    &buffer[startPos],
                    static_cast<streamsize>(i - startPos)
                );

                lastSafePosInBuffer = i;
                byteIndex = 0;
            }
        }

        if (lastSafePosInBuffer == 0)
        {
            cerr << "Error[PIC]: No progress in Lookup_and_Replace_Function(). "
                 << "currentPos=" << currentPos
                 << ", bytesRead=" << bytesRead
                 << endl;
            return -1;
        }

        currentPos += static_cast<streamoff>(lastSafePosInBuffer);
    }

    inFile.close();
    outFile.close();

    results[threadIndex] = matchCount;
    return 0;
}


// Version 5
// uint32_t Lookup_and_Replace_Function(
//     const string &inputFileNameBin,
//     streampos start,
//     streampos end,
//     const string &outputFileNameBin,
//     string searchString,
//     string replaceString,
//     int threadIndex,
//     vector<uint32_t> &results)
// {
//     ifstream inFile(inputFileNameBin, ios::binary);
//     ofstream outFile(outputFileNameBin, ios::binary | ios::app);
//     if (!inFile || !outFile)
//     {
//         cerr << "Error: Could not open file(s) in thread " << threadIndex << endl;
//         return -1;
//     }

//     inFile.seekg(start);
//     const size_t bufferSize = 4096;
//     char buffer[bufferSize];
//     streamoff currentPos = static_cast<streamoff>(start);

//     vector<uint8_t> lineCodeWords = convertSearchStringToCodeWord(processLineChar(searchString));
//     vector<uint8_t> replaceCodeWords = convertSearchStringToCodeWord(processLineChar(replaceString));

//     uint16_t lineCodeWordsSize = static_cast<uint16_t>(lineCodeWords.size());
//     uint32_t matchCount = 0;
//     uint16_t byteIndex = 0;
//     vector<uint8_t> tmpCodeWord;

//     while (currentPos < end && inFile)
//     {
//         inFile.clear();
//         inFile.seekg(currentPos);

//         size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - currentPos));
//         inFile.read(buffer, bytesToRead);
//         size_t bytesRead = inFile.gcount();

//         if (bytesRead == 0)
//             break;

//         size_t i = 0;
//         size_t lastSafePosInBuffer = 0;
//         tmpCodeWord.clear();

//         while (i < bytesRead)
//         {
//             uint8_t byte = static_cast<uint8_t>(buffer[i]);
//             uint16_t nextByteCode = byte & 1;

//             if (byteIndex < lineCodeWordsSize && byte == lineCodeWords[byteIndex])
//             {
//                 tmpCodeWord.push_back(byte);

//                 // If matching a special-code search pattern, ensure the full special token is present
//                 if (byte == Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE))
//                 {
//                     size_t specialPos = i;
//                     string specialWord = SPECIAL_CODE_WORD_READER(buffer, specialPos, bytesRead);

//                     if (specialWord.empty()) {
//                         break;
//                     }

//                     ++byteIndex;
//                     ++i;

//                     while (i <= specialPos && byteIndex < lineCodeWordsSize)
//                     {
//                         uint8_t cur = static_cast<uint8_t>(buffer[i]);
//                         tmpCodeWord.push_back(cur);

//                         if (cur == lineCodeWords[byteIndex]) {
//                             ++byteIndex;
//                             ++i;
//                         } else {
//                             break;
//                         }
//                     }

//                     if (byteIndex == lineCodeWordsSize)
//                     {
//                         outFile.write(reinterpret_cast<const char *>(replaceCodeWords.data()), replaceCodeWords.size());
//                         matchCount++;
//                     }
//                     else
//                     {
//                         outFile.write(reinterpret_cast<const char *>(tmpCodeWord.data()), tmpCodeWord.size());
//                     }

//                     tmpCodeWord.clear();
//                     byteIndex = 0;
//                     lastSafePosInBuffer = i;
//                     continue;
//                 }

//                 ++byteIndex;
//                 ++i;

//                 if (byteIndex == lineCodeWordsSize)
//                 {
//                     outFile.write(reinterpret_cast<const char *>(replaceCodeWords.data()), replaceCodeWords.size());
//                     matchCount++;
//                     tmpCodeWord.clear();
//                     byteIndex = 0;
//                 }

//                 lastSafePosInBuffer = i;
//             }
//             else
//             {
//                 // If current byte begins a special token and we are not matching it,
//                 // copy the whole special token safely.
//                 if (byte == Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE))
//                 {
//                     size_t specialPos = i;
//                     string specialWord = SPECIAL_CODE_WORD_READER(buffer, specialPos, bytesRead);

//                     if (specialWord.empty()) {
//                         break;
//                     }

//                     outFile.write(&buffer[i], static_cast<streamsize>(specialPos - i + 1));
//                     i = specialPos + 1;
//                     lastSafePosInBuffer = i;

//                     tmpCodeWord.clear();
//                     byteIndex = 0;
//                     continue;
//                 }

//                 // Flush partial match first
//                 if (!tmpCodeWord.empty()) {
//                     outFile.write(reinterpret_cast<const char *>(tmpCodeWord.data()), tmpCodeWord.size());
//                     tmpCodeWord.clear();
//                 }

//                 // Copy the remainder of the current normal codeword
//                 size_t startPos = i;

//                 if (nextByteCode == 1)
//                 {
//                     do {
//                         ++i;
//                         if (i >= bytesRead)
//                             break;
//                         nextByteCode = static_cast<uint16_t>(static_cast<uint8_t>(buffer[i])) & 1;
//                     } while (nextByteCode == 1);

//                     if (i >= bytesRead)
//                         break;

//                     ++i; // consume final byte with LSB = 0
//                 }
//                 else
//                 {
//                     ++i;
//                 }

//                 outFile.write(&buffer[startPos], static_cast<streamsize>(i - startPos));
//                 lastSafePosInBuffer = i;
//                 byteIndex = 0;
//             }
//         }

//         currentPos += static_cast<streamoff>(lastSafePosInBuffer);

//         if (lastSafePosInBuffer == 0) {
//             cerr << "Error[PIC]: No progress in Lookup_and_Replace_Function()." << endl;
//             return -1;
//         }
//     }

//     inFile.close();
//     outFile.close();
//     results[threadIndex] = matchCount;
//     return 0;
// }

// Version 4 (Stable)
// uint32_t Lookup_and_Replace_Function(
//     const string &inputFileNameBin,
//     streampos start,
//     streampos end,
//     const string &outputFileNameBin,
//     string searchString,
//     string replaceString,
//     int threadIndex,
//     vector<uint32_t> &results)
// {
//     ifstream inFile(inputFileNameBin, ios::binary);
//     ofstream outFile(outputFileNameBin, ios::binary | ios::app);
//     if (!inFile || !outFile)
//     {
//         cerr << "Error: Could not open file(s) in thread " << threadIndex << endl;
//         return -1;
//     }

//     inFile.seekg(start);
//     const size_t bufferSize = 4096;
//     char buffer[bufferSize];
//     streamoff currentPos = static_cast<streamoff>(start);

//     vector<uint8_t> lineCodeWords = convertSearchStringToCodeWord(processLineChar(searchString));
//     vector<uint8_t> replaceCodeWords = convertSearchStringToCodeWord(processLineChar(replaceString));

//     uint16_t lineCodeWordsSize = static_cast<uint16_t>(lineCodeWords.size());
//     uint16_t replaceCodeWordsSize = static_cast<uint16_t>(replaceCodeWords.size());
//     uint32_t matchCount = 0;
//     uint16_t byteIndex = 0;
//     vector<uint8_t> tmpCodeWord;

//     uint8_t byte = 0;
//     uint32_t toSkip = 0;

//     while (currentPos < end && inFile)
//     {
//         size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - currentPos));
//         inFile.read(buffer, bytesToRead);
//         size_t bytesRead = inFile.gcount();

//         if (bytesRead == bufferSize)
//         {
//             size_t safeEnd = bufferSize;
//             uint8_t stopSteps = 0;
//             for (int i = bufferSize - 1; i >= 0; --i)
//             {
//                 uint8_t byte = static_cast<uint8_t>(buffer[i]);
//                 uint8_t code = byte >> 1;
//                 if (
//                     byte == SPACE_BYTE ||
//                     byte == NEWLINE_BYTE
//                 )
//                 {
//                     stopSteps++;
//                     if(stopSteps == BACKWARD_STOP_STEPS){
//                         safeEnd = i - 1; 
//                         stopSteps = 0;
//                         break;
//                     }
//                 }
                
//             }
//             size_t unreadBytes = bytesRead - safeEnd;
//             if (unreadBytes > 0)
//             {
//                 inFile.clear();
//                 inFile.seekg(-static_cast<streamoff>(unreadBytes), ios::cur);
//                 bytesRead = safeEnd;
//             }
//         }

//         for (size_t i = 0; (i < bytesRead) && (currentPos < end); ++i, ++currentPos)
//         {
//             byte = static_cast<uint8_t>(buffer[i]);
//             uint16_t nextByteCode = byte & 1;

//             if (byte == (Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE)) && byte != lineCodeWords[byteIndex])
//             {
//                 if (i + 1 < bytesRead)
//                 {
//                     outFile.put(static_cast<char>(byte)); 
//                     i++; currentPos++;
//                     byte = static_cast<uint8_t>(buffer[i]);
//                     outFile.put(static_cast<char>(byte)); 
//                     i++; currentPos++;
//                     // uint8_t skipLength = (static_cast<uint8_t>(buffer[i])) * 2; // Why " *2 "? => each ASCII chaaracter is stored in 2 bytes
//                     uint8_t skipLength = (byte & 0x01111110) >> 1; 
                    
//                     outFile.write(&buffer[i], skipLength);
//                     i += skipLength - 1;
//                     currentPos += skipLength - 1;
//                     byteIndex = 0;
//                 }
//             }
//             else
//             {
//                 if (byte == lineCodeWords[byteIndex])
//                 {
//                     tmpCodeWord.push_back(byte);
//                     byteIndex++;
//                     if (byteIndex == lineCodeWordsSize) // match (found)
//                     {
//                         outFile.write(reinterpret_cast<const char *>(replaceCodeWords.data()), replaceCodeWords.size());
//                         matchCount++;
//                         byteIndex = 0;
//                         tmpCodeWord.clear();
//                     }
//                 }
//                 else
//                 {
//                     while (nextByteCode == 1 && i + 1 < bytesRead)
//                     {
//                         tmpCodeWord.push_back(byte);
//                         i++; currentPos++;
//                         byte = static_cast<uint8_t>(buffer[i]);
//                         nextByteCode = byte & 1;
//                     }
//                     tmpCodeWord.push_back(byte);
//                     outFile.write(reinterpret_cast<const char *>(tmpCodeWord.data()), tmpCodeWord.size());
//                     tmpCodeWord.clear();
//                     byteIndex = 0;
//                 }
//             }
//         }
//     }

//     inFile.close();
//     outFile.close();
//     results[threadIndex] = matchCount;
//     return 0;
// }



// ------------------------------------------------------
// ***** Lookup_Function ***********


// Version 5
uint32_t Lookup_Function(
    const string &inputFileNameBin,
    streampos start,
    streampos end,
    string searchString,
    int threadIndex,
    vector<uint32_t> &results)
{
    ifstream inFile(inputFileNameBin, ios::binary);
    if (!inFile)
    {
        cerr << "Error: Could not open file " << inputFileNameBin << " for reading." << endl;
        return -1;
    }

    inFile.seekg(start);

    const size_t bufferSize = 4096;
    char buffer[bufferSize];
    streamoff currentPos = static_cast<streamoff>(start);

    uint32_t matchCount = 0;
    uint16_t byteIndex = 0;

    vector<uint8_t> lineCodeWords = convertSearchStringToCodeWord(processLineChar(searchString));
    uint16_t lineCodeWordsSize = static_cast<uint16_t>(lineCodeWords.size());

    while (currentPos < end && inFile)
    {
        inFile.clear();
        inFile.seekg(currentPos);

        size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - currentPos));
        inFile.read(buffer, bytesToRead);
        size_t bytesRead = static_cast<size_t>(inFile.gcount());

        if (bytesRead == 0)
            break;

        size_t i = 0;
        size_t lastSafePosInBuffer = 0;

        while (i < bytesRead)
        {
            uint8_t byte = static_cast<uint8_t>(buffer[i]);
            uint16_t nextByteCode = byte & 1;

            if (byteIndex < lineCodeWordsSize && byte == lineCodeWords[byteIndex])
            {
                /*
                 * Matching path.
                 * If the matched byte is NEXT_SPECIAL_CODE, verify that the full
                 * special token is available using SPECIAL_CODE_WORD_READER().
                 */
                if (byte == Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE))
                {
                    size_t specialPos = i;
                    string specialWord = SPECIAL_CODE_WORD_READER(buffer, specialPos, bytesRead);

                    if (specialWord.empty())
                    {
                        break; // incomplete special token in current buffer
                    }

                    /*
                     * Continue byte-level matching through the complete special-token
                     * bytes, from i to specialPos inclusive.
                     */
                    while (i <= specialPos && byteIndex < lineCodeWordsSize)
                    {
                        uint8_t cur = static_cast<uint8_t>(buffer[i]);

                        if (cur == lineCodeWords[byteIndex])
                        {
                            ++byteIndex;
                            ++i;
                        }
                        else
                        {
                            byteIndex = 0;
                            break;
                        }
                    }

                    if (byteIndex == lineCodeWordsSize)
                    {
                        ++matchCount;
                        byteIndex = 0;
                    }

                    lastSafePosInBuffer = i;
                    continue;
                }

                ++byteIndex;
                ++i;
                lastSafePosInBuffer = i;

                if (byteIndex == lineCodeWordsSize)
                {
                    ++matchCount;
                    byteIndex = 0;
                }
            }
            else
            {
                /*
                 * Non-matching path.
                 * If current byte starts a special token, skip the whole special token
                 * using SPECIAL_CODE_WORD_READER(). No direct length calculation is used.
                 */
                if (byte == Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE))
                {
                    size_t specialPos = i;
                    string specialWord = SPECIAL_CODE_WORD_READER(buffer, specialPos, bytesRead);

                    if (specialWord.empty())
                    {
                        break; // incomplete special token
                    }

                    i = specialPos + 1;   // move past the special-code boundary byte
                    lastSafePosInBuffer = i;
                    byteIndex = 0;
                    continue;
                }

                /*
                 * Skip the remainder of the current normal codeword.
                 */
                if (nextByteCode == 1)
                {
                    do
                    {
                        ++i;

                        if (i >= bytesRead)
                            break;

                        nextByteCode = static_cast<uint16_t>(
                            static_cast<uint8_t>(buffer[i]) & 1
                        );

                    } while (nextByteCode == 1);

                    if (i >= bytesRead)
                        break;

                    ++i; // consume final byte with LSB = 0
                    lastSafePosInBuffer = i;
                }
                else
                {
                    ++i;
                    lastSafePosInBuffer = i;
                }

                byteIndex = 0;
            }
        }

        if (lastSafePosInBuffer == 0)
        {
            cerr << "Error[PIC]: No progress in Lookup_Function(). "
                 << "currentPos=" << currentPos
                 << ", bytesRead=" << bytesRead
                 << endl;
            return -1;
        }

        currentPos += static_cast<streamoff>(lastSafePosInBuffer);
    }

    inFile.close();

    results[threadIndex] = matchCount;
    return 0;
}

// Version 4
// uint32_t Lookup_Function(
//     const string &inputFileNameBin,
//     streampos start,
//     streampos end,
//     string searchString,
//     int threadIndex,
//     vector<uint32_t> &results)
// {
//     ifstream inFile(inputFileNameBin, ios::binary);
//     if (!inFile)
//     {
//         cerr << "Error: Could not open file " << inputFileNameBin << " for reading." << endl;
//         return -1;
//     }

//     inFile.seekg(start);
//     const size_t bufferSize = 4096;
//     char buffer[bufferSize];
//     streamoff currentPos = static_cast<streamoff>(start);

//     uint32_t matchCount = 0;
//     uint16_t byteIndex = 0;
//     vector<uint8_t> lineCodeWords = convertSearchStringToCodeWord(processLineChar(searchString));
//     uint16_t lineCodeWordsSize = static_cast<uint16_t>(lineCodeWords.size());

//     while (currentPos < end && inFile)
//     {
//         inFile.clear();
//         inFile.seekg(currentPos);

//         size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - currentPos));
//         inFile.read(buffer, bytesToRead);
//         size_t bytesRead = inFile.gcount();

//         if (bytesRead == 0)
//             break;

//         size_t i = 0;
//         size_t lastSafePosInBuffer = 0;

//         while (i < bytesRead)
//         {
//             uint8_t byte = static_cast<uint8_t>(buffer[i]);
//             uint16_t nextByteCode = byte & 1;

//             if (byteIndex < lineCodeWordsSize && byte == lineCodeWords[byteIndex])
//             {
//                 // If matching a special-code search pattern, ensure the full special code word exists
//                 if (byte == Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE))
//                 {
//                     size_t specialPos = i;
//                     string specialWord = SPECIAL_CODE_WORD_READER(buffer, specialPos, bytesRead);

//                     if (specialWord.empty()) {
//                         break; // incomplete special token
//                     }

//                     // specialPos points to END_SPECIAL_CODE
//                     for (; i <= specialPos; ++i) {
//                         if (byteIndex < lineCodeWordsSize && static_cast<uint8_t>(buffer[i]) == lineCodeWords[byteIndex])
//                             ++byteIndex;
//                         else {
//                             byteIndex = 0;
//                             break;
//                         }
//                     }

//                     if (byteIndex == lineCodeWordsSize)
//                     {
//                         matchCount++;
//                         byteIndex = 0;
//                     }

//                     lastSafePosInBuffer = i;
//                     continue;
//                 }

//                 ++byteIndex;
//                 ++i;
//                 lastSafePosInBuffer = i;

//                 if (byteIndex == lineCodeWordsSize)
//                 {
//                     matchCount++;
//                     byteIndex = 0;
//                 }
//             }
//             else
//             {
//                 // If the current byte begins a special token and we are not matching it,
//                 // skip the whole special token safely.
//                 if (byte == Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE))
//                 {
//                     size_t specialPos = i;
//                     string specialWord = SPECIAL_CODE_WORD_READER(buffer, specialPos, bytesRead);

//                     if (specialWord.empty()) {
//                         break; // incomplete special token
//                     }

//                     i = specialPos + 1;   // move past END_SPECIAL_CODE
//                     lastSafePosInBuffer = i;
//                     byteIndex = 0;
//                     continue;
//                 }
                

//                 // Skip the remainder of the current normal codeword
//                 if (nextByteCode == 1)
//                 {
//                     do {
//                         ++i;
//                         if (i >= bytesRead)
//                             break;
//                         nextByteCode = static_cast<uint16_t>(static_cast<uint8_t>(buffer[i])) & 1;
//                     } while (nextByteCode == 1);

//                     if (i >= bytesRead)
//                         break;

//                     ++i; // consume final byte with LSB = 0
//                     lastSafePosInBuffer = i;
//                 }
//                 else
//                 {
//                     ++i;
//                     lastSafePosInBuffer = i;
//                 }

//                 byteIndex = 0;
//             }
//         }

//         currentPos += static_cast<streamoff>(lastSafePosInBuffer);

//         if (lastSafePosInBuffer == 0) {
//             cerr << "Error[PIC]: No progress in Lookup_Function()." << endl;
//             return -1;
//         }
//     }

//     inFile.close();
//     results[threadIndex] = matchCount;
//     return 0;
// }


// Version 3.1 (Stable)
// uint32_t Lookup_Function(
//     const string &inputFileNameBin,
//     streampos start,
//     streampos end,
//     string searchString,
//     int threadIndex,
//     vector<uint32_t> &results)
// {
//     ifstream inFile(inputFileNameBin, ios::binary);
//     if (!inFile)
//     {
//         cerr << "Error: Could not open file " << inputFileNameBin << " for reading." << endl;
//         return -1;
//     }

//     inFile.seekg(start);
//     const size_t bufferSize = 4096;
//     char buffer[bufferSize];
//     streamoff currentPos = static_cast<streamoff>(start);

//     uint32_t matchCount = 0;
//     uint16_t byteIndex = 0;
//     vector<uint8_t> lineCodeWords = convertSearchStringToCodeWord(processLineChar(searchString));
//     uint16_t lineCodeWordsSize = static_cast<uint16_t>(lineCodeWords.size());

//     uint8_t byte = 0;
//     uint32_t toSkip = 0;

//     while (currentPos < end && inFile)
//     {
//         size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - currentPos));
//         inFile.read(buffer, bytesToRead);
//         size_t bytesRead = inFile.gcount();

//         // If we filled the buffer, find a safe break point
//         if (bytesRead == bufferSize)
//         {
//             size_t safeEnd = bufferSize;
//             uint8_t stopSteps = 0;
//             for (int i = bufferSize - 1; i >= 0; --i)
//             {

//                 uint8_t byte = static_cast<uint8_t>(buffer[i]);
//                 uint8_t code = byte >> 1;
//                 if (
//                     byte == SPACE_BYTE ||
//                     byte == NEWLINE_BYTE
//                 )
//                 {
//                     stopSteps++;
//                     if(stopSteps == BACKWARD_STOP_STEPS){
//                         safeEnd = i - 1; 
//                         stopSteps = 0;
//                         break;
//                     }
//                 }
//                 // if (buffer[i] == 0x0 || buffer[i] == 0x2 || buffer[i] == 0x4 || buffer[i] == 0x6) // reserved code-words
//                 // {
//                 //     safeEnd = i;
//                 //     break;
//                 // }
//             }
//             // Adjust file position to re-read the skipped bytes in the next loop
//             size_t unreadBytes = bytesRead - safeEnd;
//             if (unreadBytes > 0)
//             {
//                 inFile.clear(); // clear eofbit if set
//                 inFile.seekg(-static_cast<streamoff>(unreadBytes), ios::cur);
//                 bytesRead = safeEnd;
//             }
//         }

//         for (size_t i = 0; i < bytesRead && currentPos < end; ++i, ++currentPos)
//         {
//             byte = static_cast<uint8_t>(buffer[i]);
//             uint16_t nextByteCode = byte & 1;

//             if (byte == (Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE)) && byte != lineCodeWords[byteIndex])
//             {
//                 if (i + 1 >= bytesRead) {
//                     cerr << "Error - L: Not enough bytes to read sizeByte!\n";
//                     exit(1);
//                 }
//                 else // (i + 1 < bytesRead)
//                 {
//                     toSkip = static_cast<uint8_t>(buffer[i + 1]) * 2; // Why " *2 "? => each ASCII chaaracter is stored in 2 bytes
//                     i += toSkip + 1;
//                     currentPos += toSkip + 1;
//                     byteIndex = 0;
//                 }
//             }
//             else
//             {
//                 if (byte == lineCodeWords[byteIndex])
//                 {
//                     byteIndex++;
//                 }
//                 else if (nextByteCode == 1)
//                 {
//                     do {
//                         i++; currentPos++;
//                         nextByteCode = static_cast<uint16_t>(buffer[i]) & 1;
//                     } while (nextByteCode == 1);

//                     byteIndex = 0;
//                 }

//                 if (byteIndex == lineCodeWordsSize)
//                 {
//                     byteIndex = 0;
//                     matchCount++;
//                 }
//             }
//         }
//     }

//     inFile.close();
//     results[threadIndex] = matchCount;
//     return 0;
// }



// ----------------------------------------

// *** Consecutive Array for Decompression ***
uint8_t Build_Dictionary_Table_Decompression()
{
    // Variables to store each line and word
    string line, word;
    uint32_t serial = CODE_WORD_OFFSET; // Start serializing after the the serialized number of all reserved codeWords

    // Open the Text file
    ifstream file(dictFilename);

    // Check if the file is open
    if (!file.is_open())
    {
        cerr << "Error opening file: " << dictFilename << endl;
        return 1;
    }

    // Read the file line by line
    while (getline(file, line))
    {
        stringstream ss(line); // Use a stringstream to parse the line
        string temp;           // To hold the "count" column which we will ignore

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
    cout << "\nTotal words = " << serial - 1 << "\n";
    cout << "The hash map for decompresssion has been generated successfully!\n\n";

    // // Test the hash map
    // cout << "Test the hash map:\n";
    // uint32_t tmpSerial = 127;
    // cout << "Serial (" << tmpSerial << ") has a word of: " << dictMapCode[tmpSerial] << "\n";
    // cout << "\n\n";

    return 0;
}


// *** Hash table for Cecompression ***
uint8_t Build_Dictionary_Table_Compression()
{
    // Variables to store each line and word
    string line, word;
    uint32_t serial = CODE_WORD_OFFSET; // Start serializing from 3

    // Open the Text file
    ifstream file(dictFilename);

    // Check if the file is open
    if (!file.is_open())
    {
        cerr << "Error opening file: " << dictFilename << endl;
        return 1;
    }

    // Read the file line by line
    while (getline(file, line))
    {
        stringstream ss(line); // Use a stringstream to parse the line
        string temp;           // To hold the "count" column which we will ignore

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
    cout << "\nTotal words = " << serial - 1 << "\n";
    cout << "The hash map for compression has been generated successfully!\n\n";

    // // Test the hash map
    // cout << "Test the hash map:\n";
    // string tmp_word = "wild";
    // cout << "Word (" << tmp_word << ") has an order of: " << dictMapWord[tmp_word] << "\n";
    // cout << "\n\n";

    return 0;
}

// -------------------------------------------
// ------ Compression Function --------------


// Version 3 (Stable) – with final‐line fix
uint8_t Compression_Function(
    const string &inputFileText,
    streampos start,
    streampos end,
    const string &outputFileBin)
{
    ifstream inFile(inputFileText);
    if (!inFile) {
        cerr << "Error opening file: " << inputFileText << endl;
        return -1;
    }

    inFile.seekg(start);
    if (start > 0) {
        string temp;
        getline(inFile, temp);  // skip partial first line
    }

    ofstream outFile(outputFileBin, ios::binary | ios::app);
    if (!outFile) {
        cerr << "Error: Could not open the file." << endl;
        return 1;
    }

    const size_t bufferSize = 4096;
    char buffer[bufferSize];
    streamoff currentPos = static_cast<streamoff>(start);

    vector<string>   tokens;
    vector<uint8_t>  lineCodeWords;
    const char*     bufferPtr;
    size_t          bufferLen;

    string chunkText;
    while (currentPos < end && inFile) {
        // read up to chunk end or bufferSize
        size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - currentPos));
        inFile.read(buffer, bytesToRead);
        size_t bytesRead = inFile.gcount();

        // find last newline so we don't cut a line in half
        size_t safeEnd = bytesRead;
        for (size_t i = bytesRead; i-- > 0;) {
            if (buffer[i] == '\n') {
                safeEnd = i + 1;
                break;
            }
        }

        // rewind any unread bytes
        size_t unread = bytesRead - safeEnd;
        if (unread > 0) {
            inFile.clear();
            inFile.seekg(-static_cast<streamoff>(unread), ios::cur);
            bytesRead = safeEnd;
            // currentPos -= unread; // added 
        }

        // append full‐line portion to chunkText
        chunkText.append(buffer, bytesRead);
        // currentPos = inFile.tellg();
        currentPos = static_cast<streamoff>(inFile.tellg());

        // process all complete lines in chunkText
        istringstream ss(chunkText);
        string line;
        string leftover;
        while (getline(ss, line)) {
            if (ss.eof() && chunkText.back() != '\n') {
                // this line is incomplete—save and break
                leftover = line;
                break;
            }
            tokens = processLineChar(line);
            lineCodeWords = convertStringToCodeWord(tokens);
            bufferPtr = reinterpret_cast<const char*>(lineCodeWords.data());
            bufferLen = lineCodeWords.size();
            outFile.write(bufferPtr, bufferLen);
        }

        // keep only the incomplete trailing part
        chunkText = leftover;
    }

    inFile.close();
    outFile.close();
    return 0;
}




// -------------------------------------------------


/*
A function used to process each line read from a plain text file separately.
It will recognize between words, characters, uppercase, and puctuation characters.
*/

/*
-- processLineChar Function --
We will organize the process in the following steps:
1. Check if it is alphabets or numbers
    1.1. If uppercase and the word is not empty, then assign a code-word for uppercase
    1.2. Add the character to the word string
2. Check for ' and 's
3. Check punct
4. Check space
*/
vector<string> processLineChar(const string &line)
{
    vector<string> result;
    vector<uint8_t> lineCodeWords;
    string word;
    bool startsWithUppercase = false; // Flag to indicate if the word starts with an uppercase letter

    for (size_t i = 0; i < line.size(); ++i)
    {
        char ch = line[i];

        if (isalnum(ch))
        { // If the character is alphanumeric, build the word
            if (word.empty() && isupper(ch))
            {
                result.push_back(string(1, 0xff)); // '0xff' represents that the next word starts with an uppercase character.
                startsWithUppercase = true;        // Set the flag if the first character is uppercase
                // cout << "Uppercase character..\n"; // for testing...
            }
            // ch = tolower(ch); // set the uppercase character to lowercase character.
            word += ch;
        }
        else
        {
            // word[0] = tolower(word[0]); // set the first uppercase character to lowercase character.
            if (ch == '\"' || (i + 2 <= line.size() && line.substr(i, 3) == "“") || (i + 2 <= line.size() && line.substr(i, 3) == "”"))
            {
                if (!word.empty())
                {
                    result.push_back(word);
                    word.clear();
                }
                result.push_back("\"");
            }
            else if (ch == '\'' || (i + 2 <= line.size() && line.substr(i, 3) == "’"))
            {
                if (!word.empty())
                {
                    result.push_back(word);
                    word.clear();
                }
                result.push_back("'");

                // Check for 's' after the apostrophe
                if (i + 1 < line.size() && line[i + 1] == 's')
                {
                    result.push_back("s");
                    ++i; // Skip the 's'
                }
            }
            else if (ispunct(ch))
            // else if (isPunctModified(ch))
            { // Handle punctuation
                if (!word.empty())
                {
                    result.push_back(word);
                    word.clear();
                }
                result.push_back(string(1, ch)); // Add punctuation as a separate string
            }
            else if (isspace(ch))
            { // Handle spaces
                if (!word.empty())
                {
                    result.push_back(word);
                    word.clear();
                }
                result.push_back(string(1, ' ')); // Add space as a separate string -- SPACE
            }
            
        }

        startsWithUppercase = false;
    }

    // Add the last word if there is any
    if (!word.empty())
    {
        result.push_back(word);
    }

    return result; // return a vector of separate strings
}

vector<uint8_t> convertStringToCodeWord(vector<string> wordsSet)
{

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
    2) New line             => 0x1 --> in PIC format, shift left by 1 => 0x2
    3) Next Capital letter  => 0x2 --> in PIC format, shift left by 1 => 0x4
    */

    for (size_t i = 0; i < wordsSet.size(); ++i)
    {
        word = wordsSet[i];

        // serial = dictMapWord[word];
        if (!word.empty() && static_cast<uint8_t>(word[0]) == 0x20)
        {                                        // compare with SPACE in ASCII
            lineCodeWords.push_back(SPACE_CODE); // SPACE codeWord
        }
        else if (!word.empty() && static_cast<uint8_t>(word[0]) == 0xFF)
        {                                                                              // compare with Next Uppercase character code (0xFF)
            lineCodeWords.push_back(Shift_Left_with_Zero_Inserted(NEXT_CAPITAL_CODE)); // next uppercase letter codeWord
        }
        else
        {

            /*
            NOTE:
            - In the 'unordered_map', the returned value of 'not found' hash key is zero '0'.
            */
            string tmpWord = word;
            tmpWord[0] = tolower(tmpWord[0]); // set the first uppercase character to lowercase character.
            serial = dictMapWord[tmpWord];    // read the value of the word in the dictionary hash table

            if (serial == 0)
            { // NOT FOUND in the hash table - SPECIAL codeWord
                // Call a function to generate a special codeWord
                byteCodes = SPECIAL_CODE_WORD_GENERATOR(word);
                lineCodeWords.push_back(Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE)); // next special codeWord

                // increment the special code word counter
                specialCodeWordCounter++;

                // for debug ..
                // cout << "special code: " << word << endl;

                // Push the byteCodes to the lineCodeWords vector
                lineCodeWords.insert(lineCodeWords.end(), byteCodes.begin(), byteCodes.end());
                lineCodeWords.push_back(Shift_Left_with_Zero_Inserted(END_SPECIAL_CODE)); // end special codeWord
                byteCodes.clear();
            }
            else
            {
                // word = tmpWord; // set the first character to a lowercase letter

                if (serial >= ONE_BYTE_LOWER_BOUND && serial < ONE_BYTE_BOUND)
                {                                                     // ONE BYTE encoding
                    inputNumber = serial;                             // add the offset if the reserved codeWords (i.e. space, newline, ..)
                    byteCodes = ONE_BYTE_CODE_GENERATOR(inputNumber); // generate a single byte codeWord
                    T1_FREQ++;
                }
                else if (serial >= TWO_BYTE_OFFSET && serial < TWO_BYTE_BOUND)
                { // TWO BYTE encoding
                    inputNumber = serial - TWO_BYTE_OFFSET;
                    byteCodes = TWO_BYTE_CODE_GENERATOR(inputNumber); // generate a two bytes codeWord
                    T2_FREQ++;
                }
                else if (serial >= THREE_BYTE_OFFSET && serial < THREE_BYTE_BOUND)
                {
                    inputNumber = serial - (THREE_BYTE_OFFSET);
                    byteCodes = THREE_BYTE_CODE_GENERATOR(inputNumber); // generate a three bytes codeWord
                    T3_FREQ++;
                }
                else if (serial >= FOUR_BYTE_OFFSET && serial < FOUR_BYTE_BOUND)
                {
                    inputNumber = serial - (FOUR_BYTE_OFFSET);
                    byteCodes = FOUR_BYTE_CODE_GENERATOR(inputNumber); // generate a three bytes codeWord
                    T4_FREQ++;
                }
                else
                {
                    // Add word to the map with the current serial number
                    // dictMapWord[word] = serial;
                    T5_FREQ++;
                }

                // Push the byteCodes to the lineCodeWords vector
                lineCodeWords.insert(lineCodeWords.end(), byteCodes.begin(), byteCodes.end());
                byteCodes.clear();
            }

            

        } // end of else for special codeWords

    } // end of the for loop

    // if (!lineCodeWords.empty()) {
    lineCodeWords.push_back(Shift_Left_with_Zero_Inserted(NEW_LINE_CODE)); // newline only if line is not empty
    // }

    return lineCodeWords;
}

vector<uint8_t> convertSearchStringToCodeWord(vector<string> wordsSet)
{

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
    2) New line             => 0x1 --> in PIC format, shift left by 1 => 0x2
    3) Next Capital letter  => 0x2 --> in PIC format, shift left by 1 => 0x4
    */

    for (size_t i = 0; i < wordsSet.size(); ++i)
    {
        word = wordsSet[i];

        // serial = dictMapWord[word];
        if (!word.empty() && static_cast<uint8_t>(word[0]) == 0x20)
        {                                        // compare with SPACE in ASCII
            lineCodeWords.push_back(SPACE_CODE); // SPACE codeWord
        }
        else if (!word.empty() && static_cast<uint8_t>(word[0]) == 0xFF)
        {                                                                              // compare with Next Uppercase character code (0xFF)
            lineCodeWords.push_back(Shift_Left_with_Zero_Inserted(NEXT_CAPITAL_CODE)); // next uppercase letter codeWord
        }
        else
        {

            /*
            NOTE:
            - In the 'unordered_map', the returned value of 'not found' hash key is zero '0'.
            */
            string tmpWord = word;
            tmpWord[0] = tolower(tmpWord[0]); // set the first uppercase character to lowercase character.
            serial = dictMapWord[tmpWord];    // read the value of the word in the dictionary hash table

            if (serial == 0)
            { // NOT FOUND in the hash table - SPECIAL codeWord
                // Call a function to generate a special codeWord
                byteCodes = SPECIAL_CODE_WORD_GENERATOR(word);
                lineCodeWords.push_back(Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE)); // next special codeWord

                // increment the special code word counter
                specialCodeWordCounter++;

                // for debug ..
                // cout << "special code: " << word << endl;

                // Push the byteCodes to the lineCodeWords vector
                lineCodeWords.insert(lineCodeWords.end(), byteCodes.begin(), byteCodes.end());
                lineCodeWords.push_back(Shift_Left_with_Zero_Inserted(END_SPECIAL_CODE)); // end special codeWord
                byteCodes.clear();
            }
            else
            {
                // word = tmpWord; // set the first character to a lowercase letter

                if (serial >= ONE_BYTE_LOWER_BOUND && serial < ONE_BYTE_BOUND)
                {                                                     // ONE BYTE encoding
                    inputNumber = serial;                             // add the offset if the reserved codeWords (i.e. space, newline, ..)
                    byteCodes = ONE_BYTE_CODE_GENERATOR(inputNumber); // generate a single byte codeWord
                }
                else if (serial >= TWO_BYTE_OFFSET && serial < TWO_BYTE_BOUND)
                { // TWO BYTE encoding
                    inputNumber = serial - TWO_BYTE_OFFSET;
                    byteCodes = TWO_BYTE_CODE_GENERATOR(inputNumber); // generate a two bytes codeWord
                }
                else if (serial >= THREE_BYTE_OFFSET && serial < THREE_BYTE_BOUND)
                {
                    inputNumber = serial - (THREE_BYTE_OFFSET);
                    byteCodes = THREE_BYTE_CODE_GENERATOR(inputNumber); // generate a three bytes codeWord
                }
                else if (serial >= FOUR_BYTE_OFFSET && serial < FOUR_BYTE_BOUND)
                {
                    inputNumber = serial - (FOUR_BYTE_OFFSET);
                    byteCodes = FOUR_BYTE_CODE_GENERATOR(inputNumber); // generate a three bytes codeWord
                }
                else
                {
                    // Add word to the map with the current serial number
                    // dictMapWord[word] = serial;
                }

                // Push the byteCodes to the lineCodeWords vector
                lineCodeWords.insert(lineCodeWords.end(), byteCodes.begin(), byteCodes.end());
                byteCodes.clear();
            }

            

        } // end of else for special codeWords

    } // end of the for loop

    // We don't need to add a newline for the search string.
    // lineCodeWords.push_back(Shift_Left_with_Zero_Inserted(NEW_LINE_CODE)); // new line codeWord

    return lineCodeWords;
}

// ----------------------------------
// ---- Decompression Function ------


// Version 4
uint8_t Decompression_Function(
    const string &inputFileNameBin,
    streampos start,
    streampos end,
    const string &outputFileNameText)
{
    ifstream inFile(inputFileNameBin, ios::binary);
    ofstream outFile(outputFileNameText, ios::app);

    if (!inFile || !outFile)
    {
        cerr << "Error opening files for decompression." << endl;
        return -1;
    }

    const size_t mainChunkSize = 4096;
    const size_t lookAheadSize = 128;
    const size_t bufferSize = mainChunkSize + lookAheadSize;

    char buffer[bufferSize];

    streamoff currentPos = static_cast<streamoff>(start);
    const streamoff endPos = static_cast<streamoff>(end);

    uint32_t tmpSerial = 0, finalSerial = 0;
    string word;
    uint8_t nextByte = 0;
    bool NEXT_CAP = false;
    uint32_t count = 0;

    while (currentPos < endPos && inFile)
    {
        const streamoff oldPos = currentPos;

        inFile.clear();
        inFile.seekg(currentPos);

        size_t bytesToRead = static_cast<size_t>(
            min<streamoff>(bufferSize, endPos - currentPos)
        );

        inFile.read(buffer, bytesToRead);
        size_t bytesRead = static_cast<size_t>(inFile.gcount());

        if (bytesRead == 0)
        {
            cerr << "Error[PIC]: bytesRead == 0 in Decompression_Function(). "
                 << "currentPos=" << currentPos
                 << ", end=" << endPos << endl;
            return -1;
        }

        const bool hasLookAhead = (bytesRead > mainChunkSize);
        const size_t tokenStartLimit = hasLookAhead ? mainChunkSize : bytesRead;

        size_t i = 0;
        size_t consumedBytes = 0;

        tmpSerial = 0;
        finalSerial = 0;
        count = 0;

        while (i < bytesRead)
        {
            /*
             * Strict pointer rule:
             * Start a new token only inside the main 4096-byte region.
             * The lookahead region is only for completing a token that
             * already started inside the main region.
             */
            if (count == 0 && i >= tokenStartLimit)
                break;

            const size_t tokenStart = i;

            uint8_t rawByte = static_cast<uint8_t>(buffer[i]);
            nextByte = rawByte & 1;
            uint8_t byte = rawByte >> 1;

            if (nextByte == 0)
            {
                finalSerial = static_cast<uint32_t>(
                    concatenateBytes(finalSerial, byte, count)
                );

                if (count > 3)
                {
                    cerr << "Error[PIC]: Invalid codeword length. "
                         << "count=" << count
                         << ", currentPos=" << currentPos
                         << ", i=" << i
                         << ", bytesRead=" << bytesRead << endl;
                    return -1;
                }

                if (count == 1)
                    finalSerial += TWO_BYTE_OFFSET;
                else if (count == 2)
                    finalSerial += THREE_BYTE_OFFSET;
                else if (count == 3)
                    finalSerial += FOUR_BYTE_OFFSET;

                if (finalSerial == SPACE_CODE)
                {
                    outFile << " ";
                    ++i;
                    consumedBytes = i;
                }
                else if (finalSerial == NEW_LINE_CODE)
                {
                    outFile << "\n";
                    ++decodedLineCounter;
                    ++i;
                    consumedBytes = i;
                }
                else if (finalSerial == NEXT_CAPITAL_CODE)
                {
                    NEXT_CAP = true;
                    ++i;
                    consumedBytes = i;
                }
                else if (finalSerial == NEXT_SPECIAL_CODE)
                {
                    /*
                     * SPECIAL_CODE_WORD_READER contract assumed:
                     * - input i points to NEXT_SPECIAL_CODE
                     * - on success, i points to END_SPECIAL_CODE
                     * - on failure, returns "" and restores i
                     */
                    string specialWord = SPECIAL_CODE_WORD_READER(buffer, i, bytesRead);

                    if (specialWord.empty())
                    {
                        cerr << "Error[PIC]: Incomplete/invalid special code word. "
                             << "tokenStart=" << tokenStart
                             << ", currentPos=" << currentPos
                             << ", i=" << i
                             << ", bytesRead=" << bytesRead
                             << ", tokenStartLimit=" << tokenStartLimit
                             << endl;
                        return -1;
                    }

                    outFile << specialWord;

                    ++i;                 // move past END_SPECIAL_CODE
                    consumedBytes = i;   // exact bytes consumed from buffer start

                    tmpSerial = 0;
                    finalSerial = 0;
                    count = 0;
                    continue;
                }
                else
                {
                    /*
                     * If dictMapCodeArray is a raw pointer, replace
                     * dictMapCodeArraySize with your actual dictionary-size variable.
                     */
                    if (finalSerial >= NUMBER_OF_WORDS_DICT)
                    {
                        cerr << "Error[PIC]: finalSerial out of range. "
                             << "finalSerial=" << finalSerial
                             << ", dictSize=" << NUMBER_OF_WORDS_DICT
                             << ", currentPos=" << currentPos
                             << ", i=" << i
                             << ", bytesRead=" << bytesRead
                             << ", count=" << count << endl;
                        return -1;
                    }

                    word = dictMapCodeArray[finalSerial];

                    if (NEXT_CAP)
                    {
                        if (!word.empty())
                            word[0] = static_cast<char>(
                                toupper(static_cast<unsigned char>(word[0]))
                            );
                        NEXT_CAP = false;
                    }

                    outFile << word;
                    ++i;
                    consumedBytes = i;
                }

                tmpSerial = 0;
                finalSerial = 0;
                count = 0;
            }
            else
            {
                if (count >= 4)
                {
                    cerr << "Error[PIC]: Codeword continuation exceeded maximum length. "
                         << "count=" << count
                         << ", currentPos=" << currentPos
                         << ", i=" << i
                         << ", bytesRead=" << bytesRead
                         << ", rawByte=" << unsigned(rawByte) << endl;
                    return -1;
                }

                finalSerial = concatenateBytes(finalSerial, byte, count);
                count++;
                ++i;

                /*
                 * Do not update consumedBytes here.
                 * The token is incomplete until a byte with LSB=0 is processed.
                 */
            }
        }

        if (consumedBytes == 0)
        {
            cerr << "Error[PIC]: No progress in Decompression_Function(). "
                 << "currentPos=" << currentPos
                 << ", bytesRead=" << bytesRead
                 << ", tokenStartLimit=" << tokenStartLimit << endl;
            return -1;
        }

        currentPos = oldPos + static_cast<streamoff>(consumedBytes);

        if (currentPos <= oldPos)
        {
            cerr << "Error[PIC]: Pointer did not advance. "
                 << "oldPos=" << oldPos
                 << ", currentPos=" << currentPos
                 << ", consumedBytes=" << consumedBytes << endl;
            return -1;
        }
    }

    inFile.close();
    outFile.close();
    return 0;
}



// Version 3 (Stable)
// uint8_t Decompression_Function(const string &inputFileNameBin, streampos start, streampos end, const string &outputFileNameText)
// {
//     ifstream inFile(inputFileNameBin, ios::binary);
//     ofstream outFile(outputFileNameText, ios::app);
//     if (!inFile || !outFile)
//     {
//         cerr << "Error opening files for decompression." << endl;
//         return -1;
//     }

//     inFile.seekg(start);
//     const size_t bufferSize = 4096;
//     char buffer[bufferSize];
//     streamoff currentPos = static_cast<streamoff>(start);

//     uint32_t tmpSerial = 0, finalSerial = 0;
//     string word;
//     uint8_t nextByte;
//     bool NEXT_CAP = false;
//     uint32_t count = 0;

//     while (currentPos < end && inFile)
//     {
//         inFile.clear(); // Clear any EOF/failure flags before seeking
//         inFile.seekg(currentPos); // roll back to current position in case of a failure of buffer read

//         size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - currentPos));
//         inFile.read(buffer, bytesToRead);
//         size_t bytesRead = inFile.gcount();

//         if (bytesRead == bufferSize)
//         {
//             size_t safeEnd = bufferSize;
//             uint8_t stopSteps = 0;
//             for (int i = bufferSize - 1; i >= 0; --i)
//             {
//                 uint8_t byte = static_cast<uint8_t>(buffer[i]);
//                 uint8_t code = byte >> 1;
//                 if (
//                     byte == SPACE_BYTE 
//                     // ||
//                     // byte == NEWLINE_BYTE
//                 )
//                 {
//                     stopSteps++;
//                     if(stopSteps == BACKWARD_STOP_STEPS){
//                         safeEnd = i - 1; 
//                         stopSteps = 0;
//                         break;
//                     }
//                 }
                
//             }
//             size_t unreadBytes = bytesRead - safeEnd;
//             if (unreadBytes > 0)
//             {
//                 inFile.clear();
//                 inFile.seekg(-static_cast<streamoff>(unreadBytes), ios::cur);
//                 bytesRead = safeEnd;
//             }
//         }
        

//         for (size_t i = 0; i < bytesRead && currentPos < end;)
//         {
//             uint8_t byte = static_cast<uint8_t>(buffer[i]);
//             nextByte = byte & 1;
//             byte >>= 1;

//             if (nextByte == 0)
//             {
//                 finalSerial = static_cast<uint32_t>(concatenateBytes(finalSerial, byte, count));

//                 if (count == 1)
//                     finalSerial += TWO_BYTE_OFFSET;
//                 else if (count == 2)
//                     finalSerial += THREE_BYTE_OFFSET;
//                 else if (count == 3)
//                     finalSerial += FOUR_BYTE_OFFSET;

//                 if (finalSerial == SPACE_CODE)
//                 {
//                     outFile << " ";
//                 }
//                 else if (finalSerial == NEW_LINE_CODE)
//                 {
//                     outFile << "\n";
//                     ++decodedLineCounter;
//                 }
//                 else if (finalSerial == NEXT_CAPITAL_CODE)
//                 {
//                     NEXT_CAP = true;
//                 }
//                 else if (finalSerial == NEXT_SPECIAL_CODE)
//                 {
//                     size_t start_i = i;
//                     string word = SPECIAL_CODE_WORD_READER(buffer, i, bytesRead);

//                     if (word.empty()) {
//                         // i = start_i;
//                         i = start_i - 1;
//                         currentPos--;
//                         break;
//                     }

//                     outFile << word;
//                     i++; // to skip the END_SPECIAL_CODE byteCode 
//                     tmpSerial = finalSerial = 0;
//                     count = 0;
//                     currentPos += (i - start_i);  // update currentPos manually
//                     continue; // updated currentPos in the previous statement, and already advanced i inside reader
//                 }
//                 else
//                 {
//                     word = dictMapCodeArray[finalSerial];
//                     if (NEXT_CAP)
//                     {
//                         word[0] = toupper(word[0]);
//                         NEXT_CAP = false;
//                     }
//                     outFile << word;
//                 }

//                 tmpSerial = finalSerial = 0;
//                 count = 0;
//                 ++i; // advance only here
//             }
//             else
//             {
//                 finalSerial = concatenateBytes(finalSerial, byte, count);
//                 count++;
//                 ++i;
//             }

//             ++currentPos;
//         }

//     }

//     inFile.close();
//     outFile.close();
//     return 0;
// }


// ----------------------------------



uint32_t concatenateBytes(uint32_t final, uint32_t tmp, uint8_t count)
{
    return final | (tmp << (6 * count));
}

/*
NOTE: 'cerr' function.
In C++, cerr is the standard error stream used to output the errors.
It is an instance of the ostream class and is un-buffered,
so it is used when we need to display the error message immediately and
does not store the error message to display later.
The ‘c’ in cerr refers to “character” and ‘err’ means “error”,
Hence cerr means “character error”.
On the other hand, cout is used for standard output,
and the string message may be buffered and
displayed after the program execution completes.
*/

// Version 4
string SPECIAL_CODE_WORD_READER(const char* buffer, size_t& i, size_t bytesRead)
{
    string decoded;
    const size_t start_i = i;

    if (i + 2 >= bytesRead) {
        i = start_i;
        return "";
    }

    ++i;
    uint8_t countLowByte = static_cast<uint8_t>(buffer[i]);

    ++i;
    uint8_t countHighByte = static_cast<uint8_t>(buffer[i]);

    if ((countLowByte & 0x01) != 0x01 || (countLowByte & 0x80) != 0x00 ||
        (countHighByte & 0x01) != 0x01 || (countHighByte & 0x80) != 0x00) {
        i = start_i;
        return "";
    }

    uint16_t low6  = static_cast<uint16_t>((countLowByte >> 1) & 0x3F);
    uint16_t high6 = static_cast<uint16_t>((countHighByte >> 1) & 0x3F);

    uint16_t charCount = static_cast<uint16_t>((high6 << 6) | low6);

    if (charCount == 0) {
        i = start_i;
        return "";
    }

    size_t payloadBytes = static_cast<size_t>(charCount) * 2;

    if (i + payloadBytes >= bytesRead) {
        i = start_i;
        return "";
    }

    decoded.reserve(charCount);

    for (uint16_t j = 0; j < charCount; ++j) {
        uint8_t b1 = static_cast<uint8_t>(buffer[++i]);
        uint8_t b2 = static_cast<uint8_t>(buffer[++i]);

        uint8_t high2 = (b1 >> 1) & 0x03;
        uint8_t low6Char = (b2 >> 1) & 0x3F;

        char ch = static_cast<char>((high2 << 6) | low6Char);
        decoded += ch;
    }

    if (i + 1 >= bytesRead) {
        i = start_i;
        return "";
    }

    uint8_t endCode = static_cast<uint8_t>(buffer[i + 1]) >> 1;
    if (endCode != END_SPECIAL_CODE) {
        i = start_i;
        return "";
    }

    ++i; // now i points to END_SPECIAL_CODE
    return decoded;
}


// Version 3
// PIC version — read from an in-memory buffer
// Contract:
//  - buffer: current chunk
//  - i: index into buffer; on success advanced to last payload byte
//  - bytesRead: valid extent of buffer
// Returns decoded ASCII string or "" if incomplete/invalid in this buffer.
// On failure, i is rolled back to its position before reading size.
// string SPECIAL_CODE_WORD_READER(const char* buffer, size_t& i, size_t bytesRead)
// {
//     string decoded;
//     const size_t start_i = i;

//     // Need at least the size byte
//     if (i + 1 >= bytesRead) {
//         i = start_i;
//         return "";
//     }

//     // Read encoded size byte
//     uint8_t rawSizeByte = static_cast<uint8_t>(buffer[++i]);
//     uint8_t numBytes = (rawSizeByte >> 1) & 0x3F;

//     // Must be nonzero and even: each decoded char uses 2 encoded bytes
//     if (numBytes == 0 || (numBytes & 1) != 0) {
//         i = start_i;
//         return "";
//     }

//     // Check full payload fits in current buffer
//     if (i + numBytes >= bytesRead) {
//         i = start_i;
//         return "";
//     }

//     // Decode payload: each ASCII char is stored in two bytes
//     for (size_t j = 0; j < numBytes; j += 2) {
//         uint8_t b1 = static_cast<uint8_t>(buffer[++i]);
//         uint8_t b2 = static_cast<uint8_t>(buffer[++i]);

//         uint8_t high2 = (b1 >> 1) & 0x03;
//         uint8_t low6  = (b2 >> 1) & 0x3F;

//         char ch = static_cast<char>((high2 << 6) | low6);
//         decoded += ch;
//     }

//     return decoded;
// }


// string SPECIAL_CODE_WORD_READER(const char* buffer, size_t& i, size_t bytesRead)
// {
//     string decoded;
//     const size_t start_i = i;

//     // Need at least the size byte
//     if (i + 1 >= bytesRead) {
//         cerr << "Error[PIC]: Not enough bytes to read sizeByte!\n";
//         exit(1);
//     }

//     // Size (number of encoded bytes to follow)
//     uint8_t numBytes = ((static_cast<uint8_t>(buffer[++i])) >> 1) & 0x3F;
//     cout << "SPECIAL_CODE_WORD_READER: numBytes = " << unsigned(numBytes) << endl; // debug 


//     // Sanity: must fit in current buffer
//     if (i + numBytes >= bytesRead) {
//         cerr << "Error[PIC]: Not enough bytes to read special code word! Needed: "
//                   << static_cast<int>(numBytes)
//                   << ", Available: " << (bytesRead - i - 1) << "\n";
//         i = start_i;  // rollback to before size
//         exit(1);
//     }

//     // // Must be pairs (2 bytes per decoded char)
//     // if ((numBytes & 1) != 0) {
//     //     cerr << "Error[PIC]: Encoded special length is odd (" << static_cast<int>(numBytes)
//     //               << "); expected even (2 bytes/char).\n";
//     //     i = start_i;  // rollback so caller can treat this as incomplete/invalid
//     //     exit(1);
//     // }

//     // Decode pairs
//     for (size_t j = 0; j < numBytes; j += 2) {
//         uint8_t b1 = static_cast<uint8_t>(buffer[++i]);
//         uint8_t b2 = static_cast<uint8_t>(buffer[++i]);

//         // Extract middle 6 bits from each, then combine: [b1_5:0][b2_5:0]
//         uint8_t high6 = (b1 & 0b01111110) >> 1;
//         uint8_t low6  = (b2 & 0b01111110) >> 1;

//         char ch = static_cast<char>((high6 << 6) | low6);
//         decoded += ch;
//     }

//     // Success: i now points at the last payload byte
//     return decoded;
// }



string SPECIAL_CODE_WORD_READER_BYTES(vector<uint8_t> bytes)
{
    // Ensure the vector has at least one byte (the size byte)
    if (bytes.empty())
    {
        cerr << "Error: Empty byte vector!" << endl;
        return "";
    }

    // Extract the size byte and determine the number of characters
    uint8_t sizeByte = bytes[0];
    size_t numCharacters = sizeByte >> 1; // Ignore the least significant bit

    // Validate that the size matches the vector length
    if (bytes.size() != numCharacters + 1)
    {
        cerr << "Error: Byte vector size does not match encoded size!" << endl;
        return "";
    }

    string result;

    // Decode the remaining bytes
    for (size_t i = 1; i < bytes.size(); ++i)
    {
        uint8_t byte = bytes[i];
        if (i == bytes.size() - 1)
        {
            // Last byte: Right shift and ensure the least significant bit is 0
            byte = byte >> 1; // Drop the LSB
        }
        else
        {
            // Other bytes: Right shift and ensure the least significant bit was 1
            if ((byte & 0x01) != 1)
            {
                cerr << "Error: Invalid byte format!" << endl;
                return "";
            }
            byte = byte >> 1; // Drop the LSB
        }
        result += static_cast<char>(byte); // Append to the string
    }

    return result;
}

/*
'SPECIAL_CODE_GENERATOR' function:
Generate
*/

// Version 2
vector<uint8_t> SPECIAL_CODE_WORD_GENERATOR(const string& input)
{
    vector<uint8_t> result;

    uint16_t charCount = static_cast<uint16_t>(input.length());

    if (charCount > 0x0FFF) {
        cerr << "Error[PIC]: Special code word too long. "
             << "Length=" << charCount
             << ", Max=4095" << endl;
        exit(1);
    }

    uint8_t low6  = static_cast<uint8_t>(charCount & 0x3F);
    uint8_t high6 = static_cast<uint8_t>((charCount >> 6) & 0x3F);

    uint8_t countLowByte  = static_cast<uint8_t>((low6 << 1) | 0x01);   // 0|xxxxxx|1
    uint8_t countHighByte = static_cast<uint8_t>((high6 << 1) | 0x01);  // 0|xxxxxx|1

    result.push_back(countLowByte);
    result.push_back(countHighByte);

    for (size_t i = 0; i < input.length(); ++i) {
        uint8_t asciiVal = static_cast<uint8_t>(input[i]);

        uint8_t highByte = static_cast<uint8_t>(((asciiVal >> 6) & 0x03) << 1 | 0x01);
        uint8_t lowByte  = static_cast<uint8_t>((asciiVal & 0x3F) << 1);

        if (i < input.length() - 1) {
            lowByte |= 0x01;
        }

        result.push_back(highByte);
        result.push_back(lowByte);
    }

    return result;
}



// Version 1
// vector<uint8_t> SPECIAL_CODE_WORD_GENERATOR(const string &input) {
// vector<uint8_t> SPECIAL_CODE_WORD_GENERATOR(string input)
// {
//     vector<uint8_t> result;
//     uint8_t numBytes = static_cast<uint8_t>(input.length() * 2); // input.length() * 2 => each ASCII character is represented using two bytes
    
//     // Encode the first byte: MSB = 1, LSB = 1, middle 6 bits = numBytes
//     uint8_t firstByte = (0b10000001) | (numBytes << 1);
//     result.push_back(firstByte);
    
//     // Process each ASCII character into two bytes (high byte and low byte)
//     for (size_t i = 0; i < input.length(); ++i) {
//         uint8_t asciiVal = static_cast<uint8_t>(input[i]);
//         uint8_t highByte = ((asciiVal >> 6) & 0x03) << 1 | 1; // Extract top 2 bits, LSB = 1
//         uint8_t lowByte = ((asciiVal & 0x3F) << 1);           // Extract bottom 6 bits
        
//         // Set LSB of lowByte to 1 if not the last character, else set to 0
//         if (i < input.length() - 1) {
//             lowByte |= 1;
//         }
        
//         result.push_back(highByte);
//         result.push_back(lowByte);
//     }
    
//     return result;
// }

/*
'ONE_BYTE_CODE_GENERATOR' function:
Generate a 1-byte code of PIC algorithm
*/
vector<uint8_t> ONE_BYTE_CODE_GENERATOR(uint32_t input)
{
    vector<uint8_t> codeWord;

    uint8_t byte1 = Mask_Single_Byte(input);      // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte1 = Shift_Left_with_Zero_Inserted(byte1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte1);

    return codeWord;
}

/*
'TWO_BYTE_CODE_GENERATOR' function:
Generate a 2-byte code of PIC algorithm
*/
vector<uint8_t> TWO_BYTE_CODE_GENERATOR(uint32_t input)
{
    vector<uint8_t> codeWord;

    uint8_t byte1 = Mask_Single_Byte(input);     // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte1 = Shift_Left_with_One_Inserted(byte1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte1);

    uint8_t byte2 = Shift_Right_Six_Positions(input); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    byte2 = Shift_Left_with_Zero_Inserted(byte2);       // shift 'DICT_ORDER_NUM_shift' to the left by 1 position
    codeWord.push_back(byte2);

    return codeWord;
}

/*
'THREE_BYTE_CODE_GENERATOR' function:
Generate a 3-byte code of PIC algorithm
*/
vector<uint8_t> THREE_BYTE_CODE_GENERATOR(uint32_t input)
{
    vector<uint8_t> codeWord;
    uint8_t byte1, byte2, byte3;
    uint32_t input_shitf1;

    byte1 = Mask_Single_Byte(input);             // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte1 = Shift_Left_with_One_Inserted(byte1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte1);

    input_shitf1 = Shift_Right_Six_Positions(input); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    byte2 = Mask_Single_Byte(input_shitf1);            // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte2 = Shift_Left_with_One_Inserted(byte2);       // shift 'byte2' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte2);

    byte3 = Shift_Right_Six_Positions(input_shitf1); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    byte3 = Shift_Left_with_Zero_Inserted(byte3);      // shift 'DICT_ORDER_NUM_shift' to the left by 1 position
    codeWord.push_back(byte3);

    return codeWord;
}

/*
'FOUR_BYTE_CODE_GENERATOR' function:
Generate a 4-byte code of PIC algorithm
*/
vector<uint8_t> FOUR_BYTE_CODE_GENERATOR(uint32_t input)
{
    vector<uint8_t> codeWord;
    uint8_t byte1, byte2, byte3, byte4;
    uint32_t input_shift1, input_shitf2;

    byte1 = Mask_Single_Byte(input);             // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte1 = Shift_Left_with_One_Inserted(byte1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte1);

    input_shift1 = Shift_Right_Six_Positions(input); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    byte2 = Mask_Single_Byte(input_shift1);            // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte2 = Shift_Left_with_One_Inserted(byte2);       // shift 'byte2' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte2);

    input_shitf2 = Shift_Right_Six_Positions(input_shift1); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    byte3 = Mask_Single_Byte(input_shitf2); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    byte3 = Shift_Left_with_One_Inserted(byte3);      // shift 'DICT_ORDER_NUM_shift' to the left by 1 position
    codeWord.push_back(byte3);

    byte4 = Shift_Right_Six_Positions(input_shitf2); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    byte4 = Shift_Left_with_Zero_Inserted(byte4);      // shift 'DICT_ORDER_NUM_shift' to the left by 1 position
    codeWord.push_back(byte4);

    return codeWord;
}

// To mask the least significant byte
uint8_t Mask_Single_Byte(uint32_t number)
{
    return MASK_BYTE & number;
}

// Shift a number to the left by one position,
// and insert '1' as the LSbit.
uint32_t Shift_Left_with_One_Inserted(uint32_t number)
{
    return number << 1 | (0x1);
}

// Shift a number to the left by one position,
// and insert '0' as the LSbit.
uint32_t Shift_Left_with_Zero_Inserted(uint32_t number)
{
    return number << 1;
}

uint32_t Shift_Right_Six_Positions(uint32_t number)
{
    return number >> 6;
}

uint32_t Shift_Right_Seven_Positions(uint32_t number)
{
    return number >> 7;
}

// Check if the least significant bit (LSb) is one.
// If LSb is '1', then there is another byte code in the sequence.
// This function is used in the decompression process.
uint8_t Next_Byte_Available(uint8_t number)
{
    // return number & 1; // return one or zero.
    return number & (0x1); // return one or zero: mask it with the LSb
}

/*
A function to check ending of strings with Punctuation characters
'\0' --> represenets a null character
*/
char checkStringEndsWithPunctuation(const string &str)
{
    // Check if the string is empty
    if (str.empty())
    {
        return '\0'; // Null character for empty string
    }

    // Get the last character of the string
    char lastChar = str.back();

    // Check if the last character is a punctuation character
    if (ispunct(static_cast<unsigned char>(lastChar)))
    // if (isPunctModified(static_cast<unsigned char>(lastChar)))
    {
        return lastChar;
    }

    // Return '\0' if not a punctuation character
    return '\0';
}

/*
A funxtion that checks a newline character in a string
*/
bool endsWithNewline(const string &str)
{
    // Check if the string is empty
    if (str.empty())
    {
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
void checkLinesInFile(const string &filePath)
{
    ifstream file(filePath); // Open the file
    if (!file)
    {
        cerr << "Error opening file: " << filePath << endl;
        return;
    }

    string line;
    int lineNumber = 1;

    // Read the file line by line
    while (getline(file, line))
    {
        cout << "Line " << lineNumber << ": "
             << (endsWithNewline(line) ? "Ends with newline" : "Does not end with newline")
             << endl;
        lineNumber++;
    }

    file.close(); // Close the file
}

// Print the hex code of the binary file for testing.
void printBinaryFile(const string &filePath)
{
    ifstream file(filePath, ios::binary); // Open the file in binary mode
    if (!file)
    {
        cerr << "Error opening file: " << filePath << endl;
        return;
    }

    // Read the file contents into a vector of uint8_t
    vector<uint8_t> buffer((istreambuf_iterator<char>(file)), istreambuf_iterator<char>());
    file.close(); // Close the file after reading

    cout << "Binary contents of " << filePath << ":" << endl;
    for (size_t i = 0; i < buffer.size(); ++i)
    {
        // cout << bitset<8>(buffer[i]) << " ";  // Print each byte as an 8-bit binary number
        cout << hex << static_cast<int>(buffer[i]) << " "; // Print each byte as HEX number
    }
    cout << endl;
}

/*
NOTE:
It returns the number of lines-1.
Because there is no newline character '\n' at the ennd of file.
*/
uint32_t countLinesInFile(const string &filePath)
{
    ifstream file(filePath);
    if (!file)
    {
        cerr << "Error: Could not open file " << filePath << endl;
        return 0;
    }

    // Count newline characters using count and istreambuf_iterator
    size_t lineCount = count(istreambuf_iterator<char>(file),
                             istreambuf_iterator<char>(), '\n');

    file.close();
    return lineCount;
}

// **********************************
// Multi Threading Functions
// **********************************

// -------- Compression ----------
// **** Text to codeWord (Binary) File ****

// Function to merge binary files in order
void mergeBinaryFiles(const vector<string> &tempFiles, const string &outputFile)
{
    lock_guard<mutex> lock(fileMutex);
    ofstream outFile(outputFile, ios::binary);
    if (!outFile)
    {
        cerr << "Error creating merged output file: " << outputFile << endl;
        return;
    }

    for (const auto &tempFile : tempFiles)
    {
        ifstream inFile(tempFile, ios::binary);
        if (!inFile)
        {
            cerr << "Error opening temp file: " << tempFile << endl;
            continue;
        }

        outFile << inFile.rdbuf(); // Append to final output
        inFile.close();
        remove(tempFile.c_str()); // Delete and remove temporary file
    }
    outFile.close();
    cout << "Binary files merged into " << outputFile << endl;
}

// Function to split a text file into contiguous chunks and process them


// Version 3 (divide by lines)
uint8_t splitAndProcessTextFile(const string &inputFile, const string &outputFile, int numThreads)
{
    ifstream inFile(inputFile);
    if (!inFile)
    {
        cerr << "Error opening input file: " << inputFile << endl;
        return -1;
    }

    // Count total number of lines
    uint32_t totalLines = 0;
    string dummyLine;
    while (getline(inFile, dummyLine)) {
        totalLines++;
    }
    inFile.close();

    if (totalLines == 0) {
        cerr << "Empty input file." << endl;
        return -1;
    }

    // Divide lines among threads
    uint32_t linesPerThread = totalLines / numThreads;
    uint32_t remainder = totalLines % numThreads;

    vector<thread> threads;
    vector<string> tempFiles;

    uint32_t currentStartLine = 0;

    for (int i = 0; i < numThreads; i++) {
        uint32_t myLines = linesPerThread + (i < remainder ? 1 : 0);  // distribute remainder
        uint32_t myStartLine = currentStartLine;
        uint32_t myEndLine = myStartLine + myLines;

        string chunkFile = "chunk_" + to_string(i) + ".bin";
        tempFiles.push_back(chunkFile);

        // Spawn thread to process line range [myStartLine, myEndLine)
        threads.emplace_back([=]() {
            ifstream in(inputFile);
            ofstream out(chunkFile, ios::binary);

            if (!in || !out) {
                cerr << "Error opening chunk files." << endl;
                return;
            }

            string line;
            uint32_t lineNum = 0;
            while (getline(in, line)) {
                if (lineNum >= myStartLine && lineNum < myEndLine) {
                    vector<string> tokens = processLineChar(line);
                    vector<uint8_t> lineCodeWords = convertStringToCodeWord(tokens);
                    out.write(reinterpret_cast<const char*>(lineCodeWords.data()), lineCodeWords.size());
                }
                lineNum++;
                if (lineNum >= myEndLine) break;
            }

            in.close();
            out.close();
        });

        currentStartLine = myEndLine;
    }

    // Wait for threads
    for (auto &t : threads) {
        t.join();
    }

    mergeBinaryFiles(tempFiles, outputFile);
    cout << "Encoding completed and merged into " << outputFile << endl;

    return 0;
}


// -------- Decompression ----------
// **** codeWord (Binary) to Text File ****

// Function to merge text files in order
void mergeTextFiles(const vector<string> &tempFiles, const string &outputFile)
{
    lock_guard<mutex> lock(fileMutex); // Lock before merging files
    ofstream outFile(outputFile);
    if (!outFile)
    {
        cerr << "Error creating merged output file: " << outputFile << endl;
        return;
    }

    for (const auto &tempFile : tempFiles)
    {
        ifstream inFile(tempFile);
        if (!inFile)
        {
            cerr << "Error opening temp file: " << tempFile << endl;
            continue;
        }

        outFile << inFile.rdbuf(); // Append to final output
        inFile.close();
        remove(tempFile.c_str()); // Delete and remove temporary file
    }
    outFile.close();
    cout << "Text files merged into " << outputFile << endl;
}

// Function to split a binary file into chunks and process them

// Version 1
uint8_t splitAndProcessBinaryFile(const string &inputFile, const string &outputFile, int numThreads)
{
    ifstream inFile(inputFile, ios::binary);
    if (!inFile)
    {
        cerr << "Error opening input file: " << inputFile << endl;
        return -1;
    }

    inFile.seekg(0, ios::end);
    streampos fileSize = inFile.tellg();
    streampos chunkSize = fileSize / numThreads;

    vector<thread> threads;
    vector<string> tempFiles;
    streampos start, end;

    for (int i = 0; i < numThreads; i++)
    {
        if (i == 0)
            start = 0;
        else
            start = end;
        end = (i == numThreads - 1) ? fileSize : streampos(start + chunkSize);

        // Adjust end position to the nearest newline (0x02) boundary
        if (i != numThreads - 1)
        {
            ifstream tempFile(inputFile, ios::binary);
            tempFile.seekg(end);
            char c;
            while (tempFile.get(c))
            {
                // if (c == 0x02 || c == 0x00)
                if ((c & 0xFE) == 0x00 || (c & 0xFE) == 0x02)
                    break; // Stop at newline or space
            }
            end = tempFile.tellg();
            tempFile.close();
        }

        string chunkFile = "chunk_" + to_string(i) + ".txt";
        tempFiles.push_back(chunkFile);
        threads.emplace_back(Decompression_Function, inputFile, start, end, chunkFile);
    }

    for (auto &t : threads)
    {
        t.join();
    }

    mergeTextFiles(tempFiles, outputFile);
    cout << "Decoding completed and merged into " << outputFile << endl;

    return 0;
}

//-------------------------------------------------------------------------------


// Version 2 - Search 
uint8_t splitAndProcessBinaryFileForSearch(const string &inputFile, const string &outputFile, int numThreads, string searchString)
{
    ifstream inFile(inputFile, ios::binary);
    if (!inFile)
    {
        cerr << "Error opening input file: " << inputFile << endl;
        return -1;
    }

    inFile.seekg(0, ios::end);
    streamoff fileSize = static_cast<streamoff>(inFile.tellg());
    streamoff chunkSize = fileSize / numThreads;

    vector<thread> threads;
    streampos start = 0, end = 0;

    vector<streampos> adjustedEnds(numThreads);
    vector<uint32_t> countMatchVector(numThreads, 0);

    // First pass: calculate adjusted end boundaries to prevent overlap
    for (int i = 0; i < numThreads; i++)
    {
        streamoff roughEnd = (i == numThreads - 1) ? fileSize : (i + 1) * chunkSize;

        streampos adjustedEnd = static_cast<streampos>(roughEnd);

        if (i != numThreads - 1)
        {
            ifstream tempFile(inputFile, ios::binary);
            tempFile.seekg(adjustedEnd);
            char c;
            while (tempFile.get(c))
            {
                if (c == 0x02 || c == 0x00)
                {
                    adjustedEnd = tempFile.tellg();
                    break;
                }
            }

            tempFile.close();
        }

        adjustedEnds[i] = adjustedEnd;
    }

    // Second pass: spawn threads with safe, non-overlapping boundaries
    for (int i = 0; i < numThreads; i++)
    {
        start = (i == 0) ? static_cast<streampos>(0) : adjustedEnds[i - 1];
        end = adjustedEnds[i];

        threads.emplace_back(Lookup_Function, inputFile, start, end, searchString, i, ref(countMatchVector));
    }

    for (auto &t : threads)
    {
        t.join();
    }

    uint32_t sumAllMatch = 0;
    for (int i = 0; i < numThreads; i++)
    {
        sumAllMatch += countMatchVector[i];
        cout << "Matched count in thread " << i << " is: " << countMatchVector[i] << endl;
    }

    cout << "Total matched values = " << sumAllMatch << endl;
    //cout << "Lookup operation has been completed." << endl;

    return 0;
}



// ----------------------------------------------------------

// // Version 1 - Replace
// // Function to split a binary file into chunks and process them
uint8_t splitAndProcessBinaryFileForSearchAndReplace(
    const string &inputFile, 
    const string &outputFile, 
    int numThreads, 
    string searchString, 
    string replaceString
)
{
    ifstream inFile(inputFile, ios::binary);
    if (!inFile)
    {
        cerr << "Error opening input file: " << inputFile << endl;
        return -1;
    }

    inFile.seekg(0, ios::end);
    streampos fileSize = inFile.tellg();
    streampos chunkSize = fileSize / numThreads;

    vector<thread> threads;
    vector<string> tempFiles;
    streampos start=0, end=0;

    vector<uint32_t> countMatchVector(numThreads, 0);
    vector<char> preservedDelimiters(numThreads); // NEW

    for (int i = 0; i < numThreads; i++)
    {
        cout << "Initial value of count[" << i << "] = " << countMatchVector[i] << endl;
    }

    for (int i = 0; i < numThreads; i++)
    {
               
        start = end;
        end = (i == numThreads - 1) ? fileSize : streampos(start + chunkSize);

        // Adjust end position to the nearest newline (0x02) boundary
        if (i != numThreads - 1)
        {
            ifstream tempFile(inputFile, ios::binary);
            tempFile.seekg(end);
            char c;
            while (tempFile.get(c))
            {
                if (c == 0x02 || c == 0x00)
                    break; // Stop at newline or space
            }
            end = tempFile.tellg();
            tempFile.close();
        }

        string chunkFile = "chunk_" + to_string(i) + ".bin";
        tempFiles.push_back(chunkFile);
        threads.emplace_back(Lookup_and_Replace_Function, inputFile, start, end, chunkFile, searchString, replaceString, i, ref(countMatchVector)); // 'i' is the threadIndex

        // cout << "Matched count in thread " << i << " is: " << countMatchVector[i] << endl;
    }

    for (auto &t : threads)
    {
        t.join();
    }

    uint32_t sumAllMatch = 0;
    for (int i = 0; i < numThreads; i++) // summation of all matched values from all threads
    {
        sumAllMatch += countMatchVector[i];
        cout << "Matched count in thread " << i << " is: " << countMatchVector[i] << endl;
    }

    cout << "Total matched values = " << sumAllMatch << endl;

    mergeBinaryFiles(tempFiles, outputFile);
    cout << "Lookup completed and merged into " << outputFile << endl;
    cout << "Lookup operation has been completed." << endl;

    return 0;
}
