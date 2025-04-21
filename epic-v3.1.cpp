/*

Title: Enhanced PIC (EPIC) compression
Author: Abbas A. Fairouz
Version: 3.1
Note: multi-threaded version
Created: Apr. 8, 2025
Updated: Apr. 19, 2025

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

#include "epic-v3.1.h"

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

*/

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

// *********************************************
//            Main Function
// *********************************************
int main(int argc, char *argv[])
{
    // int main() {

    if (!(argc == 6 || argc == 7 || argc == 8) ||
        !(string(argv[2]) == "-c" || string(argv[2]) == "-d" || string(argv[2]) == "-l" || string(argv[2]) == "-r") ||
        string(argv[3]) != "-t")
    {
        cerr << "Flags:\n-c: compression\n-d: decompression\n-l: Lookup (Search)\n-r: Lookup-and-Replace (Search and Replace)\n"
             << "Usage: " << argv[0] << " <input_file> -[c,d,l,r] -t <num_threads> <output_file> [\"<search_string>\"] [\"<replace_string>\"]\n"
             << "Notes:\n"
             << "** For -l and -r flags: <search_string> is used.\n"
             << "** For -l flag: <output_file> is ignored\n"
             << "** For -r flag: <replace_string> is used\n"
             << "** For <search_string> and <replace_string>: You need to allocate them between double quotes \"\" \n"
             << endl;

        return 1;
    }

    if(string(argv[2]) == "-l" && argc != 7)
    {
        cerr << "For -l flag, you need to add the search string.\n";
    }
    if(string(argv[2]) == "-r" && argc != 8)
    {
        cerr << "For -r flag, you need to add the search string and the replace string.\n";
    }

    string inputFileName = argv[1];
    string operationMode = argv[2];
    string outputFileName = argv[5];
    string searchString = "", replaceString = "";

    if (argc == 7 || argc == 8)
        searchString = argv[6];

    if (argc == 8)
        replaceString = argv[7];

    int numThreads = 0;

    try
    {
        numThreads = stoi(argv[4]);
        if (numThreads <= 0)
            throw invalid_argument("Number of threads must be positive");
    }
    catch (const invalid_argument &e)
    {
        cerr << "Invalid thread count: " << argv[4] << endl;
        return 1;
    }

    // Record the start time
    auto start = high_resolution_clock::now();

    uint32_t numberOfWords = countLinesInFile(dictFilename);
    cout << "Number of lines in the dictionary file: " << numberOfWords << endl;

    dictMapCodeArray = new string[numberOfWords + 10]; // add an extra spaces

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
            cout << "The compression function is successful." << endl;
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

        if (splitAndProcessBinaryFile(inputFileName, outputFileName, numThreads) == 0)
            cout << "The decompression function is successful." << endl;
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
    cout << "Number of special codeWords = " << specialCodeWordCounter << endl;

    return 0;
} // main function

/*
--------------------------
    OTHER FUNCTIONS
--------------------------
*/

// Abbas Reached here ...
/*

"Lookup_and_Replace_Function"

I need to copy the logic from the "Lookup_Function"

*/

// ------------------------------------------------------
// ***** Lookup_and_Replace_Function ***********

// // // Version 3
uint32_t Lookup_and_Replace_Function(
    const string &inputFileNameBin,
    streampos start,
    streampos end,
    const string &outputFileNameBin,
    string searchString,
    string replaceString,
    int threadIndex,
    vector<uint32_t> &results,
    char preservedDelimiter)
{
    ifstream inFile(inputFileNameBin, ios::binary);
    ofstream outFile(outputFileNameBin, ios::binary | ios::app);
    if (!inFile || !outFile)
    {
        cerr << "Error opening files in thread " << threadIndex << endl;
        return -1;
    }

    inFile.seekg(start);
    const size_t bufferSize = 4096;
    char buffer[bufferSize];

    vector<uint8_t> lineCodeWords = convertSearchStringToCodeWord(processLineChar(searchString));
    vector<uint8_t> replaceCodeWords = convertSearchStringToCodeWord(processLineChar(replaceString));

    size_t lineCodeWordsSize = lineCodeWords.size();
    uint32_t matchCount = 0;
    size_t byteIndex = 0;
    vector<uint8_t> tmpCodeWord;
    streamoff currentOffset = 0;

    while (start + currentOffset < end && inFile)
    {
        size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - (start + currentOffset)));
        inFile.read(buffer, bytesToRead);
        size_t bytesRead = inFile.gcount();

        for (size_t i = 0; i < bytesRead && start + currentOffset < end; ++i, ++currentOffset)
        {
            uint8_t byte = static_cast<uint8_t>(buffer[i]);

            if (byte == (Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE)) && byte != lineCodeWords[byteIndex])
            {
                outFile.put(static_cast<char>(byte));
                if (++i < bytesRead)
                {
                    uint8_t skipLength = static_cast<uint8_t>(buffer[i]);
                    outFile.put(static_cast<char>(skipLength));
                    ++currentOffset;
                    for (uint8_t j = 0; j < skipLength && i + 1 < bytesRead; ++j, ++i, ++currentOffset)
                    {
                        outFile.put(buffer[i + 1]);
                    }
                }
                byteIndex = 0;
                tmpCodeWord.clear();
            }
            else
            {
                if (byte == lineCodeWords[byteIndex])
                {
                    tmpCodeWord.push_back(byte);
                    byteIndex++;
                    if (byteIndex == lineCodeWordsSize)
                    {
                        outFile.write(reinterpret_cast<const char*>(replaceCodeWords.data()), replaceCodeWords.size());
                        matchCount++;
                        byteIndex = 0;
                        tmpCodeWord.clear();
                    }
                }
                else
                {
                    if (!tmpCodeWord.empty())
                    {
                        outFile.write(reinterpret_cast<const char*>(tmpCodeWord.data()), tmpCodeWord.size());
                        tmpCodeWord.clear();
                    }
                    outFile.put(static_cast<char>(byte));
                    byteIndex = 0;
                }
            }
        }
    }

    // Write preserved delimiter only if this is not already present as the last byte
    if (!outFile.fail() && preservedDelimiter != 0)
    {
        // outFile.put(preservedDelimiter); // tmp commented - Abbas
    }

    inFile.close();
    outFile.close();

    results[threadIndex] = matchCount;
    return 0;
}
 


