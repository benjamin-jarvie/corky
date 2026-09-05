import com.sparrowwallet.drongo.*;
import com.sparrowwallet.drongo.crypto.*;
import com.sparrowwallet.drongo.policy.*;
import com.sparrowwallet.drongo.protocol.*;
import com.sparrowwallet.drongo.psbt.PSBT;
import com.sparrowwallet.drongo.wallet.*;

import java.util.*;

/**
 * RECOVERY, not export. Rebuilds a spending wallet in Sparrow Wallet's own
 * library from nothing but Corky's paper backup: the 111-character master
 * private key, and the script type.
 *
 * This is the question the paper backup exists to answer. If Corky is lost,
 * broken or thrown in a river, does that string get the money back out
 * through software that is not Corky?
 *
 * Keystore.fromMasterPrivateExtendedKey is the same call Sparrow's own
 * "master private key" import drives, so what passes here is what a person
 * can do in the application.
 *
 * usage: SparrowRecover <NETWORK> <SCRIPT_TYPE> <xprv> addresses <count>
 *        SparrowRecover <NETWORK> <SCRIPT_TYPE> <xprv> sign <psbt-base64>
 */
public class SparrowRecover {
    public static void main(String[] args) throws Exception {
        Network.set(Network.valueOf(args[0]));
        ScriptType st = ScriptType.valueOf(args[1]);
        String xprv = args[2];
        String mode = args[3];

        // The paper backup is a bare master key. Sparrow needs to be told
        // which script type it is being used as, which is exactly what its
        // import dialog asks a person.
        ExtendedKey master = ExtendedKey.fromDescriptor(xprv);
        MasterPrivateExtendedKey mpek =
                new MasterPrivateExtendedKey(master.getKey());
        List<ChildNumber> path = st.getDefaultDerivation();
        Keystore ks = Keystore.fromMasterPrivateExtendedKey(
                mpek, PolicyType.SINGLE_HD, path);

        // The 3-arg Wallet constructor seeds one empty keystore in an
        // IMMUTABLE list, so the recovered keystore is copied onto that one
        // rather than swapped in. SparrowGen does the same; replacing the
        // element throws UnsupportedOperationException.
        Wallet wallet = new Wallet("corky-recovered", PolicyType.SINGLE_HD, st);
        Keystore slot = wallet.getKeystores().get(0);
        slot.setLabel("Corky paper backup");
        slot.setSource(KeystoreSource.SW_SEED);
        slot.setWalletModel(WalletModel.SPARROW);
        slot.setMasterPrivateExtendedKey(ks.getMasterPrivateExtendedKey());
        slot.setKeyDerivation(ks.getKeyDerivation());
        slot.setExtendedPublicKey(ks.getExtendedPublicKey());
        ks = slot;
        wallet.setDefaultPolicy(Policy.getPolicy(
                PolicyType.SINGLE_HD, st, wallet.getKeystores(), null));
        wallet.setGapLimit(20);
        wallet.setStoredBlockHeight(Integer.getInteger("chain.height", 200));

        System.out.println("INFO\tfp=" + ks.getKeyDerivation().getMasterFingerprint()
                + "\tpath=" + ks.getKeyDerivation().getDerivationPath()
                + "\tscript=" + st);

        if ("addresses".equals(mode)) {
            int count = Integer.parseInt(args[4]);
            WalletNode node = wallet.getNode(KeyPurpose.RECEIVE);
            node.fillToIndex(count - 1);
            List<WalletNode> kids = new ArrayList<>(node.getChildren());
            kids.sort(Comparator.comparingInt(WalletNode::getIndex));
            for (WalletNode n : kids) {
                if (n.getIndex() < count) {
                    System.out.println("OUT\t" + n.getIndex() + "\t"
                            + wallet.getAddress(n));
                }
            }
            return;
        }

        // Sign a PSBT Bitcoin Core built for the same key. This is the
        // proof that matters: addresses matching says the wallet was
        // rebuilt, a signature says the money moves.
        PSBT psbt = PSBT.fromString(args[4]);
        System.out.println("INFO\tcanSign=" + wallet.canSign(psbt)
                + "\tsigningNodes=" + wallet.getSigningNodes(psbt).size()
                + "\tinputs=" + psbt.getPsbtInputs().size()
                + "\ttaproot=" + psbt.getPsbtInputs().get(0).isTaproot()
                + "\ttapInternalKey=" + (psbt.getPsbtInputs().get(0)
                        .getTapInternalKey() != null)
                + "\ttapDerived=" + psbt.getPsbtInputs().get(0)
                        .getTapDerivedPublicKeys().size());
        wallet.sign(psbt);
        com.sparrowwallet.drongo.psbt.PSBTInput in0 = psbt.getPsbtInputs().get(0);
        System.out.println("INFO\tafterSign partialSigs="
                + in0.getPartialSignatures().size()
                + "\ttapKeySig=" + (in0.getTapKeyPathSignature() != null));

        // The SIGNED psbt is what leaves, not a finalised one. Bitcoin Core
        // is the judge of whether a signature is good, through finalizepsbt,
        // so a second opinion from drongo's own finaliser only adds a way
        // for the two to disagree about a signature that is fine.
        System.out.println("OUT\t" + psbt.toBase64String());
    }
}
