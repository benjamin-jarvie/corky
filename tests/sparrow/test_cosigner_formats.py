"""FORMATS. Which of Sparrow's own importers takes what Core Signer writes?

Map multisig-cosigner, ticket M8. M7 answered this by READING Sparrow's
importer sources. Rule 8 is the house rule of this map: a claim about
Sparrow that Sparrow has not been asked is a rumour. This asks, by
calling the importer a person would pick from Sparrow's list.

It corrected M7 once, and the correction matters: the NESTED `bip48_2`
form M7 named is refused by every JSON importer, with or without a
SLIP-132 prefix. The FLAT `p2wsh_deriv` pair is what works, and a plain
`tpub` is enough.

It also records which menu entries Sparrow offers a FILE import for at
all. Three of them are scan-only, so an importer that parses a format is
not the same as a menu entry a person can hand a file to.

Run: python3 tests/sparrow/test_cosigner_formats.py
"""
import json
import sys
import tempfile
from pathlib import Path

from harness import Java, Regtest, Results

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "coresigner"))
import signer  # noqa: E402

PATH = "48h/1h/0h/2h"
DERIV = "m/48'/1'/0'/2'"

#: Everything Core Signer could hand a coordinator, and the shapes M7 named
#: that turn out not to work. Kept in one place because the NEGATIVES
#: are the point: they are what stops the JSON being written the wrong
#: way if it is ever written at all.
def formats(xfp, tpub):
    flat = {"chain": "XRT", "xfp": xfp.upper(), "account": 0,
            "p2wsh_deriv": DERIV, "p2wsh": tpub}
    nested = {"chain": "XRT", "xfp": xfp.upper(), "account": 0,
              "bip48_2": {"name": "p2wsh", "xfp": xfp.upper(),
                          "deriv": DERIV, "xpub": tpub}}
    return {
        "one-liner": f"[{xfp}/{PATH}]{tpub}",
        "flat json": json.dumps(flat),
        "nested json": json.dumps(nested),
    }


#: What each importer must do with each format. This is the table M8
#: decides from, so a change in Sparrow shows up here as a failure
#: rather than as a surprise in someone's wallet.
EXPECT = {
    # Krux and SeedSigner both extend SpecterDIY, so the one-liner IS
    # the Specter DIY format and all three read it.
    ("SpecterDIY", "one-liner"): True,
    ("Krux", "one-liner"): True,
    ("SeedSigner", "one-liner"): True,
    ("ColdcardMultisig", "one-liner"): False,
    ("ColdcardMultisig", "flat json"): True,
    ("JadeMultisig", "flat json"): True,
    ("PassportMultisig", "flat json"): True,
    ("KeystoneMultisig", "flat json"): True,
    ("ColdcardMultisig", "nested json"): False,
    ("JadeMultisig", "nested json"): False,
    ("Krux", "flat json"): False,
    ("SeedSigner", "flat json"): False,
    # Jade extends ColdcardMultisig, so the JSON is the Coldcard format.
    ("PassportMultisig", "one-liner"): False,
}

#: Whether Sparrow's UI offers a FILE import for each menu entry, and
#: the exact words it puts in the list. Core Signer has to name the entry a
#: person picks, so it reads the menu rather than guessing at it. Three
#: entries are scan-only, which no amount of format work changes.
#:
#: These two flags are also what decides the BUTTONS. `hw_airgapped.fxml`
#: is an Accordion, `HwAirgappedController` puts one pane in it per
#: importer, and `FileImportPane` shows "Scan..." and "Import File..."
#: according to `isKeystoreImportScannable()` and
#: `isFileFormatAvailable()`. So pinning them here pins what Core Signer's
#: export screen is allowed to tell a person to press.
MENU = {
    "SpecterDIY": ("Specter DIY", True),
    "Krux": ("Krux", True),
    "SeedSigner": ("SeedSigner", False),
    "ColdcardMultisig": ("Coldcard Multisig", True),
    "PassportMultisig": ("Passport Multisig", True),
    "KeystoneMultisig": ("Keystone Multisig", True),
    "JadeMultisig": ("Jade Multisig", False),
}


