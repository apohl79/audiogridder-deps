#!/usr/bin/env python3
#
# Author: Andreas Pohl

import os, argparse, sys, shutil, glob, subprocess

def execute(cmd, ignoreError=False):
    print('>>> ' + cmd)
    if os.system(cmd) != 0 and not ignoreError:
        sys.exit(1)

def executeReadOutput(cmd):
    print('>>> ' + cmd)
    return subprocess.run(cmd.split(' '), stdout=subprocess.PIPE).stdout.decode('utf8').rstrip()

def getPlatform(args=None):
    if args is not None and 'platform' in vars(args) and args.platform is not None:
        return args.platform
    if sys.platform == 'darwin':
        return 'macos'
    elif sys.platform in ('linux', 'linux2'):
        return 'linux'
    elif sys.platform == 'win32':
        return 'windows'

def getPlatformArch(args):
    if getPlatform(args) == 'macos':
        return getPlatform(args) + '-' + args.macostarget + '-' + args.arch
    else:
        return getPlatform(args) + '-' + args.arch

def getInstDir(args):
    return os.getcwd() + '/' + getPlatformArch(args)

def isCrossCompilation(args):
    if getPlatform(args) == 'macos':
        hostArch = executeReadOutput('uname -m')
        return hostArch != args.arch
    return False

def getMacToolchain(args):
    toolchain = ''
    sysroot = ''
    if args.macostarget == '10.7':
        toolchain = '/Library/Developer/10/CommandLineTools'
        sysroot = toolchain + '/SDKs/MacOSX10.14.sdk'
    elif args.macostarget == '10.8':
        toolchain = '/Library/Developer/10/CommandLineTools'
        sysroot = toolchain + '/SDKs/MacOSX10.14.sdk'
    elif args.macostarget == '11.1':
        toolchain = '/Library/Developer/13/CommandLineTools'
        sysroot = toolchain + '/SDKs/MacOSX11.sdk'
    return (toolchain, sysroot)

def setMacToolchain(args):
    (newToolchain, sysroot) = getMacToolchain(args)
    lastToolchain = executeReadOutput('xcode-select -p')
    if newToolchain != lastToolchain:
        print('required toolchain not selected, trying xcode-select')
        execute('sudo xcode-select -s ' + newToolchain)
    return (newToolchain, lastToolchain, sysroot)

def buildLibwebp(args):
    instDir = getInstDir(args)
    platform = getPlatform(args)

    os.chdir('repos/libwebp')

    cmake_conf_params = []
    cmake_build_params = []
    cmake_inst_params = []
    post_commands = []

    cmake_conf_params.append('-B build')
    cmake_conf_params.append('-DWEBP_BUILD_GIF2WEBP=OFF')
    cmake_conf_params.append('-DWEBP_BUILD_ANIM_UTILS=OFF')
    cmake_conf_params.append('-DWEBP_BUILD_CWEBP=OFF')
    cmake_conf_params.append('-DWEBP_BUILD_DWEBP=OFF')
    cmake_conf_params.append('-DWEBP_BUILD_IMG2WEBP=OFF')
    cmake_conf_params.append('-DWEBP_BUILD_VWEBP=OFF')
    cmake_conf_params.append('-DWEBP_BUILD_WEBPINFO=OFF')
    cmake_conf_params.append('-DWEBP_BUILD_WEBPMUX=OFF')
    cmake_conf_params.append('-DWEBP_BUILD_EXTRAS=OFF')
    cmake_conf_params.append('-DWEBP_BUILD_WEBP_JS=OFF')

    cmake_build_params.append('--build build')
    cmake_build_params.append('--target webp')
    cmake_build_params.append('--target libwebpmux')
    cmake_build_params.append('--target webpdemux')
    cmake_build_params.append('--target webpdecoder')

    cmake_inst_params.append('--install build')
    cmake_inst_params.append('--prefix ' + instDir)

    if platform == 'windows':
        with open('user.cmake', 'w') as f:
            f.write('add_definitions(/MT)\n')
        cmake_conf_params.append('-DCMAKE_USER_MAKE_RULES_OVERRIDE="user.cmake"')
        cmake_build_params.append('--config Release')
    elif platform == 'macos':
        cmake_conf_params.append('-DCMAKE_BUILD_TYPE=Release')
        cmake_conf_params.append('-DCMAKE_OSX_ARCHITECTURES=' + args.arch)
        cmake_conf_params.append('-DCMAKE_OSX_DEPLOYMENT_TARGET=' + args.macostarget)

        (newToolchain, lastToolchain, sysroot) = setMacToolchain(args)
        if newToolchain != lastToolchain:
            post_commands.append('sudo xcode-select -s ' + lastToolchain)

    elif platform == 'linux':
        cmake_conf_params.append('-DCMAKE_BUILD_TYPE=Release')

    if args.jobs > 0:
        cmake_build_params.append('-j ' + str(args.jobs))

    if args.verbose:
        cmake_build_params.append('--verbose')

    execute('cmake ' + ' '.join(cmake_conf_params))
    execute('cmake ' + ' '.join(cmake_build_params))
    execute('cmake ' + ' '.join(cmake_inst_params))

    shutil.rmtree('build')
    if platform == 'windows':
        os.remove('user.cmake')

    os.chdir('../..')

    for cmd in post_commands:
        execute(cmd)

