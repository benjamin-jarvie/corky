import com.google.zxing.*;
import com.google.zxing.client.j2se.BufferedImageLuminanceSource;
import com.google.zxing.common.HybridBinarizer;
import com.sparrowwallet.drongo.Network;
import com.sparrowwallet.drongo.Utils;
import com.sparrowwallet.drongo.psbt.PSBT;
import com.sparrowwallet.hummingbird.UR;
import com.sparrowwallet.hummingbird.UREncoder;
import com.sparrowwallet.hummingbird.URDecoder;
import com.sparrowwallet.hummingbird.registry.RegistryType;

import javax.imageio.ImageIO;
import java.io.File;
import java.util.Base64;
import java.util.Locale;
import java.util.Map;

/**
 * Sparrow's QR side of the air gap, driven directly.
 *
 *   urencode <psbtBase64> [maxFragmentLength]
 *       One full cycle of ur:crypto-psbt parts, upper-cased, exactly as
 *       QRDisplayDialog animates them. Sparrow's own defaults are
 *       QRDensity.NORMAL = 400 and MIN_FRAGMENT_LENGTH = 10.
 *
 *   urdecode <part>...
 *       Sparrow's URDecoder, the receiving half of QRScanDialog.
 *
 *   qrdecode <png>...
 *       Sparrow's zxing reader against real image files.
 *
 *   inspect <psbtBase64>
 *       Parse with drongo and report what Sparrow would see.
 */
public class SparrowQr {

    private static final int MIN_FRAGMENT_LENGTH = 10;   // QRDisplayDialog:44

    public static void main(String[] args) throws Exception {
        switch (args[0]) {
            case "urencode" -> urencode(args);
            case "urdecode" -> urdecode(args);
            case "qrdecode" -> qrdecode(args);
            case "inspect"  -> inspect(args);
            default -> throw new IllegalArgumentException("mode: " + args[0]);
        }
    }

    private static void urencode(String[] args) throws Exception {
        byte[] psbt = Base64.getDecoder().decode(args[1]);
        int maxFragment = args.length > 2 ? Integer.parseInt(args[2]) : 400;
        UR ur = new UR(RegistryType.CRYPTO_PSBT, cborByteString(psbt));
        UREncoder enc = new UREncoder(ur, maxFragment, MIN_FRAGMENT_LENGTH, 0);
        int parts = Math.max(1, enc.getSeqLen());
        for (int i = 0; i < parts; i++) {
            // QRDisplayDialog:245 upper-cases every fragment before display
            System.out.println("OUT\t" + enc.nextPart().toUpperCase(Locale.ROOT));
        }
    }

    private static void urdecode(String[] args) throws Exception {
        URDecoder dec = new URDecoder();
        for (int i = 1; i < args.length; i++) {
            dec.receivePart(args[i]);
            if (dec.getResult() != null) break;
        }
        URDecoder.Result r = dec.getResult();
        if (r == null) throw new IllegalStateException("UR incomplete");
        if (r.type != com.sparrowwallet.hummingbird.ResultType.SUCCESS) {
            throw new IllegalStateException("UR error: " + r.error);
        }
        byte[] raw = stripCborByteString(r.ur.getCborBytes());
        System.out.println("OUT\t" + Base64.getEncoder().encodeToString(raw));
    }

    private static void qrdecode(String[] args) throws Exception {
        MultiFormatReader reader = new MultiFormatReader();
        for (int i = 1; i < args.length; i++) {
            var img = ImageIO.read(new File(args[i]));
            var bitmap = new BinaryBitmap(new HybridBinarizer(
                    new BufferedImageLuminanceSource(img)));
            try {
                Result r = reader.decode(bitmap,
                        Map.of(DecodeHintType.TRY_HARDER, Boolean.TRUE));
                System.out.println("OUT\t" + r.getText());
            } catch (NotFoundException e) {
                // Name the image. Dying on the first one hides how many of a
                // set failed, which is the number that matters.
                throw new IllegalStateException("no QR found in " + args[i], e);
            } finally {
                // zxing readers carry state between images. Without this a
                // later image can fail for a reason belonging to an earlier
                // one, which shows up as an intermittent test failure.
                reader.reset();
            }
        }
    }

    private static void inspect(String[] args) throws Exception {
        // global xpubs carry testnet version bytes on regtest
        Network.set(Network.valueOf(System.getProperty("network", "REGTEST")));
        PSBT psbt = new PSBT(Base64.getDecoder().decode(args[1]), false);
        int signed = 0;
        for (var in : psbt.getPsbtInputs()) {
            if (!in.getPartialSignatures().isEmpty()
                    || in.getTapKeyPathSignature() != null
                    || in.getFinalScriptWitness() != null) {
                signed++;
            }
        }
        System.out.println("OUT\tinputs=" + psbt.getPsbtInputs().size()
                + " signed=" + signed
                + " outputs=" + psbt.getPsbtOutputs().size()
                + " txid=" + psbt.getTransaction().getTxId().toString().substring(0, 12));
    }

    /** CBOR major type 2, definite length: what ur:crypto-psbt wraps. */
    private static byte[] cborByteString(byte[] data) {
        byte[] head;
        int n = data.length;
        if (n < 24)          head = new byte[]{(byte)(0x40 + n)};
        else if (n < 256)    head = new byte[]{0x58, (byte) n};
        else if (n < 65536)  head = new byte[]{0x59, (byte)(n >> 8), (byte) n};
        else                 head = new byte[]{0x5a, (byte)(n >> 24), (byte)(n >> 16),
                                               (byte)(n >> 8), (byte) n};
        byte[] out = new byte[head.length + n];
        System.arraycopy(head, 0, out, 0, head.length);
        System.arraycopy(data, 0, out, head.length, n);
        return out;
    }

    private static byte[] stripCborByteString(byte[] cbor) {
        int b = cbor[0] & 0xff, off;
        if (b >= 0x40 && b < 0x58)  off = 1;
        else if (b == 0x58)         off = 2;
        else if (b == 0x59)         off = 3;
        else if (b == 0x5a)         off = 5;
        else throw new IllegalArgumentException("not a CBOR byte string: " + Utils.bytesToHex(new byte[]{cbor[0]}));
        byte[] out = new byte[cbor.length - off];
        System.arraycopy(cbor, off, out, 0, out.length);
        return out;
    }
}
