
// main.cpp
// AAF Embedder: Command-line tool for creating embedded AAF files (audio/video)
// Usage: see README.md

#include <iostream>
#include <string>
#include <fstream>
#include <vector>
#include <AAF.h>

void print_usage() {
    std::cout << "Usage: aaf_embedder [options]\n"
              << "  --audio <file.wav|file.aiff>   Input audio file (WAV or AIFF)\n"
              << "  --video <file.mxf>             Input video file (DNxHD/DNxHR MXF)\n"
              << "  --output <file.aaf>            Output AAF file (optional)\n"
              << "  --mode <audio|video|audiovideo>  Type of AAF to create\n"
              << "  --help                         Show usage\n";
}


// WAV header struct
struct WAVHeader {
    uint16_t audioFormat;
    uint16_t numChannels;
    uint32_t sampleRate;
    uint32_t byteRate;
    uint16_t blockAlign;
    uint16_t bitsPerSample;
    uint32_t dataSize;
};

// Parse WAV header and return PCM data offset
bool parse_wav_header(const std::string& path, WAVHeader& header, size_t& pcm_offset) {
    std::ifstream file(path, std::ios::binary);
    if (!file) return false;
    char riff[4]; file.read(riff, 4);
    if (std::string(riff, 4) != "RIFF") return false;
    file.seekg(20); // skip to format
    file.read(reinterpret_cast<char*>(&header.audioFormat), 2);
    file.read(reinterpret_cast<char*>(&header.numChannels), 2);
    file.read(reinterpret_cast<char*>(&header.sampleRate), 4);
    file.read(reinterpret_cast<char*>(&header.byteRate), 4);
    file.read(reinterpret_cast<char*>(&header.blockAlign), 2);
    file.read(reinterpret_cast<char*>(&header.bitsPerSample), 2);
    // Find "data" chunk
    char chunkId[4];
    uint32_t chunkSize;
    while (file.read(chunkId, 4)) {
        file.read(reinterpret_cast<char*>(&chunkSize), 4);
        if (std::string(chunkId, 4) == "data") {
            header.dataSize = chunkSize;
            pcm_offset = file.tellg();
            return true;
        }
        file.seekg(chunkSize, std::ios::cur);
    }
    return false;
}

// Helper to read PCM data from WAV
std::vector<char> read_pcm_data(const std::string& path, size_t offset, uint32_t dataSize) {
    std::ifstream file(path, std::ios::binary);
    if (!file) throw std::runtime_error("Cannot open file: " + path);
    file.seekg(offset);
    std::vector<char> data(dataSize);
    file.read(data.data(), dataSize);
    return data;
}

void embed_audio(IAAFFile* pFile, const std::string& audio_path) {
    WAVHeader header;
    size_t pcm_offset = 0;
    if (!parse_wav_header(audio_path, header, pcm_offset)) {
        throw std::runtime_error("Failed to parse WAV header: " + audio_path);
    }
    std::vector<char> audio_data = read_pcm_data(audio_path, pcm_offset, header.dataSize);

    std::cout << "WAV Info: "
              << "Channels=" << header.numChannels << ", "
              << "SampleRate=" << header.sampleRate << ", "
              << "BitsPerSample=" << header.bitsPerSample << ", "
              << "DataSize=" << header.dataSize << std::endl;

    // Get AAF header
    IAAFHeader* pHeader = nullptr;
    HRESULT hr = pFile->GetHeader(&pHeader);
    if (FAILED(hr)) throw std::runtime_error("Failed to get AAF header");

    // Create source mob for audio
    IAAFMob* pAudioMob = nullptr;
    hr = pHeader->CreateMob(&pAudioMob);
    if (FAILED(hr)) throw std::runtime_error("Failed to create audio mob");
    pAudioMob->SetName(L"AudioMob");

    // Create audio descriptor
    IAAFWAVEDescriptor* pWaveDesc = nullptr;
    hr = CoCreateInstance(CLSID_AAFWAVEDescriptor, NULL, CLSCTX_INPROC_SERVER, IID_IAAFWAVEDescriptor, (void**)&pWaveDesc);
    if (FAILED(hr)) throw std::runtime_error("Failed to create WAVE descriptor");
    pWaveDesc->SetSummary((aafUInt32)44, (aafDataBuffer)audio_data.data()); // 44 is typical WAV header size
    pWaveDesc->SetSampleRate(header.sampleRate);
    pWaveDesc->SetBitsPerSample(header.bitsPerSample);
    pWaveDesc->SetChannels(header.numChannels);

    // Add descriptor to mob
    IAAFEssenceDescriptor* pEssDesc = nullptr;
    hr = pWaveDesc->QueryInterface(IID_IAAFEssenceDescriptor, (void**)&pEssDesc);
    if (FAILED(hr)) throw std::runtime_error("Failed to get essence descriptor");
    hr = pAudioMob->AppendEssenceDescriptor(pEssDesc);
    if (FAILED(hr)) throw std::runtime_error("Failed to append essence descriptor");

    // Add mob to header
    hr = pHeader->AddMob(pAudioMob);
    if (FAILED(hr)) throw std::runtime_error("Failed to add audio mob");

    // Create essence data
    IAAFEssenceAccess* pEssenceAccess = nullptr;
    hr = pFile->CreateEssence(
        pAudioMob,
        1, // slot ID
        kAAFCodecWAVE,
        kAAFContainerAAF,
        pEssDesc,
        kAAFCompressionEnable,
        &pEssenceAccess
    );
    if (FAILED(hr)) throw std::runtime_error("Failed to create essence");

    // Write PCM samples
    aafUInt32 samplesWritten = 0;
    hr = pEssenceAccess->WriteSamples(
        header.dataSize / (header.bitsPerSample / 8 * header.numChannels), // number of samples
        (aafDataBuffer)audio_data.data(),
        &samplesWritten
    );
    if (FAILED(hr)) throw std::runtime_error("Failed to write samples");

    std::cout << "Embedded audio: " << audio_path << " (" << samplesWritten << " samples)" << std::endl;

    // Release COM objects
    pEssenceAccess->Release();
    pEssDesc->Release();
    pWaveDesc->Release();
    pAudioMob->Release();
    pHeader->Release();
}