def buildFFmpeg(args):
    instDir = getInstDir(args)
    platform = getPlatform(args)

    conf_params = []
    post_commands = []

    conf_params.append('--prefix=' + instDir)
    conf_params.append('--arch=' + args.arch)
    conf_params.append('--enable-static')
    conf_params.append('--enable-libwebp')
    conf_params.append('--disable-shared')
    conf_params.append('--disable-debug')
    conf_params.append('--disable-programs')
    conf_params.append('--disable-sdl2')
    conf_params.append('--disable-securetransport')
    conf_params.append('--disable-bzlib')
    conf_params.append('--disable-xlib')
    conf_params.append('--disable-zlib')
    conf_params.append('--disable-lzma')
    conf_params.append('--disable-iconv')
    conf_params.append('--disable-doc')
    conf_params.append('--disable-everything')
    conf_params.append('--enable-encoder=libwebp,mjpeg')
    conf_params.append('--enable-decoder=webp,rawvideo')
    conf_params.append('--enable-parser=mjpeg,webp')
    conf_params.append('--enable-muxer=mjpeg,webp')
    conf_params.append('--enable-indev=avfoundation,gdigrab')

    if platform == 'windows':
        if os.environ.get('MSYSTEM') != 'MSYS':
            print('FFmpeg must be built under MSYS2 on windows')
            exit(1)
        conf_params.append('--toolchain=msvc')
        conf_params.append('--target-os=win64')
        conf_params.append('--enable-w32threads')
        conf_params.append('--extra-cflags="-I{}/include"'.format(instDir))
        conf_params.append('--extra-ldflags="-L{}/lib"'.format(instDir))
    elif platform == 'macos':
        conf_params.append('--disable-libxcb')
        if isCrossCompilation(args):
            conf_params.append('--enable-cross-compile')

        (newToolchain, lastToolchain, sysroot) = setMacToolchain(args)
        if newToolchain != lastToolchain:
            post_commands.append('sudo xcode-select -s ' + lastToolchain)

        if args.macostarget == '10.7':
            conf_params.append('--disable-videotoolbox')

        conf_params.append('--extra-cflags="-isysroot {} -mmacosx-version-min={} -arch {} -I{}/include"'
                           .format(sysroot, args.macostarget, args.arch, instDir))
        conf_params.append('--extra-ldflags="-isysroot {} -mmacosx-version-min={} -arch {} -L{}/lib"'
                           .format(sysroot, args.macostarget, args.arch, instDir))
    elif platform == 'linux':
        conf_params.append('--enable-pic')
        conf_params.append('--disable-asm')
        conf_params.append('--extra-cflags="-I{}/include"'.format(instDir))

    build_params = []
    if args.jobs > 0:
        build_params.append('-j ' + str(args.jobs))

    os.chdir('repos/FFmpeg')
    execute('sh configure ' + ' '.join(conf_params))
    execute('make ' + ' '.join(build_params))
    execute('make install')
    execute('make clean distclean')
    os.chdir('../..')

    if platform == 'windows':
        for f in glob.glob(instDir + '/lib/lib*.a'):
            name = f.replace(instDir + '/lib/lib', '').replace('.a', '.lib')
            os.rename(f, instDir + '/lib/' + name)

    for cmd in post_commands:
        execute(cmd)

