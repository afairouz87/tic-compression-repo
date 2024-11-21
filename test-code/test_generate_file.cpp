#include <iostream>
#include <fstream>
#include <vector>
#include <cstdint>
#include <bitset>
#include <iomanip>

using namespace std;

void printBinaryFile(const string &filePath);
void writeBinaryFile(ofstream *file, const vector<uint8_t> &data);
void writeBinaryFileOLD(const string &filePath, const vector<uint8_t> &data);

int main() {
    // Define multiple uint8_t variables
    uint8_t byte1 = 0xA1; // Example byte value 1
    uint8_t byte2 = 0xB2; // Example byte value 2
    uint8_t byte3 = 0xC3; // Example byte value 3

    // Create a vector to store the concatenated bytes
    //vector<uint8_t> byteBuffer;
    vector<uint8_t> byteBuffer = {0xAB, 0xCD, 0xEF, 0x12, 0x34};
    
    // Add bytes to the buffer
    byteBuffer.push_back(byte1);
    byteBuffer.push_back(byte2);
    byteBuffer.push_back(byte3);

    // Open a binary file to write the concatenated bytes
    string outputFilePath = "output.bin";  // Replace with your binary file path
    
    writeBinaryFileOLD(outputFilePath, byteBuffer);
    
    // ofstream outputFile(outputFilePath, ios::binary);

    // if (!outputFile) {
    //     cerr << "Error opening file for writing!" << endl;
    //     return 1;
    // }

    // // Write the byte buffer to the file
    // outputFile.write(reinterpret_cast<const char*>(byteBuffer.data()), byteBuffer.size());

    // // Close the file
    // outputFile.close();

    // cout << "File generated successfully!" << endl;

    
    printBinaryFile(outputFilePath);

    return 0;
}


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