void embed_video(IAAFFile* pFile, const std::string& video_path) {
    // Stub for DNxHD/DNxHR video embedding
    std::cout << "[Stub] Embedded video: " << video_path << std::endl;
}

int main(int argc, char* argv[]) {
    std::string audio_file, video_file, output_file, mode;
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--audio" && i + 1 < argc) audio_file = argv[++i];
        else if (arg == "--video" && i + 1 < argc) video_file = argv[++i];
        else if (arg == "--output" && i + 1 < argc) output_file = argv[++i];
        else if (arg == "--mode" && i + 1 < argc) mode = argv[++i];
        else if (arg == "--help") { print_usage(); return 0; }
    }

    if (mode.empty() || (mode == "audio" && audio_file.empty()) ||
        (mode == "video" && video_file.empty()) ||
        (mode == "audiovideo" && (audio_file.empty() || video_file.empty()))) {
        print_usage();
        return 1;
    }

    // If output not specified, use input file name(s)
    if (output_file.empty()) {
        if (!audio_file.empty()) {
            size_t dot = audio_file.find_last_of('.');
            output_file = audio_file.substr(0, dot) + ".aaf";
        } else if (!video_file.empty()) {
            size_t dot = video_file.find_last_of('.');
            output_file = video_file.substr(0, dot) + ".aaf";
        }
    }

    std::cout << "Creating " << mode << " AAF: " << output_file << std::endl;
    if (!audio_file.empty()) std::cout << "  Audio: " << audio_file << std::endl;
    if (!video_file.empty()) std::cout << "  Video: " << video_file << std::endl;

    // Initialize AAF SDK
    HRESULT hr = AAFLoad(NULL);
    if (FAILED(hr)) {
        std::cerr << "Failed to initialize AAF SDK." << std::endl;
        return 1;
    }

    // Create new AAF file
    IAAFFile* pFile = NULL;
    hr = AAFCreateFileWide(
        std::wstring(output_file.begin(), output_file.end()).c_str(),
        kAAFFileExistence_new,
        kAAFFileAccess_modify,
        NULL, // password
        &pFile
    );
    if (FAILED(hr)) {
        std::cerr << "Failed to create AAF file." << std::endl;
        return 1;
    }

    // Embed assets
    try {
        if (mode == "audio" || mode == "audiovideo") {
            embed_audio(pFile, audio_file);
        }
        if (mode == "video" || mode == "audiovideo") {
            embed_video(pFile, video_file);
        }
    } catch (const std::exception& ex) {
        std::cerr << "Error: " << ex.what() << std::endl;
        pFile->Close();
        pFile->Release();
        AAFUnload();
        return 1;
    }

    // Save and close
    hr = pFile->Save();
    if (FAILED(hr)) std::cerr << "Failed to save AAF file." << std::endl;
    pFile->Close();
    pFile->Release();

    // Unload AAF SDK
    AAFUnload();

    std::cout << "AAF file created: " << output_file << std::endl;
    return 0;
}
