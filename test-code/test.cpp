#include <iostream>

using namespace std;

int main() {
    // Define multiple uint8_t variables
    uint32_t number1 = 0x1a; // Example byte value 1
    uint32_t number2 = 0x03; // Example byte value 1
    cout << "number1 = " << hex << number1 << "\n"; // print in hex format
    cout << "number2 = " << int(number2) << "\n";
    cout << "number1 & number2 = " << hex << (number1 & number2) << "\n";

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
