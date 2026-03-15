# This file contains utility functions to build CesiumForGodot in SCons
import subprocess
import os
import fnmatch
import sys

from SCons.Script import Dir, ARGUMENTS

ROOT_DIR_MODULE = "#modules/cesium_godot"

ROOT_DIR_EXT = "#cesium_godot"

BINDINGS_DIR = "#godot-cpp"

CESIUM_MODULE_DEF = "CESIUM_GD_MODULE"

CESIUM_EXT_DEF = "CESIUM_GD_EXT"

CESIUM_NATIVE_DIR_EXT = "#cesium_godot/native"

CESIUM_NATIVE_DIR_MODULE = "#modules/cesium_godot/native"

OS_WIN = "nt"

OS_LINUX = "posix"

STATIC_TRIPLET = "x64-windows-static"

RELEASE_CONFIG = "Release"

ezvcpkgFoundPath: str = ""


def is_android_target(argsDict=None):
    """Check if we're building for Android (target platform, not host OS)."""
    if argsDict is None:
        argsDict = ARGUMENTS
    return argsDict.get("platform", "") == "android"


def get_android_ndk_root():
    """Find Android NDK root path."""
    ndk = os.environ.get("ANDROID_NDK_ROOT", os.environ.get("ANDROID_NDK_HOME", ""))
    if ndk and os.path.isdir(ndk):
        return ndk
    # Search common locations
    import glob
    candidates = glob.glob(os.path.expanduser("~/Library/Android/sdk/ndk/*"))
    candidates += glob.glob(os.path.expanduser("~/Android/Sdk/ndk/*"))
    candidates += glob.glob("/opt/android-ndk-*")
    for c in sorted(candidates, reverse=True):
        if os.path.isdir(c):
            return c
    return ""


def get_android_abi(argsDict=None):
    """Get Android ABI from arch argument."""
    if argsDict is None:
        argsDict = ARGUMENTS
    arch = argsDict.get("arch", "arm64")
    if arch in ("arm64", "aarch64"):
        return "arm64-v8a"
    elif arch in ("x86_64", "x64"):
        return "x86_64"
    elif arch in ("arm32", "armv7"):
        return "armeabi-v7a"
    return "arm64-v8a"


def get_compile_flags(argsDict=None):
    if is_android_target(argsDict):
        return ["-std=c++20", "-fexceptions", "-frtti", "-fPIC", "-DFMT_USE_CONSTEVAL=0"]
    if os.name == OS_WIN:
        return ["/std:c++20", "/Zc:__cplusplus", "/utf-8", "/bigobj"]
    elif os.name == OS_LINUX:
        return ["-std=c++20", "-fexceptions", "-fpermissive", "-fPIC"]


def get_linker_flags(argsDict=None):
    if is_android_target(argsDict):
        return []
    if os.name == OS_WIN:
        return ["/IGNORE:4217"]
    return []


def is_extension_target(argsDict) -> bool:
    return get_compile_target_definition(argsDict) == CESIUM_EXT_DEF


def get_curl_lib_name() -> str:
    if os.name == OS_WIN:
        return "libcurl"
    return "curl"


def generate_precision_symbols(argsDict, env):
    print("Generating double precision compile symbols")
    desiredPrecision = argsDict.get("precision")
    if desiredPrecision == "double":
        env.Append(CPPDEFINES=["REAL_T_IS_DOUBLE"])


def get_compile_target_definition(argsDict) -> str:
    # Get the format (default is extension)
    global currentRootDir
    compileTarget = argsDict.get("compileTarget", CESIUM_EXT_DEF)
    if compileTarget == "module":
        print("[CESIUM] - Compiling Cesium For Godot as an engine module...")
        currentRootDir = ROOT_DIR_MODULE
        return CESIUM_MODULE_DEF
    if compileTarget == "" or compileTarget == "extension":
        print("[CESIUM] - Compiling Cesium For Godot as a GDExtension")
        currentRootDir = ROOT_DIR_EXT
        return CESIUM_EXT_DEF

    print("[CESIUM] - Compile target not recognized, options are: module / extension")
    exit(1)


