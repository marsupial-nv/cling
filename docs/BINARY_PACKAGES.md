# Downloadable Windows 11 and Ubuntu 26.04 archives

This fork's **Downloadable Cling archives** workflow builds its own checked-out
revision, paired with the exact LLVM revision in
`tools/binary-packages/llvm.lock.json`. It creates x86-64 Release archives:

- `cling-windows11-x86_64.zip`: Windows 11 target, built and smoke-tested with
  MSVC on the GitHub `windows-2022` hosted runner (Windows Server 2022).
  This is not a claim of a Windows 11 desktop CI test. GitHub's standard Windows
  11 hosted runners are ARM64; this package is x86-64.
- `cling-ubuntu26.04-x86_64.tar.gz`: built and smoke-tested directly on
  `ubuntu-26.04`. Compatibility with older Ubuntu/glibc versions is not promised.

Builds run on pushes to master and the packaging development branch, or via
manual dispatch once the workflow is on the default branch. The existing upstream
Linux test workflow remains separate. Binary smoke tests are not the full
upstream regression suite.

## Download

Open [the archive workflow](https://github.com/marsupial-nv/cling/actions/workflows/binary-packages.yml),
select a successful run, and download the artifact for your operating system.
GitHub wraps it in an artifact ZIP; extract that wrapper, then extract the
contained platform archive. Each platform archive has a SHA-256 sidecar.
Artifacts expire after 30 days. Successful packaging also publishes a GitHub prerelease.
Manual dispatch accepts windows, linux or all; runtime validation is advisory.

Each archive contains:

- `bin/cling` or `bin/cling.exe`;
- the Cling shared library and Windows import library, plus the built static
  libraries used for embedding;
- matching Cling, Clang and LLVM development headers and generated headers;
- Clang builtin resource headers;
- upstream license notices and a build manifest recording source revisions,
  build host and per-file SHA-256 hashes.

The version is the fork's current development version, not an invented stable
release number. Keep the directory layout intact. Archives do not contain Kit,
a Python extension, or proprietary application binaries.

## Windows 11 use

Install Visual Studio 2022 Build Tools with **Desktop development with C++** and
a Windows SDK. Launch from an **x64 Native Tools Command Prompt for VS 2022** so
the interpreter can find the MSVC standard-library and SDK headers and runtime.
These Microsoft development files are not redistributed in the archive.

```bat
C:\tools\cling-windows11-x86_64\bin\cling.exe
```

For native embedding, use this archive's `include` and `lib` directories with
the same x64 MSVC runtime ABI (`/MD`, Release), and make its `bin` available to
the DLL loader. Do not combine these headers with a different Cling/LLVM build.
The CI embedding smoke test in `tools/binary-packages/embed-smoke.cpp` shows
the tested API. Arbitrary application C++ ABI compatibility is not established.

## Ubuntu 26.04 use

Install the system C++ development toolchain before interpreting C++:

```sh
sudo apt-get install build-essential
./cling-ubuntu26.04-x86_64/bin/cling
```

The package uses the Ubuntu 26.04 system C/C++ runtime. Development headers and
standard libraries from the OS remain prerequisites. It targets native x86-64
CPU compilation; CUDA/NVPTX and ARM builds are outside this workflow's scope.

## Validation and status

Archives are created and uploaded after successful compilation and staging.
CLI and embedding smoke tests run afterward and do not block downloads or
prerelease publication. A downloadable archive may have known runtime failures.
The tests compile against the staged SDK and exercise retained interpreter state,
a native callback, compile-error recovery, C++ exceptions and static destruction.
Build logs, test logs and per-test JUnit XML are uploaded separately, including
on failure. Check the actual run result before treating a package as usable.

The `kit-cling` extension must separately validate a selected archive and pin
its source identity before adopting it. Producing these binaries does not prove
Kit integration or GPU rendering works. Windows 11 desktop validation remains
separate from the Windows Server CI smoke test.

