#include <napi.h>
#include "key_assassin.hpp"
#include "atomizer.hpp"
#include "fingerprint.hpp"

// The Wrapper Function
Napi::String CleanseWrapped(const Napi::CallbackInfo& info) {
    Napi::Env env = info.Env();

    // 1. Validation
    if (info.Length() < 1 || !info[0].IsString()) {
        Napi::TypeError::New(env, "String expected").ThrowAsJavaScriptException();
        return Napi::String::New(env, "");
    }

    // 2. Get arguments from JS (Zero-copy if possible, but N-API usually copies)
    std::string input = info[0].As<Napi::String>().Utf8Value();

    // 3. Call C++ Logic
    // We pass as string_view to avoid internal copies
    std::string output = ECE::KeyAssassin::Cleanse(input);

    // 4. Return to JS
    return Napi::String::New(env, output);
}

// Atomizer Wrapper
Napi::Array AtomizeWrapped(const Napi::CallbackInfo& info) {
    Napi::Env env = info.Env();

    if (info.Length() < 1 || !info[0].IsString()) {
        Napi::TypeError::New(env, "String expected").ThrowAsJavaScriptException();
        return Napi::Array::New(env);
    }

    std::string input = info[0].As<Napi::String>().Utf8Value();
    std::string strategy = "prose";
    if (info.Length() > 1 && info[1].IsString()) {
        strategy = info[1].As<Napi::String>().Utf8Value();
    }

    std::vector<std::string> atoms = ECE::Atomizer::Atomize(input, strategy);

    Napi::Array result = Napi::Array::New(env, atoms.size());
    for (size_t i = 0; i < atoms.size(); i++) {
        result[i] = Napi::String::New(env, atoms[i]);
    }
    
    return result;
}

// Fingerprint Wrapper (Returns BigInt)
Napi::Value FingerprintWrapped(const Napi::CallbackInfo& info) {
    Napi::Env env = info.Env();
    if (info.Length() < 1 || !info[0].IsString()) {
        Napi::TypeError::New(env, "String expected").ThrowAsJavaScriptException();
        return Napi::BigInt::New(env, (uint64_t)0);
    }
    std::string input = info[0].As<Napi::String>().Utf8Value();
    uint64_t hash = ECE::Fingerprint::Generate(input);
    return Napi::BigInt::New(env, hash);
}

// Distance Wrapper (Takes 2 BigInts)
Napi::Value DistanceWrapped(const Napi::CallbackInfo& info) {
    Napi::Env env = info.Env();
    if (info.Length() < 2) {
        Napi::TypeError::New(env, "Two arguments expected").ThrowAsJavaScriptException();
        return Napi::Number::New(env, 64);
    }
    
    bool lossless; 
    // Note: JS BigInt -> C++ uint64_t
    uint64_t a = 0; 
    uint64_t b = 0;

    // Robust casting
    if (info[0].IsBigInt()) a = info[0].As<Napi::BigInt>().Uint64Value(&lossless);
    if (info[1].IsBigInt()) b = info[1].As<Napi::BigInt>().Uint64Value(&lossless);

    int dist = ECE::Fingerprint::Distance(a, b);
    return Napi::Number::New(env, dist);
}

// The Initialization (Like module.exports)
Napi::Object Init(Napi::Env env, Napi::Object exports) {
    exports.Set(Napi::String::New(env, "cleanse"), Napi::Function::New(env, CleanseWrapped));
    exports.Set(Napi::String::New(env, "atomize"), Napi::Function::New(env, AtomizeWrapped));
    exports.Set(Napi::String::New(env, "fingerprint"), Napi::Function::New(env, FingerprintWrapped));
    exports.Set(Napi::String::New(env, "distance"), Napi::Function::New(env, DistanceWrapped));
    return exports;
}

NODE_API_MODULE(ece_native, Init)
