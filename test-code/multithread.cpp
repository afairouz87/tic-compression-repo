#include <iostream>
#include <fstream>
#include <vector>
#include <thread>
#include <chrono>
#include <sys/stat.h>

using namespace std;
using namespace chrono;

// Function to get file size
size_t getFileSize(const string &filePath) {
    struct stat statBuf;
    if (stat(filePath.c_str(), &statBuf) != 0) {
        cerr << "Error: Cannot determine file size!" << endl;
        return 0;
    }
    return statBuf.st_size;
}

// Function to split the file into multiple streams for parallel processing
vector<ifstream*> splitFileIntoThreads(const string &filePath, size_t &chunkSize, unsigned int &numThreads) {
    size_t fileSize = getFileSize(filePath);
    if (fileSize == 0) {
        cerr << "Error: File is empty or cannot be accessed!" << endl;
        return {};
    }

    // Get the number of system threads
    numThreads = thread::hardware_concurrency();
    if (numThreads == 0) numThreads = 2; // Fallback to 2 if undetectable

    // Calculate chunk size for each thread
    chunkSize = fileSize / numThreads;
    
    // Open multiple file streams
    vector<ifstream*> fileStreams(numThreads);
    for (unsigned int i = 0; i < numThreads; ++i) {
        fileStreams[i] = new ifstream(filePath, ios::binary);
        if (!fileStreams[i]->is_open()) {
            cerr << "Error: Failed to open file!" << endl;
            return {};
        }

        // Move each file pointer to its corresponding chunk
        fileStreams[i]->seekg(i * chunkSize);
    }

    return fileStreams;
}

// Function for each thread to read its chunk
void processChunk(ifstream* fileStream, size_t chunkSize, int threadID) {
    vector<char> buffer(chunkSize);
    
    if (fileStream && fileStream->is_open()) {
        fileStream->read(buffer.data(), chunkSize);
        
        cout << "Thread " << threadID << " read " << fileStream->gcount() << " bytes.\n";
    }
}

// Function to perform **single-threaded reading**
void singleThreadRead(const string &filePath) {
    ifstream file(filePath, ios::binary);
    if (!file.is_open()) {
        cerr << "Error: Failed to open file!" << endl;
        return;
    }

    size_t fileSize = getFileSize(filePath);
    vector<char> buffer(fileSize);
    
    file.read(buffer.data(), fileSize);
    cout << "Single-thread read " << file.gcount() << " bytes.\n";
}

// Function to perform **multi-threaded reading**
void multiThreadRead(const string &filePath) {
    size_t chunkSize;
    unsigned int numThreads;

    // Split the file into multiple file streams
    vector<ifstream*> fileStreams = splitFileIntoThreads(filePath, chunkSize, numThreads);

    if (fileStreams.empty()) {
        cerr << "Error: File splitting failed!" << endl;
        return;
    }

    // Create threads to process each chunk in parallel
    vector<thread> threads;
    for (size_t i = 0; i < fileStreams.size(); ++i) {
        threads.emplace_back(processChunk, fileStreams[i], chunkSize, i);
    }

    // Join all threads
    for (auto &t : threads) {
        t.join();
    }

    // Clean up file streams
    for (auto &fs : fileStreams) {
        if (fs) {
            fs->close();
            delete fs;
        }
    }
}

int main() {
    string filePath = "test1.txt";

    // Measure **Single-threaded execution time**
    auto startSingle = high_resolution_clock::now();
    singleThreadRead(filePath);
    auto endSingle = high_resolution_clock::now();
    auto durationSingle = duration_cast<milliseconds>(endSingle - startSingle);
    cout << "Single-threaded execution time: " << durationSingle.count() << " ms\n\n";

    // Measure **Multi-threaded execution time**
    auto startMulti = high_resolution_clock::now();
    multiThreadRead(filePath);
    auto endMulti = high_resolution_clock::now();
    auto durationMulti = duration_cast<milliseconds>(endMulti - startMulti);
    cout << "Multi-threaded execution time: " << durationMulti.count() << " ms\n";

    return 0;
}
