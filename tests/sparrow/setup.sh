#!/bin/sh
# Prepares the Sparrow interop harness. Downloads two things, verifies both,
# and installs neither: everything stays under tests/sparrow/.build/.
#
#   1. Sparrow 2.5.4 (macOS aarch64), checked against Sparrow's own manifest.
#   2. Temurin JDK 25, checked against the Adoptium API checksum. Sparrow 2.5.4
#      ships class file version 69, so JDK 24 and older cannot read it.
#
# The Sparrow app is a jlink image with no java launcher, so its modules are
# extracted with jimage and put on the classpath. The PSBTs the test uses are
# then built by Sparrow's own code, not by a reimplementation of it.
set -e
DIR=$(cd "$(dirname "$0")" && pwd)
B="$DIR/.build"
mkdir -p "$B"

SPARROW_VER=2.5.4
SPARROW_SHA=e8d8637a737480721bc820a1b96a79483fc4c73bc0095f6ce1cfb93637158173
JDK_VER=25.0.4.1_1
JDK_DIR="jdk-25.0.4.1+1"
JDK_SHA=61979887f7506a24a57439ff99adb8b3a7fc89977d9cfe3b8984f58a981b7b9d

check() {
  got=$(shasum -a 256 "$1" | awk '{print $1}')
  [ "$got" = "$2" ] || { echo "CHECKSUM FAIL for $1"; echo " got  $got"; echo " want $2"; exit 1; }
  echo "ok   checksum $1"
}

if [ ! -f "$B/Sparrow.dmg" ]; then
  echo "downloading Sparrow $SPARROW_VER ..."
  curl -sL -o "$B/Sparrow.dmg" \
    "https://github.com/sparrowwallet/sparrow/releases/download/$SPARROW_VER/Sparrow-$SPARROW_VER-aarch64.dmg"
fi
check "$B/Sparrow.dmg" "$SPARROW_SHA"

if [ ! -f "$B/jdk25.tar.gz" ]; then
  echo "downloading Temurin JDK 25 ..."
  curl -sL -o "$B/jdk25.tar.gz" \
    "https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25.0.4.1%2B1/OpenJDK25U-jdk_aarch64_mac_hotspot_$JDK_VER.tar.gz"
fi
check "$B/jdk25.tar.gz" "$JDK_SHA"

[ -d "$B/$JDK_DIR" ] || tar xzf "$B/jdk25.tar.gz" -C "$B"
JH="$B/$JDK_DIR/Contents/Home"

if [ ! -d "$B/ext" ]; then
  hdiutil attach -nobrowse -readonly -mountpoint "$B/mnt" "$B/Sparrow.dmg" >/dev/null
  RT="$B/mnt/Sparrow.app/Contents/runtime/Contents/Home"
  mkdir -p "$B/ext"
  "$JH/bin/jimage" extract --dir "$B/ext" "$RT/lib/modules"
  mkdir -p "$B/res/native/osx/aarch64"
  cp "$RT/lib/libsecp256k1.dylib" "$B/res/native/osx/aarch64/libsecp256k1.dylib"
  hdiutil detach "$B/mnt" >/dev/null
fi

# every Sparrow module, none of the JDK's own
ls -d "$B/ext"/*/ | grep -v -E '/(java|jdk|javafx)\.[^/]*/$' | tr '\n' ':' | sed 's/:$//' > "$B/cp.txt"
printf ':%s' "$B/res" >> "$B/cp.txt"

mkdir -p "$B/out"
"$JH/bin/javac" -nowarn -cp "$(cat "$B/cp.txt")" -d "$B/out" "$DIR/SparrowGen.java"
echo "ok   harness built at $B"
