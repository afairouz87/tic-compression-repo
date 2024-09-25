#include <iostream>
#include <fstream>
#include <vector>
#include <cstdint>

using namespace std;

int main() {
    // Define multiple uint8_t variables
    uint8_t byte1 = 0xA1; // Example byte value 1
    uint8_t byte2 = 0xB2; // Example byte value 2
    uint8_t byte3 = 0xC3; // Example byte value 3

    // Create a vector to store the concatenated bytes
    vector<uint8_t> byteBuffer;

    // Add the bytes to the buffer
    byteBuffer.push_back(byte1);
    byteBuffer.push_back(byte2);
    byteBuffer.push_back(byte3);

    // Open a binary file to write the concatenated bytes
    ofstream outputFile("output.bin", ios::binary);

    if (!outputFile) {
        cerr << "Error opening file for writing!" << endl;
        return 1;
    }

    // Write the byte buffer to the file
    outputFile.write(reinterpret_cast<const char*>(byteBuffer.data()), byteBuffer.size());

    // Close the file
    outputFile.close();

    cout << "File generated successfully!" << endl;

    return 0;
}
