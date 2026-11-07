"""Stage and test a relocatable Cling runtime/embedding SDK, then create an archive."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def stage(llvm, build, output, target):
    if output.exists():
        raise RuntimeError(f"Refusing to overwrite {output}")
    output.mkdir(parents=True)
    for relative in ("bin", "lib", "include"):
        (output / relative).mkdir()
    executable = "cling.exe" if os.name == "nt" else "cling"
    copy(build / "bin" / executable, output / "bin" / executable)
    for directory in ("bin", "lib"):
        for path in (build / directory).iterdir():
            if path.is_file() and (path.suffix in (".dll", ".lib", ".a", ".dylib") or ".so" in path.name):
                copy(path, output / directory / path.name)
    for source in (llvm / "llvm/include", llvm / "clang/include", ROOT / "include",
                   build / "include", build / "tools/clang/include", build / "tools/cling/include"):
        shutil.copytree(source, output / "include", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("CMakeFiles", "cmake_install.cmake", "Makefile"))
    shutil.copy2(ROOT / "include/cling/module.modulemap.build", output / "include/cling/module.modulemap")
    resources = list((build / "lib/clang").glob("*/include"))
    if len(resources) != 1:
        raise RuntimeError(f"Expected one compiler resource directory: {resources}")
    shutil.copytree(resources[0], output / "lib/clang" / resources[0].parent.name / "include")
    for name, source in (("Cling", ROOT / "LICENSE.TXT"),
                         ("LLVM", llvm / "llvm/LICENSE.TXT"), ("Clang", llvm / "clang/LICENSE.TXT")):
        copy(source, output / "licenses" / (name + "-LICENSE.TXT"))
    shutil.copy2(ROOT / "docs/BINARY_PACKAGES.md", output / "BINARY_PACKAGES.md")
    receipt = {
        "target": target, "build_host": platform.platform(),
        "runner_image": os.environ.get("ImageVersion"),
        "cling_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "cling_version": (ROOT / "VERSION").read_text().strip(),
        "llvm": json.loads((ROOT / "tools/binary-packages/llvm.lock.json").read_text()),
        "files_sha256": {str(p.relative_to(output)).replace("\\", "/"): digest(p)
                         for p in sorted(output.rglob("*")) if p.is_file()},
    }
    (output / "build-manifest.json").write_text(json.dumps(receipt, indent=2))


def validate(output, evidence):
    evidence.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = str(output / "bin") + os.pathsep + env["PATH"]
    executable = output / "bin" / ("cling.exe" if os.name == "nt" else "cling")
    cases = []
    def check(name, command, expected=None):
        started = time.monotonic()
        try:
            result = subprocess.run([str(c) for c in command], cwd=evidence, env=env,
                                    capture_output=True, text=True, errors="replace", timeout=180)
            log = result.stdout + result.stderr
            code = result.returncode
            passed = code == 0 and (expected is None or expected in result.stdout)
        except (OSError, subprocess.TimeoutExpired) as error:
            log, code, passed = str(error), type(error).__name__, False
        (evidence / (name + ".log")).write_text(log, encoding="utf-8")
        cases.append((name, time.monotonic() - started, passed, code))
        return passed
    check("cli", [executable, "-I" + str(output / "include"),
                  '#include <cstdio>', 'std::puts("CLING_ARCHIVE_PASSED");'], "CLING_ARCHIVE_PASSED")
    probe = evidence / ("embed-smoke.exe" if os.name == "nt" else "embed-smoke")
    source = ROOT / "tools/binary-packages/embed-smoke.cpp"
    if os.name == "nt":
        command = ["cl", "/nologo", "/EHsc", "/MD", "/GR-", "/std:c++17",
                   "/I" + str(output / "include"), source, "/Fe:" + str(probe), "/link",
                   "/LIBPATH:" + str(output / "lib"), "libcling.lib"]
    else:
        command = ["g++", "-std=c++17", "-fno-rtti", source, "-I" + str(output / "include"),
                   "-L" + str(output / "lib"), "-Wl,-rpath," + str(output / "lib"),
                   "-lcling", "-o", probe]
    if check("embedding-build", command):
        check("embedding-runtime", [probe, output], "EMBEDDING_SMOKE_PASSED")
    else:
        cases.append(("embedding-runtime", 0, False, "compile-failed"))
    suite = ET.Element("testsuite", name="cling-archive", tests=str(len(cases)),
                       failures=str(sum(not c[2] and c[3] != "compile-failed" for c in cases)))
    for name, duration, passed, code in cases:
        case = ET.SubElement(suite, "testcase", name=name, time=str(duration))
        if code == "compile-failed":
            ET.SubElement(case, "skipped", message="Embedding compilation failed")
        elif not passed:
            ET.SubElement(case, "failure", message=f"Exit/status {code}; see {name}.log")
    ET.ElementTree(suite).write(evidence / "junit.xml", encoding="utf-8", xml_declaration=True)
    (evidence / "results.json").write_text(json.dumps(cases, indent=2))
    if not all(c[2] for c in cases):
        raise RuntimeError(f"Archive validation failed; see {evidence}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--target", choices=("windows11-x86_64", "ubuntu26.04-x86_64"), required=True)
    args = parser.parse_args()
    if args.target.startswith("ubuntu") and platform.freedesktop_os_release().get("VERSION_ID") != "26.04":
        raise RuntimeError("Ubuntu archive must be built and tested on Ubuntu 26.04")
    if args.target.startswith("windows") and (os.name != "nt" or platform.machine().lower() not in ("amd64", "x86_64")):
        raise RuntimeError("Windows archive requires a Windows x86-64 build host")
    output = ROOT / "_packages" / ("cling-" + args.target)
    stage(args.llvm.resolve(), args.build.resolve(), output, args.target)
    validate(output, ROOT / "_evidence")
    archive = Path(shutil.make_archive(str(output), "zip" if os.name == "nt" else "gztar",
                                      root_dir=output.parent, base_dir=output.name))
    archive.with_name(archive.name + ".sha256").write_text(f"{digest(archive)}  {archive.name}\n")
    print(archive)


if __name__ == "__main__":
    main()