// // Version 1 (original, but slow)
// uint32_t Lookup_and_Replace_Function(
//     const string& inputFileNameBin, 
//     streampos start, 
//     streampos end, 
//     const string& outputFileNameBin, 
//     string searchString, 
//     string replaceString, 
//     int threadIndex, 
//     vector<uint32_t>& results,
//     char preservedDelimiter // NEW
//     )
// {

//     // Compress the searchString text to code-words
//     vector<string> tokens, replaceTokens;
//     vector<uint8_t> lineCodeWords, replaceCodeWords;
//     uint16_t lineCodeWordsSize, replaceCodeWordsSize;   

//     // Process the searchString
//     tokens = processLineChar(searchString);                // Process the line
//     lineCodeWords = convertSearchStringToCodeWord(tokens); // Generate the code words for the search string
//     lineCodeWordsSize = static_cast<uint16_t>(lineCodeWords.size());
//     uint16_t byteIndex = 0; // index of the searchString byteCode

//     // Process the searchString
//     replaceTokens = processLineChar(replaceString);                // Process the line
//     replaceCodeWords = convertSearchStringToCodeWord(replaceTokens); // Generate the code words for the search string
//     replaceCodeWordsSize = static_cast<uint16_t>(replaceCodeWords.size());

//     // -- for debug --
//     //cout << "Code-word size: " << lineCodeWordsSize << endl;

//     // Compare the searchString code-words over the compressed file
//     uint8_t tmpSerial = 0;

//     // Open the file in binary mode
//     ifstream inFile(inputFileNameBin, ios::binary | ios::app);
//     if (!inFile)
//     {
//         cerr << "Error: Could not open file " << inputFileNameBin << " for reading." << endl;
//         return -1;
//     }

//     // Set the file pointer to the start of this thread's chunk
//     inFile.seekg(start); // Move file pointer to start position

//      // For output file
//      const char *buffer;
//      size_t bufferSize;

//     ofstream outFile(outputFileNameBin, ios::app); // Open in append mode
//     if (!outFile)
//     {
//         cerr << "Error: Could not open file " << outputFileNameText << " for appending." << endl;
//         return -1;
//     }

//     // Lock before writing to the output file
//     //lock_guard<mutex> lock(fileMutex);
//     uint32_t matchCount = 0;
//     uint32_t byteCount = 0;
//     uint32_t toSkip = 0;


//     char byte;
//     size_t byteSize = sizeof(byte);
//     //cout << "Reading file byte by byte:" << endl;

//     vector<uint8_t> tmpCodeWord;

//     // Read the file byte by byte
//     // while (inFile.read(&byte, 1)) {
//     while (inFile.peek() != EOF && inFile.tellg() < end) // peek() -> checks the next character without advancing the file pointer.
//     {                     
//         inFile.get(byte); // reads the next byte

//         // -- for debug -- 
//         byteCount++;

//         tmpSerial = static_cast<uint8_t>(byte);

//         // Handle special code-word, and if it is not matching the searchString
//         if(tmpSerial == (Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE)) && tmpSerial != lineCodeWords[byteIndex])
//         {
            
//             outFile.write(reinterpret_cast<const char*>(&byte), sizeof(byte)); // write the NEXT_SPECIAL_CODE

//             inFile.get(byte); // read the number of ASCII character in the special code-word to skip them
//             toSkip = static_cast<uint32_t>(byte); // cast the read byte to uint32_t
//             outFile.write(reinterpret_cast<const char*>(&byte), sizeof(byte)); // write the number of ASCII character in the special code-word
            
//             //inFile.ignore(toSkip); // skip all ASCII characters (bytes) in the special code-word
//             for(int i=0; i<toSkip; i++)
//             {
//                 inFile.get(byte); // read the ASCII character of the special code-word
//                 outFile.write(reinterpret_cast<const char*>(&byte), sizeof(byte)); // write the ASCII character of the special code-word
//             }

//             // // -- for debug -- 
//             // byteCount += toSkip + 1;
//             // cout << "Skipped Special Code, at byteCount = " << byteCount << endl;

//             byteIndex = 0;
//         }
//         else
//         {
//             if (tmpSerial == lineCodeWords[byteIndex]) // check the searchString byte with the corresponding byte in the compressed file
//             {
//                 byteIndex++;

//                 // // -- for debug --
//                 // cout << "Partial match, byteCount = " << byteCount << endl;

//                 if (byteIndex == lineCodeWordsSize) // reset byteIndex if it exeeds the size of the searchString byteCode
//                 {
//                     byteIndex = 0;
//                     matchCount++;
                    
