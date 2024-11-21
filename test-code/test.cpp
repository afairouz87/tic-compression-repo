#include <iostream>
#include <fstream>
#include <sstream>
#include <random> // correct? 
#include <string>
#include <vector>
#include <cctype> // For std::ispunct

#define TWO_SEVEN pow(2,7) - 1
#define TWO_FOURTEEN pow(2,14) - 1

using namespace std;

void TWO_BYTE_CODE_GENERATOR(uint32_t input);
void THREE_BYTE_CODE_GENERATOR(uint32_t input);

uint8_t Mask_Single_Byte(uint32_t number);
uint32_t Shift_Left_with_One_Inserted(uint32_t number);
uint32_t Shift_Left_with_Zero_Inserted(uint32_t number);
uint32_t Shift_Right_Seven_Positions(uint32_t number);

// Reading a plain text file functions
void processFile(const string &filePath);
vector<string> processLine(const string &line);

char checkStringEndsWithPunctuation(const string &str);
void checkLinesInFile(const string &filePath);
bool endsWithNewline(const string &str);

void writeStringToFile(const string &filePath, const string &line);

int main() {
    // // Define multiple uint8_t variables
    // uint32_t number1 = 0x1a; // Example byte value 1
    // uint32_t number2 = 0x03; // Example byte value 1
    // cout << "number1 = " << hex << number1 << "\n"; // print in hex format
    // cout << "number2 = " << int(number2) << "\n";
    // cout << "number1 & number2 = " << hex << (number1 & number2) << "\n";

    string filePath = "test1.txt"; // Replace with the path to your file

    processFile(filePath);



    // checkLinesInFile(filePath);

    // int tmp = (pow(2,7) - 1);
    // const int TWO_BYTE_MID = tmp << 7;

    // int sum=0;
    // for(int i=7; i<=13; i++)
    //     sum += pow(2,i);
    
    // uint8_t number = pow(2,7)-1;
    // cout << "2^7 + ... + 2^13 = " << sum << endl;
    // cout << "2^7 + ... + 2^13 = " << bitset<16>(sum) << endl;
    // cout << "using sheft operation:\n2^7 + ... + 2^13 = " << (number << 7) << endl;
    // cout << "using define:\n2^7 + ... + 2^13 = " << TWO_BYTE_MID << endl;

    // uint8_t number2 = pow(2,7)-1;

    
    // //uint16_t input_number = pow(2,13) + 7854; // random number
    // uint16_t input_number = pow(2,14) - 2345; // random number
    // TWO_BYTE_CODE_GENERATOR(input_number);

    // cout << endl << endl;
    
    // uint32_t input_number2 = pow(2,21) - 45678; // random number
    // THREE_BYTE_CODE_GENERATOR(input_number2);


    // /*
    // Test Punctuation Characters
    // */
    // string testStr1 = "Hello, world!";
    
    // char result1 = checkStringEndsWithPunctuation(testStr1);
    
    // // Display the results
    // if (result1 != '\0') {
    //     cout << "String 1 ends with punctuation: " << result1 << endl;
    // } else {
    //     cout << "String 1 does not end with punctuation." << endl;
    // }


    // /*
    // Test writing multiple lines of plain text 
    // to a text file, by adding newline characters after each string.
    // */
    // string outputFilePath = "output_text.txt"; // Replace with your desired file path

    // string line1 = "Hello, world! This is a single string.";
    // string line2 = "This is a second line.";

    // writeStringToFile(outputFilePath, line1);
    // writeStringToFile(outputFilePath, line2);

    // cout << "String written to " << outputFilePath << " with a newline at the end." << endl;


    return 0;
}

vector<string> processLine(const string &line) {
    vector<string> result;
    string word;
    bool startsWithUppercase = false; // Flag to indicate if the word starts with an uppercase letter

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
        }

        startsWithUppercase = false;
    }

    // Add the last word if there is any
    if (!word.empty()) {
        result.push_back(word);
    }

    return result;
}

// Function to read a file line by line and process each line
void processFile(const string &filePath) {
    ifstream file(filePath); // Open the file
    if (!file) {
        cerr << "Error opening file: " << filePath << endl;
        return;
    }

    string line;
    while (getline(file, line)) { // Read each line
        vector<string> tokens = processLine(line); // Process the line

        // Output the processed tokens
        // for (const auto &token : tokens) {
        //     cout << "\"" << token << "\" ";
        // }
        for (size_t i = 0; i < tokens.size(); ++i) {
            //cout << "\"" << tokens[i] << "\" "; 
            cout << tokens[i] << endl;
        }
        cout << endl;
    }

    file.close(); // Close the file
}














