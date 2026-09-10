import com.sparrowwallet.drongo.*;
import com.sparrowwallet.drongo.psbt.PSBT;
import com.sparrowwallet.drongo.wallet.*;
import com.sparrowwallet.drongo.policy.PolicyType;

import java.util.*;

/**
 * Signs ONE SHARE of a quorum with Sparrow Wallet's own library, as the
 * other vendor in a multivendor multisig.
 *
 * Map multisig-cosigner, ticket M4. tests/sparrow/test_cosigner.py proves
 * Sparrow PARSES a quorum holding a Corky cosigner key. This proves the
 * other half: Sparrow, holding a different key of the same quorum, adds
 * its signature to the one Corky already put there, and Bitcoin Core
 * accepts the result.
 *
 * The wallet is built from the descriptor exactly as SparrowDesc builds
 * it, so all three cosigners arrive as Sparrow's own parser makes them.
 * Then the ONE keystore whose fingerprint matches the key we were handed
 * gets its private half attached. Nothing else is touched: the other two
 * stay watch-only, which is what a cosigner's wallet actually looks like.
 *
 * usage: SparrowCosigner <NETWORK> <descriptor> <xprv> <psbt-base64>
 */
public class SparrowCosigner {
    public static void main(String[] args) throws Exception {
        Network.set(Network.valueOf(args[0]));
        OutputDescriptor od = OutputDescriptor.getOutputDescriptor(args[1]);
        Wallet wallet = od.toWallet();
        wallet.setGapLimit(20);

        ExtendedKey master = ExtendedKey.fromDescriptor(args[2]);
        MasterPrivateExtendedKey mpek =
                new MasterPrivateExtendedKey(master.getKey());
        int attached = 0;
        for (Keystore ks : wallet.getKeystores()) {
            // Match by deriving this xprv down the keystore's OWN path and
            // comparing the xpub. Fingerprints are 4 bytes and a match on
            // one is not proof; the extended key is.
            Keystore candidate = Keystore.fromMasterPrivateExtendedKey(
                    mpek, PolicyType.MULTI_HD,
                    ks.getKeyDerivation().getDerivation());
            if (candidate.getExtendedPublicKey().toString()
                    .equals(ks.getExtendedPublicKey().toString())) {
                ks.setSource(KeystoreSource.SW_SEED);
                ks.setWalletModel(WalletModel.SPARROW);
                ks.setMasterPrivateExtendedKey(mpek);
                attached++;
            }
        }
        System.out.println("INFO\tkeystores=" + wallet.getKeystores().size()
                + "\tattached=" + attached);
        if (attached != 1) {
            throw new IllegalStateException(
                "expected exactly one keystore to match the key given, got "
                + attached);
        }

        PSBT psbt = PSBT.fromString(args[3]);
        System.out.println("INFO\tsigningNodes="
                + wallet.getSigningNodes(psbt).size());
        wallet.sign(psbt);
        System.out.println("OUT\t" + psbt.toBase64String());
    }
}