def link_abseil_libs(env):
    if is_android_target():
        # For Android, abseil is built inside cesium-native's vcpkg
        isExt = is_extension_target(ARGUMENTS)
        repoDirectory = CESIUM_NATIVE_DIR_EXT if isExt else CESIUM_NATIVE_DIR_MODULE
        repoDirectory = scons_to_abs_path(repoDirectory)
        build_dir = os.path.join(repoDirectory, "build-android-arm64")
        # Search multiple possible locations for abseil libs
        search_paths = [
            f"{build_dir}/vcpkg/packages/abseil_{determine_triplet()}/lib",
            f"{build_dir}/vcpkg/installed/{determine_triplet()}/lib",
            f"{find_ezvcpkg_path()}/packages/abseil_{determine_triplet()}/lib",
            f"{find_ezvcpkg_path()}/installed/{determine_triplet()}/lib",
        ]
        foundLibs = []
        for sp in search_paths:
            foundLibs = env.Glob(f"{sp}/*absl*.a")
            if foundLibs:
                print(f"[CESIUM] Found abseil libs at: {sp}")
                break
    else:
        foundLibs = env.Glob(
            f"{find_ezvcpkg_path()}/packages/abseil_{determine_triplet()}/lib/*absl*.a"
        )

    # Dark magic to strip the lib prefix and the file extension
    foundLibs = [lib.name.replace("lib", "")[:-2] for lib in foundLibs]

    env.Append(LINKFLAGS=["-Wl,--start-group"], LIBS=foundLibs)

    env.Append(LINKFLAGS=["-Wl,--end-group"])

    env.Append(
        LINKFLAGS=["-Wl,--start-group"],
        LIBS=[
            "absl_log_internal_log_sink_set",
            "absl_log_globals",
            "absl_leak_check",
            "absl_log_internal_globals",
            "absl_log_internal_format",
            "absl_base",
            "absl_hash",
            "absl_city",
            "absl_low_level_hash",
            "absl_examine_stack",
            "absl_stacktrace",
            "absl_debugging_internal",
            "absl_synchronization",
            "absl_base",
            "absl_malloc_internal",
            "absl_int128",
            "absl_symbolize",
            "absl_kernel_timeout_internal",
            "absl_debugging_internal",
            "absl_demangle_internal",
            "absl_log_sink",
            "absl_demangle_rust",
            "absl_decode_rust_punycode",
            "absl_utf8_for_code_point",
        ],
    )
    env.Append(LINKFLAGS=["-Wl,--end-group"])


def clone_native_repo_if_needed():
    clone_repo_if_needed(
        ROOT_DIR_EXT + "/native",
        "Cesium Native",
        "https://github.com/CesiumGS/cesium-native.git",
        "v0.52.1",
        "9f6ae299e2709f866db52c4be29b6c31e10718c8",
    )


def clone_bindings_repo_if_needed():
    clone_repo_if_needed(
        BINDINGS_DIR,
        "Godot CPP Bindings",
        "https://github.com/godotengine/godot-cpp",
        "godot-4.1.4-stable",
        "4b0ee133274d67687b6003b8d5fdaf7b79cf4921",
    )


def clone_lite_html_if_needed():
    # clone_repo_if_needed(ROOT_DIR_EXT + "/third_party/lite-html", "Lite HTML",
    #                      "https://github.com/litehtml/litehtml.git", "v0.9", "6ca1ab0419e770e6d35a1ef690238773a1dafcee")
    pass


def clone_repo_if_needed(
    targetDir: str, name: str, repoUrl: str, branch: str, acceptedCommitSHA: str
):
    print(f"Cloning {name} repo")
    repoDirectory = scons_to_abs_path(targetDir)
    if os.path.exists(repoDirectory):
        return
    subprocess.run(
        ["git", "clone", "--depth=1", "-b", branch, repoUrl, "--recursive", repoDirectory]
    )

    # Shouldn't we just rely on the repo tags?
    # prevDir: str = os.getcwd()
    # os.chdir(repoDirectory)
    # subprocess.run(["git", "reset", "--hard", acceptedCommitSHA])
    # os.chdir(prevDir)