def buildSentry(args):
    platform = getPlatform(args)
    instDir = getInstDir(args)

    os.chdir('repos/sentry-native')

    if not os.path.isfile('external/crashpad/CMakeLists.txt'):
        print("Pulling crashpad...")
        execute('git submodule update --init --recursive')

    cmake_conf_params = []
    cmake_build_params = []
    cmake_inst_params = []
    post_commands = []

    cmake_conf_params.append('-B build')

    cmake_build_params.append('--build build')

    cmake_inst_params.append('--install build')
    cmake_inst_params.append('--prefix ' + instDir)

    if platform == 'windows':
        if os.environ.get('MSYSTEM') == 'MSYS':
            print('Sentry cannot be built under MSYS2 on windows')
            exit(1)
        cmake_conf_params.append('-DSENTRY_BUILD_RUNTIMESTATIC=ON')
        cmake_build_params.append('--config RelWithDebInfo')
        cmake_inst_params.append('--config RelWithDebInfo')
    else:
        cmake_conf_params.append('-DCMAKE_BUILD_TYPE=RelWithDebInfo')

    if platform == 'macos':
        cmake_conf_params.append('-DCMAKE_OSX_ARCHITECTURES=' + args.arch)
        cmake_conf_params.append('-DCMAKE_OSX_DEPLOYMENT_TARGET=' + args.macostarget)

        if args.macostarget in ('10.7', '10.8'):
            cmake_conf_params.append('-DCMAKE_CXX_FLAGS="-stdlib=libc++"')

        (newToolchain, lastToolchain, sysroot) = setMacToolchain(args)
        if newToolchain != lastToolchain:
            post_commands.append('sudo xcode-select -s ' + lastToolchain)

    cmake_conf_params.append('-DSENTRY_BUILD_SHARED_LIBS=OFF')
    cmake_conf_params.append('-DSENTRY_BACKEND=crashpad')
    cmake_conf_params.append('-DSENTRY_BUILD_TESTS=OFF')
    cmake_conf_params.append('-DSENTRY_BUILD_EXAMPLES=OFF')

    if args.jobs > 0:
        cmake_build_params.append('-j ' + str(args.jobs))

    if args.verbose:
        cmake_build_params.append('--verbose')

    execute('cmake ' + ' '.join(cmake_conf_params))
    execute('cmake ' + ' '.join(cmake_build_params))
    execute('cmake ' + ' '.join(cmake_inst_params))
    shutil.rmtree('build')

    os.chdir('..')

    for cmd in post_commands:
        execute(cmd)

