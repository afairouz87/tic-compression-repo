#include <iostream>

#define TWO_SEVEN pow(2,7) - 1
#define TWO_FOURTEEN pow(2,14) - 1

using namespace std;

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
        Test how to break down the number into two bytes code
    */

    uint16_t number3 = pow(2,10) + 235;
    cout << "number3 = " << bitset<16>(number3) << endl;
    uint16_t mask1 = 0x007f;
    cout << "mask1 = " << bitset<16>(mask1) << endl;
    uint8_t byte1 = number3 & mask1;
    cout << "number3 & mask1 = " << bitset<8>(byte1) << endl;
    byte1 = (byte1 << 1) | (0x1);
    cout << "BYTE CODE 1 = " << bitset<8>(byte1) << endl;
    uint8_t number3_shift = number3 >> 7;
    cout << "number3 shift >> 7 = " << bitset<8>(number3_shift) << endl;



    return 0;
}




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