# Configure with CMake
def configure_native(argumentsDict):
    print("Configuring Cesium Native")
    isExt = is_extension_target(argumentsDict)
    repoDirectory = CESIUM_NATIVE_DIR_EXT if isExt else CESIUM_NATIVE_DIR_MODULE
    repoDirectory = scons_to_abs_path(repoDirectory)

    # For Android, build in a separate directory to avoid mixing host/target artifacts
    if is_android_target(argumentsDict):
        build_dir = os.path.join(repoDirectory, "build-android-arm64")
        os.makedirs(build_dir, exist_ok=True)
        os.chdir(build_dir)
        source_dir = repoDirectory
    else:
        os.chdir(repoDirectory)
        source_dir = "."

    # Assume you already have the triplet (for now)
    triplet: str = determine_triplet(argumentsDict)
    os.environ["VCPKG_TRIPLET"] = triplet

    cmake_args = [
        "cmake",
        f"-DCMAKE_BUILD_TYPE={RELEASE_CONFIG}",
        "-DCESIUM_TESTS_ENABLED=OFF",
        "-DBUILD_SHARED_LIBS=OFF",
        "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
        "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
        "-DGIT_LFS_SKIP_SMUDGE=1",
    ]

    if is_android_target(argumentsDict):
        ndk_root = get_android_ndk_root()
        if not ndk_root:
            print("ERROR: Android NDK not found. Set ANDROID_NDK_ROOT.", file=sys.stderr)
            exit(1)
        toolchain_file = os.path.join(ndk_root, "build", "cmake", "android.toolchain.cmake")
        if not os.path.exists(toolchain_file):
            print(f"ERROR: NDK toolchain not found at: {toolchain_file}", file=sys.stderr)
            exit(1)
        android_abi = get_android_abi(argumentsDict)
        cmake_args.extend([
            f"-DCMAKE_TOOLCHAIN_FILE={toolchain_file}",
            f"-DANDROID_ABI={android_abi}",
            "-DANDROID_PLATFORM=android-29",
            "-DCMAKE_CXX_FLAGS=-fexceptions -frtti",
            "-DCESIUM_MSVC_STATIC_RUNTIME_ENABLED=OFF",
        ])
        # Set vcpkg triplet for Android
        cmake_args.append(f"-DVCPKG_TARGET_TRIPLET={triplet}")
        print(f"[CESIUM] Android NDK: {ndk_root}")
        print(f"[CESIUM] Android ABI: {android_abi}")
    else:
        cmake_args.extend([
            "-DCESIUM_MSVC_STATIC_RUNTIME_ENABLED=ON",
            "-DVCPKG_TRIPLET=%s" % triplet,
        ])

    cmake_args.append(source_dir)

    # Run Cmake
    result = subprocess.run(cmake_args)

    # We pray this works haha
    if result.returncode != 0:
        errorMsg = "cmake return code: %s" % str(result.returncode)
        print(
            "Error configuring Cesium native, please make sure you have CMake installed and up to date: "
            + errorMsg
        )
        exit(1)
    print("Configuration completed without any errors!")


def determine_triplet(argsDict=None):
    if is_android_target(argsDict):
        abi = get_android_abi(argsDict)
        if abi == "arm64-v8a":
            return "arm64-android"
        elif abi == "x86_64":
            return "x64-android"
        return "arm64-android"
    if os.name == OS_WIN:
        return "x64-windows-static"
    if os.name == OS_LINUX:
        return "x64-linux"


