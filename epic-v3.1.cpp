/*

Title: Enhanced PIC (TIC) compression
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
    2) New line             => 0x1 --> in TIC format, shift left by 1 => 0x2
    3) Next Capital letter  => 0x2 --> in TIC format, shift left by 1 => 0x4
    4) Special codeWord     => 0x3 --> in TIC format, shift left by 1 => 0x6


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


#include "epic-v3.1.h"
#include <unistd.h>   // getpid() for unique temporary file names (D-14)
#include <atomic>    // ticV2EncoderRejected is written from worker threads

// Declare the unordered_map to store the word and serialized integer
unordered_map<string, uint32_t> dictMapWord; // Compression Hash Table
// unordered_map<uint32_t, string> dictMapCode; // Decompression Hash Table (UNUSED)
string *dictMapCodeArray = nullptr; // Decompression Consecutive Array of rank of codeWords
size_t dictMapCodeArraySize = 0;    // allocated length of dictMapCodeArray (bounds checking)
// Highest serial the loaded dictionary can legally produce. Set by BOTH dictionary
// builders so the lookup/replace pre-scan can reject an out-of-range rank without
// performing a dictionary access on the match path.
uint64_t ticMaxValidSerial = 0;

// ===========================================================================
// TIC codec revision.
//
// v1 is the completed, publication-ready codec: a T_S payload length is ONE raw
// byte, and a token longer than 255 bytes is emitted as consecutive frames (the
// approved T42 fix). v1 behaviour is frozen and must stay byte-identical.
//
// v2 encodes a T_S length as a CANONICAL variable-length header -- LSB is the
// continuation flag, 7-bit groups least-significant first -- so ONE T_S
// structure is ONE logical token. Spec: ~/Projects/.claude/knowledge/tic-codec-v2.md
//
// The revision is never inferred from payload bytes. It is selected explicitly
// and defaults to v1 so existing scripts and experiments are unaffected.
// ===========================================================================
enum TicCodec : uint8_t { TIC_CODEC_V1 = 1, TIC_CODEC_V2 = 2 };
TicCodec ticCodec = TIC_CODEC_V1;

const uint64_t TIC_MAX_TS_PAYLOAD      = 2097151;  // 2^21 - 1, semantic limit
const int      TIC_MAX_TS_HEADER_BYTES = 3;        // its encoding consequence

// Canonical v2 length header. Returns false only if L is outside the legal range.
static bool ticV2EncodeLength(uint64_t L, vector<uint8_t> &out)
{
    if (L == 0 || L > TIC_MAX_TS_PAYLOAD) return false;   // L == 0 is invalid in v2
    vector<uint8_t> groups;
    uint64_t v = L;
    do { groups.push_back(static_cast<uint8_t>(v & 0x7F)); v >>= 7; } while (v != 0);
    for (size_t k = 0; k < groups.size(); k++)
        out.push_back(static_cast<uint8_t>((groups[k] << 1) | (k + 1 < groups.size() ? 1 : 0)));
    return true;
}

// Canonical v2 length header decode.
//   ok        : header well formed, canonical, within limits, L in range
//   consumed  : header bytes read
// Rejects: truncated, more than 3 bytes, non-canonical (zero top group in a
// multi-byte header), L == 0, L > MAX.
static bool ticV2DecodeLength(const uint8_t *buf, size_t avail,
                              uint64_t &L, size_t &consumed)
{
    L = 0; consumed = 0;
    uint64_t acc = 0;
    for (int i = 0; i < TIC_MAX_TS_HEADER_BYTES; i++)
    {
        if (static_cast<size_t>(i) >= avail) return false;      // truncated header
        const uint8_t b = buf[i];
        const uint8_t g = static_cast<uint8_t>(b >> 1);
        acc |= (static_cast<uint64_t>(g) << (7 * i));
        if ((b & 1) == 0)                                        // final byte
        {
            if (i > 0 && g == 0) return false;                   // non-canonical padding
            if (acc == 0) return false;                          // zero length invalid
            if (acc > TIC_MAX_TS_PAYLOAD) return false;
            L = acc; consumed = static_cast<size_t>(i) + 1;
            return true;
        }
    }
    return false;                                                // needs a 4th byte
}

// Forward declaration: emits a token as one or more legal T_S frames (<=255 B each).
static void EMIT_SPECIAL_FRAMES(vector<uint8_t> &out, const string &word);
std::atomic<bool> ticV2EncoderRejected{false};   // set when a token is outside the v2 legal range (written from worker threads)

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
uint64_t T1_FREQ = 0, T2_FREQ = 0, T3_FREQ = 0, T4_FREQ = 0;

const uint8_t SPACE_BYTE       = Shift_Left_with_Zero_Inserted(SPACE_CODE);
const uint8_t NEXT_SPECIAL_BYTE_D14 = Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE);
const uint8_t NEWLINE_BYTE     = Shift_Left_with_Zero_Inserted(NEW_LINE_CODE);
const uint8_t END_SPECIAL_BYTE = Shift_Left_with_Zero_Inserted(END_SPECIAL_CODE);

// *********************************************
//            Main Function
// *********************************************
// ---------------------------------------------------------------------------
// Dictionary path resolution
// ---------------------------------------------------------------------------
// The dictionary path is resolved once, at start-up, in this order:
//
//   1. $TIC_DICT_PATH, if set and non-empty
//   2. "dict.txt" relative to the current working directory (historical default)
//
// The environment variable was chosen over a new command-line flag because the
// argument parser validates argc strictly (6, 7 or 8); adding a flag would
// change every existing invocation. Every documented command keeps working
// unchanged, and the compression algorithm is unaffected: the same dictionary
// bytes always produce the same output.
//
// See docs/dictionary.md.
static void resolveDictionaryPath()
{
    const char *envPath = getenv("TIC_DICT_PATH");

    if (envPath != nullptr && envPath[0] != '\0')
        dictFilename = envPath;

    ifstream probe(dictFilename);
    if (!probe.is_open())
    {
        cerr << "Main Error: cannot open the dictionary file: " << dictFilename << "\n"
             << "  The dictionary is required for every operation.\n"
             << "  Set TIC_DICT_PATH to its location, for example:\n"
             << "    TIC_DICT_PATH=/path/to/dict.txt " << "<binary> -c -t 1 in.txt out\n"
             << "  Or run from a directory containing dict.txt.\n"
             << "  See docs/dictionary.md for how to obtain or build one." << endl;
        exit(1);
    }
    probe.close();
}


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

    // Explicit codec selection, removed from argv before the positional parse so
    // every existing invocation keeps working unchanged. Default stays v1.
    {
        vector<char *> kept;
        for (int i = 0; i < argc; i++)
        {
            const string a = argv[i];
            if (a == "--codec-v2" || a == "--codec=v2") { ticCodec = TIC_CODEC_V2; continue; }
            if (a == "--codec-v1" || a == "--codec=v1") { ticCodec = TIC_CODEC_V1; continue; }
            kept.push_back(argv[i]);
        }
        static vector<char *> filtered;
        filtered = kept;
        argc = static_cast<int>(filtered.size());
        argv = filtered.data();
    }

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

    // // Record the start time
    // auto start = high_resolution_clock::now();

    resolveDictionaryPath();

    uint64_t numberOfWords = countLinesInFile(dictFilename);
    // cout << "Number of lines in the dictionary file: " << numberOfWords << endl;

    dictMapCodeArray = new string[numberOfWords + 10]; // add an extra spaces
    dictMapCodeArraySize = static_cast<size_t>(numberOfWords + 10);
    if (numberOfWords + CODE_WORD_OFFSET - 1 > ticMaxValidSerial)
        ticMaxValidSerial = numberOfWords + CODE_WORD_OFFSET - 1;

    // **** TESTs ****
    // int TMP_NUM = ONE_BYTE_BOUND-1;
    // const int TWO_BYTE_MID = TMP_NUM << 7;
    // cout << "Two byte mid = " << TWO_BYTE_MID << "bits = " << bitset<14> (TWO_BYTE_MID) << endl;
    // ****************


    // *** DEBUG ***
    // std::clock_t cpu_start = std::clock();


    if (operationMode == "-c") // compression operation flag
    { 
        // *** Compression ***
        // Building the dictionary hash table for compression
        // cout << "Building the dictionary hash table for compression.." << endl;
        if (Build_Dictionary_Table_Compression() == 0){
            // cout << "The dictionary hash table for compression has been built successfully." << endl;
        }
        else{
            cerr << "Main Error: in building the dictionary hash table!" << endl;
            return 1;
        }

        // Send the text file to multiple compression threads
        if (splitAndProcessTextFile(inputFileName, outputFileName, numThreads) == 0)
        {
            // cout << "The compression function is successful." << endl;

            // cout << "T1_FREQ = " << T1_FREQ << endl;
            // cout << "T2_FREQ = " << T2_FREQ << endl;
            // cout << "T3_FREQ = " << T3_FREQ << endl;
            // cout << "T4_FREQ = " << T4_FREQ << endl;
        }
        else{
            cerr << "Main Error: in running the compression function!" << endl;
            return 1;
        }
    } // compression operation flag
    else if (operationMode == "-d") // decompression operation flag
    { 
        // *** Decompression ***
        // Building the dictionary hash table for decompression
        // cout << "Building the dictionary hash table for decompression.." << endl;
        if (Build_Dictionary_Table_Decompression() == 0){
            // cout << "The dictionary hash table for decompression has been built successfully." << endl;
        }
        else{
            cerr << "Main Error: in building the dictionary hash table!" << endl;
            return 1;
        }

        if (splitAndProcessBinaryFile(inputFileName, outputFileName, numThreads) == 0){
            // cout << "The decompression function is successful." << endl;
            // cout << "Decoded lines: " << decodedLineCounter << endl;
        }
        else{
            cerr << "Main Error: in running the decompression function!" << endl;
            return 1;
        }
    } // decompression operation flag
    else if (operationMode == "-l") // lookup operation flag
    { 
        // Building the dictionary hash table for compressing the search string
        // cout << "Building the dictionary hash table for compression.." << endl;
        if (Build_Dictionary_Table_Compression() == 0){
            // cout << "The dictionary hash table for compression has been built successfully." << endl;
        }
        else{
            cerr << "Main Error: in building the dictionary hash table!" << endl;
            return 1;
        }

        if (splitAndProcessBinaryFileForSearch(inputFileName, outputFileName, numThreads, searchString) == 0){
            // cout << "The lookup function is successful." << endl;
        }
        else{
            cerr << "Main Error: in running the lookup function!" << endl;
            return 1;
        }
    } // lookup operation flag
    else if (operationMode == "-r") // lookup and replace operation flag
    { 
        // Building the dictionary hash table for compressing the search string
        // cout << "Building the dictionary hash table for compression.." << endl;
        if (Build_Dictionary_Table_Compression() == 0){
            // cout << "The dictionary hash table for compression has been built successfully." << endl;
        }
        else{
            cerr << "Main Error: in building the dictionary hash table!" << endl;
            return 1;
        }

        if (splitAndProcessBinaryFileForSearchAndReplace(inputFileName, outputFileName, numThreads, searchString, replaceString) == 0){
        //if (splitAndProcessBinaryFileWithReplacement(inputFileName, outputFileName, numThreads, searchString, replaceString) == 0)
            // cout << "The lookup function is successful." << endl;
        }
        else{
            cerr << "Main Error: in running the lookup function!" << endl;
            return 1;
        }

    } // lookup and replace operation flag
    else
    { // error
        cerr << "Main Error - Invalid operation: " << argv[2] << endl;
        return 1;
    }

    // For testing ...
    // printBinaryFile(outputFileNameBin);

    // cout << "Sleep for one second..\n";
    // this_thread::sleep_for(chrono::seconds(1));

    delete[] dictMapCodeArray;
    dictMapWord.clear();
    dictMapCodeArray = nullptr;

    // // Record the end time
    // auto end = high_resolution_clock::now();

    // // Calculate the duration in microseconds (or other units)
    // auto duration = duration_cast<milliseconds>(end - start);

    // cout << "Total execution time: " << duration.count() << " milliseconds" << endl;
    // cout << "Total execution time: " << duration.count() / 1000.0 << " seconds" << endl;
    // cout << "Number of special codeWords = " << specialCodeWordCounter << endl;





    // *** DEBUG ***
    // std::clock_t cpu_end = std::clock();
    // double cpu_time_sec = static_cast<double>(cpu_end - cpu_start) / CLOCKS_PER_SEC;
    // std::cerr << std::fixed << std::setprecision(6)
            //   << "CPU_TIME_SECONDS=" << cpu_time_sec << std::endl;


    return 0;
} // main function

/*
--------------------------
***  OTHER FUNCTIONS  ***
--------------------------
*/


// ------------------------------------------------------
// ***** Lookup_and_Replace_Function ***********


// Version 5
// Version 4 (Stable)
// uint64_t Lookup_and_Replace_Function(
//     const string &inputFileNameBin,
//     streampos start,
//     streampos end,
//     const string &outputFileNameBin,
//     string searchString,
//     string replaceString,
//     int threadIndex,
//     vector<uint64_t> &results)
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
//     vector<char> buffer(bufferSize);
//     streamoff currentPos = static_cast<streamoff>(start);