def main():
    java = Java()
    r = Results()
    work = Path(tempfile.mkdtemp(prefix="m8-"))
    with Regtest() as net:
        record = signer.cosigner_key(net.rpc, net.wallet, PATH)
        xfp = record[1:9]
        tpub = record[record.index("]") + 1:]
        r.record("the record Core Signer writes today is the one-liner",
                 record == f"[{xfp}/{PATH}]{tpub}", record[:40] + "…")

        files = {}
        for name, body in formats(xfp, tpub).items():
            f = work / (name.replace(" ", "_") + ".txt")
            f.write_text(body)
            files[name] = f
        # THE ONE-LINER COMES FROM THE DEVICE, not from this file. The
        # rest of the table is built here because Core Signer does not write
        # those shapes, and the point of them is what they prove about
        # the one it does.
        written = signer.write_cosigner(net.rpc, net.wallet, PATH, work)
        files["one-liner"] = written
        r.record("the device writes one line, named by the fingerprint",
                 written.name == f"coresigner-{xfp}-cosigner.txt"
                 and written.read_text() == record,
                 f"{written.name}, {len(written.read_text())} bytes")

        for (importer, fmt), want in EXPECT.items():
            out = java("SparrowImport", "REGTEST", importer, "P2WSH",
                       str(files[fmt]), tags=("OUT",))[0].split("\t")
            took = out[0] == "OK"
            detail = (f"path {out[2]}" if took
                      else (out[1][:44] if len(out) > 1 else out[0]))
            r.record(f"{importer} {'takes' if want else 'refuses'} "
                     f"the {fmt}",
                     took == want and (not took or out[2] == DERIV),
                     detail)

        for cls, (menu_name, has_file) in MENU.items():
            out = java("SparrowImport", "REGTEST", cls, "P2WSH", "-",
                       tags=("OUT",))[0].split("\t")
            r.record(f"Sparrow lists it as \"{menu_name}\" and "
                     f"{'offers' if has_file else 'offers NO'} file import",
                     out[0] == menu_name and (out[2] == "true") == has_file,
                     f"name={out[0]!r} qr={out[1]} file={out[2]}")

        # THE NAMED ROW FOLLOWS THE CHAIN. A mainnet path offered on a
        # regtest key is a path the coordinator will not find a coin at,
        # and the person reads the row rather than typing it, so nothing
        # else would catch it.
        r.record("the named cosigner row uses this chain's coin type",
                 signer.cosigner_path(net.rpc) == PATH
                 and signer.cosigner_path(net.rpc, "sh-wsh")
                 == "48h/1h/0h/1h",
                 f"{signer.cosigner_path(net.rpc)} and "
                 f"{signer.cosigner_path(net.rpc, 'sh-wsh')}")

        # A TRAILING NEWLINE BREAKS IT. Sparrow refuses the file with
        # one, and with \r\n, and with two, where a LEADING space is
        # tolerated. Writing a text file without a final newline looks
        # like an oversight, so this is the check that stops someone
        # helpfully adding one.
        for name, suffix in (("a newline", "\n"), ("CRLF", "\r\n"),
                             ("two newlines", "\n\n")):
            f = work / "nl.txt"
            f.write_text(record + suffix)
            out = java("SparrowImport", "REGTEST", "SpecterDIY", "P2WSH",
                       str(f), tags=("OUT",))[0].split("\t")
            r.record(f"the file must NOT end with {name}",
                     out[0] != "OK",
                     out[1][:40] if len(out) > 1 else out[0])

        # THE SCAN PATH IS A DIFFERENT QUESTION, and it does not use
        # those importers: only Bip93 implements KeystoreCodexImport, so
        # everything else arrives through QRScanDialog, whose Result
        # carries an ExtendedKey or an OutputDescriptor. These drive the
        # two drongo parsers that dialog hands the payload to. Not the
        # dialog, which needs a camera.
        SCANS = {
            "the one-liner": (record, False),
            "the one-liner with a range": (record + "/0/*", False),
            "a bare tpub": (tpub, False),
            "wsh() around the record": (f"wsh({record})", True),
            "wsh() with a range": (f"wsh({record}/0/*)", True),
            "the flat json": (json.dumps({"p2wsh": tpub}), False),
        }
        for name, (body, want) in SCANS.items():
            f = work / "scan.txt"
            f.write_text(body)
            out = java("SparrowScan", "REGTEST", str(f),
                       tags=("OUT",))[0].split("\t")
            took = out[0] == "DESCRIPTOR"
            ok_ = (took == want and (not took or (out[1] == xfp
                                                  and out[2] == DERIV)))
            r.record(f"a QR of {name} "
                     f"{'carries the key AND its origin' if want else 'does NOT'}",
                     ok_,
                     (f"{out[1]} {out[2]}" if took
                      else out[0] + " " + (out[1][:34] if len(out) > 1 else "")))

        # WHAT CORESIGNER ACTUALLY PUTS ON THE QR. The scan wants a whole
        # descriptor, and `wsh(<key>)` is NOT one: Core refuses it with
        # "A function is needed within P2WSH", so Core Signer would be emitting
        # a string its own brain calls invalid. `sortedmulti(1, ...)` is
        # a descriptor both agree on, and its script type matches the
        # P2WSH wallet the key is being added to, which is what
        # `getScannedKeystore(ScriptType)` is handed.
        qr = signer.cosigner_qr(net.rpc, net.wallet, PATH)
        f = work / "qr.txt"
        f.write_text(qr)
        out = java("SparrowScan", "REGTEST", str(f), tags=("OUT",))[0] \
            .split("\t")
        r.record("the QR payload carries the key, the fingerprint and "
                 "the path",
                 out[0] == "DESCRIPTOR" and out[1] == xfp
                 and out[2] == DERIV,
                 f"{out[0]} {out[1] if len(out) > 1 else ''} "
                 f"{out[2] if len(out) > 2 else ''}")
        r.record("and Core calls that payload a valid descriptor",
                 "#" in qr and net.rpc.call(
                     "getdescriptorinfo", qr,
                     stdin=True)["checksum"] == qr.split("#")[1],
                 f"{len(qr)} chars, checksum {qr.split('#')[-1]}")
        r.record("the file payload is NOT a descriptor, and that is why "
                 "the two channels differ",
                 record != qr and record in qr,
                 f"file {len(record)} chars, QR {len(qr)}")

        # SLIP-132 is the finding that matters for the decision. M7 said
        # the JSON needs a Vpub, and Sparrow enforcing that would have
        # put a base58check re-encode inside coresigner/, which PLAN A-22
        # forbids and Core cannot do for us. It does not: a plain tpub
        # lands.
        r.record("the JSON Sparrow takes needs NO SLIP-132 prefix, so no "
                 "key re-encoding is required of Core Signer",
                 tpub.startswith("tpub"), f"accepted as {tpub[:8]}…")
    return r.summary()


if __name__ == "__main__":
    sys.exit(main())