def compile_native(argumentsDict):
    shouldBuildArg = argumentsDict.get("buildCesium", None)
    if shouldBuildArg is None:
        # For Android, default to building if native dir doesn't exist
        if is_android_target(argumentsDict):
            isExt = is_extension_target(argumentsDict)
            repoDirectory = CESIUM_NATIVE_DIR_EXT if isExt else CESIUM_NATIVE_DIR_MODULE
            repoDirectory = scons_to_abs_path(repoDirectory)
            build_dir = os.path.join(repoDirectory, "build-android-arm64")
            shouldBuildArg = not os.path.exists(os.path.join(build_dir, "CMakeCache.txt"))
            if not shouldBuildArg:
                print("[CESIUM] Android build already configured, skipping rebuild. Pass buildCesium=yes to force.")
        else:
            shouldBuildResponse = input(
                "Do you wanna build Cesium Native (Choose yes if it's the first install)? [y/n]"
            )
            shouldBuildArg = shouldBuildResponse.capitalize()[0] == "Y"
    else:
        shouldBuildArg = (
            shouldBuildArg.upper() == "YES" or shouldBuildArg.upper() == "TRUE"
        )

    if not shouldBuildArg:
        return

    print("Building Cesium Native, this might take a few minutes...")
    configure_native(argumentsDict)
    print("Compiling Cesium Native...")

    result = None
    if is_android_target(argumentsDict):
        result = build_native_android()
    elif os.name == OS_WIN:
        result = build_native_win()
    elif os.name == OS_LINUX:
        result = build_native_linux()
    else:
        # macOS host also uses cmake --build
        result = build_native_linux()

    if result is None or result.returncode != 0:
        err = str(result.stderr) if result else "Unknown error"
        print("Error building Cesium Native: %s" % err)
        exit(1)
    print("Cleaning definitions on generated files...")
    clean_cesium_definitions()
    print("Finished building Cesium Native!")


def build_native_linux():
    import multiprocessing
    jobs = str(multiprocessing.cpu_count())
    return subprocess.run(["cmake", "--build", ".", "--config", RELEASE_CONFIG, "--parallel", jobs])


def build_native_android():
    import multiprocessing
    jobs = str(multiprocessing.cpu_count())
    return subprocess.run(["cmake", "--build", ".", "--config", RELEASE_CONFIG, "--parallel", jobs])


def build_native_win():
    # execute MSBuild
    buildConfig: str = RELEASE_CONFIG
    solutionName: str = "cesium-native.sln"
    msbuildPath: str = find_ms_build()
    if msbuildPath == "":
        print(
            "Could not find MSBuild.exe, make sure to have Visual Studio installed",
            file=sys.stderr,
        )
        return
    releaseConfig = "/property:Configuration=%s" % buildConfig
    return subprocess.run([msbuildPath, solutionName, releaseConfig])


def clean_cesium_definitions():
    """
    This function modifies some of Cesium's header files to clean up
    definitions that conflict with the engine's
    """
    # Get the conflicting file (Material.h in our case)
    print("Cleaning native definitions")

    conflictFilePath: str = "%s/%s" % (
        CESIUM_NATIVE_DIR_EXT,
        "/CesiumGltf/generated/include/CesiumGltf",
    )
    conflictFilePath = scons_to_abs_path(conflictFilePath) + "/Material.h"
    # Load the file into memory

    # Read in the file
    fileData: str = ""
    with open(conflictFilePath, "r") as file:
        fileData = file.read()

    # Replace the target string
    fileData = fileData.replace("#pragma once", "#pragma once\n#undef OPAQUE")

    # Write the file out again
    with open(conflictFilePath, "w") as file:
        file.write(fileData)
    print("Finished cleaning native definitions")


def install_additional_libs(argsDict=None):
    if is_android_target(argsDict):
        print("[CESIUM] Skipping vcpkg install for Android — cesium-native cmake handles deps")
        return
    print("Installing additional libraries")
    vcpkgPath = find_ezvcpkg_path()
    execExtension = ".exe" if os.name == OS_WIN else ""
    executable = "%s/%s" % (vcpkgPath, "vcpkg" + execExtension)
    subprocess.run([executable, "install", "uriparser:%s" % (determine_triplet(argsDict))])
    subprocess.run([executable, "install", "ada-url:%s" % (determine_triplet(argsDict))])
    if os.name == OS_WIN:
        subprocess.run([executable, "install", "curl:%s" % (determine_triplet(argsDict))])


