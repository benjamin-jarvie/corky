import com.sparrowwallet.drongo.*;
import com.sparrowwallet.drongo.address.Address;
import com.sparrowwallet.drongo.policy.Policy;
import com.sparrowwallet.drongo.policy.PolicyType;
import com.sparrowwallet.drongo.protocol.ScriptType;
import com.sparrowwallet.drongo.protocol.Sha256Hash;
import com.sparrowwallet.drongo.protocol.Transaction;
import com.sparrowwallet.drongo.psbt.PSBT;
import com.sparrowwallet.drongo.wallet.*;

import java.util.*;

/**
 * Builds PSBTs using Sparrow Wallet's own library (drongo), extracted from the
 * signed Sparrow 2.5.4 macOS release. Nothing here is a reimplementation: the
 * wallet, the transaction construction and the PSBT serialisation are Sparrow's.
 *
 * usage:
 *   addresses <NETWORK> <SCRIPTTYPE> <xpub> <fingerprint> <path> <count> <RECEIVE|CHANGE>
 *   psbt      <NETWORK> <SCRIPTTYPE> <xpub> <fingerprint> <path> <toAddr> <amountSats> <feeRate> <utxo>...
 *      utxo = PURPOSE:index:txid:vout:valueSats:rawtxhex
 */
public class SparrowGen {

    public static void main(String[] args) throws Exception {
        String mode = args[0];
        Network.set(Network.valueOf(args[1]));
        ScriptType st = ScriptType.valueOf(args[2]);
        String xpub = args[3];
        String fingerprint = args[4];
        String path = args[5];

        // The 3-arg constructor seeds one empty keystore in an immutable list,
        // exactly as Sparrow's own wallet-import path does; configure that one.
        Wallet wallet = new Wallet("corky-test", PolicyType.SINGLE_HD, st);
        Keystore ks = wallet.getKeystores().get(0);
        ks.setLabel("Corky");
        ks.setSource(KeystoreSource.HW_AIRGAPPED);
        ks.setWalletModel(WalletModel.SPARROW);
        ks.setKeyDerivation(new KeyDerivation(fingerprint, path));
        ks.setExtendedPublicKey(ExtendedKey.fromDescriptor(xpub));
        wallet.setDefaultPolicy(Policy.getPolicy(PolicyType.SINGLE_HD, st, wallet.getKeystores(), null));
        wallet.setGapLimit(20);
        wallet.setStoredBlockHeight(Integer.getInteger("chain.height", 200));

        if ("addresses".equals(mode)) {
            int count = Integer.parseInt(args[6]);
            KeyPurpose kp = KeyPurpose.valueOf(args[7]);
            WalletNode purposeNode = wallet.getNode(kp);
            purposeNode.fillToIndex(count - 1);
            List<WalletNode> kids = new ArrayList<>(purposeNode.getChildren());
            kids.sort(Comparator.comparingInt(WalletNode::getIndex));
            for (WalletNode n : kids) {
                if (n.getIndex() < count) {
                    System.out.println("OUT\t" + n.getIndex() + "\t" + wallet.getAddress(n) + "\t" + n.getDerivationPath());
                }
            }
            return;
        }

        // args[6] = feeRate, then repeated "p=addr,amount,sendMax" and
        // "u=PURPOSE,index,txid,vout,value,height,rawtxhex"
        double feeRate = Double.parseDouble(args[6]);
        List<Payment> payments = new ArrayList<>();
        Set<BlockTransactionHashIndex> utxos = new LinkedHashSet<>();
        Date now = new Date();

        for (int i = 7; i < args.length; i++) {
            String arg = args[i];
            if (arg.startsWith("p=")) {
                String[] f = arg.substring(2).split(",");
                payments.add(new Payment(Address.fromString(f[0]), "test",
                        Long.parseLong(f[1]), Boolean.parseBoolean(f[2])));
            } else if (arg.startsWith("u=")) {
                String[] f = arg.substring(2).split(",");
                KeyPurpose kp = KeyPurpose.valueOf(f[0]);
                int index = Integer.parseInt(f[1]);
                Sha256Hash txid = Sha256Hash.wrap(f[2]);
                long vout = Long.parseLong(f[3]);
                long value = Long.parseLong(f[4]);
                int height = Integer.parseInt(f[5]);
                Transaction fundingTx = new Transaction(Utils.hexToBytes(f[6]));

                WalletNode purposeNode = wallet.getNode(kp);
                purposeNode.fillToIndex(index);
                WalletNode node = null;
                for (WalletNode c : purposeNode.getChildren()) {
                    if (c.getIndex() == index) { node = c; break; }
                }
                if (node == null) throw new IllegalStateException("no node at " + kp + "/" + index);

                BlockTransactionHashIndex ref =
                        new BlockTransactionHashIndex(txid, height, now, 0L, vout, value);
                TreeSet<BlockTransactionHashIndex> outs = new TreeSet<>(node.getTransactionOutputs());
                outs.add(ref);
                node.setTransactionOutputs(outs);
                utxos.add(ref);
                wallet.updateTransactions(Map.of(txid,
                        new BlockTransaction(txid, height, now, 0L, fundingTx)));
            } else {
                throw new IllegalArgumentException("bad arg: " + arg);
            }
        }

        List<UtxoSelector> selectors = List.of(new PresetUtxoSelector(utxos));

        TransactionParameters params = new TransactionParameters(
                selectors,
                Collections.emptyList(),   // txoFilters
                payments,
                Collections.emptyList(),   // opReturns
                Collections.emptySet(),    // excludedChangeNodes
                feeRate,
                feeRate,                   // longTermFeeRate
                1.0d,                      // minRelayFeeRate
                null,                      // fee (null = derive from rate)
                Integer.getInteger("chain.height", 200),
                false,                     // groupByAddress
                false,                     // includeMempoolOutputs
                true);                     // allowRbf

        WalletTransaction wtx = wallet.createWalletTransaction(params);
        PSBT psbt = wtx.createPSBT();
        // Sparrow holds PSBTv2 internally (2.4.0 changelog) and downgrades on
        // the way out. HeadersController.savePSBT and the QR export both call
        // getForExport(), so an air-gapped signer sees whatever this returns.
        PSBT out = "raw".equals(System.getProperty("psbt.mode")) ? psbt : psbt.getForExport();
        System.out.println("OUT\t" + out.toBase64String());

        // What Sparrow itself would put on its own review screen. Ticket 07
        // compares Corky's describe_psbt against these, which is the M1 gate
        // criterion in PLAN.md:377.
        System.out.println("FEE\t" + wtx.getFee());
        for (WalletTransaction.Output o : wtx.getOutputs()) {
            var txo = o.getTransactionOutput();
            System.out.println("VOUT\t" + txo.getScript().getToAddresses()[0]
                    + "\t" + txo.getValue());
        }
    }
}