//                     // // -- for debug --
//                     // cout << "Match in byteCount = " << byteCount << endl;
//                     // cout << "The byte value in the file is: " << static_cast<uint32_t>(tmpSerial) << endl;

//                     buffer = reinterpret_cast<const char *>(replaceCodeWords.data());
//                     bufferSize = replaceCodeWords.size();
//                     outFile.write(buffer, bufferSize);
//                 }

                
//             }
//             else if(byteIndex != 0)
//             {
//                 tmpCodeWord.push_back(byte);

//                 buffer = reinterpret_cast<const char *>(tmpCodeWord.data());
//                 bufferSize = tmpCodeWord.size();
//                 outFile.write(buffer, bufferSize);

//                 byteIndex = 0;
//                 tmpCodeWord.clear();
//             }
//             else
//             {
//                 byteIndex = 0;
//                 tmpCodeWord.clear();

//                 outFile.write(reinterpret_cast<const char*>(&byte), sizeof(byte)); // write the unmatched code-word
//             }

            
//         }

//         if (inFile.tellg() >= end)
//         {
//             break; // break after its own part of the binary file
//         }

//     } // while loop: read byte-by-byte

//     if (inFile.eof())
//     {
//         cerr << "End of file reached." << endl;
//     }
//     else if (inFile.fail())
//     {
//         cerr << "Error: Failed to read the file." << endl;
//     }

//     //cout << "byteCount reached = " << byteCount << endl;

//     outFile.write(reinterpret_cast<const char*>(&preservedDelimiter), sizeof(preservedDelimiter)); // NEW
//     inFile.close();

//     results[threadIndex] = matchCount; // return the matched values found in the compressed file

//     // // -- for debug --
//     // cout << "Lookup Function: Match count = " << matchCount << endl;

//     return 0;
// }



// // Version 4
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
//     vector<string> tokens = processLineChar(searchString);
//     vector<uint8_t> lineCodeWords = convertSearchStringToCodeWord(tokens);
//     uint16_t lineCodeWordsSize = static_cast<uint16_t>(lineCodeWords.size());

//     uint8_t tmpSerial = 0;
//     uint32_t toSkip = 0;

//     while (currentPos < end && inFile)
//     {
//         size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - currentPos));
//         inFile.read(buffer, bytesToRead);
//         size_t bytesRead = inFile.gcount();

//         // --- Abbas ---
        
//         if(bytesToRead == bufferSize){
//             //for(int i = bufferSize-1; i >= 0; i--)
//             for(int i=bytesToRead-1; i>=0; i--)
//             {
//                 if( buffer[i] == 0x0 || buffer[i] == 0x2 || buffer[i] == 0x4 || buffer[i] == 0x6)
//                 {
//                     bytesRead = i+1;
//                     break;
//                 }
//             }
//         }

//         // -------------

//         for (size_t i = 0; (i < bytesRead) && (currentPos < end); ++i, ++currentPos)
//         {
//             tmpSerial = static_cast<uint8_t>(buffer[i]);

//             if (tmpSerial == (Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE)) && tmpSerial != lineCodeWords[byteIndex])
//             {
//                 if (i + 1 < bytesRead)
//                 {
//                     toSkip = static_cast<uint8_t>(buffer[i + 1]);
//                     i += toSkip + 1;
//                     currentPos += toSkip + 1;
//                     byteIndex = 0;
//                 }
//                 else
//                 {
//                     inFile.read(buffer, 1);
//                     toSkip = static_cast<uint8_t>(buffer[0]);
//                     inFile.ignore(toSkip);
//                     currentPos = inFile.tellg();
//                     byteIndex = 0;
//                     break;
//                 }
//             }
//             else
//             {
//                 if (tmpSerial == lineCodeWords[byteIndex])
//                 {
//                     byteIndex++;
//                 }
//                 else
//                 {
//                     byteIndex = 0;
//                 }

//                 if (byteIndex == lineCodeWordsSize)
//                 {
//                     byteIndex = 0;
//                     matchCount++;

//                     // -- for debug --
//                     cout << "Match found in byte number = " << << endl;
//                 }
//             }
//         }
//     }

//     inFile.close();
//     results[threadIndex] = matchCount;
//     return 0;
// }

// ------------------------------------------------------
// ***** Lookup_Function ***********


// Version 3
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
    vector<string> tokens = processLineChar(searchString);
    vector<uint8_t> lineCodeWords = convertSearchStringToCodeWord(tokens);
    uint16_t lineCodeWordsSize = static_cast<uint16_t>(lineCodeWords.size());

    uint8_t tmpSerial = 0;
    uint32_t toSkip = 0;

    while (currentPos < end && inFile)
    {
        size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - currentPos));
        inFile.read(buffer, bytesToRead);
        size_t bytesRead = inFile.gcount();

        for (size_t i = 0; i < bytesRead && currentPos < end; ++i, ++currentPos)
        {
            tmpSerial = static_cast<uint8_t>(buffer[i]);
            uint16_t nextByteCode = tmpSerial % 2;

            if (tmpSerial == (Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE)) && tmpSerial != lineCodeWords[byteIndex])
            {
                if (i + 1 < bytesRead)
                {
                    toSkip = static_cast<uint8_t>(buffer[i + 1]);
                    i += toSkip + 1;
                    currentPos += toSkip + 1;
                    byteIndex = 0;
                }
                else
                {
                    inFile.read(buffer, 1);
                    toSkip = static_cast<uint8_t>(buffer[0]);
                    inFile.ignore(toSkip);
                    currentPos = inFile.tellg();
                    byteIndex = 0;
                    break;
                }
            }
            else
            {
                if (tmpSerial == lineCodeWords[byteIndex])
                {
                    byteIndex++;
                }
                // else
                // {
                //     byteIndex = 0;
                // }
                else if(nextByteCode == 1)
                {
                    // toSkip = static_cast<uint8_t>(buffer[i + 1]);
                    // i += toSkip + 1;
                    // currentPos += toSkip + 1;
                    do{
                        i++; currentPos++; // skip he next byte of the code-word chain
                        nextByteCode = static_cast<uint16_t>(buffer[i]) % 2;
                    } while(nextByteCode==1);
                    
                    byteIndex = 0;
                }
                if (byteIndex == lineCodeWordsSize)
                {
                    byteIndex = 0;
                    matchCount++;
                }
            }
        }
    }

    inFile.close();
    results[threadIndex] = matchCount;
    return 0;
}