def buildBoost(args):
    platform = getPlatform(args)
    instDir = getInstDir(args)

    os.chdir('repos/boost')

    if not os.path.isfile('libs/any/.git'):
        print("Pulling libraries...")
        execute('git submodule update --init --recursive')

    bootstrap = ''
    bootstrap_params = []
    b2 = ''
    b2_params = []

    if platform == 'windows':
        bootstrap = 'cmd /C bootstrap.bat '
        b2 = 'b2 '
    else:
        bootstrap = 'sh bootstrap.sh '
        b2 = './b2 '

    bootstrap_params.append('--prefix=' + instDir)

    b2_params.append('--build-dir=build')
    b2_params.append('--user-config=user-config.jam')
    b2_params.append('-a')
    b2_params.append('-q')

    if args.jobs > 0:
        b2_params.append('-j' + str(args.jobs))

    if args.verbose:
        b2_params.append('-d+2')

    b2_params.append('variant=release')
    b2_params.append('link=static')
    b2_params.append('runtime-link=static')
    b2_params.append('threading=multi')

    toolset_base = ''
    toolset_compiler = ''
    toolset = dict()
    toolset['cxxstd'] = ['14']
    toolset['architecture'] = ['x86']
    toolset['address-model'] = ['64']

    if platform == 'macos':
        toolset_base = 'clang'
        toolset_compiler = executeReadOutput('which clang++')
        toolset['cxxflags'] = ['-stdlib=libc++', '-std=c++14']
        toolset['target-os'] = ['darwin']

        (toolchain, sysroot) = getMacToolchain(args)
        toolset['compileflags'] = [
            '-isysroot ' + sysroot,
            '-mmacosx-version-min=' + args.macostarget,
            '-arch ' + args.arch
        ]
        toolset['linkflags'] = [
            '-isysroot ' + sysroot,
            '-mmacosx-version-min=' + args.macostarget
        ]

        if args.arch == 'arm64':
            toolset['architecture'] = ['arm']
            toolset['compileflags'].append('-DBOOST_AC_USE_PTHREADS')
            toolset['compileflags'].append('-DBOOST_SP_USE_PTHREADS')
            toolset['abi'] = ['aapcs']
            toolset['binary-format'] = ['mach-o']
            bootstrap_params.append('--without-libraries=coroutine,fiber,context')
    elif platform == 'windows':
        toolset_base = 'msvc'
        toolset['target-os'] = ['windows']
    elif platform == 'linux':
        toolset_base = 'gcc'
        toolset_compiler = executeReadOutput('which g++')
        toolset['target-os'] = ['linux']

    b2_params.append('toolset=' + toolset_base)
    b2_params.append('install')
    b2_params.append('--prefix=' + instDir)

    with open('user-config.jam', 'w') as f:
        print('Writing user-config.jam')
        f.write('using ' + toolset_base + ' : : ' + toolset_compiler + ' :\n')
        for key in toolset:
            needsQuotes = len(toolset[key]) > 1 or ' ' in toolset[key][0]
            f.write('  <' + key + '>')
            if needsQuotes:
                f.write('"')
            f.write(' '.join(toolset[key]))
            if needsQuotes:
                f.write('"')
            f.write('\n')
        f.write(';\n')

    execute(bootstrap + ' '.join(bootstrap_params))
    execute(b2 + ' '.join(b2_params))

    for d in glob.glob(instDir + '/include/boost-*'):
        if os.path.isdir(d + '/boost'):
            src = d + '/boost'
            dst = instDir + '/include/boost'
            print('moving ' + src + ' to ' + dst)
            shutil.move(src, dst)
            shutil.rmtree(d)
            break

    execute(b2 + '--clean release')
    shutil.rmtree('build')

    os.chdir('../..')

def main():
    parser = argparse.ArgumentParser(description='AudioGridder Dependencies Build Script.')
    subparsers = parser.add_subparsers(title='Commands', dest='mode',
                                       help='Available commands, use <command> -h for more info')

    def addParser(name):
        subParser = subparsers.add_parser(name, help='Build ' + name)
        subParser.add_argument('--arch', dest='arch', type=str, default='x86_64',
                               help='CPU architecture (default: %(default)s)')
        subParser.add_argument('--macos-target', dest='macostarget', type=str, default='10.8',
                               help='MacOS deplyoment target (default: %(default)s)')
        subParser.add_argument('-j', '--jobs', dest='jobs', metavar='N', type=int, default=0,
                               help='Use N CPU cores')
        subParser.add_argument('-v', '--verbose', dest='verbose', action='store_true', default=False,
                               help='Show compile/link commands')

    addParser('all')
    addParser('libwebp')
    addParser('ffmpeg')
    addParser('sentry')
    addParser('boost')

    args = parser.parse_args()

    newToolchain = ''
    lastToolchain = ''

    if getPlatform() == 'macos':
        if args.arch == 'arm64':
            args.macostarget = '11.1'
        (newToolchain, lastToolchain, sysroot) = setMacToolchain(args)

    if args.mode == 'all':
        buildLibwebp(args)
        buildFFmpeg(args)
        buildSentry(args)
        buildBoost(args)
    elif args.mode == 'libwebp':
        buildLibwebp(args)
    elif args.mode == 'ffmpeg':
        buildFFmpeg(args)
    elif args.mode == 'sentry':
        buildSentry(args)
    elif args.mode == 'boost':
        buildBoost(args)
    else:
        parser.print_usage()

    if getPlatform() == 'macos' and newToolchain != lastToolchain:
        execute('sudo xcode-select -s ' + lastToolchain)

if __name__ == "__main__":
    main()