//     vector<uint8_t> lineCodeWords = convertSearchStringToCodeWord(processLineChar(searchString));
//     vector<uint8_t> replaceCodeWords = convertSearchStringToCodeWord(processLineChar(replaceString));

//     uint16_t lineCodeWordsSize = static_cast<uint16_t>(lineCodeWords.size());
//     uint16_t replaceCodeWordsSize = static_cast<uint16_t>(replaceCodeWords.size());
//     uint64_t matchCount = 0;
//     uint16_t byteIndex = 0;
//     vector<uint8_t> tmpCodeWord;

//     uint8_t byte = 0;
//     uint64_t toSkip = 0;

//     while (currentPos < end && inFile)
//     {
//         size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - currentPos));
//         inFile.read(buffer.data(), bytesToRead);
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
//                     code == SPACE_CODE ||
//                     code == NEW_LINE_CODE
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
//             uint16_t nextByteCode = byte & (0x1);

//             if (byte == (Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE)) && byte != lineCodeWords[byteIndex])
//             {
//                 if (i + 1 >= bytesRead) {
//                     cerr << "Error - L and R: Not enough bytes to read sizeByte!\n";
//                     exit(1);
//                 }
//                 else // (i + 1 < bytesRead)
//                 {
//                     outFile.put(static_cast<char>(byte)); 
//                     i++; currentPos++;
//                     uint8_t skipLength = static_cast<uint8_t>(buffer[i]);
//                     outFile.put(static_cast<char>(skipLength));
//                     i++; currentPos++;
                    
//                     outFile.write(buffer.data() + i, skipLength);
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
//                         nextByteCode = byte & (0x1);
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
// ----------------------------------------

// *** Consecutive Array for Decompression ***
uint8_t Build_Dictionary_Table_Decompression()
{
    // Variables to store each line and word
    string line, word;
    uint64_t serial = CODE_WORD_OFFSET; // Start serializing after the the serialized number of all reserved codeWords

    // Open the Text file
    ifstream file(dictFilename);

    // Check if the file is open
    if (!file.is_open())
    {
        cerr << "Error - Build D table: opening file: " << dictFilename << endl;
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
    // cout << "\nTotal words = " << serial - 1 << "\n";
    // cout << "The hash map for decompresssion has been generated successfully!\n\n";

    // // Test the hash map
    // cout << "Test the hash map:\n";
    // uint64_t tmpSerial = 127;
    // cout << "Serial (" << tmpSerial << ") has a word of: " << dictMapCode[tmpSerial] << "\n";
    // cout << "\n\n";

    return 0;
}


// *** Hash table for Cecompression ***
uint8_t Build_Dictionary_Table_Compression()
{
    // Variables to store each line and word
    string line, word;
    uint64_t serial = CODE_WORD_OFFSET; // Start serializing from 3

    // Open the Text file
    ifstream file(dictFilename);

    // Check if the file is open
    if (!file.is_open())
    {
        cerr << "Error - Build C table: opening file: " << dictFilename << endl;
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
        if (serial > ticMaxValidSerial) ticMaxValidSerial = serial;
        serial++;
    }

    // Close the file after reading
    file.close();

    //** for testing ... **
    // cout << "\nTotal words = " << serial - 1 << "\n";
    // cout << "The hash map for compression has been generated successfully!\n\n";

    // // Test the hash map
    // cout << "Test the hash map:\n";
    // string tmp_word = "wild";
    // cout << "Word (" << tmp_word << ") has an order of: " << dictMapWord[tmp_word] << "\n";
    // cout << "\n\n";

    return 0;
}

// -------------------------------------------
// ------ Compression Function --------------


// // Version 4
// uint8_t Compression_Function(
//     const string &inputFileText,
//     uint64_t startLine,
//     uint64_t endLine,
//     const string &outputFileBin)
// {
//     ifstream inFile(inputFileText);

//     if (!inFile)
//     {
//         cerr << "Error - C: opening file: "
//              << inputFileText << endl;

//         return -1;
//     }

//     ofstream outFile(outputFileBin, ios::binary);

//     if (!outFile)
//     {
//         cerr << "Error - C: opening output file: "
//              << outputFileBin << endl;

//         return -1;
//     }

//     string line;

//     uint64_t currentLine = 0;

//     // =====================================================
//     // Skip lines before startLine
//     // =====================================================

//     while (
//         currentLine < startLine &&
//         getline(inFile, line)
//     )
//     {
//         currentLine++;
//     }

//     // =====================================================
//     // Process assigned line range
//     // =====================================================

//     while (
//         currentLine < endLine &&
//         getline(inFile, line)
//     )
//     {
//         vector<string> tokens =
//             processLineChar(line);

//         vector<uint8_t> lineCodeWords =
//             convertStringToCodeWord(tokens);

//         if (!lineCodeWords.empty())
//         {
//             outFile.write(
//                 reinterpret_cast<const char*>(
//                     lineCodeWords.data()
//                 ),
//                 static_cast<streamsize>(
//                     lineCodeWords.size()
//                 )
//             );
//         }

//         currentLine++;
//     }

//     inFile.close();
//     outFile.close();

//     return 0;
// }


// Version 3 (Stable) – with final‐line fix
uint8_t Compression_Function(
    const string &inputFileText,
    streampos start,
    streampos end,
    const string &outputFileBin)
{

    // DEBUG - to be removed
    // cout << "[Compression_Function START] "
    //         << "start=" << start
    //         << ", end=" << end
    //         << endl;

    ifstream inFile(inputFileText);
    if (!inFile) {
        cerr << "Error - C: opening file: " << inputFileText << endl;
        return -1;
    }

    inFile.seekg(start);
    if (start > 0) {
        string temp;
        getline(inFile, temp);  // skip partial first line
    }

    // ofstream outFile(outputFileBin, ios::binary | ios::app);
    ofstream outFile(outputFileBin, ios::binary);
    if (!outFile) {
        cerr << "Error C: Could not open the file." << endl;
        return 1;
    }

    // v1: exactly 1 MiB, unchanged. v2: must hold one contiguous T_S payload.
    const size_t bufferSize = (ticCodec == TIC_CODEC_V2 ? static_cast<size_t>(TIC_MAX_TS_PAYLOAD) + 4096 : static_cast<size_t>(1) << 20);
    // constexpr size_t bufferSize = 4096; 
    vector<char> buffer(bufferSize);
    streamoff currentPos = static_cast<streamoff>(start);

    vector<string>   tokens;
    vector<uint8_t>  lineCodeWords;
    const char*     bufferPtr;
    size_t          bufferLen;

    string chunkText;
    while (currentPos < end && inFile) {

        // DEBUG - to be removed
        // static uint64_t debugCounter = 0;
        // debugCounter++;
        // if (debugCounter % 1000 == 0)
        // {
        //     cout << "[THREAD PROGRESS] "
        //         << "currentPos=" << currentPos
        //         << ", end=" << end
        //         << endl;
        // }

        streamoff previousPos = currentPos;

        // read up to chunk end or bufferSize
        size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - currentPos));
        inFile.read(buffer.data(), bytesToRead);
        size_t bytesRead = inFile.gcount();
        if (bytesRead == 0)
        {
            break;
        }

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
        chunkText.append(buffer.data(), bytesRead);
        // currentPos = inFile.tellg();
        // currentPos = static_cast<streamoff>(inFile.tellg());
        streampos pos = inFile.tellg();
        if (pos == streampos(-1))
        {
            break;
        }
        currentPos = static_cast<streamoff>(pos);

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

        // if (currentPos <= previousPos)
        // {
        //     cerr << "Error[TIC Compression]: No progress. "
        //         // << "threadIndex=" << threadIndex
        //         << ", previousPos=" << previousPos
        //         << ", currentPos=" << currentPos
        //         << ", end=" << static_cast<streamoff>(end)
        //         << endl;

        //     return -1;
        // }
    }

    inFile.close();
    outFile.close();

    // DEBUG - to be removed
    // cout << "[Compression_Function DONE] "
    //         << "start=" << start
    //         << ", end=" << end
    //         << endl;


    return 0;
}

// // Version 2
// uint8_t Compression_Function(
//     const string &inputFileText,
//     streampos start,
//     streampos end,
//     const string &outputFileBin)
// {
//     ifstream inFile(inputFileText);
//     if (!inFile) {
//         cerr << "Error - C: opening file: " << inputFileText << endl;
//         return -1;
//     }

//     inFile.seekg(start);
//     if (start > 0) {
//         string temp;
//         getline(inFile, temp);  // skip partial first line
//     }

//     ofstream outFile(outputFileBin, ios::binary | ios::app);
//     if (!outFile) {
//         cerr << "Error C: Could not open the file." << endl;
//         return 1;
//     }

//     const size_t bufferSize = 4096;
//     char buffer[bufferSize];
//     streamoff currentPos = static_cast<streamoff>(start);

//     vector<string>   tokens;
//     vector<uint8_t>  lineCodeWords;
//     const char*     bufferPtr;
//     size_t          bufferLen;

//     string chunkText;
//     while (currentPos < end && inFile) {
//         // read up to chunk end or bufferSize
//         size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - currentPos));
//         inFile.read(buffer, bytesToRead);
//         size_t bytesRead = inFile.gcount();

//         // find last newline so we don't cut a line in half
//         size_t safeEnd = bytesRead;
//         for (size_t i = bytesRead; i-- > 0;) {
//             if (buffer[i] == '\n') {
//                 safeEnd = i + 1;
//                 break;
//             }
//         }

//         // rewind any unread bytes
//         size_t unread = bytesRead - safeEnd;
//         if (unread > 0) {
//             inFile.clear();
//             inFile.seekg(-static_cast<streamoff>(unread), ios::cur);
//             bytesRead = safeEnd;
//             // currentPos -= unread; // added 
//         }

//         // append full‐line portion to chunkText
//         chunkText.append(buffer, bytesRead);
//         // currentPos = inFile.tellg();
//         currentPos = static_cast<streamoff>(inFile.tellg());

//         // process all complete lines in chunkText
//         istringstream ss(chunkText);
//         string line;
//         string leftover;
//         while (getline(ss, line)) {
//             if (ss.eof() && chunkText.back() != '\n') {
//                 // this line is incomplete—save and break
//                 leftover = line;
//                 break;
//             }
//             tokens = processLineChar(line);
//             lineCodeWords = convertStringToCodeWord(tokens);
//             bufferPtr = reinterpret_cast<const char*>(lineCodeWords.data());
//             bufferLen = lineCodeWords.size();
//             outFile.write(bufferPtr, bufferLen);
//         }

//         // keep only the incomplete trailing part
//         chunkText = leftover;
//     }