// // Version 1 (original, but slow)
// uint32_t Lookup_Function(
//     const string &inputFileNameBin,
//     streampos start,
//     streampos end,
//     string searchString,
//     int threadIndex,
//     vector<uint32_t> &results)
// {

//     // Compress the searchString text to code-words
//     vector<string> tokens;
//     vector<uint8_t> lineCodeWords;
//     uint16_t lineCodeWordsSize;

//     // Process the current line
//     tokens = processLineChar(searchString);                // Process the line
//     lineCodeWords = convertSearchStringToCodeWord(tokens); // Generate the code words for the search string
//     lineCodeWordsSize = static_cast<uint16_t>(lineCodeWords.size());
//     uint16_t byteIndex = 0; // index of the searchString byteCode

//     // -- for debug --
//     cout << "Code-word size: " << lineCodeWordsSize << endl;
//     cout << "Code-word is: ";
//     for(int i=0; i<lineCodeWordsSize; i++)
//         cout << static_cast<uint16_t>(lineCodeWords[i]) << " ";
//     cout << endl;

//     // Compare the searchString code-words over the compressed file
//     uint8_t tmpSerial = 0;

//     // Open the file in binary mode
//     ifstream inFile(inputFileNameBin, ios::binary);
//     if (!inFile)
//     {
//         cerr << "Error: Could not open file " << inputFileNameBin << " for reading." << endl;
//         return -1;
//     }

//     // Set the file pointer to the start of this thread's chunk
//     inFile.seekg(start); // Move file pointer to start position

//     // Lock before writing to the output file
//     //lock_guard<mutex> lock(fileMutex);
//     uint32_t matchCount = 0;
//     uint32_t byteCount = 0;
//     uint32_t toSkip = 0;


//     char byte;
//     //cout << "Reading file byte by byte:" << endl;

//     // Read the file byte by byte
//     // while (inFile.read(&byte, 1)) {
//     while (inFile.peek() != EOF && inFile.tellg() < end) // peek() -> checks the next character without advancing the file pointer.
//     {                     
//         inFile.get(byte); // reads the next byte

//         // -- for debug -- 
//         byteCount++;

//         tmpSerial = static_cast<uint8_t>(byte);

//         if(tmpSerial == (Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE)) && tmpSerial != lineCodeWords[byteIndex])
//         //if((tmpSerial >> 1) == NEXT_SPECIAL_CODE)
//         {
//             inFile.get(byte); // read the number of ASCII character in the special code-word to skip them
//             toSkip = static_cast<uint32_t>(byte); // cast the read byte to uint32_t
//             inFile.ignore(toSkip); // skip all ASCII characters (bytes) in the special code-word

//             // -- for debug -- 
//             byteCount += toSkip + 1;
//             cout << "Skipped Special Code, at byteCount = " << byteCount << endl;

//             byteIndex = 0;
//         }
//         else
//         {
//             if (tmpSerial == lineCodeWords[byteIndex]) // check the searchString byte with the corresponding byte in the compressed file
//             {
//                 byteIndex++;

//                 // -- for debug --
//                 cout << "Partial match, byteCount = " << byteCount << endl;
//                 cout << "byteIndex = " << byteIndex << endl;
//             }
//             else if(tmpSerial%2 == 1)
//             {
//                 uint16_t nextByteCode = 1;
//                 while(nextByteCode==1)
//                 {
//                     inFile.get(byte); // skip the next byte in the code-word chain
//                     nextByteCode = static_cast<uint16_t>(byte) % 2;
//                 }
//                 byteIndex = 0;
//             }

//             if (byteIndex == lineCodeWordsSize) // reset byteIndex if it exeeds the size of the searchString byteCode
//             {
//                 cout << "byteIndex = " << byteIndex << ", lineCodeWordsSize = " << lineCodeWordsSize << endl;

//                 byteIndex = 0;
//                 matchCount++;
                
//                 // -- for debug --
//                 cout << "Match in byteCount = " << byteCount << endl;
//                 cout << "The byte value in the file is: " << static_cast<uint32_t>(tmpSerial) << endl;
//             }
//         }

//         if (inFile.tellg() >= end)
//         {
//             break; // break after its own part of the binary file
//         }

//     } // while loop: read byte-by-byte

//     if (inFile.eof())
//     {
//         cerr << "End of file reached." << endl;
//     }
//     else if (inFile.fail())
//     {
//         cerr << "Error: Failed to read the file." << endl;
//     }

//     //cout << "byteCount reached = " << byteCount << endl;
//     inFile.close();

//     results[threadIndex] = matchCount; // return the matched values found in the compressed file

//     // // -- for debug --
//     // cout << "Lookup Function: Match count = " << matchCount << endl;

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

