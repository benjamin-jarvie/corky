import com.sparrowwallet.drongo.Network;
import com.sparrowwallet.drongo.policy.PolicyType;
import com.sparrowwallet.drongo.protocol.ScriptType;
import com.sparrowwallet.drongo.wallet.Keystore;

import java.io.ByteArrayInputStream;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Asks ONE of Sparrow's own cosigner importers to read a file Core Signer
 * wrote, and says what it made of it.
 *
 * Map multisig-cosigner, ticket M8. M7 read the importer sources and
 * concluded which formats land. Rule 8 is the house rule of this map: a
 * claim about Sparrow that Sparrow has not been asked is a rumour. This
 * asks, by calling the importer the user would pick from the list.
 *
 * The call is reflective because the importers share no common base for
 * `getKeystoreMultisig`, and naming each one here would mean a new class
 * per format for no gain.
 *
 * usage: SparrowImport <network> <importer class> <script type> <file>
 */
public class SparrowImport {
    public static void main(String[] args) throws Exception {
        Network.set(Network.valueOf(args[0]));
        String cls = "com.sparrowwallet.sparrow.io." + args[1];
        ScriptType st = ScriptType.valueOf(args[2]);
        Object importer = Class.forName(cls).getDeclaredConstructor()
                .newInstance();

        if (args[3].equals("-")) {
            // What Sparrow's own UI knows about this importer: whether a
            // QR can feed it, and the words it puts in front of the user.
            // Core Signer has to name the menu entry, so it has to read the
            // menu rather than guess at it.
            Object scan = importer.getClass()
                    .getMethod("isKeystoreImportScannable").invoke(importer);
            Object file = importer.getClass()
                    .getMethod("isFileFormatAvailable").invoke(importer);
            Object name = importer.getClass().getMethod("getName")
                    .invoke(importer);
            System.out.println("OUT\t" + name + "\t" + scan + "\t" + file);
            return;
        }
        byte[] body = Files.readAllBytes(Path.of(args[3]));
        Method m = null;
        for (String name : new String[]{"getKeystoreMultisig", "getKeystore"}) {
            try {
                m = importer.getClass().getMethod(name, PolicyType.class,
                        ScriptType.class, java.io.InputStream.class,
                        String.class);
                break;
            } catch (NoSuchMethodException ignored) { }
        }
        if (m == null) {
            System.out.println("OUT\tNO-IMPORTER-METHOD");
            return;
        }
        System.out.println("INFO\tmethod=" + m.getName());
        try {
            Keystore k = (Keystore) m.invoke(importer, PolicyType.MULTI_HD, st,
                    new ByteArrayInputStream(body), null);
            System.out.println("OUT\tOK\t"
                    + k.getKeyDerivation().getMasterFingerprint() + "\t"
                    + k.getKeyDerivation().getDerivationPath() + "\t"
                    + k.getExtendedPublicKey().toString().substring(0, 12));
        } catch (Exception e) {
            Throwable c = e.getCause() == null ? e : e.getCause();
            String msg = c.getMessage() == null ? c.getClass().getSimpleName()
                    : c.getMessage();
            System.out.println("OUT\tREFUSED\t"
                    + msg.replace('\t', ' ').replace('\n', ' '));
        }
    }
}