//     inFile.close();
//     outFile.close();
//     return 0;
// }


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
    uint64_t serial = 0, inputNumber = 0;
    string word;

    /*
    *** Open the output file in appen mode **
    WARNING:
    Since the output file is in an append mode,
    you need to delete the output file after each run.

    *** Generate T0 ***
    Have reserved values:
    1) Space                => 0x0
    2) New line             => 0x1 --> in TIC format, shift left by 1 => 0x2
    3) Next Capital letter  => 0x2 --> in TIC format, shift left by 1 => 0x4
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
            // P1: this MUST NOT mutate the dictionary. operator[] inserts a
            // default-constructed 0 for every miss, so out-of-dictionary tokens were
            // rewriting a map that every compression worker shares, unsynchronised --
            // causing concurrent rehashing, heap-use-after-free and hangs. find() is
            // non-mutating and preserves the not-found sentinel exactly: absent => 0.
            const auto dictIt = dictMapWord.find(tmpWord);
            serial = (dictIt == dictMapWord.end()) ? 0 : dictIt->second;

            if (serial == 0)
            { // NOT FOUND in the hash table - SPECIAL codeWord
                // Call a function to generate a special codeWord
                // Split payloads longer than 255 bytes into consecutive legal
                // T_S frames; identical output for payloads <= 255 bytes.
                EMIT_SPECIAL_FRAMES(lineCodeWords, word);

                // increment the special code word counter (once per TOKEN, as before)
                specialCodeWordCounter++;

                // for debug ..
                // cout << "special code: " << word << endl;

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
                else
                {
                    // Add word to the map with the current serial number
                    // dictMapWord[word] = serial;
                    T4_FREQ++;
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
    uint64_t serial = 0, inputNumber = 0;
    string word;

    /*
    *** Open the output file in appen mode **
    WARNING:
    Since the output file is in an append mode,
    you need to delete the output file after each run.

    *** Generate T0 ***
    Have reserved values:
    1) Space                => 0x0
    2) New line             => 0x1 --> in TIC format, shift left by 1 => 0x2
    3) Next Capital letter  => 0x2 --> in TIC format, shift left by 1 => 0x4
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
                // Split payloads longer than 255 bytes into consecutive legal
                // T_S frames; identical output for payloads <= 255 bytes.
                EMIT_SPECIAL_FRAMES(lineCodeWords, word);

                // increment the special code word counter (once per TOKEN, as before)
                specialCodeWordCounter++;

                // for debug ..
                // cout << "special code: " << word << endl;

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



// Version 3 (Stable)
uint8_t Decompression_Function(const string &inputFileNameBin, streampos start, streampos end, const string &outputFileNameText)
{
    ifstream inFile(inputFileNameBin, ios::binary);
    // D-14: was ios::app. Each worker owns exactly one temporary file, so append
    // mode gained nothing and was a hazard: a temp file left behind by a crashed
    // run would be appended to rather than replaced, silently duplicating text.
    ofstream outFile(outputFileNameText, ios::out | ios::trunc | ios::binary);
    if (!inFile || !outFile)
    {
        cerr << "Error - D: opening files for decompression." << endl;
        return -1;
    }

    inFile.seekg(start);
    
    // v1: exactly 1 MiB, unchanged. v2: must hold one contiguous T_S payload.
    const size_t bufferSize = (ticCodec == TIC_CODEC_V2 ? static_cast<size_t>(TIC_MAX_TS_PAYLOAD) + 4096 : static_cast<size_t>(1) << 20);
    vector<char> buffer(bufferSize);
    streamoff currentPos = static_cast<streamoff>(start);

    uint64_t tmpSerial = 0, finalSerial = 0;
    string word;
    uint8_t nextByte;
    bool NEXT_CAP = false;
    uint64_t count = 0;

    while (currentPos < end && inFile)
    {
        inFile.clear(); // Clear any EOF/failure flags before seeking
        inFile.seekg(currentPos); // roll back to current position in case of a failure of buffer read

        size_t bytesToRead = static_cast<size_t>(min<streamoff>(bufferSize, end - currentPos));
        inFile.read(buffer.data(), bytesToRead);
        size_t bytesRead = inFile.gcount();

        if (bytesRead == bufferSize)
        {
            size_t safeEnd = bufferSize;
            uint8_t stopSteps = 0;
            for (int i = bufferSize - 1; i >= 0; --i)
            {
                uint8_t byte = static_cast<uint8_t>(buffer[i]);
                uint8_t code = byte >> 1;
                if (
                    code == SPACE_CODE ||
                    code == NEW_LINE_CODE
                )
                {
                    stopSteps++;
                    if(stopSteps == BACKWARD_STOP_STEPS){
                        safeEnd = i - 1; 
                        stopSteps = 0;
                        break;
                    }
                }
                
            }
            size_t unreadBytes = bytesRead - safeEnd;
            if (unreadBytes > 0)
            {
                inFile.clear();
                inFile.seekg(-static_cast<streamoff>(unreadBytes), ios::cur);
                bytesRead = safeEnd;
            }
        }

        for (size_t i = 0; i < bytesRead && currentPos < end;)
        {
            uint8_t byte = static_cast<uint8_t>(buffer[i]);
            nextByte = byte & (0x1);
            byte >>= 1;

            if (nextByte == 0)
            {
                // GUARD: a valid codeword never uses more than 3 groups. A longer
                // run means the stream is malformed; shifting by 7*count would be
                // undefined behaviour for count >= 10.
                if (count > 2)
                {
                    cerr << "Error - D: malformed codeword (continuation run of "
                         << static_cast<unsigned>(count) + 1 << " bytes)" << endl;
                    inFile.close(); outFile.close(); return 2;
                }
                finalSerial = static_cast<uint64_t>(concatenateBytes(finalSerial, byte, count));

                if (count == 1)
                    finalSerial += TWO_BYTE_OFFSET;
                else if (count == 2)
                    finalSerial += THREE_BYTE_OFFSET;

                if (finalSerial == SPACE_CODE)
                {
                    outFile << " ";
                }
                else if (finalSerial == NEW_LINE_CODE)
                {
                    outFile << "\n";
                    ++decodedLineCounter;
                }
                else if (finalSerial == NEXT_CAPITAL_CODE)
                {
                    NEXT_CAP = true;
                }
                else if (finalSerial == NEXT_SPECIAL_CODE)
                {
                    size_t start_i = i;
                    string word = SPECIAL_CODE_WORD_READER(buffer.data(), i, bytesRead);

                    if (word.empty()) {
                        // The reader fails when the T_S frame runs past the end of
                        // this buffer. Recoverable ONLY if more of the file remains;
                        // otherwise the frame is genuinely truncated. Guards also
                        // prevent the size_t wrap of "start_i - 1" and the
                        // no-progress loop that re-reads the same buffer forever.
                        if (currentPos + static_cast<streamoff>(bytesRead) >= end)
                        {
                            cerr << "Error - D: truncated T_S frame at end of stream" << endl;
                            inFile.close(); outFile.close(); return 5;
                        }
                        if (start_i == 0)
                        {
                            cerr << "Error - D: T_S frame exceeds the read buffer" << endl;
                            inFile.close(); outFile.close(); return 6;
                        }
                        i = start_i - 1;
                        currentPos--;
                        break;
                    }

                    // GUARD: the payload must be followed by END_SPECIAL. After the
                    // reader, i indexes the LAST PAYLOAD byte, so the terminator is
                    // at i + 1.
                    // Validate ONLY when the terminator lies inside this buffer.
                    // A frame whose END_SPECIAL falls exactly past the buffer edge
                    // is legitimate: the original flow lets the loop exit and the
                    // next refill consume it. Checking it here would reject valid
                    // streams.
                    if (i + 1 < bytesRead &&
                        static_cast<uint8_t>(buffer[i + 1]) !=
                            Shift_Left_with_Zero_Inserted(END_SPECIAL_CODE))
                    {
                        cerr << "Error - D: T_S frame not terminated by END_SPECIAL" << endl;
                        inFile.close(); outFile.close(); return 3;
                    }

                    outFile << word;
                    i++; // to skip the END_SPECIAL_CODE byteCode 
                    tmpSerial = finalSerial = 0;
                    count = 0;
                    currentPos += (i - start_i);  // update currentPos manually
                    continue; // updated currentPos in the previous statement, and already advanced i inside reader
                }
                else
                {
                    // GUARD: reconstructed rank must be inside the decode array.
                    if (finalSerial >= dictMapCodeArraySize)
                    {
                        cerr << "Error - D: dictionary rank " << finalSerial
                             << " out of range (max " << dictMapCodeArraySize - 1 << ")" << endl;
                        inFile.close(); outFile.close(); return 4;
                    }
                    word = dictMapCodeArray[finalSerial];
                    if (NEXT_CAP)
                    {
                        word[0] = toupper(word[0]);
                        NEXT_CAP = false;
                    }
                    outFile << word;
                }

                tmpSerial = finalSerial = 0;
                count = 0;
                ++i; // advance only here
            }
            else
            {
                // GUARD: bound the continuation run before the next shift.
                if (count > 2)
                {
                    cerr << "Error - D: malformed codeword (oversized continuation)" << endl;
                    inFile.close(); outFile.close(); return 2;
                }
                finalSerial = concatenateBytes(finalSerial, byte, count);
                count++;
                ++i;
            }

            ++currentPos;
        }

    }

    inFile.close();
    outFile.close();
    return 0;
}


// ----------------------------------



uint64_t concatenateBytes(uint64_t final, uint64_t tmp, uint8_t count)
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


// Version 3
string SPECIAL_CODE_WORD_READER(const char* buffer, size_t& i, size_t bytesRead)
{
    string result;

    // Step 1: Make sure there's at least 1 byte to read the size
    if (i + 1 >= bytesRead) {
        cerr << "Error - SPECIAL_CODE_WORD_READER: Not enough bytes to read sizeByte!\n";
        return "";
    }

    if (ticCodec == TIC_CODEC_V2)
    {
        uint64_t L = 0; size_t used = 0;
        const uint8_t *hdr = reinterpret_cast<const uint8_t *>(buffer) + i + 1;
        const size_t avail = bytesRead - (i + 1);
        if (!ticV2DecodeLength(hdr, avail, L, used))
        {
            // Truncated headers are recoverable by refilling the buffer; a header
            // that is complete but illegal is not. Distinguish the two so a real
            // malformed stream is not retried forever.
            bool complete = false;
            for (size_t k = 0; k < avail && k < static_cast<size_t>(TIC_MAX_TS_HEADER_BYTES); k++)
                if ((hdr[k] & 1) == 0) { complete = true; break; }
            if (complete || avail >= static_cast<size_t>(TIC_MAX_TS_HEADER_BYTES))
                cerr << "Error - D(v2): MALFORMED_STREAM -- illegal T_S length header" << endl;
            return "";
        }
        if (i + used + L >= bytesRead) return "";       // payload not fully buffered yet
        string out;
        out.reserve(static_cast<size_t>(L));
        for (uint64_t j = 0; j < L; j++)
            out += static_cast<char>(buffer[i + used + 1 + j]);
        i += used + static_cast<size_t>(L);             // leave i on the last payload byte
        return out;
    }

    uint8_t sizeByte = static_cast<uint8_t>(buffer[++i]); // read size byte

    // Step 2: Check if enough bytes remain for the actual data
    if (i + sizeByte >= bytesRead) {
        cerr << "Error - SPECIAL_CODE_WORD_READER: Not enough bytes to read special code word! Needed: " 
            << static_cast<int>(sizeByte) << ", Available: " << (bytesRead - i - 1) << "\n";
        i--; // rollback to before reading sizeByte
        return "";
    }

    // Step 3: Append raw bytes to result
    for (uint8_t j = 0; j < sizeByte; ++j)
        result += static_cast<char>(buffer[++i]); // advance i as we read

    return result;
}


string SPECIAL_CODE_WORD_READER_BYTES(vector<uint8_t> bytes)
{
    // Ensure the vector has at least one byte (the size byte)
    if (bytes.empty())
    {
        cerr << "Error - SPECIAL_CODE_WORD_READER_BYTES: Empty byte vector!" << endl;
        return "";
    }

    // Extract the size byte and determine the number of characters
    uint8_t sizeByte = bytes[0];
    size_t numCharacters = sizeByte >> 1; // Ignore the least significant bit

    // Validate that the size matches the vector length
    if (bytes.size() != numCharacters + 1)
    {
        cerr << "Error - SPECIAL_CODE_WORD_READER_BYTES: Byte vector size does not match encoded size!" << endl;
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
                cerr << "Error - SPECIAL_CODE_WORD_READER_BYTES: Invalid byte format!" << endl;
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

// Emit one token as ONE OR MORE legal T_S frames, each carrying at most 255
// payload bytes.  The T_S length field is a single byte and therefore cannot
// express a longer payload; the previous code assigned the length to a uint8_t,
// which silently truncated it (length & 0xFF) while still writing the whole
// payload, producing a stream no conforming decoder can parse.  Splitting keeps
// the on-disk format unchanged: consecutive T_S frames concatenate naturally on
// decode.  For payloads <= 255 bytes this emits exactly the previous bytes.
static void EMIT_SPECIAL_FRAMES(vector<uint8_t> &out, const string &word)
{
    if (ticCodec == TIC_CODEC_V2)
    {
        // ONE T_S structure = ONE logical token. The T42 multi-frame form is v1 only.
        vector<uint8_t> hdr;
        if (!ticV2EncodeLength(word.size(), hdr))
        {
            cerr << "Error - C(v2): T_S payload length " << word.size()
                 << " is invalid (must be 1.." << TIC_MAX_TS_PAYLOAD << ")" << endl;
            ticV2EncoderRejected = true;
            return;
        }
        out.push_back(Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE));
        out.insert(out.end(), hdr.begin(), hdr.end());
        out.insert(out.end(), word.begin(), word.end());
        out.push_back(Shift_Left_with_Zero_Inserted(END_SPECIAL_CODE));
        return;
    }

    const size_t MAX_TS_PAYLOAD = 255;
    size_t off = 0;
    do
    {
        const size_t n = min(MAX_TS_PAYLOAD, word.size() - off);
        out.push_back(Shift_Left_with_Zero_Inserted(NEXT_SPECIAL_CODE));
        vector<uint8_t> frame = SPECIAL_CODE_WORD_GENERATOR(word.substr(off, n));
        out.insert(out.end(), frame.begin(), frame.end());
        out.push_back(Shift_Left_with_Zero_Inserted(END_SPECIAL_CODE));
        off += n;
    } while (off < word.size());
}

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
        
        result.push_back(byte);
    }

    return result;
}

/*
'ONE_BYTE_CODE_GENERATOR' function:
Generate a 1-byte code of TIC algorithm
*/
vector<uint8_t> ONE_BYTE_CODE_GENERATOR(uint64_t input)
{
    vector<uint8_t> codeWord;

    uint8_t byte1 = Mask_Single_Byte(input);      // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    byte1 = Shift_Left_with_Zero_Inserted(byte1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    codeWord.push_back(byte1);

    return codeWord;
}