// Function to read a file line by line and process each line
// uint8_t Compression_Function() {
uint8_t Compression_Function(
    const string &inputFileText,
    streampos start,
    streampos end,
    const string &outputFileBin)
{

    ifstream inFile(inputFileText); // Open the file
    if (!inFile)
    {
        cerr << "Error opening file: " << inputFileNameText << endl;
        return -1;
    }

    // Set the file pointer to the start of this thread's chunk
    inFile.seekg(start); // Move file pointer to start position

    // Adjust the start position to the nearest newline
    if (start > 0)
    { // Not the first chunk
        string temp;
        getline(inFile, temp); // Skip the partial line
    }

    // // Recalculate end within this thread to avoid race conditions
    // streampos adjustedEnd = end;
    // if (inFile.tellg() < end) {
    //     inFile.seekg(end);
    //     string temp;
    //     getline(inFile, temp); // Move past partial line
    //     adjustedEnd = inFile.tellg(); // Adjusted to the next newline
    // }

    lock_guard<mutex> lock(fileMutex);
    // Open the output file in binary mode and in append mode
    ofstream outFile(outputFileBin, ios::binary | ios::app);
    if (!outFile)
    {
        cerr << "Error: Could not open the file." << endl;
        return 1;
    }

    vector<string> tokens;
    vector<uint8_t> lineCodeWords;
    const char *buffer;
    size_t bufferSize;
    string line;

    //*** Method 1 ***
    string currentLine, nextLine;

    // Read the first line before entering the loop
    // if (inFile.tellg() < end && getline(inFile, currentLine)) {
    if (getline(inFile, currentLine))
    {
        while (inFile.tellg() <= end)
        { // Check if the next position would exceed 'end'
            // Peek ahead to check for the next line
            if (getline(inFile, nextLine))
            {
                // Process the current line
                tokens = processLineChar(currentLine);           // Process the line
                lineCodeWords = convertStringToCodeWord(tokens); // Generate the code words

                buffer = reinterpret_cast<const char *>(lineCodeWords.data());
                bufferSize = lineCodeWords.size();
                outFile.write(buffer, bufferSize);

                // Move to the next line
                currentLine = nextLine;
            }
            else
            {
                // Handle the last line (no next line available)
                tokens = processLineChar(currentLine);           // Process the line
                lineCodeWords = convertStringToCodeWord(tokens); // Generate the code words

                lineCodeWords.pop_back(); // remove the last new line at the end of file
                buffer = reinterpret_cast<const char *>(lineCodeWords.data());
                bufferSize = lineCodeWords.size();
                outFile.write(buffer, bufferSize);

                // Break out of the loop after processing the last line
                break;
            }
        }
    }

    inFile.close();  // Close the input file
    outFile.close(); // Close the output file

    return 0;
}

/*
-- Compression Function --
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
            if (ch == '\'' || (i + 2 <= line.size() && line.substr(i, 3) == "’"))
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
    2) New line             => 0x1 --> in EPIC format, shift left by 1 => 0x2
    3) Next Capital letter  => 0x2 --> in EPIC format, shift left by 1 => 0x4
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
                else
                {
                    // Add word to the map with the current serial number
                    // dictMapWord[word] = serial;
                }
            }

            // Push the byteCodes to the lineCodeWords vector
            lineCodeWords.insert(lineCodeWords.end(), byteCodes.begin(), byteCodes.end());
            byteCodes.clear();

        } // end of else for special codeWords

    } // end of the for loop

    lineCodeWords.push_back(Shift_Left_with_Zero_Inserted(NEW_LINE_CODE)); // new line codeWord

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
    2) New line             => 0x1 --> in EPIC format, shift left by 1 => 0x2
    3) Next Capital letter  => 0x2 --> in EPIC format, shift left by 1 => 0x4
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
                else
                {
                    // Add word to the map with the current serial number
                    // dictMapWord[word] = serial;
                }
            }

            // Push the byteCodes to the lineCodeWords vector
            lineCodeWords.insert(lineCodeWords.end(), byteCodes.begin(), byteCodes.end());
            byteCodes.clear();

        } // end of else for special codeWords

    } // end of the for loop

    // We don't need to add a newline for the search string.
    // lineCodeWords.push_back(Shift_Left_with_Zero_Inserted(NEW_LINE_CODE)); // new line codeWord

    return lineCodeWords;
}

uint8_t Decompression_Function(const string &inputFileNameBin, streampos start, streampos end, const string &outputFileNameText)
{
    vector<uint8_t> byteCodes;
    uint32_t tmpSerial = 0, finalSerial = 0;
    string word;

    // Open the file in binary mode
    ifstream inFile(inputFileNameBin, ios::binary);
    if (!inFile)
    {
        cerr << "Error: Could not open file " << inputFileNameBin << " for reading." << endl;
        return -1;
    }

    // Set the file pointer to the start of this thread's chunk
    inFile.seekg(start); // Move file pointer to start position

    // Lock before writing to the output file
    lock_guard<mutex> lock(fileMutex);

    ofstream outFile(outputFileNameText, ios::app); // Open in append mode
    if (!outFile)
    {
        cerr << "Error: Could not open file " << outputFileNameText << " for appending." << endl;
        return -1;
    }

    uint8_t nextByte;     // Variable to store each byte
    size_t byteIndex = 0; // Optional: Index of the byte being read
    bool NEXT_CAP = false;
    int serial = 0;
    uint32_t count = 0;

    char byte;
    //cout << "Reading file byte by byte:" << endl;

    // Read the file byte by byte
    // while (inFile.read(&byte, 1)) {
    while (inFile.peek() != EOF && inFile.tellg() < end)
    {                     // peek() -> checks the next character without advancing the file pointer.
        inFile.get(byte); // reads the next byte

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

        if (nextByte == 0)
        {
            // Finalize the concatenated serial number
            finalSerial = static_cast<uint32_t>(concatenateBytes(finalSerial, tmpSerial, count));

            /*
            ----------
            Note:
            The variable "count" is used to count the number of ones
            realized in the codeWord while reading each byte separately.
            ----------
            */
            if (count == 1) // TWO CODE
                finalSerial += TWO_BYTE_OFFSET;
            else if (count == 2) // THREE CODE
                finalSerial += THREE_BYTE_OFFSET;

            if (finalSerial == SPACE_CODE)
            { // space
                outFile << " ";
            }
            else if (finalSerial == NEW_LINE_CODE)
            { // newline
                // cout << "NEW LINE\n";
                outFile << "\n";
            }
            else if (finalSerial == NEXT_CAPITAL_CODE)
            { // next uppercase (capital letter) character
                // cout << "NEXT CAP\n";
                NEXT_CAP = true;
            }
            else if (finalSerial == NEXT_SPECIAL_CODE)
            { // next special codeWord
                // next special codeWord bytes ...
                // To-Do ...
                word = SPECIAL_CODE_WORD_READER(&inFile);
                outFile << word;
            }
            else
            { // check the dictionary hash table

                // Check the word in the dictionary hash table
                // word = dictMapCode[finalSerial];

                // Check the word in the dictionary array of words
                word = dictMapCodeArray[finalSerial];

                if (NEXT_CAP)
                {
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
        else
        { // if (nextByte==1)
            // finalSerial = (finalSerial << 7) | tmpSerial;
            finalSerial = concatenateBytes(finalSerial, tmpSerial, count);
            count++;
        }

        byteIndex++;

        if (inFile.tellg() >= end)
            break; // break after its own part of the binary file
    }

    if (inFile.eof())
    {
        cerr << "End of file reached." << endl;
    }
    else if (inFile.fail())
    {
        cerr << "Error: Failed to read the file." << endl;
    }

    inFile.close();
    outFile.close();

    return 0;
}

