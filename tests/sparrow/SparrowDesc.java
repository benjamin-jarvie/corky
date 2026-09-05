import com.sparrowwallet.drongo.*;
import com.sparrowwallet.drongo.wallet.*;

import java.util.*;

/**
 * Reads a Bitcoin Core output descriptor with Sparrow Wallet's own library
 * (drongo, from the signed Sparrow 2.5.4 release) and derives receive
 * addresses from it. Nothing here is a reimplementation: OutputDescriptor
 * and Wallet are the same classes Sparrow's own import path drives.
 *
 * This is what proves Corky's export lands: Sparrow must accept the string
 * Core wrote, verbatim, and agree with Core about the addresses.
 *
 * usage: SparrowDesc <NETWORK> <descriptor> <count>
 */
public class SparrowDesc {
    public static void main(String[] args) throws Exception {
        Network.set(Network.valueOf(args[0]));
        OutputDescriptor od = OutputDescriptor.getOutputDescriptor(args[1]);
        int count = Integer.parseInt(args[2]);
        Wallet wallet = od.toWallet();
        wallet.setGapLimit(20);
        System.out.println("INFO\tscript=" + wallet.getScriptType()
                + "\tpolicy=" + wallet.getPolicyType());
        for (Keystore ks : wallet.getKeystores()) {
            System.out.println("INFO\tfp=" + ks.getKeyDerivation().getMasterFingerprint()
                    + "\tpath=" + ks.getKeyDerivation().getDerivationPath());
        }
        WalletNode purposeNode = wallet.getNode(KeyPurpose.RECEIVE);
        purposeNode.fillToIndex(count - 1);
        List<WalletNode> kids = new ArrayList<>(purposeNode.getChildren());
        kids.sort(Comparator.comparingInt(WalletNode::getIndex));
        for (WalletNode n : kids) {
            if (n.getIndex() < count) {
                System.out.println("OUT\t" + n.getIndex() + "\t" + wallet.getAddress(n));
            }
        }
    }
}
