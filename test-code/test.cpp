#include <iostream>
#include <random> // correct? 

#define TWO_SEVEN pow(2,7) - 1
#define TWO_FOURTEEN pow(2,14) - 1

using namespace std;

void TWO_BYTE_CODE_GENERATOR(uint32_t input);
void THREE_BYTE_CODE_GENERATOR(uint32_t input);

uint8_t Mask_Single_Byte(uint32_t number);
uint32_t Shift_Left_with_One_Inserted(uint32_t number);
uint32_t Shift_Left_with_Zero_Inserted(uint32_t number);
uint32_t Shift_Right_Seven_Positions(uint32_t number);

int main() {
    // // Define multiple uint8_t variables
    // uint32_t number1 = 0x1a; // Example byte value 1
    // uint32_t number2 = 0x03; // Example byte value 1
    // cout << "number1 = " << hex << number1 << "\n"; // print in hex format
    // cout << "number2 = " << int(number2) << "\n";
    // cout << "number1 & number2 = " << hex << (number1 & number2) << "\n";

    int tmp = (pow(2,7) - 1);
    const int TWO_BYTE_MID = tmp << 7;

    int sum=0;
    for(int i=7; i<=13; i++)
        sum += pow(2,i);
    
    uint8_t number = pow(2,7)-1;
    cout << "2^7 + ... + 2^13 = " << sum << endl;
    cout << "2^7 + ... + 2^13 = " << bitset<16>(sum) << endl;
    cout << "using sheft operation:\n2^7 + ... + 2^13 = " << (number << 7) << endl;
    cout << "using define:\n2^7 + ... + 2^13 = " << TWO_BYTE_MID << endl;

    uint8_t number2 = pow(2,7)-1;

    /* 
        ** TWO BYTE CODE **
        Test how to break down the number into two bytes code for Enhanced PIC (EPIC)
    */

    // cout << endl << endl;
    // cout << "Testing the 'TWO BYTE CODE' generation in EPIC:\n";
    // cout << "-----------------------------------------------\n\n";
    // cout << "Generate a random number of 14 bits size.\n";
    // cout << "This random number will be used later from\nthe order of the word in the dictionary.\n\n";
    // uint16_t input_number = pow(2,13) + 7854; // random number 

    // cout << "Random number generated:\n";
    // uint16_t DICT_ORDER_NUM = input_number; 
    // cout << "DICT_ORDER_NUM = " << bitset<16>(DICT_ORDER_NUM) << endl; // print 'DICT_ORDER_NUM' as 16-bit
    // cout << endl;

    // cout << "Generate the mask for the least 7 significant bits (LSb-7):\n";
    // uint16_t mask1 = 0x007f; // mask the least significant 7 bits (LSb-7), named as 'mask1'
    // cout << "mask1 = " << bitset<16>(mask1) << endl; // print the 'mask1' value as 16 bits 
    // cout << endl;
    
    // cout << "Generate the 1st BYTE CODE:\n";
    // cout << "* Mask the DICT_ORDER_NUM with mask1 *\n";
    // uint8_t byte1 = DICT_ORDER_NUM & mask1; // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    // cout << "DICT_ORDER_NUM & mask1 = " << bitset<8>(byte1) << endl; // print the LSb masked value of 'DICT_ORDER_NUM'
    // cout << "* shift 'byte1' to the left by 1, and insert '1' as the LSb *\n";
    // byte1 = (byte1 << 1) | (0x1); // shift 'byte1' to the left by 1, and insert '1' as the LSb
    // cout << "BYTE CODE 1 = " << bitset<8>(byte1) << endl; // BYTE CODE 1: 'byte1' has the 1st BYTE CODE 
    // cout << endl;
    
    // cout << "Generate the 2nd BYTE CODE:";
    // cout << "* shift 'DICT_ORDER_NUM' to the right by 7 positions *\n";
    // uint8_t DICT_ORDER_NUM_shift = DICT_ORDER_NUM >> 7; // shift 'DICT_ORDER_NUM' to the right by 7 positions
    // cout << "DICT_ORDER_NUM shift >> 7 = " << bitset<8>(DICT_ORDER_NUM_shift) << endl; // print the shifted value of 'DICT_ORDER_NUM'
    // cout << endl;
    
    // uint8_t byte2 = DICT_ORDER_NUM_shift << 1; // shift 'DICT_ORDER_NUM_shift' to the left by 1 position
    // cout << "BYTE CODE 2 = " << bitset<8>(byte2) << endl; // BYTE CODE 2: 'byte2' has the 2nd BYTE CODE 
    // cout << endl;


    //uint16_t input_number = pow(2,13) + 7854; // random number
    uint16_t input_number = pow(2,14) - 2345; // random number
    TWO_BYTE_CODE_GENERATOR(input_number);

    cout << endl << endl;
    
    uint32_t input_number2 = pow(2,21) - 45678; // random number
    THREE_BYTE_CODE_GENERATOR(input_number2);

    return 0;
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


// Check if the least significant bit is one.
// If LSbit is '1', then there is another byte code in the sequence.
// This function is used in the decompression process.
uint8_t Next_Byte_Available(uint8_t number){
    return number % 2; // return one or zero.
}


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
void THREE_BYTE_CODE_GENERATOR(uint32_t input)
{
    cout << endl << endl;
    cout << "Testing the 'THREE BYTE CODE' generation in EPIC:\n";
    cout << "-----------------------------------------------\n\n";
    cout << "Generate a random number of 21 bits size. (3 sets of 7 bits: 7 x 3 = 21)\n";
    cout << "This random number will be used later from\nthe order of the word in the dictionary.\n\n";

    cout << "Random number generated:\n";
    uint32_t DICT_ORDER_NUM = input; 
    cout << "DICT_ORDER_NUM = " << bitset<22>(DICT_ORDER_NUM) << endl; // print 'DICT_ORDER_NUM' as 16-bit
    cout << endl;

    cout << "Generate the mask for the least 7 significant bits (LSb-7):\n";
    uint32_t mask1 = 0x007f; // mask the least significant 7 bits (LSb-7), named as 'mask1'
    cout << "mask1 = " << bitset<22>(mask1) << endl; // print the 'mask1' value as 16 bits 
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
    cout << "DICT_ORDER_NUM shift >> 7 = " << bitset<16>(DICT_ORDER_NUM_shift) << endl; // print the shifted value of 'DICT_ORDER_NUM'
    uint16_t byte2 = DICT_ORDER_NUM_shift & mask1; // mask the LSb of 'DICT_ORDER_NUM' using mask1, store it in 'byte1'
    cout << "DICT_ORDER_NUM shift & mask1 = " << bitset<16>(byte2) << endl; // print the LSb masked value of 'DICT_ORDER_NUM'
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