uint32_t concatenateBytes(uint32_t final, uint32_t tmp, uint8_t count)
{
    // if (count == 0)
    //     return tmp;
    // else
    return final | (tmp << (7 * count));
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

string SPECIAL_CODE_WORD_READER(ifstream *filePtr)
{
    if (!filePtr || !filePtr->is_open())
    {
        cerr << "Error: Invalid or unopened file pointer!" << endl;
        return "";
    }

    // Read the size byte (first byte)
    uint8_t sizeByte;
    filePtr->read(reinterpret_cast<char *>(&sizeByte), sizeof(uint8_t));
    if (filePtr->eof())
    {
        cerr << "Error: File is empty or invalid!" << endl;
        return "";
    }

    // Determine the number of characters
    // size_t numCharacters = sizeByte >> 1; // Ignore the least significant bit
    size_t numCharacters = sizeByte;

    // Read the remaining bytes (numCharacters bytes)
    vector<uint8_t> bytes(numCharacters);
    filePtr->read(reinterpret_cast<char *>(bytes.data()), numCharacters);

    // Check if the number of bytes read matches the expected number
    if (filePtr->gcount() != static_cast<streamsize>(numCharacters))
    {
        cerr << "Error: File does not contain the expected number of bytes!" << endl;
        return "";
    }

    // Decode the bytes into a string
    string result;
    for (size_t i = 0; i < bytes.size(); ++i)
    {
        uint8_t byte = bytes[i];
        // if (i == bytes.size() - 1) {
        //     // Last byte: Right shift and ensure the least significant bit is 0
        //     // byte = byte >> 1; // Drop the LSB
        // } else {
        //     // Other bytes: Right shift and ensure the least significant bit was 1
        //     if ((byte & 0x01) != 1) {
        //         cerr << "Error: Invalid byte format!" << endl;
        //         return "";
        //     }
        //     // byte = byte >> 1; // Drop the LSB
        // }
        // byte = byte >> 1; // Drop the LSB
        result += static_cast<char>(byte); // Append to the string
    }

    return result;
}

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
// vector<uint8_t> SPECIAL_CODE_WORD_GENERATOR(const string &input) {
vector<uint8_t> SPECIAL_CODE_WORD_GENERATOR(string input)
{
    vector<uint8_t> result;

    // Calculate the number of upcoming bytes (excluding the first byte)
    uint8_t sizeByte = input.length();
    // sizeByte = (sizeByte << 1) | 1; // Shift left by 1 and set the least significant bit to 1
    result.push_back(sizeByte); // Add the size byte to the vector

    // Process each character in the string
    for (size_t i = 0; i < input.length(); ++i)
    {
        uint8_t byte = static_cast<uint8_t>(input[i]);
        // if (i == input.length() - 1) {
        //     // For the last byte, shift left by 1 and set the least significant bit to 0
        //     byte = (byte << 1) & 0xFE; // Ensure the least significant bit is 0
        // } else {
        //     // For other bytes, shift left by 1 and set the least significant bit to 1
        //     byte = (byte << 1) | 0x01; // Ensure the least significant bit is 1
        // }
        result.push_back(byte);
    }

    return result;
}

/*
'ONE_BYTE_CODE_GENERATOR' function:
Generate a 1-byte code of EPIC algorithm
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
Generate a 2-byte code of EPIC algorithm
*/
vector<uint8_t> TWO_BYTE_CODE_GENERATOR(uint32_t input)
{
    vector<uint8_t> codeWord;

    uint8_t byte1 = Mask_Single_Byte(input);     // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte1 = Shift_Left_with_One_Inserted(byte1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte1);

    uint8_t byte2 = Shift_Right_Seven_Positions(input); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    byte2 = Shift_Left_with_Zero_Inserted(byte2);       // shift 'DICT_ORDER_NUM_shift' to the left by 1 position
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
    uint8_t byte1, byte2, byte3;
    uint32_t input_shitf1;

    byte1 = Mask_Single_Byte(input);             // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte1 = Shift_Left_with_One_Inserted(byte1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte1);

    input_shitf1 = Shift_Right_Seven_Positions(input); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    byte2 = Mask_Single_Byte(input_shitf1);            // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte2 = Shift_Left_with_One_Inserted(byte2);       // shift 'byte2' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte2);

    byte3 = Shift_Right_Seven_Positions(input_shitf1); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    byte3 = Shift_Left_with_Zero_Inserted(byte3);      // shift 'DICT_ORDER_NUM_shift' to the left by 1 position
    codeWord.push_back(byte3);

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

uint32_t Shift_Right_Seven_Positions(uint32_t number)
{
    return number >> 7;
}

// Check if the least significant bit (LSb) is one.
// If LSb is '1', then there is another byte code in the sequence.
// This function is used in the decompression process.
uint8_t Next_Byte_Available(uint8_t number)
{
    // return number % 2; // return one or zero.
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

    // Count newline characters using std::count and istreambuf_iterator
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
        std::remove(tempFile.c_str()); // Delete and remove temporary file
    }
    outFile.close();
    cout << "Binary files merged into " << outputFile << endl;
}

// Function to split a text file into contiguous chunks and process them
uint8_t splitAndProcessTextFile(const string &inputFile, const string &outputFile, int numThreads)
{

    ifstream inFile(inputFile);
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
        
        start = i * chunkSize;
        end = (i == numThreads - 1) ? fileSize : streampos((i + 1) * chunkSize);

        // if (i == 0)
        //     start = 0;
        // else
        //     start = end;
        // end = (i == numThreads - 1) ? fileSize : streampos(start + chunkSize);

        // Adjust end position to the nearest newline
        if (i != numThreads - 1)
        {
            ifstream tempFile(inputFile);
            tempFile.seekg(end);
            string temp;
            getline(tempFile, temp); // Move past partial line
            end = tempFile.tellg();
            tempFile.close();
        }

        string chunkFile = "chunk_" + to_string(i) + ".bin";
        tempFiles.push_back(chunkFile);
        threads.emplace_back(Compression_Function, inputFile, start, end, chunkFile);
    }

    for (auto &t : threads)
    {
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
        std::remove(tempFile.c_str()); // Delete and remove temporary file
    }
    outFile.close();
    cout << "Text files merged into " << outputFile << endl;
}

