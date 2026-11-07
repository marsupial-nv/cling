#include <cling/Interpreter/Interpreter.h>
#include <cling/Interpreter/Value.h>
#include <cstdint>
#include <string>
#include <stdexcept>
#include <iostream>

int main(int argc, char** argv) {
    if (argc != 2) return 1;
    int destroyed = 0;
    {
        std::string include = "-I" + std::string(argv[1]) + "/include";
        const char* options[] = {"cling", "-std=c++17", include.c_str()};
        cling::Interpreter interpreter(3, options, argv[1]);
        if (interpreter.declare("#include <vector>\n#include <stdexcept>\nstd::vector<int> values{20,22};")
            != cling::Interpreter::kSuccess) return 2;
        cling::Value value;
        if (interpreter.evaluate("(double)(values[0]+values[1])", value)
            != cling::Interpreter::kSuccess || value.castAs<double>() != 42) return 3;
        auto callback = reinterpret_cast<int(*)(int)>(
            interpreter.compileFunction("archive_smoke", "extern \"C\" int archive_smoke(int n) { return n*2; }"));
        if (!callback || callback(21) != 42) return 4;
        if (interpreter.declare("this is intentionally invalid C++!!!")
            == cling::Interpreter::kSuccess || callback(21) != 42) return 5;
        std::string sentinel = "struct Sentinel { ~Sentinel() { *reinterpret_cast<int*>("
            + std::to_string(reinterpret_cast<std::uintptr_t>(&destroyed))
            + "ULL)=123; } }; Sentinel sentinel;";
        if (interpreter.declare(sentinel) != cling::Interpreter::kSuccess) return 6;
        auto throwing = reinterpret_cast<void(*)()>(interpreter.compileFunction(
            "archive_throw", "extern \"C\" void archive_throw() { throw std::runtime_error(\"expected\"); }"));
        if (!throwing) return 7;
        try { throwing(); return 8; }
        catch (const std::runtime_error& error) {
            if (std::string(error.what()) != "expected") return 9;
        }
    }
    if (destroyed != 123) return 10;
    std::cout << "EMBEDDING_SMOKE_PASSED\n";
}