def find_ms_build() -> str:
    print("Searching for MS Build")
    # Try to search for an msbuild executable in the system
    try:
        testCmd = subprocess.run(
            ["msbuild", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Yay, we found it... (not gonna happen lol)
        if testCmd.returncode == 0:
            return "msbuild"
    except:
        # More likely we'll need to search for another path
        vsPath = "C:\\Program Files\\Microsoft Visual Studio"
        found, path = find_in_dir_recursive(vsPath, "*MSBuild.exe")

        if found:
            # Access the next latest directory (latest VS version)
            return path

        # Try with a .NET path
        print(".NET path is not yet supported!", sys.stderr)
        return ""


def find_in_dir_recursive(path: str, pattern: str) -> (bool, str):
    """
    Use only when there might be a few directories left to search
    as this function is recursive
    """

    if not os.path.exists(path):
        return False, ""

    foundFiles: list[str] = os.listdir(path)

    if len(foundFiles) == 0:
        return False, ""

    for root, dirnames, filenames in os.walk(path):
        for filename in fnmatch.filter(filenames, pattern):
            return True, os.path.join(root, filename)

    return False, ""


def find_ezvcpkg_path() -> str:
    global ezvcpkgFoundPath
    if ezvcpkgFoundPath != "":
        return ezvcpkgFoundPath

    # For Android, vcpkg is inside cesium-native's build directory
    if is_android_target():
        isExt = is_extension_target(ARGUMENTS)
        repoDirectory = CESIUM_NATIVE_DIR_EXT if isExt else CESIUM_NATIVE_DIR_MODULE
        repoDirectory = scons_to_abs_path(repoDirectory)
        build_dir = os.path.join(repoDirectory, "build-android-arm64")
        # ezvcpkg creates a cache dir inside the build tree
        vcpkg_dir = os.path.join(build_dir, "vcpkg")
        if os.path.exists(vcpkg_dir):
            ezvcpkgFoundPath = vcpkg_dir
            print(f"Found Android vcpkg at {ezvcpkgFoundPath}")
            return ezvcpkgFoundPath
        # Also check ~/.ezvcpkg for Android triplets
        from pathlib import Path
        home_vcpkg = (Path.home() / ".ezvcpkg").as_posix()
        if os.path.exists(home_vcpkg):
            subDirs = [x for x in next(os.walk(home_vcpkg))[1]]
            subDirs.sort(reverse=True, key=lambda x: os.stat("%s/%s" % (home_vcpkg, x)).st_ctime)
            if subDirs:
                ezvcpkgFoundPath = "%s/%s" % (home_vcpkg, subDirs[0])
                print(f"Found ezvcpkg at {ezvcpkgFoundPath}")
                return ezvcpkgFoundPath
        print("[CESIUM] Warning: vcpkg not found for Android build")
        ezvcpkgFoundPath = build_dir  # fallback
        return ezvcpkgFoundPath

    # Search the home directory
    assumedPath = "%s.ezvcpkg" % (os.path.abspath(os.sep))
    print(f"Searching vcpkg at: {assumedPath}")
    if not os.path.exists(assumedPath):
        from pathlib import Path

        assumedPath = (Path.home() / ".ezvcpkg").as_posix()
        print(f"Searching vcpkg at: {assumedPath}")
        if not os.path.exists(assumedPath):
            print(
                "EZVCPKG not found, please make sure that CesiumNative was compiled and configured properly!"
            )
            return ""
        # Assume it is in /home (C:/Users/currUser)
    # Then find the latest version (use the last created folder)
    subDirs = [x for x in next(os.walk(assumedPath))[1]]
    subDirs.sort(
        reverse=True, key=lambda x: os.stat("%s/%s" % (assumedPath, x)).st_ctime
    )
    latestDir = subDirs[0]
    ezvcpkgFoundPath = "%s/%s" % (assumedPath, latestDir)
    print(f"Found ezvcpkg at {ezvcpkgFoundPath}")
    return ezvcpkgFoundPath


def clone_engine_repo_if_needed():
    pass


def scons_to_abs_path(path: str) -> str:
    return Dir(path).get_abspath()


def find_ezvcpkg_include_path() -> str:
    return f"{find_ezvcpkg_path()}/installed/{determine_triplet()}/include"


def find_ezvcpkg_lib_path() -> str:
    return f"{find_ezvcpkg_path()}/installed/{determine_triplet()}/lib"


def get_root_dir() -> str:
    return currentRootDir


def get_root_dir_native() -> str:
    return scons_to_abs_path(currentRootDir + "/native")