// Function to split a binary file into chunks and process them
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
        // if (i == 0)
        //     start = 0;
        // else
        //     start = end+1;

        // // end = (i == numThreads - 1) ? fileSize : streampos((i + 1) * chunkSize); // tmp - Abbas
        // end = (i == numThreads - 1) ? fileSize : streampos((i+1) * chunkSize);

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
                if (c == 0x02 || c == 0x00)
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
        streamoff roughStart = i * chunkSize;
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
    cout << "Lookup operation has been completed." << endl;

    return 0;
}




// // Version 1  - Search 
// // Function to split a binary file into chunks and process them
// uint8_t splitAndProcessBinaryFileForSearch(const string &inputFile, const string &outputFile, int numThreads, string searchString)
// {
//     ifstream inFile(inputFile, ios::binary);
//     if (!inFile)
//     {
//         cerr << "Error opening input file: " << inputFile << endl;
//         return -1;
//     }

//     inFile.seekg(0, ios::end);
//     streampos fileSize = inFile.tellg();
//     streampos chunkSize = fileSize / numThreads;

//     vector<thread> threads;
//     // vector<string> tempFiles;
//     streampos start=0, end=0;

//     vector<uint32_t> countMatchVector(numThreads, 0);

//     for (int i = 0; i < numThreads; i++)
//     {
//         cout << "Initial value of count[" << i << "] = " << countMatchVector[i] << endl;
//     }

//     for (int i = 0; i < numThreads; i++)
//     {
//         // if (i == 0)
//         //     start = 0;
//         // else
//         //     start = end+1;

//         // // end = (i == numThreads - 1) ? fileSize : streampos((i + 1) * chunkSize); // tmp - Abbas
//         // end = (i == numThreads - 1) ? fileSize : streampos((i+1) * chunkSize);

//         // if (i == 0)
//         //     start = 0;
//         // else
//         //     start = end;
//         start = end;
//         end = (i == numThreads - 1) ? fileSize : streampos(start + chunkSize);      

//         // Adjust end position to the nearest newline (0x02) boundary
//         if (i != numThreads - 1)
//         {
//             ifstream tempFile(inputFile, ios::binary);
//             tempFile.seekg(end);
//             char c;
//             while (tempFile.get(c))
//             {
//                 if (c == 0x02 || c == 0x00)
//                     break; // Stop at newline or space
//             }
//             end = tempFile.tellg();
//             tempFile.close();
//         }

