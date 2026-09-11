import com.sparrowwallet.drongo.ExtendedKey;
import com.sparrowwallet.drongo.Network;
import com.sparrowwallet.drongo.OutputDescriptor;
import com.sparrowwallet.drongo.wallet.Keystore;
import com.sparrowwallet.drongo.wallet.Wallet;

import java.nio.file.Files;
import java.nio.file.Path;

/**
 * What Sparrow makes of a TEXT payload scanned from a QR.
 *
 * Map multisig-cosigner, ticket M8. The file half of that ticket is
 * driven through the importer a person picks from Sparrow's list. The
 * scan half does not use those importers at all: only Bip93 implements
 * KeystoreCodexImport, and everything else arrives through
 * QRScanDialog, whose Result carries an ExtendedKey or an
 * OutputDescriptor.
 *
 * So this drives the two drongo parsers that dialog hands the payload
 * to. It is not the dialog, which needs a camera, and it does not claim
 * to be: it is the decoding the dialog performs, on the same classes,
 * from the same release.
 *
 * usage: SparrowScan <network> <file holding the payload>
 */
public class SparrowScan {
    public static void main(String[] args) throws Exception {
        Network.set(Network.valueOf(args[0]));
        String payload = Files.readString(Path.of(args[1])).trim();

        if (ExtendedKey.isValid(payload)) {
            ExtendedKey k = ExtendedKey.fromDescriptor(payload);
            System.out.println("OUT\tEXTENDED-KEY\t-\t" + k.toString()
                    .substring(0, 12));
            return;
        }
        try {
            OutputDescriptor od = OutputDescriptor.getOutputDescriptor(payload);
            Wallet w = od.toKeystoreWallet(null);
            Keystore ks = w.getKeystores().get(0);
            System.out.println("OUT\tDESCRIPTOR\t"
                    + ks.getKeyDerivation().getMasterFingerprint() + "\t"
                    + ks.getKeyDerivation().getDerivationPath() + "\t"
                    + ks.getExtendedPublicKey().toString().substring(0, 12));
        } catch (Exception e) {
            Throwable c = e.getCause() == null ? e : e.getCause();
            String msg = c.getMessage() == null ? c.getClass().getSimpleName()
                    : c.getMessage();
            System.out.println("OUT\tREFUSED\t"
                    + msg.replace('\t', ' ').replace('\n', ' '));
        }
    }
}