uint32_t MASK_BYTE = 0x0000007f; // Mask value for the least significant byte (LSB)

/*
'TWO_BYTE_CODE_GENERATOR' function:
Generate a 2-byte code of EPIC algorithm
*/
void TWO_BYTE_CODE_GENERATOR(uint32_t input)
{
    cout << endl << endl;
    cout << "Testing the 'TWO BYTE CODE' generation in EPIC:\n";
    cout << "-----------------------------------------------\n\n";
    cout << "Generate a random number of 14 bits size. (2 sets of 7 bits: 7 x 2 = 14)\n";
    cout << "This random number will be used later from\nthe order of the word in the dictionary.\n\n";

    cout << "Random number generated:\n";
    cout << "DICT_ORDER_NUM = " << bitset<32>(input) << endl; // print 'DICT_ORDER_NUM' as 16-bit
    cout << endl;

    cout << "Generate the mask for the least 7 significant bits (LSb-7):\n";
    cout << "mask1 = " << bitset<32>(MASK_BYTE) << endl; // print the 'mask1' value as 16 bits 
    cout << endl;
    
    cout << "Generate the 1st BYTE CODE:\n";
    cout << "* Mask the DICT_ORDER_NUM with mask1 *\n";
    uint8_t byte1 = Mask_Single_Byte(input); // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    cout << "DICT_ORDER_NUM & mask1 = " << bitset<8>(byte1) << endl; // print the LSb masked value of 'DICT_ORDER_NUM'
    cout << "* shift 'byte1' to the left by 1, and insert '1' as the LSb *\n";
    byte1 = Shift_Left_with_One_Inserted(byte1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    cout << "BYTE CODE 1 = " << bitset<8>(byte1) << endl; // BYTE CODE 1: 'byte1' has the 1st BYTE CODE 
    cout << endl;
    
    cout << "Generate the 2nd BYTE CODE:";
    cout << "* shift 'DICT_ORDER_NUM' to the right by 7 positions *\n";
    uint8_t byte2 = Shift_Right_Seven_Positions(input); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    cout << "DICT_ORDER_NUM shift >> 7 = " << bitset<32>(byte2) << endl; // print the shifted value of 'DICT_ORDER_NUM'
    cout << endl;
    
    byte2 = Shift_Left_with_Zero_Inserted(byte2); // shift 'DICT_ORDER_NUM_shift' to the left by 1 position
    cout << "BYTE CODE 2 = " << bitset<8>(byte2) << endl; // BYTE CODE 2: 'byte2' has the 2nd BYTE CODE 
    cout << endl;

    uint32_t CODEWORD = byte1 | (byte2 << 8);
    cout << "Concatenating byte1 & byte2: " << bitset<32>(CODEWORD) << endl;
    cout << endl;
}


/*
'THREE_BYTE_CODE_GENERATOR' function:
Generate a 3-byte code of EPIC algorithm
*/
void THREE_BYTE_CODE_GENERATOR(uint32_t input)
{
    cout << endl << endl;
    cout << "Testing the 'THREE BYTE CODE' generation in EPIC:\n";
    cout << "-----------------------------------------------\n\n";
    cout << "Generate a random number of 21 bits size. (3 sets of 7 bits: 7 x 3 = 21)\n";
    cout << "This random number will be used later from\nthe order of the word in the dictionary.\n\n";

    cout << "Random number generated:\n";
    cout << "DICT_ORDER_NUM = " << bitset<32>(input) << endl; // print 'DICT_ORDER_NUM' as 16-bit
    cout << endl;

    cout << "Generate the mask for the least 7 significant bits (LSb-7):\n";
    cout << "mask1 = " << bitset<32>(MASK_BYTE) << endl; // print the 'mask1' value as 16 bits 
    cout << endl;
    
    cout << "Generate the 1st BYTE CODE:\n";
    cout << "* Mask the DICT_ORDER_NUM with mask1 *\n";
    uint16_t byte1 = Mask_Single_Byte(input); // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    cout << "DICT_ORDER_NUM & mask1 = " << bitset<8>(byte1) << endl; // print the LSb masked value of 'DICT_ORDER_NUM'
    cout << "* shift 'byte1' to the left by 1, and insert '1' as the LSb *\n";
    byte1 = Shift_Left_with_One_Inserted(byte1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    cout << "BYTE CODE 1 = " << bitset<8>(byte1) << endl; // BYTE CODE 1: 'byte1' has the 1st BYTE CODE 
    cout << endl;
    
    cout << "Generate the 2nd BYTE CODE:";
    cout << "* shift 'DICT_ORDER_NUM' to the right by 7 positions *\n";
    uint32_t input_shitf1 = Shift_Right_Seven_Positions(input); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    cout << "DICT_ORDER_NUM shift >> 7 = " << bitset<32>(input_shitf1) << endl; // print the shifted value of 'DICT_ORDER_NUM'
    uint8_t byte2 = Mask_Single_Byte(input_shitf1); // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    cout << "DICT_ORDER_NUM shift & mask1 = " << bitset<8>(byte2) << endl; // print the LSb masked value of 'DICT_ORDER_NUM'
    cout << "* shift 'byte2' to the left by 1, and insert '1' as the LSb *\n";
    byte2 = Shift_Left_with_One_Inserted(byte2); // shift 'byte2' to the left by 1, and insert '1' as the LSb
    cout << "BYTE CODE 2 = " << bitset<8>(byte2) << endl; // BYTE CODE 2: 'byte2' has the 2nd BYTE CODE 
    cout << endl;

    cout << "Generate the 3rd BYTE CODE:";
    cout << "* shift 'DICT_ORDER_NUM' to the right by 7 positions *\n";
    uint8_t byte3 = Shift_Right_Seven_Positions(input_shitf1); // shift 'DICT_ORDER_NUM' to the right by 7 positions
    cout << "DICT_ORDER_NUM shift >> 7 = " << bitset<8>(byte3) << endl; // print the shifted value of 'DICT_ORDER_NUM'
    cout << endl;
    
    byte3 = byte3 << 1; // shift 'DICT_ORDER_NUM_shift' to the left by 1 position
    cout << "BYTE CODE 3 = " << bitset<8>(byte3) << endl; // BYTE CODE 2: 'byte3' has the 2nd BYTE CODE 
    cout << endl;
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











// *******************************************************************
// *******************************************************************
// *******************************************************************
/* ********** BACKUP functions *********** */

void TWO_BYTE_CODE_GENERATOR_BACKUP(uint16_t input)
{
    cout << endl << endl;
    cout << "Testing the 'TWO BYTE CODE' generation in EPIC:\n";
    cout << "-----------------------------------------------\n\n";
    cout << "Generate a random number of 14 bits size. (2 sets of 7 bits: 7 x 2 = 14)\n";
    cout << "This random number will be used later from\nthe order of the word in the dictionary.\n\n";

    cout << "Random number generated:\n";
    uint16_t DICT_ORDER_NUM = input; 
    cout << "DICT_ORDER_NUM = " << bitset<16>(DICT_ORDER_NUM) << endl; // print 'DICT_ORDER_NUM' as 16-bit
    cout << endl;

    cout << "Generate the mask for the least 7 significant bits (LSb-7):\n";
    uint16_t mask1 = 0x007f; // mask the least significant 7 bits (LSb-7), named as 'mask1'
    cout << "mask1 = " << bitset<16>(mask1) << endl; // print the 'mask1' value as 16 bits 
    cout << endl;
    
    cout << "Generate the 1st BYTE CODE:\n";
    cout << "* Mask the DICT_ORDER_NUM with mask1 *\n";
    uint8_t byte1 = DICT_ORDER_NUM & mask1; // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    cout << "DICT_ORDER_NUM & mask1 = " << bitset<8>(byte1) << endl; // print the LSb masked value of 'DICT_ORDER_NUM'
    cout << "* shift 'byte1' to the left by 1, and insert '1' as the LSb *\n";
    byte1 = (byte1 << 1) | (0x1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    cout << "BYTE CODE 1 = " << bitset<8>(byte1) << endl; // BYTE CODE 1: 'byte1' has the 1st BYTE CODE 
    cout << endl;
    
    cout << "Generate the 2nd BYTE CODE:";
    cout << "* shift 'DICT_ORDER_NUM' to the right by 7 positions *\n";
    uint8_t DICT_ORDER_NUM_shift = DICT_ORDER_NUM >> 7; // shift 'DICT_ORDER_NUM' to the right by 7 positions
    cout << "DICT_ORDER_NUM shift >> 7 = " << bitset<8>(DICT_ORDER_NUM_shift) << endl; // print the shifted value of 'DICT_ORDER_NUM'
    cout << endl;
    
    uint8_t byte2 = DICT_ORDER_NUM_shift << 1; // shift 'DICT_ORDER_NUM_shift' to the left by 1 position
    cout << "BYTE CODE 2 = " << bitset<8>(byte2) << endl; // BYTE CODE 2: 'byte2' has the 2nd BYTE CODE 
    cout << endl;
}


/*
'THREE_BYTE_CODE_GENERATOR' function:
Generate a 3-byte code of EPIC algorithm
*/
void THREE_BYTE_CODE_GENERATOR_BACKUP(uint32_t input)
{
    cout << endl << endl;
    cout << "Testing the 'THREE BYTE CODE' generation in EPIC:\n";
    cout << "-----------------------------------------------\n\n";
    cout << "Generate a random number of 21 bits size. (3 sets of 7 bits: 7 x 3 = 21)\n";
    cout << "This random number will be used later from\nthe order of the word in the dictionary.\n\n";

    cout << "Random number generated:\n";
    uint32_t DICT_ORDER_NUM = input; 
    cout << "DICT_ORDER_NUM = " << bitset<32>(DICT_ORDER_NUM) << endl; // print 'DICT_ORDER_NUM' as 16-bit
    cout << endl;

    cout << "Generate the mask for the least 7 significant bits (LSb-7):\n";
    uint32_t mask1 = 0x007f; // mask the least significant 7 bits (LSb-7), named as 'mask1'
    cout << "mask1 = " << bitset<32>(mask1) << endl; // print the 'mask1' value as 16 bits 
    cout << endl;
    
    cout << "Generate the 1st BYTE CODE:\n";
    cout << "* Mask the DICT_ORDER_NUM with mask1 *\n";
    uint16_t byte1 = DICT_ORDER_NUM & mask1; // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    cout << "DICT_ORDER_NUM & mask1 = " << bitset<8>(byte1) << endl; // print the LSb masked value of 'DICT_ORDER_NUM'
    cout << "* shift 'byte1' to the left by 1, and insert '1' as the LSb *\n";
    byte1 = (byte1 << 1) | (0x1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    cout << "BYTE CODE 1 = " << bitset<8>(byte1) << endl; // BYTE CODE 1: 'byte1' has the 1st BYTE CODE 
    cout << endl;
    
    cout << "Generate the 2nd BYTE CODE:";
    cout << "* shift 'DICT_ORDER_NUM' to the right by 7 positions *\n";
    uint16_t DICT_ORDER_NUM_shift = DICT_ORDER_NUM >> 7; // shift 'DICT_ORDER_NUM' to the right by 7 positions
    cout << "DICT_ORDER_NUM shift >> 7 = " << bitset<32>(DICT_ORDER_NUM_shift) << endl; // print the shifted value of 'DICT_ORDER_NUM'
    uint16_t byte2 = DICT_ORDER_NUM_shift & mask1; // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    cout << "DICT_ORDER_NUM shift & mask1 = " << bitset<8>(byte2) << endl; // print the LSb masked value of 'DICT_ORDER_NUM'
    cout << "* shift 'byte2' to the left by 1, and insert '1' as the LSb *\n";
    byte2 = (byte2 << 1) | (0x1); // shift 'byte2' to the left by 1, and insert '1' as the LSb
    cout << "BYTE CODE 2 = " << bitset<8>(byte2) << endl; // BYTE CODE 2: 'byte2' has the 2nd BYTE CODE 
    cout << endl;

    cout << "Generate the 3rd BYTE CODE:";
    cout << "* shift 'DICT_ORDER_NUM' to the right by 7 positions *\n";
    uint8_t DICT_ORDER_NUM_2nd_shift = DICT_ORDER_NUM_shift >> 7; // shift 'DICT_ORDER_NUM' to the right by 7 positions
    cout << "DICT_ORDER_NUM shift >> 7 = " << bitset<8>(DICT_ORDER_NUM_2nd_shift) << endl; // print the shifted value of 'DICT_ORDER_NUM'
    cout << endl;
    
    uint8_t byte3 = DICT_ORDER_NUM_2nd_shift << 1; // shift 'DICT_ORDER_NUM_shift' to the left by 1 position
    cout << "BYTE CODE 3 = " << bitset<8>(byte3) << endl; // BYTE CODE 2: 'byte3' has the 2nd BYTE CODE 
    cout << endl;
}









//***************************************************** 

/*
To check if C++14 is supported
*/

// #include <iostream>

// int main() {
//     #if __cplusplus >= 201402L
//         std::cout << "C++14 is supported!" << std::endl;
//     #else
//         std::cout << "C++14 is not supported." << std::endl;
//     #endif
//     return 0;
// }