//         // string chunkFile = "chunk_" + to_string(i) + ".txt";
//         // tempFiles.push_back(chunkFile);
//         threads.emplace_back(Lookup_Function, inputFile, start, end, searchString, i, ref(countMatchVector)); // 'i' is the threadIndex

//         // cout << "Matched count in thread " << i << " is: " << countMatchVector[i] << endl;
//     }

//     for (auto &t : threads)
//     {
//         t.join();
//     }

//     uint32_t sumAllMatch = 0;
//     for (int i = 0; i < numThreads; i++) // summation of all matched values from all threads
//     {
//         sumAllMatch += countMatchVector[i];
//         cout << "Matched count in thread " << i << " is: " << countMatchVector[i] << endl;
//     }

//     cout << "Total matched values = " << sumAllMatch << endl;

//     // Don't need to merge, we don't have an output file to generate
//     // mergeTextFiles(tempFiles, outputFile);
//     // cout << "Lookup completed and merged into " << outputFile << endl;
//     cout << "Lookup operation has been completed." << endl;

//     return 0;
// }


// ----------------------------------------------------------

// // Version 1 - Replace
// // Function to split a binary file into chunks and process them
// uint8_t splitAndProcessBinaryFileForSearchAndReplace(
//     const string &inputFile, 
//     const string &outputFile, 
//     int numThreads, 
//     string searchString, 
//     string replaceString
// )
// {
//     ifstream inFile(inputFile, ios::binary);
//     if (!inFile)
//     {
//         cerr << "Error opening input file: " << inputFile << endl;
//         return -1;
//     }

//     inFile.seekg(0, ios::end);
//     streampos fileSize = inFile.tellg();
//     streampos chunkSize = fileSize / numThreads;

//     vector<thread> threads;
//     vector<string> tempFiles;
//     streampos start=0, end=0;

//     vector<uint32_t> countMatchVector(numThreads, 0);
//     vector<char> preservedDelimiters(numThreads); // NEW

//     for (int i = 0; i < numThreads; i++)
//     {
//         cout << "Initial value of count[" << i << "] = " << countMatchVector[i] << endl;
//     }

//     for (int i = 0; i < numThreads; i++)
//     {
//         // if (i == 0)
//         //     start = 0;
//         // else
//         //     start = end+1;

//         // // end = (i == numThreads - 1) ? fileSize : streampos((i + 1) * chunkSize); // tmp - Abbas
//         // end = (i == numThreads - 1) ? fileSize : streampos((i+1) * chunkSize);

//         // if (i == 0)
//         //     start = 0;
//         // else
//         //     start = end;
        
//         start = end;
//         end = (i == numThreads - 1) ? fileSize : streampos(start + chunkSize);

//         // Adjust end position to the nearest newline (0x02) boundary
//         if (i != numThreads - 1)
//         {
//             ifstream tempFile(inputFile, ios::binary);
//             tempFile.seekg(end);
//             char c;
//             while (tempFile.get(c))
//             {
//                 if (c == 0x02 || c == 0x00)
//                     break; // Stop at newline or space
//             }
//             end = tempFile.tellg();
//             tempFile.close();
//         }

//         string chunkFile = "chunk_" + to_string(i) + ".bin";
//         tempFiles.push_back(chunkFile);
//         threads.emplace_back(Lookup_and_Replace_Function, inputFile, start, end, chunkFile, searchString, replaceString, i, ref(countMatchVector)); // 'i' is the threadIndex

//         // cout << "Matched count in thread " << i << " is: " << countMatchVector[i] << endl;
//     }

//     for (auto &t : threads)
//     {
//         t.join();
//     }

//     uint32_t sumAllMatch = 0;
//     for (int i = 0; i < numThreads; i++) // summation of all matched values from all threads
//     {
//         sumAllMatch += countMatchVector[i];
//         cout << "Matched count in thread " << i << " is: " << countMatchVector[i] << endl;
//     }

//     cout << "Total matched values = " << sumAllMatch << endl;

//     // Don't need to merge, we don't have an output file to generate
//     mergeTextFiles(tempFiles, outputFile);
//     cout << "Lookup completed and merged into " << outputFile << endl;
//     cout << "Lookup operation has been completed." << endl;

//     return 0;
// }


// // Version 2 - Replace
uint8_t splitAndProcessBinaryFileForSearchAndReplace(
    const string &inputFile,
    const string &outputFile,
    int numThreads,
    string searchString,
    string replaceString)
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
        char delimiterByte = 0x02; // default
        if (i != numThreads - 1)
        {
            ifstream tempFile(inputFile, ios::binary);
            tempFile.seekg(end);
            char c;
            while (tempFile.get(c))
            {
                if (c == 0x02 || c == 0x00)
                {
                    delimiterByte = c;
                    break; // Stop at newline or space
                }
            }
            end = tempFile.tellg();
            tempFile.close();
        }
        preservedDelimiters[i] = delimiterByte; // store the preserved delimiter

        string chunkFile = "chunk_" + to_string(i) + ".bin";
        tempFiles.push_back(chunkFile);
        threads.emplace_back(Lookup_and_Replace_Function, inputFile, start, end, chunkFile, searchString, replaceString, i, ref(countMatchVector), preservedDelimiters[i]); // 'i' is the threadIndex
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

    // Don't need to merge, we don't have an output file to generate
    mergeTextFiles(tempFiles, outputFile);
    cout << "Lookup completed and merged into " << outputFile << endl;
    cout << "Lookup operation has been completed." << endl;

    return 0;
}