/*
'TWO_BYTE_CODE_GENERATOR' function:
Generate a 2-byte code of TIC algorithm
*/
vector<uint8_t> TWO_BYTE_CODE_GENERATOR(uint64_t input)
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
Generate a 3-byte code of TIC algorithm
*/
vector<uint8_t> THREE_BYTE_CODE_GENERATOR(uint64_t input)
{
    vector<uint8_t> codeWord;
    uint8_t byte1, byte2, byte3;
    uint64_t input_shitf1;

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
uint8_t Mask_Single_Byte(uint64_t number)
{
    return MASK_BYTE & number;
}

// Shift a number to the left by one position,
// and insert '1' as the LSbit.
uint64_t Shift_Left_with_One_Inserted(uint64_t number)
{
    return number << 1 | (0x1);
}

// Shift a number to the left by one position,
// and insert '0' as the LSbit.
uint64_t Shift_Left_with_Zero_Inserted(uint64_t number)
{
    return number << 1;
}

uint64_t Shift_Right_Seven_Positions(uint64_t number)
{
    return number >> 7;
}

// Check if the least significant bit (LSb) is one.
// If LSb is '1', then there is another byte code in the sequence.
// This function is used in the decompression process.
uint8_t Next_Byte_Available(uint8_t number)
{
    // return number & (0x1); // return one or zero.
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
        cerr << "Error - checkLinesInFile: opening file: " << filePath << endl;
        return;
    }

    string line;
    int lineNumber = 1;

    // Read the file line by line
    while (getline(file, line))
    {
        // cout << "Line " << lineNumber << ": "
        //      << (endsWithNewline(line) ? "Ends with newline" : "Does not end with newline")
        //      << endl;
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
        // cerr << "Error - printBinaryFile: opening file: " << filePath << endl;
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
uint64_t countLinesInFile(const string &filePath)
{
    ifstream file(filePath);
    if (!file)
    {
        // cerr << "Error - countLinesInFile: Could not open file " << filePath << endl;
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

// Function to merge binary files in order.
// Returns false on ANY failure. A missing or unreadable chunk must never be
// skipped: each chunk carries one contiguous range of input lines, so skipping
// one silently drops that range and yields a truncated stream that still looks
// like a successful compression.
bool mergeBinaryFiles(const vector<string> &tempFiles, const string &outputFile)
{
    lock_guard<mutex> lock(fileMutex);
    ofstream outFile(outputFile, ios::binary);
    if (!outFile)
    {
        cerr << "Error - mergeBinaryFiles: creating merged output file: " << outputFile << endl;
        return false;
    }

    for (const auto &tempFile : tempFiles)
    {
        ifstream inFile(tempFile, ios::binary);
        if (!inFile)
        {
            cerr << "Error - mergeBinaryFiles: opening temp file: " << tempFile << endl;
            outFile.close();
            return false;
        }

        outFile << inFile.rdbuf(); // Append to final output
        // Inserting an EMPTY chunk sets failbit even though nothing is wrong:
        // a worker whose line range produced no bytes is legitimate.
        if (outFile.fail() && !outFile.bad()) outFile.clear();
        if (!outFile)
        {
            cerr << "Error - mergeBinaryFiles: writing merged output from: " << tempFile << endl;
            inFile.close(); outFile.close();
            return false;
        }
        inFile.close();
        std::remove(tempFile.c_str()); // Delete and remove temporary file
    }
    outFile.flush();
    const bool ok = static_cast<bool>(outFile);
    outFile.close();
    if (!ok)
    {
        cerr << "Error - mergeBinaryFiles: finalising merged output file: " << outputFile << endl;
        return false;
    }
    // cout << "Binary files merged into " << outputFile << endl;
    return true;
}

// Function to split a text file into contiguous chunks and process them


// Version 6
uint8_t splitAndProcessTextFile(
    const string &inputFile,
    const string &outputFile,
    int numThreads
)
{
    ifstream inFile(inputFile);

    if (!inFile)
    {
        cerr << "Error opening input file: "
             << inputFile << endl;

        return -1;
    }

    // =====================================================
    // Count total number of lines
    // =====================================================

    uint64_t totalLines = 0;

    string dummyLine;

    while (getline(inFile, dummyLine))
    {
        totalLines++;
    }

    inFile.close();

    if (totalLines == 0)
    {
        cerr << "Empty input file." << endl;
        return -1;
    }

    // =====================================================
    // Divide lines among threads
    // =====================================================

    uint64_t linesPerThread =
        totalLines / numThreads;

    uint64_t remainder =
        totalLines % numThreads;

    vector<thread> threads;

    vector<string> tempFiles;

    uint64_t currentStartLine = 0;

    // Temporary chunk names must be unique per PROCESS as well as per worker.
    // The name was previously "chunk_<i>.bin", relative to the working
    // directory, so two independent compressions sharing a directory used the
    // SAME files: each truncated the other's chunks and removed them during its
    // own merge, producing truncated or empty output while still exiting 0.
    // A live PID is unique among running processes, which is exactly the
    // property needed here; a stale file left by a crashed process whose PID was
    // recycled is harmless because the name is removed below and then reopened
    // truncating. This matches the D-14 decompression convention.
    const string tempTag = to_string(static_cast<long long>(getpid()));

    // Raised by any worker that cannot open or write its chunk. Without it a
    // failed worker returned silently and its whole line range vanished from
    // the merged stream.
    std::atomic<bool> chunkIoFailed{false};

    // =====================================================
    // Launch threads
    // =====================================================

    for (int i = 0; i < numThreads; i++)
    {
        uint64_t myLines =
            linesPerThread +
            (i < remainder ? 1 : 0);

        uint64_t myStartLine =
            currentStartLine;

        uint64_t myEndLine =
            myStartLine + myLines;

        string chunkFile =
            "chunk_" + tempTag + "_" + to_string(i) + ".bin";

        remove(chunkFile.c_str());

        tempFiles.push_back(chunkFile);

        // DEBUG
        // cout << "[THREAD START] "
        //      << "thread=" << i
        //      << ", startLine=" << myStartLine
        //      << ", endLine=" << myEndLine
        //      << endl;

        threads.emplace_back(
            [=, &chunkIoFailed]()
            {
                ifstream in(inputFile);

                ofstream out(
                    chunkFile,
                    ios::binary
                );

                if (!in || !out)
                {
                    cerr << "Error opening chunk files: "
                         << chunkFile << endl;

                    chunkIoFailed.store(true);
                    return;
                }

                string line;

                uint64_t lineNum = 0;

                // =========================================
                // Skip lines before assigned range
                // =========================================

                while (
                    lineNum < myStartLine &&
                    getline(in, line)
                )
                {
                    lineNum++;
                }

                // =========================================
                // Process assigned range
                // =========================================

                while (
                    lineNum < myEndLine &&
                    getline(in, line)
                )
                {
                    vector<string> tokens =
                        processLineChar(line);

                    vector<uint8_t> lineCodeWords =
                        convertStringToCodeWord(tokens);

                    if (!lineCodeWords.empty())
                    {
                        out.write(
                            reinterpret_cast<const char*>(
                                lineCodeWords.data()
                            ),
                            static_cast<streamsize>(
                                lineCodeWords.size()
                            )
                        );
                    }

                    lineNum++;
                }

                in.close();
                out.flush();
                if (!out)
                {
                    cerr << "Error writing chunk file: " << chunkFile << endl;
                    chunkIoFailed.store(true);
                }
                out.close();

                // // DEBUG
                // cout << "[THREAD DONE] "
                //      << "thread=" << i
                //      << endl;
            }
        );

        currentStartLine = myEndLine;
    }

    // =====================================================
    // Wait for all threads
    // =====================================================

    for (auto &t : threads)
    {
        t.join();
    }

    // =====================================================
    // Merge chunks
    // =====================================================

    // A token outside the v2 legal range was refused by EMIT_SPECIAL_FRAMES. That
    // token is NOT in the temp chunks, so merging would produce a silently
    // incomplete stream and still report success. Refuse instead: discard the
    // chunks, write no output, and fail. v1 can never set this flag.
    if (ticV2EncoderRejected.load())
    {
        for (const auto &tempFile : tempFiles)
            std::remove(tempFile.c_str());
        cerr << "Error - C(v2): input contains a token that cannot be encoded in "
                "Codec v2 (payload > " << TIC_MAX_TS_PAYLOAD << " bytes); "
                "no output written" << endl;
        return 7;
    }

    // A worker failed to open or write its chunk. Its line range is therefore
    // absent, so merging would emit a truncated stream and report success.
    if (chunkIoFailed.load())
    {
        for (const auto &tempFile : tempFiles)
            std::remove(tempFile.c_str());
        cerr << "Error - C: a compression worker could not write its temporary "
                "chunk; no output written" << endl;
        return 8;
    }

    if (!mergeBinaryFiles(tempFiles, outputFile))
    {
        // Remove only THIS process's own temporary files; never another's.
        for (const auto &tempFile : tempFiles)
            std::remove(tempFile.c_str());
        std::remove(outputFile.c_str());   // no partial output is left behind
        cerr << "Error - C: merging temporary chunks failed; no output written"
             << endl;
        return 9;
    }

    cout << "Encoding completed and merged into "
         << outputFile << endl;

    return 0;
}

// Version 5
// uint8_t splitAndProcessTextFile(
//     const string &inputFile,
//     const string &outputFile,
//     int numThreads
// )
// {
//     ifstream inFile(inputFile);

//     if (!inFile)
//     {
//         cerr << "Error opening input file: "
//              << inputFile << endl;

//         return -1;
//     }

//     // =====================================================
//     // Get total file size
//     // =====================================================

//     inFile.seekg(0, ios::end);

//     streampos fileSize = inFile.tellg();

//     inFile.close();

//     if (fileSize <= 0)
//     {
//         cerr << "Empty input file." << endl;
//         return -1;
//     }

//     // =====================================================
//     // Split file by byte ranges
//     // =====================================================

//     streampos chunkSize =
//         fileSize / numThreads;

//     vector<thread> threads;

//     vector<string> tempFiles;

//     streampos start = 0;
//     streampos end = 0;

//     // =====================================================
//     // Launch threads
//     // =====================================================

//     for (int i = 0; i < numThreads; i++)
//     {
//         start = end;

//         end =
//             (i == numThreads - 1)
//             ? fileSize
//             : start + chunkSize;

//         // -------------------------------------------------
//         // Move end to nearest newline boundary
//         // -------------------------------------------------

//         if (i != numThreads - 1)
//         {
//             ifstream tempFile(inputFile);

//             tempFile.seekg(end);

//             char c;

//             // while (tempFile.get(c))
//             // {
//             //     if (c == '\n')
//             //     {
//             //         break;
//             //     }
//             // }

//             // end = tempFile.tellg();
//             bool foundBoundary = false;

//             while (tempFile.get(c))
//             {
//                 if (c == '\n')
//                 {
//                     end = tempFile.tellg();
//                     foundBoundary = true;
//                     break;
//                 }
//             }

//             if (!foundBoundary || end <= start)
//             {
//                 cerr << "[WARNING] Invalid or missing newline boundary. "
//                     << "thread=" << i
//                     << ", start=" << start
//                     << ", end=" << end
//                     << ", fileSize=" << fileSize
//                     << endl;

//                 end = fileSize;
//             }

//             tempFile.close();

//             tempFile.close();
//         }

//         // -------------------------------------------------
//         // Create chunk file
//         // -------------------------------------------------

//         string chunkFile =
//             "chunk_" + to_string(i) + ".bin";

//         tempFiles.push_back(chunkFile);

//         // -------------------------------------------------
//         // Spawn compression thread
//         // -------------------------------------------------

//         // // DEBUG - to be removed
//         // cout << "[THREAD START] "
//         //     << "thread=" << i
//         //     << ", start=" << start
//         //     << ", end=" << end
//         //     << ", size=" << (end - start)
//         //     << endl;

//         threads.emplace_back(
//             Compression_Function,
//             inputFile,
//             start,
//             end,
//             chunkFile
//         );
//     }

//     // =====================================================
//     // Wait for all threads
//     // =====================================================

//     for (auto &t : threads)
//     {
//         t.join();
//     }

//     // =====================================================
//     // Merge compressed chunks
//     // =====================================================

//     mergeBinaryFiles(
//         tempFiles,
//         outputFile
//     );

//     cout << "Encoding completed and merged into "
//          << outputFile << endl;

//     return 0;
// }


// // Version 4
// uint8_t splitAndProcessTextFile(
//     const string &inputFile,
//     const string &outputFile,
//     int numThreads
// )
// {
//     ifstream inFile(inputFile);

//     if (!inFile)
//     {
//         cerr << "Error opening input file: "
//              << inputFile << endl;

//         return -1;
//     }

//     // =====================================================
//     // Count total lines
//     // =====================================================

//     uint64_t totalLines = 0;
//     string line;

//     while (getline(inFile, line))
//     {
//         totalLines++;
//     }

//     inFile.close();

//     if (totalLines == 0)
//     {
//         cerr << "Empty input file." << endl;
//         return -1;
//     }

//     // =====================================================
//     // Divide lines among threads
//     // =====================================================

//     uint64_t linesPerThread =
//         totalLines / static_cast<uint64_t>(numThreads);

//     uint64_t remainder =
//         totalLines % static_cast<uint64_t>(numThreads);

//     vector<thread> threads;
//     vector<string> tempFiles;

//     uint64_t currentStartLine = 0;

//     // =====================================================
//     // Launch threads
//     // =====================================================

//     for (int i = 0; i < numThreads; i++)
//     {
//         uint64_t myLines =
//             linesPerThread +
//             (static_cast<uint64_t>(i) < remainder ? 1 : 0);

//         uint64_t myStartLine =
//             currentStartLine;

//         uint64_t myEndLine =
//             myStartLine + myLines;

//         string chunkFile =
//             outputFile + ".chunk_" + to_string(i) + ".bin";

//         tempFiles.push_back(chunkFile);

//         // threads.emplace_back(
//         //     Compression_Function,
//         //     inputFile,
//         //     myStartLine,
//         //     myEndLine,
//         //     chunkFile
//         // );

//         using CompressionWorker =
//             uint8_t (*)(
//                 const string &,
//                 uint64_t,
//                 uint64_t,
//                 const string &
//             );

//         CompressionWorker worker = &Compression_Function;

//         threads.emplace_back(
//             worker,
//             inputFile,
//             myStartLine,
//             myEndLine,
//             chunkFile
//         );

//         currentStartLine = myEndLine;
//     }

//     // =====================================================
//     // Wait for threads
//     // =====================================================

//     for (auto &t : threads)
//     {
//         t.join();
//     }

//     // =====================================================
//     // Merge compressed chunks
//     // =====================================================

//     mergeBinaryFiles(
//         tempFiles,
//         outputFile
//     );

//     return 0;
// }

// // Version 3 (divide by lines)
// uint8_t splitAndProcessTextFile(
//     const string &inputFile,
//     const string &outputFile,
//     int numThreads
// )
// {
//     ifstream inFile(inputFile);

//     if (!inFile)
//     {
//         cerr << "Error opening input file: "
//              << inputFile << endl;

//         return -1;
//     }

//     // =====================================================
//     // Get total file size
//     // =====================================================

//     inFile.seekg(0, ios::end);

//     streampos fileSize = inFile.tellg();

//     inFile.close();

//     if (fileSize <= 0)
//     {
//         cerr << "Empty input file." << endl;
//         return -1;
//     }

//     // =====================================================
//     // Split by byte ranges
//     // =====================================================

//     streampos chunkSize =
//         fileSize / numThreads;

//     vector<thread> threads;
//     vector<string> tempFiles;

//     streampos start = 0;
//     streampos end = 0;

//     // =====================================================
//     // Launch threads
//     // =====================================================

//     for (int i = 0; i < numThreads; i++)
//     {
//         start = end;

//         end =
//             (i == numThreads - 1)
//             ? fileSize
//             : streampos(start + chunkSize);

//         // -------------------------------------------------
//         // Move end to nearest newline boundary
//         // -------------------------------------------------

//         if (i != numThreads - 1)
//         {
//             ifstream tempFile(inputFile);

//             tempFile.seekg(end);

//             char c;

//             while (tempFile.get(c))
//             {
//                 if (c == '\n')
//                 {
//                     break;
//                 }
//             }

//             end = tempFile.tellg();

//             tempFile.close();
//         }

//         // -------------------------------------------------
//         // Thread output file
//         // -------------------------------------------------

//         string chunkFile =
//             "chunk_" + to_string(i) + ".bin";

//         tempFiles.push_back(chunkFile);

//         // -------------------------------------------------
//         // Spawn compression thread
//         // -------------------------------------------------

//         threads.emplace_back(
//             Compression_Function,
//             inputFile,
//             start,
//             end,
//             chunkFile
//         );
//     }

//     // =====================================================
//     // Wait for all threads
//     // =====================================================

//     for (auto &t : threads)
//     {
//         t.join();
//     }

//     // =====================================================
//     // Merge compressed chunks
//     // =====================================================

//     mergeBinaryFiles(
//         tempFiles,
//         outputFile
//     );

//     return 0;
// }





// // Version 2
// uint8_t splitAndProcessTextFile(const string &inputFile, const string &outputFile, int numThreads)
// {
//     ifstream inFile(inputFile);
//     if (!inFile)
//     {
//         cerr << "Error opening input file: " << inputFile << endl;
//         return -1;
//     }

//     // Count total number of lines
//     uint64_t totalLines = 0;
//     string dummyLine;
//     while (getline(inFile, dummyLine)) {
//         totalLines++;
//     }
//     inFile.close();

//     if (totalLines == 0) {
//         cerr << "Empty input file." << endl;
//         return -1;
//     }

//     // Divide lines among threads
//     uint64_t linesPerThread = totalLines / numThreads;
//     uint64_t remainder = totalLines % numThreads;

//     vector<thread> threads;
//     vector<string> tempFiles;

//     uint64_t currentStartLine = 0;

//     for (int i = 0; i < numThreads; i++) {
//         uint64_t myLines = linesPerThread + (i < remainder ? 1 : 0);  // distribute remainder
//         uint64_t myStartLine = currentStartLine;
//         uint64_t myEndLine = myStartLine + myLines;

//         string chunkFile = "chunk_" + to_string(i) + ".bin";
//         tempFiles.push_back(chunkFile);

//         // Spawn thread to process line range [myStartLine, myEndLine)
//         threads.emplace_back([=]() {
//             ifstream in(inputFile);
//             ofstream out(chunkFile, ios::binary);

//             if (!in || !out) {
//                 cerr << "Error - splitAndProcessTextFile: opening chunk files." << endl;
//                 return;
//             }

//             string line;
//             uint64_t lineNum = 0;
//             while (getline(in, line)) {
//                 if (lineNum >= myStartLine && lineNum < myEndLine) {
//                     vector<string> tokens = processLineChar(line);
//                     vector<uint8_t> lineCodeWords = convertStringToCodeWord(tokens);
//                     out.write(reinterpret_cast<const char*>(lineCodeWords.data()), lineCodeWords.size());
//                 }
//                 lineNum++;
//                 if (lineNum >= myEndLine) break;
//             }

//             in.close();
//             out.close();
//         });

//         currentStartLine = myEndLine;
//     }

//     // Wait for threads
//     for (auto &t : threads) {
//         t.join();
//     }

//     mergeBinaryFiles(tempFiles, outputFile);
//     cout << "Encoding completed and merged into " << outputFile << endl;

//     return 0;
// }


// -------- Decompression ----------
// **** codeWord (Binary) to Text File ****

// Function to merge text files in order
void mergeTextFiles(const vector<string> &tempFiles, const string &outputFile)
{
    lock_guard<mutex> lock(fileMutex); // Lock before merging files
    ofstream outFile(outputFile);
    if (!outFile)
    {
        cerr << "Error - mergeTextFiles: creating merged output file: " << outputFile << endl;
        return;
    }

    for (const auto &tempFile : tempFiles)
    {
        ifstream inFile(tempFile);
        if (!inFile)
        {
            cerr << "Error - mergeTextFiles: opening temp file: " << tempFile << endl;
            continue;
        }

        outFile << inFile.rdbuf(); // Append to final output
        inFile.close();
        std::remove(tempFile.c_str()); // Delete and remove temporary file
    }
    outFile.close();
    // cout << "Text files merged into " << outputFile << endl;
}

// Function to split a binary file into chunks and process them

// Version 1
// ---------------------------------------------------------------------------
// D-14: certified restart-atomic split points for multi-threaded decompression.
//
// A raw byte value is NEVER evidence that a split point is safe. The previous
// heuristic scanned for bytes matching (c & 0xFE) == 0x00 || (c & 0xFE) == 0x02,
// which accepts 0x00-0x03; 0x01 and 0x03 are continuation bytes (always strictly
// inside a codeword), while 0x00/0x02 also occur as terminal bytes of valid
// T2/T3 codewords and as T_S length bytes. That silently corrupted valid data.
//
// An offset is a valid restart point only when BOTH hold:
//   1. it is the first byte of a LOGICAL TIC token, and
//   2. the decoder has no pending NEXT_CAPITAL state there.
//
// Pending-capital semantics, verified by crafted-stream decodes:
//   CAP + dictionary word -> capital consumed
//   CAP + T_S             -> capital consumed/discarded
//   CAP + SPACE           -> NOT cleared
//   CAP + NEWLINE         -> NOT cleared
//
// A multi-frame T_S sequence produced by the post-T42 encoder is ONE logical
// token; no checkpoint may fall inside it. Merging consecutive frames errs on
// the safe side: at worst it skips a candidate, never admits an unsafe one.
//
// The .tic payload is only read here, never modified.
// ---------------------------------------------------------------------------
const uint64_t D14_CHECKPOINT_SPACING = 64ull * 1024ull; // target, not a guarantee

static bool buildSafeRestartOffsets(const string &inputFile,
                                    uint64_t targetSpacing,
                                    vector<uint64_t> &safeOffsets,
                                    uint64_t &payloadLength)
{
    safeOffsets.clear();
    payloadLength = 0;

    ifstream in(inputFile, ios::binary);
    if (!in)
    {
        cerr << "Error - D14 pre-scan: opening input file: " << inputFile << endl;
        return false;
    }
    in.seekg(0, ios::end);
    const streamoff sz = in.tellg();
    if (sz <= 0) return true;                 // empty payload: no checkpoints
    payloadLength = static_cast<uint64_t>(sz);

    // A single T_S frame is at most 1 (length) + 255 (payload) + 1 (END) bytes,
    // so no more than a few hundred contiguous bytes are ever needed at once.
    const size_t BUFSZ = (ticCodec == TIC_CODEC_V2 ? static_cast<size_t>(TIC_MAX_TS_PAYLOAD) + 4096 : static_cast<size_t>(1) << 20);
    vector<uint8_t> buf(BUFSZ);
    uint64_t base = 0;      // absolute offset of buf[0]
    size_t   have = 0;      // valid bytes in buf
    size_t   cur  = 0;      // cursor within buf

    auto refill = [&](uint64_t absPos) -> bool
    {
        in.clear();
        in.seekg(static_cast<streamoff>(absPos));
        in.read(reinterpret_cast<char *>(buf.data()), static_cast<streamsize>(BUFSZ));
        have = static_cast<size_t>(in.gcount());
        base = absPos;
        cur  = 0;
        return have > 0;
    };
    auto need = [&](size_t n) -> bool
    {
        if (have - cur >= n) return true;
        const uint64_t absPos = base + cur;
        if (absPos >= payloadLength) return false;
        if (!refill(absPos)) return false;
        return have - cur >= n;
    };

    if (!refill(0)) return true;

    bool     pendingCapital = false;
    uint64_t nextTarget     = 0;   // forces a checkpoint at offset 0

    while (true)
    {
        const uint64_t tokenStart = base + cur;
        if (tokenStart >= payloadLength) break;

        // Emit only at a logical token start with no pending capital, and only
        // at or after the running target. Spacing is therefore NOT uniform: a
        // long logical token can delay a checkpoint arbitrarily.
        if (!pendingCapital && tokenStart >= nextTarget)
        {
            safeOffsets.push_back(tokenStart);
            nextTarget = tokenStart + targetSpacing;   // measured from the ACTUAL
        }                                              // offset, so drift cannot accumulate

        // ---- one codeword: 7-bit groups, little-endian, LSB = continuation ----
        uint64_t tmpSerial = 0;
        int      count     = 0;
        bool     ok        = true;
        while (true)
        {
            if (!need(1)) { ok = false; break; }
            const uint8_t b = buf[cur++];
            tmpSerial |= (static_cast<uint64_t>(b >> 1) << (7 * count));
            if (b & 1)
            {
                if (++count > 2) { ok = false; break; }   // malformed codeword
            }
            else break;
        }
        if (!ok) break;

        const uint64_t finalSerial =
            tmpSerial + (count == 0 ? 0
                       : (count == 1 ? TWO_BYTE_OFFSET : THREE_BYTE_OFFSET));

        if (finalSerial == NEXT_SPECIAL_CODE)
        {
            if (ticCodec == TIC_CODEC_V2)
            {
                uint64_t L = 0; size_t used = 0;
                if (!need(1)) { ok = false; }
                else
                {
                    need(static_cast<size_t>(TIC_MAX_TS_HEADER_BYTES));
                    if (!ticV2DecodeLength(&buf[cur], have - cur, L, used)) ok = false;
                    else
                    {
                        cur += used;
                        if (!need(static_cast<size_t>(L) + 1)) ok = false;
                        else
                        {
                            cur += static_cast<size_t>(L);
                            if (buf[cur] != END_SPECIAL_BYTE) ok = false; else cur++;
                        }
                    }
                }
                if (!ok) break;
                pendingCapital = false;
                continue;
            }
            // v1: consume every consecutive frame: together they are ONE logical token
            while (true)
            {
                if (!need(1)) { ok = false; break; }
                const size_t len = buf[cur++];
                if (!need(len + 1)) { ok = false; break; }
                cur += len;
                if (buf[cur] != END_SPECIAL_BYTE) { ok = false; break; }
                cur++;
                if (!need(1)) break;                      // stream ends here
                if (buf[cur] == NEXT_SPECIAL_BYTE_D14) { cur++; continue; }
                break;
            }
            if (!ok) break;
            pendingCapital = false;                       // T_S consumes the capital
        }
        else if (finalSerial == NEXT_CAPITAL_CODE)
        {
            pendingCapital = true;
        }
        else if (finalSerial == SPACE_CODE || finalSerial == NEW_LINE_CODE)
        {
            // verified: neither clears a pending capital
        }
        else
        {
            pendingCapital = false;                       // dictionary word consumes it
        }
    }

    // A malformed or truncated tail simply ends the scan; every offset already
    // recorded remains valid, and the final worker still runs to payloadLength.
    return true;
}

uint8_t splitAndProcessBinaryFile(const string &inputFile, const string &outputFile, int numThreads)
{
    ifstream inFile(inputFile, ios::binary);
    if (!inFile)
    {
        cerr << "Error - splitAndProcessBinaryFile: opening input file: " << inputFile << endl;
        return -1;
    }

    inFile.close();
    if (numThreads < 1) numThreads = 1;

    // D-14: certified restart-atomic split points replace the raw-byte heuristic.
    const auto preScanBegin = steady_clock::now();
    vector<uint64_t> safeOffsets;
    uint64_t payloadLength = 0;
    if (!buildSafeRestartOffsets(inputFile, D14_CHECKPOINT_SPACING, safeOffsets, payloadLength))
        return -1;
    const double preScanMs =
        duration_cast<duration<double, milli>>(steady_clock::now() - preScanBegin).count();

    if (payloadLength == 0)   // empty payload -> empty output, no workers
    {
        ofstream emptyOut(outputFile, ios::out | ios::trunc | ios::binary);
        if (!emptyOut)
        {
            cerr << "Error - splitAndProcessBinaryFile: creating output file: " << outputFile << endl;
            return -1;
        }
        return 0;
    }
    if (safeOffsets.empty())
        safeOffsets.push_back(0);   // defensive: offset 0 is always restart-atomic

    // Partition: map each nominal target to the greatest certified checkpoint that
    // does not exceed it, then deduplicate. Coincident targets collapse, so the
    // actual worker count W may be < numThreads -- degrade rather than split unsafely.
    vector<uint64_t> starts;
    starts.push_back(safeOffsets.front());          // always 0
    for (int i = 1; i < numThreads; i++)
    {
        const uint64_t target =
            static_cast<uint64_t>((static_cast<unsigned long long>(i) * payloadLength) / numThreads);
        auto it = upper_bound(safeOffsets.begin(), safeOffsets.end(), target);
        if (it == safeOffsets.begin()) continue;    // no checkpoint at or before target
        const uint64_t candidate = *(it - 1);
        if (candidate > starts.back())
            starts.push_back(candidate);
    }

    vector<thread> threads;
    vector<string> tempFiles;
    const size_t workerCount = starts.size();

    if (const char *verbose = getenv("TIC_D14_VERBOSE"))
    {
        if (verbose[0] && verbose[0] != '0')
            cerr << "[D14] payload=" << payloadLength
                 << " checkpoints=" << safeOffsets.size()
                 << " requested_workers=" << numThreads
                 << " actual_workers=" << workerCount
                 << " prescan_ms=" << preScanMs << endl;
    }

    // Unique per process: temp files live in the CWD, so two concurrent TIC
    // processes would otherwise collide on chunk_<i>.txt.
    const string tempTag = to_string(static_cast<long long>(getpid()));

    for (size_t w = 0; w < workerCount; w++)
    {
        const uint64_t startOffset = starts[w];
        const uint64_t endOffset   = (w + 1 < workerCount) ? starts[w + 1] : payloadLength;

        string chunkFile = "chunk_" + tempTag + "_" + to_string(w) + ".txt";
        tempFiles.push_back(chunkFile);
        threads.emplace_back(Decompression_Function, inputFile,
                             static_cast<streampos>(static_cast<streamoff>(startOffset)),
                             static_cast<streampos>(static_cast<streamoff>(endOffset)),
                             chunkFile);
    }

    for (auto &t : threads)
    {
        t.join();
    }

    mergeTextFiles(tempFiles, outputFile);
    // cout << "Decoding completed and merged into " << outputFile << endl;

    return 0;
}

//-------------------------------------------------------------------------------


// Version 2 - Search 
// ===========================================================================
// TIC lookup (-l): logical-token KMP matcher with location and line reporting.
//
// Replaces the previous matcher, which compared raw compressed BYTES with an
// unsound reset. That produced three defects:
//   D2  false negatives  -- a repeated query prefix caused the scan to resync
//                           mid-token and skip a genuine match start;
//   D3  false positives  -- matching was not constrained to the logical token
//                           sequence, so "of How the" matched the query
//                           "of the";
//   D4  no locations     -- only an aggregate count was computed.
// The parallel splitter additionally scanned raw bytes for boundaries, the
// same class of defect fixed for decompression in D-14.
//
// Semantics implemented here (approved specification):
//   * matching is over LOGICAL tokens, never byte substrings;
//   * matches are token aligned at both ends, leftmost-first, NON-overlapping
//     (the automaton resets to state 0 after a reported match);
//   * T1/T2/T3/T_S/reserved are compared uniformly by token identity;
//   * a multi-frame T_S sequence is ONE logical token;
//   * NEXT_CAPITAL is its own logical token, so a lowercase query matches a
//     capitalised dictionary word (the CAP simply lies outside the match).
// Lookup is read-only: no .tic byte is written or altered.
// ===========================================================================

enum TicTokKind : uint8_t { TK_SPACE = 0, TK_NL = 1, TK_CAP = 2, TK_DICT = 3, TK_TS = 4 };

struct TicLogicalToken
{
    TicTokKind kind = TK_SPACE;
    uint64_t   serial = 0;   // dictionary rank when kind == TK_DICT
    string     payload;      // T_S payload (materialised only when needed)
    uint64_t   cstart = 0;   // compressed offset of the first byte
    uint64_t   cend   = 0;   // one past the last byte  -> span is [cstart, cend)
};

static inline bool ticTokenIdentical(const TicLogicalToken &a, const TicLogicalToken &b)
{
    if (a.kind != b.kind) return false;
    if (a.kind == TK_DICT) return a.serial == b.serial;
    if (a.kind == TK_TS)   return a.payload == b.payload;
    return true;                       // SPACE / NEWLINE / NEXT_CAPITAL
}

// --------------------------------------------------------------------------
// Streaming logical-token reader. Never treats an arbitrary byte as a token
// start: it follows the LSB continuation discipline and skips T_S frames by
// their declared length, exactly as the decoder does.
// --------------------------------------------------------------------------
class TicTokenReader
{
public:
    bool open(const string &path, uint64_t startOffset, bool wantPayload)
    {
        needPayload = wantPayload;
        in.open(path, ios::binary);
        if (!in) return false;
        in.seekg(0, ios::end);
        const streamoff sz = in.tellg();
        if (sz < 0) return false;
        fileLen = static_cast<uint64_t>(sz);
        buf.resize((ticCodec == TIC_CODEC_V2 ? static_cast<size_t>(TIC_MAX_TS_PAYLOAD) + 4096 : static_cast<size_t>(1) << 20));
        return refill(startOffset) || startOffset >= fileLen;
    }
    uint64_t length() const { return fileLen; }

    bool next(TicLogicalToken &t)
    {
        const uint64_t st = base + cur;
        if (st >= fileLen) return false;

        uint64_t tmp = 0; int cnt = 0;
        while (true)
        {
            if (!need(1)) return false;
            const uint8_t b = buf[cur++];
            tmp |= (static_cast<uint64_t>(b >> 1) << (7 * cnt));
            if (b & 1) { if (++cnt > 2) return false; }
            else break;
        }
        const uint64_t ser =
            tmp + (cnt == 0 ? 0 : (cnt == 1 ? TWO_BYTE_OFFSET : THREE_BYTE_OFFSET));

        t.serial = 0;
        t.payload.clear();
        t.cstart = st;

        if (ser == NEXT_SPECIAL_CODE)
        {
            t.kind = TK_TS;
            if (ticCodec == TIC_CODEC_V2)
            {
                // v2: ONE canonical variable-length header, ONE payload, ONE token.
                if (!need(1)) return false;
                need(static_cast<size_t>(TIC_MAX_TS_HEADER_BYTES));
                uint64_t L = 0; size_t used = 0;
                if (!ticV2DecodeLength(&buf[cur], have - cur, L, used)) return false;
                cur += used;
                if (!need(static_cast<size_t>(L) + 1)) return false;
                if (needPayload)
                    t.payload.append(reinterpret_cast<const char *>(&buf[cur]), static_cast<size_t>(L));
                cur += static_cast<size_t>(L);
                if (buf[cur] != END_SPECIAL_BYTE) return false;
                cur++;
                t.cend = base + cur;
                return true;
            }
            // v1: every consecutive frame belongs to ONE logical token
            while (true)
            {
                if (!need(1)) return false;
                const size_t len = buf[cur++];
                if (!need(len + 1)) return false;
                if (needPayload)
                    t.payload.append(reinterpret_cast<const char *>(&buf[cur]), len);
                cur += len;
                if (buf[cur] != END_SPECIAL_BYTE) return false;
                cur++;
                // A logical token is split ONLY by the 255-byte frame cap, so a
                // frame shorter than 255 ENDS it. Two adjacent symbol tokens --
                // "__" is two 1-byte T_S frames -- must not be merged into one.
                if (len != 255) break;
                if (!need(1)) break;
                if (buf[cur] == NEXT_SPECIAL_BYTE_D14) { cur++; continue; }
                break;
            }
        }
        else if (ser == SPACE_CODE)        t.kind = TK_SPACE;
        else if (ser == NEW_LINE_CODE)     t.kind = TK_NL;
        else if (ser == NEXT_CAPITAL_CODE) t.kind = TK_CAP;
        else if (ser == END_SPECIAL_CODE)  return false;   // stray terminator
        else
        {
            // A rank the loaded dictionary cannot produce is malformed: the byte
            // sequence is structurally well formed (the LSB discipline is
            // satisfied) but semantically impossible. Matching compares encoded
            // identity and never consults the dictionary, so without this check
            // such a stream would be searched as if it were valid.
            if (ticMaxValidSerial != 0 && ser > ticMaxValidSerial) return false;
            t.kind = TK_DICT; t.serial = ser;
        }

        t.cend = base + cur;
        return true;
    }

private:
    ifstream in;
    vector<uint8_t> buf;
    uint64_t base = 0, fileLen = 0;
    size_t   have = 0, cur = 0;
    bool     needPayload = false;

    bool refill(uint64_t absPos)
    {
        in.clear();
        in.seekg(static_cast<streamoff>(absPos));
        in.read(reinterpret_cast<char *>(buf.data()), static_cast<streamsize>(buf.size()));
        have = static_cast<size_t>(in.gcount());
        base = absPos; cur = 0;
        return have > 0;
    }
    bool need(size_t n)
    {
        if (have - cur >= n) return true;
        const uint64_t absPos = base + cur;
        if (absPos >= fileLen) return false;
        if (!refill(absPos)) return false;
        return have - cur >= n;
    }
};

// Parse an in-memory codeword buffer (used for the query) into logical tokens.
static bool ticParseTokensFromBytes(const vector<uint8_t> &b, vector<TicLogicalToken> &out)
{
    out.clear();
    size_t i = 0;
    while (i < b.size())
    {
        TicLogicalToken t;
        t.cstart = i;
        uint64_t tmp = 0; int cnt = 0;
        while (true)
        {
            if (i >= b.size()) return false;
            const uint8_t x = b[i++];
            tmp |= (static_cast<uint64_t>(x >> 1) << (7 * cnt));
            if (x & 1) { if (++cnt > 2) return false; }
            else break;
        }
        const uint64_t ser =
            tmp + (cnt == 0 ? 0 : (cnt == 1 ? TWO_BYTE_OFFSET : THREE_BYTE_OFFSET));
        if (ser == NEXT_SPECIAL_CODE)
        {
            t.kind = TK_TS;
            if (ticCodec == TIC_CODEC_V2)
            {
                uint64_t L = 0; size_t used = 0;
                if (!ticV2DecodeLength(&b[i], b.size() - i, L, used)) return false;
                i += used;
                if (i + L >= b.size()) return false;
                t.payload.append(reinterpret_cast<const char *>(&b[i]), static_cast<size_t>(L));
                i += static_cast<size_t>(L);
                if (b[i] != END_SPECIAL_BYTE) return false;
                i++;
                t.cend = i;
                out.push_back(t);
                continue;
            }
            while (true)
            {
                if (i >= b.size()) return false;
                const size_t len = b[i++];
                if (i + len >= b.size()) return false;
                t.payload.append(reinterpret_cast<const char *>(&b[i]), len);
                i += len;
                if (b[i] != END_SPECIAL_BYTE) return false;
                i++;
                if (len != 255) break;              // see TicTokenReader::next
                if (i < b.size() && b[i] == NEXT_SPECIAL_BYTE_D14) { i++; continue; }
                break;
            }
        }
        else if (ser == SPACE_CODE)        t.kind = TK_SPACE;
        else if (ser == NEW_LINE_CODE)     t.kind = TK_NL;
        else if (ser == NEXT_CAPITAL_CODE) t.kind = TK_CAP;
        else if (ser == END_SPECIAL_CODE)  return false;
        else { t.kind = TK_DICT; t.serial = ser; }
        t.cend = i;
        out.push_back(t);
    }
    return true;
}

// --------------------------------------------------------------------------
// Result record. Spans are HALF-OPEN: [t_start, t_end) and [c_start, c_end).
// Token indices are 0-based; line numbers are 1-BASED.
// --------------------------------------------------------------------------
struct TicLookupMatch
{
    uint64_t t_start, t_end;
    uint64_t c_start, c_end;
    uint64_t start_line, end_line;
};

// Safe restart checkpoint for lookup. Decompression needed only the offset,
// because a decompression worker just emits plaintext and concatenation
// restores order -- it never needs to know where it is. Lookup must report
// ABSOLUTE token indices and ABSOLUTE line numbers, and both are prefix
// quantities over the whole stream, so a worker has to be seeded with them.
struct TicLookupCheckpoint
{
    uint64_t compressed_offset;
    uint64_t token_index;      // logical tokens fully emitted before this offset
    uint64_t newline_prefix;   // NEWLINE tokens consumed before this offset
};

static bool ticBuildLookupCheckpoints(const string &path, uint64_t spacing,
                                      vector<TicLookupCheckpoint> &cps,
                                      uint64_t &payloadLength,
                                      uint64_t *parsedEnd)
{
    if (parsedEnd) *parsedEnd = 0;
    cps.clear();
    TicTokenReader rd;
    if (!rd.open(path, 0, false)) { payloadLength = 0; return false; }
    payloadLength = rd.length();
    if (payloadLength == 0) return true;

    // A lookup worker needs only a LOGICAL TOKEN BOUNDARY: NEXT_CAPITAL is itself
    // a token here, so a matcher starting just after one still sees exactly the
    // same token identities, and a match whose first token is that CAP is owned
    // by the previous worker (which holds it and has forward halo). The stricter
    // D-14 restart-atomic rule -- token boundary AND no pending capital -- is
    // reused anyway so the codebase keeps ONE notion of a safe restart point. It
    // costs almost nothing: on prose ~95% of token starts still qualify.
    uint64_t idx = 0, newlines = 0, nextTarget = 0;
    bool pendingCapital = false;
    TicLogicalToken t;
    while (rd.next(t))
    {
        if (!pendingCapital && t.cstart >= nextTarget)
        {
            cps.push_back({t.cstart, idx, newlines});
            nextTarget = t.cstart + spacing;
        }
        if (t.kind == TK_NL) newlines++;
        if (t.kind == TK_CAP) pendingCapital = true;
        else if (t.kind == TK_DICT || t.kind == TK_TS) pendingCapital = false;
        idx++;
        if (parsedEnd) *parsedEnd = t.cend;      // last byte the parser accepted
    }
    return true;
}

// --------------------------------------------------------------------------
// Shared malformed-stream gate.
//
// The pre-scan parses the WHOLE payload to place safe restart checkpoints. If it
// could not reach the end, the stream is malformed and no operation may report a
// normal result over the prefix it happened to understand: a caller cannot tell
// such a result from a genuine one. Both -l and -r use this single check so they
// reject exactly the same byte streams.
// --------------------------------------------------------------------------
static bool ticStreamFullyParsed(uint64_t payloadLength, uint64_t parsedEnd,
                                 const char *op)
{
    if (payloadLength == 0 || parsedEnd == payloadLength) return true;
    cerr << "Error - " << op << ": MALFORMED_STREAM -- parser stopped at byte "
         << parsedEnd << " of " << payloadLength
         << "; refusing to report a result over a partially parsed stream" << endl;
    return false;
}

// --------------------------------------------------------------------------
// KMP over logical tokens for one worker range.
//
// Ownership: a match belongs to the worker whose PRIMARY range contains the
// first logical token of that match. A worker may read a forward halo of at
// most m-1 logical tokens past its primary end to finish a match it owns, and
// must not report a match that starts in that halo.
// --------------------------------------------------------------------------
static bool ticLookupRange(const string &path,
                           uint64_t cBegin, uint64_t cPrimaryEnd,
                           uint64_t baseTokenIndex, uint64_t baseLine,
                           const vector<TicLogicalToken> &P,
                           const vector<size_t> &pi,
                           const vector<uint64_t> &N,
                           const vector<uint64_t> &Cb,
                           vector<TicLookupMatch> &out,
                           string &err)
{
    const size_t m = P.size();
    if (m == 0) { err = "empty query"; return false; }

    bool wantPayload = false;
    for (size_t k = 0; k < m; k++) if (P[k].kind == TK_TS) wantPayload = true;

    TicTokenReader rd;
    if (!rd.open(path, cBegin, wantPayload)) { err = "cannot open input"; return false; }

    vector<uint64_t> ringC(m), ringL(m);       // last m token starts / lines
    uint64_t idx  = baseTokenIndex;            // index of the token being read
    uint64_t line = baseLine;                  // line CONTAINING that token
    size_t   j    = 0;
    uint64_t haloLeft = UINT64_MAX;

    TicLogicalToken t;
    while (rd.next(t))
    {
        if (t.cstart >= cPrimaryEnd)
        {
            if (haloLeft == UINT64_MAX)
                haloLeft = (m > 0 ? m - 1 : 0);
            if (haloLeft == 0) break;
            haloLeft--;
        }

        ringC[idx % m] = t.cstart;
        ringL[idx % m] = line;

        while (j > 0 && !ticTokenIdentical(t, P[j])) j = pi[j - 1];
        if (ticTokenIdentical(t, P[j])) j++;

        // NEWLINE belongs to the line it terminates: advance AFTER consuming.
        if (t.kind == TK_NL) line++;
        const uint64_t myIdx = idx;
        idx++;

        if (j == m)
        {
            const uint64_t tEnd   = myIdx + 1;
            const uint64_t tStart = tEnd - m;
            const uint64_t cEnd   = t.cend;

            // Primary: static per-query prefix tables.
            const uint64_t cStartF = cEnd - Cb[m];
            const uint64_t sLineF  = line - N[m];
            const uint64_t eLineF  = sLineF + N[m - 1];
            // Self-check against the observed ring buffer. These must agree;
            // if they ever do not, the formula assumption is wrong and we stop
            // rather than emit a plausible-looking wrong location.
            const uint64_t cStartR = ringC[tStart % m];
            const uint64_t sLineR  = ringL[tStart % m];
            const uint64_t eLineR  = ringL[(tEnd - 1) % m];
            if (cStartF != cStartR || sLineF != sLineR || eLineF != eLineR)
            {
                err = "internal: lookup location self-check failed at token "
                    + to_string(tStart);
                return false;
            }

            if (cStartR < cPrimaryEnd)          // ownership
                out.push_back({tStart, tEnd, cStartR, cEnd, sLineR, eLineR});

            j = 0;                              // non-overlapping
        }
    }
    return true;
}

// --------------------------------------------------------------------------
// Driver: build the query token sequence, the KMP tables, the safe checkpoint
// table, partition, run workers, and emit results in stream order.
// --------------------------------------------------------------------------
const uint64_t TIC_LOOKUP_CHECKPOINT_SPACING = 64ull * 1024ull;

static bool ticBuildQueryTokens(const string &searchString,
                                vector<TicLogicalToken> &P, string &err,
                                vector<uint8_t> *encodedOut)
{
    if (searchString.empty()) { err = "QUERY_EMPTY"; return false; }

    // Encode the query through the SAME encoder path the stream used, then parse
    // it with the same logical-token parser. That guarantees identical token
    // identity semantics instead of re-deriving the tokenizer here.
    //
    // processLineChar() has no case for 0x0A -- it is only ever handed one line
    // -- so a multi-line query could not express a NEWLINE token and never
    // matched. It is shared with -r, which this task must not touch, so the
    // query is split on newlines here and a NEWLINE token is interleaved
    // explicitly. Each segment still goes through the unmodified encoder path.
    vector<uint8_t> q;
    P.clear();
    size_t segBegin = 0;
    while (true)
    {
        const size_t nl = searchString.find('\n', segBegin);
        const string seg = searchString.substr(segBegin,
                              nl == string::npos ? string::npos : nl - segBegin);
        if (!seg.empty())
        {
            vector<uint8_t> part = convertSearchStringToCodeWord(processLineChar(seg));
            vector<TicLogicalToken> partTokens;
            if (!ticParseTokensFromBytes(part, partTokens))
            { err = "QUERY_MALFORMED"; return false; }
            const size_t segBase = q.size();
            for (auto &t : partTokens)
            {
                t.cstart += segBase;   // shift, never overwrite: the byte LENGTH
                t.cend   += segBase;   // (cend - cstart) feeds the Cb[] table
                P.push_back(t);
            }
            q.insert(q.end(), part.begin(), part.end());
        }
        if (nl == string::npos) break;
        TicLogicalToken nlTok;
        nlTok.kind = TK_NL;
        nlTok.cstart = q.size();
        nlTok.cend = q.size() + 1;
        P.push_back(nlTok);
        q.push_back(static_cast<uint8_t>(Shift_Left_with_Zero_Inserted(NEW_LINE_CODE)));
        segBegin = nl + 1;
    }
    if (P.empty()) { err = "QUERY_EMPTY"; return false; }
    if (encodedOut) *encodedOut = q;      // Enc(R) for the splice pass; encoded once

    // Optional conformance mode for HW/SW comparison. Off by default: software
    // lookup supports arbitrary practical query lengths. Never truncates.
    if (const char *mt = getenv("TIC_LOOKUP_MAX_TOKENS"))
    {
        const unsigned long lim = strtoul(mt, nullptr, 10);
        if (lim && P.size() > lim)
        { err = "QUERY_TOO_LONG: " + to_string(P.size()) + " logical tokens > limit "
              + to_string(lim); return false; }
    }
    if (const char *mb = getenv("TIC_LOOKUP_MAX_QUERY_BYTES"))
    {
        const unsigned long lim = strtoul(mb, nullptr, 10);
        if (lim && q.size() > lim)
        { err = "QUERY_TOO_LONG: " + to_string(q.size()) + " encoded bytes > limit "
              + to_string(lim); return false; }
    }
    return true;
}

uint8_t splitAndProcessBinaryFileForSearch(const string &inputFile, const string &outputFile,
                                           int numThreads, string searchString)
{
    if (numThreads < 1) numThreads = 1;

    string err;
    vector<TicLogicalToken> P;
    if (!ticBuildQueryTokens(searchString, P, err, nullptr))
    { cerr << "Error - lookup: " << err << endl; return -1; }
    const size_t m = P.size();

    // KMP failure function over LOGICAL TOKENS.
    vector<size_t> pi(m, 0);
    for (size_t i = 1, k = 0; i < m; i++)
    {
        while (k > 0 && !ticTokenIdentical(P[i], P[k])) k = pi[k - 1];
        if (ticTokenIdentical(P[i], P[k])) k++;
        pi[i] = k;
    }
    // Static per-query prefix tables.
    //   N[j]  = NEWLINE tokens in P[0..j-1]        -> start_line = line_after - N[m]
    //   Cb[j] = encoded bytes of P[0..j-1]         -> c_start    = c_end - Cb[m]
    vector<uint64_t> N(m + 1, 0), Cb(m + 1, 0);
    for (size_t j = 0; j < m; j++)
    {
        N[j + 1]  = N[j] + (P[j].kind == TK_NL ? 1 : 0);
        Cb[j + 1] = Cb[j] + (P[j].cend - P[j].cstart);
    }

    const auto preScanBegin = steady_clock::now();
    vector<TicLookupCheckpoint> cps;
    uint64_t payloadLength = 0;
    uint64_t parsedEnd = 0;
    if (!ticBuildLookupCheckpoints(inputFile, TIC_LOOKUP_CHECKPOINT_SPACING, cps, payloadLength, &parsedEnd))
    { cerr << "Error - lookup: pre-scan failed on " << inputFile << endl; return -1; }

    // Reject before any worker runs, any result file is written, and any
    // MATCHES= line is printed -- a partial match list must never be mistaken
    // for a valid zero-match answer.
    if (!ticStreamFullyParsed(payloadLength, parsedEnd, "lookup")) return -1;
    const double preScanMs =
        duration_cast<duration<double, milli>>(steady_clock::now() - preScanBegin).count();

    // scan_ms: the in-process parallel lookup. It starts here, once the
    // checkpoint table and the compiled query are both available, and stops
    // once every worker has joined and `all` holds the ordered match list.
    // It therefore covers partitioning, thread creation, the worker scans and
    // their per-worker file opens, halo handling, in-memory record creation,
    // line-number computation, join, and the merge into stream order. It does
    // NOT cover process startup, dictionary loading, the pre-scan, query
    // compilation, or writing the TSV. Diagnostic only: nothing below reads it.
    const auto scanBegin = steady_clock::now();

    vector<TicLookupMatch> all;
    size_t workerCount = 0;

    if (payloadLength > 0 && !cps.empty())
    {
        // Partition on certified checkpoints; coincident targets collapse, so the
        // actual worker count may be below the request. Never split unsafely.
        vector<size_t> starts(1, 0);
        for (int i = 1; i < numThreads; i++)
        {
            const uint64_t target =
                static_cast<uint64_t>((static_cast<unsigned long long>(i) * payloadLength) / numThreads);
            size_t lo = 0, hi = cps.size();
            while (lo < hi) { size_t mid = (lo + hi) / 2;
                              if (cps[mid].compressed_offset <= target) lo = mid + 1; else hi = mid; }
            if (lo == 0) continue;
            if (lo - 1 > starts.back()) starts.push_back(lo - 1);
        }
        workerCount = starts.size();

        vector<vector<TicLookupMatch>> parts(workerCount);
        vector<string> errs(workerCount);
        vector<char> okv(workerCount, 1);
        vector<thread> ths;
        for (size_t w = 0; w < workerCount; w++)
        {
            const TicLookupCheckpoint &cp = cps[starts[w]];
            const uint64_t endOff = (w + 1 < workerCount)
                                  ? cps[starts[w + 1]].compressed_offset : payloadLength;
            ths.emplace_back([&, w, cp, endOff]() {
                okv[w] = ticLookupRange(inputFile, cp.compressed_offset, endOff,
                                        cp.token_index, cp.newline_prefix + 1,
                                        P, pi, N, Cb, parts[w], errs[w]) ? 1 : 0;
            });
        }
        for (auto &t : ths) t.join();
        for (size_t w = 0; w < workerCount; w++)
            if (!okv[w]) { cerr << "Error - lookup worker " << w << ": " << errs[w] << endl; return -1; }
        for (size_t w = 0; w < workerCount; w++)
            all.insert(all.end(), parts[w].begin(), parts[w].end());
    }

    const double scanMs =
        duration_cast<duration<double, milli>>(steady_clock::now() - scanBegin).count();

    // Results in stream order, one record per match. No deduplication by line.
    ofstream out(outputFile, ios::out | ios::trunc);
    if (!out) { cerr << "Error - lookup: creating output file: " << outputFile << endl; return -1; }
    out << "# start_token_index\tend_token_index\tcompressed_start\tcompressed_end\tstart_line\tend_line\n";
    for (const auto &r : all)
        out << r.t_start << '\t' << r.t_end << '\t' << r.c_start << '\t'
            << r.c_end << '\t' << r.start_line << '\t' << r.end_line << '\n';
    out.close();

    cout << "MATCHES=" << all.size() << endl;
    if (const char *v = getenv("TIC_LOOKUP_VERBOSE"))
        if (v[0] && v[0] != '0')
            cerr << "[LOOKUP] payload=" << payloadLength
                 << " query_tokens=" << m
                 << " checkpoints=" << cps.size()
                 << " requested_workers=" << numThreads
                 << " actual_workers=" << workerCount
                 << " matches=" << all.size()
                 << " prescan_ms=" << preScanMs
                 << " scan_ms=" << scanMs << endl;
    return 0;
}



// ----------------------------------------------------------

// // Version 1 - Replace
// // Function to split a binary file into chunks and process them
// ===========================================================================
// TIC lookup-and-replace (-r): span-driven splice built on the validated lookup.
//
// The previous implementation interleaved matching with output emission, so a
// matcher error became byte corruption (defect D1: a failed partial match
// silently deleted its consumed prefix, and a ZERO-match replace destroyed a
// 2.3 MB stream). That coupling is removed here by construction:
//
//     compressed input -> validated lookup matcher -> ordered match spans
//                      -> splice pass -> compressed output
//
// The splice pass performs NO matching. It copies input bytes verbatim and
// substitutes Enc(R) over each span, so:
//   * bytes outside a replaced span are copied byte-for-byte, never re-encoded;
//   * zero matches yields a byte-identical copy of the input -- by construction,
//     not as an invariant something must maintain.
// Replacement text is never re-scanned, so there is no cascading replacement.
// Reported locations are always ORIGINAL INPUT locations.
// ===========================================================================

struct TicReplaceWorkerResult
{
    uint64_t input_start = 0, input_end = 0;   // this worker's primary INPUT range
    vector<uint8_t> output_buffer;             // variable length, concatenated in input order
    size_t matches_owned = 0;
};

// Splice one input range using the GLOBAL ordered span list. Overhang from a
// predecessor's match is resolved from the span list itself -- no messaging.
static bool ticSpliceRange(const string &path,
                           uint64_t inStart, uint64_t inEnd,
                           const vector<TicLookupMatch> &spans,
                           const vector<uint8_t> &encR,
                           TicReplaceWorkerResult &res, string &err)
{
    ifstream in(path, ios::binary);
    if (!in) { err = "cannot open input"; return false; }
    if (inEnd > inStart) res.output_buffer.reserve(static_cast<size_t>(inEnd - inStart));

    // A match owned by an EARLIER range may extend into this one; its bytes were
    // already consumed there, so start after it.
    uint64_t cursor = inStart;
    for (const auto &sp : spans)
    {
        if (sp.c_start >= inStart) break;
        if (sp.c_end > cursor) cursor = sp.c_end;
    }

    // One buffer per worker, not per span: spans are in increasing order and the
    // copy is always forward, so the stream stays positioned and no seek is
    // needed between consecutive copies. Allocating inside the lambda made the
    // splice cost scale with the MATCH COUNT rather than the byte count.
    const size_t CH = 1u << 20;
    vector<char> buf(CH);
    uint64_t streamPos = UINT64_MAX;          // where `in` is currently positioned

    auto copyRange = [&](uint64_t from, uint64_t to) -> bool
    {
        if (to <= from) return true;
        if (streamPos != from)
        {
            in.clear();
            in.seekg(static_cast<streamoff>(from));
            streamPos = from;
        }
        uint64_t left = to - from;
        while (left > 0)
        {
            const size_t want = static_cast<size_t>(min<uint64_t>(static_cast<uint64_t>(CH), left));
            in.read(buf.data(), static_cast<streamsize>(want));
            const size_t got = static_cast<size_t>(in.gcount());
            if (got == 0) return false;
            res.output_buffer.insert(res.output_buffer.end(), buf.begin(), buf.begin() + got);
            left -= got;
            streamPos += got;
        }
        return true;
    };

    for (const auto &sp : spans)
    {
        if (sp.c_start < inStart) continue;      // owned by an earlier range
        if (sp.c_start >= inEnd)  break;         // owned by a later range
        if (!copyRange(cursor, sp.c_start)) { err = "short read before span"; return false; }
        res.output_buffer.insert(res.output_buffer.end(), encR.begin(), encR.end());
        cursor = sp.c_end;                       // replacement is never re-scanned
        res.matches_owned++;
    }
    // Tail. If a match owned here overhangs inEnd, cursor > inEnd and the next
    // range starts after it, so nothing is copied twice or lost.
    if (cursor < inEnd && !copyRange(cursor, inEnd)) { err = "short read in tail"; return false; }

    res.input_start = inStart;
    res.input_end   = inEnd;
    return true;
}

uint8_t splitAndProcessBinaryFileForSearchAndReplace(const string &inputFile, const string &outputFile,
                                                     int numThreads, string searchString,
                                                     string replaceString)
{
    if (numThreads < 1) numThreads = 1;
    string err;

    // ---- query and replacement, each encoded exactly once -------------------
    vector<TicLogicalToken> P;
    if (!ticBuildQueryTokens(searchString, P, err, nullptr))
    { cerr << "Error - replace: query: " << err << endl; return -1; }
    const size_t m = P.size();

    vector<uint8_t> encR;
    if (replaceString.empty())
    {
        encR.clear();                            // deletion is a legal replacement
    }
    else
    {
        vector<TicLogicalToken> Rtok;
        if (!ticBuildQueryTokens(replaceString, Rtok, err, &encR))
        { cerr << "Error - replace: replacement: " << err << endl; return -1; }
    }

    // ---- KMP tables over the query's logical tokens -------------------------
    vector<size_t> pi(m, 0);
    for (size_t i = 1, k = 0; i < m; i++)
    {
        while (k > 0 && !ticTokenIdentical(P[i], P[k])) k = pi[k - 1];
        if (ticTokenIdentical(P[i], P[k])) k++;
        pi[i] = k;
    }
    vector<uint64_t> N(m + 1, 0), Cb(m + 1, 0);
    for (size_t j = 0; j < m; j++)
    {
        N[j + 1]  = N[j] + (P[j].kind == TK_NL ? 1 : 0);
        Cb[j + 1] = Cb[j] + (P[j].cend - P[j].cstart);
    }

    // ---- safe restart checkpoints ------------------------------------------
    const auto preScanBegin = steady_clock::now();
    vector<TicLookupCheckpoint> cps;
    uint64_t payloadLength = 0;
    uint64_t parsedEnd = 0;
    if (!ticBuildLookupCheckpoints(inputFile, TIC_LOOKUP_CHECKPOINT_SPACING, cps, payloadLength, &parsedEnd))
    { cerr << "Error - replace: pre-scan failed on " << inputFile << endl; return -1; }

    // Same gate as -l: a malformed stream must fail loudly, before any output
    // file is created. Emitting the part the parser understood would be silent
    // data loss -- the failure mode the -r rewrite exists to remove.
    if (!ticStreamFullyParsed(payloadLength, parsedEnd, "replace")) return -1;
    const double preScanMs =
        duration_cast<duration<double, milli>>(steady_clock::now() - preScanBegin).count();

    // ---- partition on certified checkpoints (never raw-byte splits) ---------
    vector<size_t> startIdx(1, 0);
    if (payloadLength > 0 && !cps.empty())
    {
        for (int i = 1; i < numThreads; i++)
        {
            const uint64_t target =
                static_cast<uint64_t>((static_cast<unsigned long long>(i) * payloadLength) / numThreads);
            size_t lo = 0, hi = cps.size();
            while (lo < hi) { size_t mid = (lo + hi) / 2;
                              if (cps[mid].compressed_offset <= target) lo = mid + 1; else hi = mid; }
            if (lo == 0) continue;
            if (lo - 1 > startIdx.back()) startIdx.push_back(lo - 1);
        }
    }
    const size_t workerCount = (payloadLength == 0 || cps.empty()) ? 0 : startIdx.size();

    // ---- PHASE 1: authoritative match spans, via the validated matcher ------
    const auto lookupBegin = steady_clock::now();
    vector<TicLookupMatch> spans;
    if (workerCount > 0)
    {
        vector<vector<TicLookupMatch>> parts(workerCount);
        vector<string> errs(workerCount);
        vector<char> okv(workerCount, 1);
        vector<thread> ths;
        for (size_t w = 0; w < workerCount; w++)
        {
            const TicLookupCheckpoint &cp = cps[startIdx[w]];
            const uint64_t endOff = (w + 1 < workerCount)
                                  ? cps[startIdx[w + 1]].compressed_offset : payloadLength;
            ths.emplace_back([&, w, cp, endOff]() {
                okv[w] = ticLookupRange(inputFile, cp.compressed_offset, endOff,
                                        cp.token_index, cp.newline_prefix + 1,
                                        P, pi, N, Cb, parts[w], errs[w]) ? 1 : 0;
            });
        }
        for (auto &t : ths) t.join();
        for (size_t w = 0; w < workerCount; w++)
            if (!okv[w]) { cerr << "Error - replace (match) worker " << w << ": " << errs[w] << endl; return -1; }
        for (size_t w = 0; w < workerCount; w++)
            spans.insert(spans.end(), parts[w].begin(), parts[w].end());
    }
    const double lookupMs =
        duration_cast<duration<double, milli>>(steady_clock::now() - lookupBegin).count();

    // ---- PHASE 2: splice. No matching happens here. -------------------------
    const auto spliceBegin = steady_clock::now();
    vector<TicReplaceWorkerResult> results(workerCount);
    if (workerCount > 0)
    {
        vector<string> errs(workerCount);
        vector<char> okv(workerCount, 1);
        vector<thread> ths;
        for (size_t w = 0; w < workerCount; w++)
        {
            const uint64_t s0 = cps[startIdx[w]].compressed_offset;
            const uint64_t e0 = (w + 1 < workerCount)
                              ? cps[startIdx[w + 1]].compressed_offset : payloadLength;
            ths.emplace_back([&, w, s0, e0]() {
                okv[w] = ticSpliceRange(inputFile, s0, e0, spans, encR, results[w], errs[w]) ? 1 : 0;
            });
        }
        for (auto &t : ths) t.join();
        for (size_t w = 0; w < workerCount; w++)
            if (!okv[w]) { cerr << "Error - replace (splice) worker " << w << ": " << errs[w] << endl; return -1; }
    }
    const double spliceMs =
        duration_cast<duration<double, milli>>(steady_clock::now() - spliceBegin).count();

    // ---- merge: concatenate per-worker buffers in INPUT order ---------------
    // No temporary files: per-worker in-memory buffers make the old fixed-name
    // chunk_<i>.bin scratch files unnecessary, removing that collision hazard.
    const auto mergeBegin = steady_clock::now();
    ofstream out(outputFile, ios::out | ios::trunc | ios::binary);
    if (!out) { cerr << "Error - replace: creating output file: " << outputFile << endl; return -1; }
    for (const auto &r : results)
        if (!r.output_buffer.empty())
            out.write(reinterpret_cast<const char *>(r.output_buffer.data()),
                      static_cast<streamsize>(r.output_buffer.size()));
    out.close();
    const double mergeMs =
        duration_cast<duration<double, milli>>(steady_clock::now() - mergeBegin).count();

    cout << "MATCHES=" << spans.size() << endl;

    if (const char *v = getenv("TIC_REPLACE_LOCATIONS"))
    {
        // ORIGINAL INPUT locations. They never shift because an earlier
        // replacement changed the output length.
        ofstream loc(v, ios::out | ios::trunc);
        if (loc)
        {
            loc << "# start_token_index\tend_token_index\tcompressed_start\tcompressed_end\tstart_line\tend_line\n";
            for (const auto &sp : spans)
                loc << sp.t_start << '\t' << sp.t_end << '\t' << sp.c_start << '\t'
                    << sp.c_end << '\t' << sp.start_line << '\t' << sp.end_line << '\n';
        }
    }
    if (const char *v = getenv("TIC_REPLACE_VERBOSE"))
        if (v[0] && v[0] != '0')
            cerr << "[REPLACE] payload=" << payloadLength
                 << " query_tokens=" << m
                 << " repl_bytes=" << encR.size()
                 << " checkpoints=" << cps.size()
                 << " requested_workers=" << numThreads
                 << " actual_workers=" << workerCount
                 << " matches=" << spans.size()
                 << " prescan_ms=" << preScanMs
                 << " lookup_ms=" << lookupMs
                 << " splice_ms=" << spliceMs
                 << " merge_ms=" << mergeMs << endl;
    return 0;
}
