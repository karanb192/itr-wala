"""Golden tests for the document-extraction tooling - decrypt_ais.py,
unzip_26as.py, parse_26as.py, redact_ais.py, extract_tis.py, shape.py,
ais_schema.py and blind_copy.py.
Run: python3 test_extraction.py  (or python3 -m unittest test_extraction -v)

Two properties are locked here, because both have failed in practice and
neither fails loudly:

1. **Nothing leaks.** These scripts exist so a user can work from AIS/TIS/26AS
   without payer names, TANs or PAN reaching the model. Every test that
   produces output asserts the identifying strings are absent - not merely
   that a pseudonym appeared somewhere.
2. **Nothing is silently miscounted.** 26AS packs two row shapes per part
   whose headers share a field count; keying on the count shifts every column
   and lands TANs where section codes belong. AIS keeps superseded rows
   flagged Inactive; summing them overstates the TDS claim. Both are locked.

Fixtures are synthetic. No real document is required, and no test touches the
network.
"""

import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import ais_schema
import blind_copy
import decrypt_ais
import extract_tis
import parse_26as
import redact_ais
import shape
import unzip_26as

HAVE_ZIP = shutil.which("zip") is not None
HAVE_OPENSSL = shutil.which("openssl") is not None

# Identifying strings that must never survive into output.
PAYER_A = "SOME LARGE COMPANY LIMITED"
PAYER_B = "ANOTHER ENTITY LIMITED"
TAN_A = "DELE00069G"
PAN_A = "ABCDE1234F"


def run(script, *args):
    """Run a script as the user would; return (stdout, stderr, returncode)."""
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, script)] + list(args),
        capture_output=True, text=True)
    return proc.stdout, proc.stderr, proc.returncode


def write(tmp, name, text):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


# ---------------------------------------------------------------------------
# decrypt_ais.py
# ---------------------------------------------------------------------------

def make_ais_blob(plaintext, pan, dob):
    """Build an encrypted AIS payload the way the portal does."""
    iv = bytes(range(16))
    salt = bytes(range(16, 32))
    password = f"{pan}{decrypt_ais.SEP}{dob}"
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt,
                              decrypt_ais.ITERATIONS, decrypt_ais.KEY_LEN)
    ct = subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-K", key.hex(), "-iv", iv.hex()],
        input=plaintext, capture_output=True, check=True).stdout
    return iv.hex() + salt.hex() + base64.b64encode(ct).decode()


@unittest.skipUnless(HAVE_OPENSSL, "openssl not on PATH")
class TestDecryptAis(unittest.TestCase):

    PAN, DOB = "ABCDE1234F", "09081962"

    def test_round_trip(self):
        plain = json.dumps({"AISData": {"x": 1}}).encode()
        blob = make_ais_blob(plain, self.PAN, self.DOB)
        self.assertEqual(decrypt_ais.decrypt(blob, self.PAN, self.DOB), plain)

    def test_separator_is_required(self):
        """The literal between PAN and DOB is the whole point - without it the
        password is wrong. Locks the constant against a silent edit."""
        self.assertEqual(decrypt_ais.SEP, "GQ39%*g")
        blob = make_ais_blob(b'{"a":1}', self.PAN, self.DOB)
        salt = bytes.fromhex(blob[32:64])
        naive = hashlib.pbkdf2_hmac("sha256", (self.PAN + self.DOB).encode(),
                                    salt, decrypt_ais.ITERATIONS,
                                    decrypt_ais.KEY_LEN)
        real = hashlib.pbkdf2_hmac(
            "sha256", (self.PAN + decrypt_ais.SEP + self.DOB).encode(),
            salt, decrypt_ais.ITERATIONS, decrypt_ais.KEY_LEN)
        self.assertNotEqual(naive, real)

    def test_wrong_dob_raises(self):
        blob = make_ais_blob(b'{"a":1}', self.PAN, self.DOB)
        with self.assertRaises(Exception):
            decrypt_ais.decrypt(blob, self.PAN, "01011999")

    def test_scheme_parameters_locked(self):
        self.assertEqual(decrypt_ais.ITERATIONS, 1000)
        self.assertEqual(decrypt_ais.KEY_LEN, 32)

    def test_rejects_file_without_hex_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write(tmp, "notais.json", "{}")
            out, err, rc = run("decrypt_ais.py", p)
            self.assertEqual(rc, 1)
            self.assertIn("encrypted AIS", out + err)

    def test_usage_without_args(self):
        _, _, rc = run("decrypt_ais.py")
        self.assertEqual(rc, 2)


# ---------------------------------------------------------------------------
# unzip_26as.py
# ---------------------------------------------------------------------------

class TestUnzip26as(unittest.TestCase):

    def test_candidates_cover_known_shapes(self):
        got = unzip_26as.candidates("ABCDE1234F", "09081962")
        self.assertIn("09081962", got)                    # DOB alone
        self.assertIn("ABCDE1234F09081962", got)          # PAN upper + DOB
        self.assertIn("abcde1234f09081962", got)          # PAN lower + DOB
        self.assertEqual(len(got), len(set(got)), "candidates must be unique")

    def test_dob_alone_is_tried_first(self):
        """TRACES text exports use the bare DOB; trying it first avoids
        needless failed attempts."""
        self.assertEqual(unzip_26as.candidates("ABCDE1234F", "09081962")[0],
                         "09081962")

    @unittest.skipUnless(HAVE_ZIP, "zip binary not available")
    def test_zipcrypto_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "26AS.txt", "PAN^x\nTDS Section 194^100\n")
            subprocess.run(["zip", "-q", "-P", "09081962", "z.zip", "26AS.txt"],
                           cwd=tmp, check=True)
            os.remove(os.path.join(tmp, "26AS.txt"))
            out, err, rc = subprocess.run(
                [sys.executable, os.path.join(SCRIPT_DIR, "unzip_26as.py"),
                 os.path.join(tmp, "z.zip"), tmp],
                input="ABCDE1234F\n09081962\n", capture_output=True,
                text=True).stdout, None, None
            self.assertIn("[ok]", out)
            self.assertTrue(os.path.exists(os.path.join(tmp, "26AS.txt")))

    def test_usage_without_args(self):
        _, _, rc = run("unzip_26as.py")
        self.assertEqual(rc, 2)


# ---------------------------------------------------------------------------
# parse_26as.py
# ---------------------------------------------------------------------------

# Two row shapes, exactly as TRACES emits them: the per-deductor SUMMARY row
# starts with the serial number; the per-transaction DETAIL row starts with an
# empty field. Both headers carry the same number of fields.
FAKE_26AS = """Form 26AS
^PART-I - Details of Tax Deducted at Source^
Sr. No.^Name of Deductor^TAN of Deductor^^^^^Total Amount Paid / Credited(Rs.)^Total Tax Deducted(Rs.)^Total TDS Deposited(Rs.)
1^{a}^{tan}^^^^^100000.00^10000.00^10000.00
^Sr. No.^Section^Transaction Date^Status of Booking^Date of Booking^Remarks^Amount Paid / Credited(Rs.)^Tax Deducted(Rs.)^TDS Deposited(Rs.)
^1^194^01-Jul-2025^F^15-Aug-2025^^60000.00^6000.00^6000.00
^2^194^01-Oct-2025^F^15-Nov-2025^^40000.00^4000.00^4000.00
2^{b}^{tan}^^^^^50000.00^5000.00^5000.00
^Sr. No.^Section^Transaction Date^Status of Booking^Date of Booking^Remarks^Amount Paid / Credited(Rs.)^Tax Deducted(Rs.)^TDS Deposited(Rs.)
^1^194^01-Jan-2026^F^15-Feb-2026^^50000.00^5000.00^5000.00
""".replace("{a}", PAYER_A).replace("{b}", PAYER_B).replace("{tan}", TAN_A)


class TestParse26as(unittest.TestCase):

    def setUp(self):
        parse_26as._book.clear()

    def parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write(tmp, "26as.txt", FAKE_26AS)
            out, _, rc = run("parse_26as.py", p)
            self.assertEqual(rc, 0, out)
            return out

    def test_section_194_totals(self):
        out = self.parse()
        self.assertIn("150,000.00", out)   # 60k + 40k + 50k paid
        self.assertIn("15,000.00", out)    # 6k + 4k + 5k deducted

    def test_summary_and_detail_not_double_counted(self):
        """Summary rows repeat the detail totals. Counting both doubles every
        figure - the bug that a field-count-keyed parser produces."""
        out = self.parse()
        self.assertNotIn("300,000", out)
        self.assertNotIn("30,000.00", out)

    def test_deductor_names_never_appear(self):
        out = self.parse()
        self.assertNotIn(PAYER_A, out)
        self.assertNotIn(PAYER_B, out)
        self.assertIn("DEDUCTOR", out)

    def test_tan_never_appears(self):
        """Regression lock: a header/row misalignment once put TANs into the
        section column, so they printed verbatim."""
        out = self.parse()
        self.assertNotIn(TAN_A, out)

    def test_section_column_holds_only_section_codes(self):
        out = self.parse()
        section_block = out.split("BY SECTION")[-1]
        self.assertIn("194", section_block)
        for line in section_block.splitlines():
            token = line.strip().split(" ")[0]
            if token:
                self.assertNotRegex(token, r"^[A-Z]{4}\d{5}[A-Z]$")

    def test_distinct_deductors_counted(self):
        out = self.parse()
        self.assertIn("DEDUCTOR: 2 distinct", out)

    def test_safe_masks_tan_and_pan_shapes(self):
        self.assertNotIn(TAN_A, parse_26as.safe("deductor " + TAN_A))
        self.assertNotIn(PAN_A, parse_26as.safe("holder " + PAN_A))

    def test_usage_without_args(self):
        _, _, rc = run("parse_26as.py")
        self.assertEqual(rc, 2)


# ---------------------------------------------------------------------------
# redact_ais.py / ais_schema.py / shape.py
# ---------------------------------------------------------------------------

def fake_ais():
    """AIS-shaped payload: one Active row, one Inactive (superseded) row, and
    a column that is not on the whitelist."""
    labels = [{"name": n} for n in
              ["TSN", "Quarter", "Date of Payment/Credit",
               "Amount Paid/Credited", "TDS Deducted", "TDS Deposited",
               "Status", "Undocumented Column"]]
    rows = [
        ["TXN1", "Q1(Apr-Jun)", "01-05-2025", "10000", "1000", "1000",
         "Active", "SENSITIVE-EXTRA"],
        ["TXN2", "Q2(Jul-Sep)", "01-08-2025", "5000", "500", "500",
         "Inactive", "SENSITIVE-EXTRA"],
    ]
    l2labels = ["Information Category", "Information Source",
                "Information Description", "Amount"]
    return {
        "partB": {"sections": [{
            "sectionKey": "tdsTcs", "heading": "TDS/TCS Information",
            "elements": [{
                "title": "Dividend",
                "l1": {"columnLabel": labels, "columnData": rows,
                       "columnDataType": ["String"] * 8},
                "l2": {"columnLabel": l2labels,
                       "columnData": [["Dividend", PAYER_A,
                                       "Dividend received", "10000"]],
                       "columnDataType": ["String"] * 4},
            }],
        }]}
    }


class TestRedactAis(unittest.TestCase):

    def setUp(self):
        redact_ais._pseudonyms.clear()

    def redact(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write(tmp, "ais.json", json.dumps(fake_ais()))
            out, _, rc = run("redact_ais.py", p)
            self.assertEqual(rc, 0, out)
            return out

    def test_inactive_row_excluded_from_sums(self):
        """Regression lock: including Inactive rows overstates income and,
        worse, the TDS claim."""
        out = self.redact()
        self.assertIn("10,000.00", out)          # the Active row only
        self.assertNotIn("15,000.00", out)       # Active + Inactive

    def test_inactive_row_reported_not_hidden(self):
        out = self.redact()
        self.assertIn("EXCLUDED 1 Inactive row", out)

    def test_payer_never_appears(self):
        out = self.redact()
        self.assertNotIn(PAYER_A, out)
        self.assertIn("PAYER: 1 distinct", out)

    def test_payer_tag_used_in_row_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write(tmp, "ais.json", json.dumps(fake_ais()))
            out, _, rc = run("redact_ais.py", p, "--rows")
            self.assertEqual(rc, 0, out)
            self.assertNotIn(PAYER_A, out)
            self.assertIn("PAYER-01", out)

    def test_unwhitelisted_column_dropped(self):
        """Whitelist must fail closed: an unrecognised column is dropped, not
        shown."""
        out = self.redact()
        self.assertNotIn("SENSITIVE-EXTRA", out)

    def test_quarter_breakup_present(self):
        out = self.redact()
        self.assertIn("Q1(Apr-Jun)", out)
        self.assertNotIn("Q2(Jul-Sep)", out)     # that row is Inactive

    def test_usage_without_args(self):
        _, _, rc = run("redact_ais.py")
        self.assertEqual(rc, 2)


class TestAisSchema(unittest.TestCase):

    def test_shows_columns_never_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write(tmp, "ais.json", json.dumps(fake_ais()))
            out, _, rc = run("ais_schema.py", p)
            self.assertEqual(rc, 0, out)
            self.assertIn("Amount Paid/Credited", out)   # column name
            self.assertNotIn(PAYER_A, out)               # never a value
            self.assertNotIn("10000", out)


class TestShape(unittest.TestCase):

    def test_no_values_in_output(self):
        data = {"holder": PAYER_A, "amount": 123456, "nested": {"tan": TAN_A}}
        with tempfile.TemporaryDirectory() as tmp:
            p = write(tmp, "d.json", json.dumps(data))
            out, _, rc = run("shape.py", p)
            self.assertEqual(rc, 0, out)
            self.assertIn("holder", out)          # key
            self.assertNotIn(PAYER_A, out)        # value
            self.assertNotIn(TAN_A, out)
            self.assertNotIn("123456", out)

    def test_string_length_disclosed(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rows = list(shape.walk({"a": "abcd"}))
        self.assertEqual(rows, [("a", "string", 4)])

    def test_number_magnitude_withheld(self):
        rows = list(shape.walk({"a": 987654321}))
        self.assertEqual(rows, [("a", "number", None)])

    def test_collapse_groups_array_elements(self):
        data = {"rows": [{"v": i} for i in range(50)]}
        with tempfile.TemporaryDirectory() as tmp:
            p = write(tmp, "d.json", json.dumps(data))
            out, _, rc = run("shape.py", p, "--collapse")
            self.assertEqual(rc, 0, out)
            self.assertIn("rows[*].v", out)
            self.assertNotIn("rows[7].v", out)


# ---------------------------------------------------------------------------
# blind_copy.py
# ---------------------------------------------------------------------------

class TestBlindCopy(unittest.TestCase):

    MAPPING = [{"from": "accounts[0].number", "to": "schedule[0].number"}]

    def _files(self, tmp, value):
        src = write(tmp, "src.json",
                    json.dumps({"accounts": [{"number": value}]}))
        mp = write(tmp, "map.json", json.dumps(self.MAPPING))
        return src, mp, os.path.join(tmp, "dest.json")

    def test_copy_and_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, mp, dst = self._files(tmp, "VALUE-12345678")
            out, _, rc = run("blind_copy.py", src, mp, dst)
            self.assertEqual(rc, 0, out)
            self.assertIn("PASS", out)
            self.assertNotIn("VALUE-12345678", out)
            with open(dst) as fh:
                self.assertEqual(json.load(fh)["schedule"][0]["number"],
                                 "VALUE-12345678")

    def test_tamper_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, mp, dst = self._files(tmp, "VALUE-12345678")
            run("blind_copy.py", src, mp, dst)
            with open(dst) as fh:
                data = json.load(fh)
            data["schedule"][0]["number"] = "VALUE-1234"      # truncated
            with open(dst, "w") as fh:
                json.dump(data, fh)
            out, err, rc = run("blind_copy.py", "--verify", src, mp, dst)
            self.assertEqual(rc, 1)
            self.assertIn("FAIL", out)
            self.assertNotIn("VALUE-12345678", out + err)

    def test_digest_is_stable_and_opaque(self):
        d = blind_copy.digest("secret")
        self.assertEqual(d, blind_copy.digest("secret"))
        self.assertNotEqual(d, blind_copy.digest("secrey"))
        self.assertNotIn("secret", d)

    def test_describe_never_returns_the_value(self):
        self.assertEqual(blind_copy.describe("abcd"), "string (4 chars)")
        self.assertEqual(blind_copy.describe(42), "number")

    def test_parse_path(self):
        self.assertEqual(blind_copy.parse_path("a.b[0].c"), ["a", "b", 0, "c"])


# ---------------------------------------------------------------------------
# extract_tis.py
# ---------------------------------------------------------------------------

class TestExtractTis(unittest.TestCase):

    def setUp(self):
        extract_tis._payers.clear()

    def test_masks_identifiers(self):
        line = extract_tis.mask(
            f"PAN: {PAN_A} Email: a@b.com Aadhaar: 123456789012")
        self.assertNotIn(PAN_A, line)
        self.assertNotIn("a@b.com", line)
        self.assertNotIn("123456789012", line)

    def test_masks_tan(self):
        self.assertNotIn(TAN_A, extract_tis.mask(f"deductor ({TAN_A})"))

    def test_pseudonymises_payer_names(self):
        out = extract_tis.mask(f"SFT Dividend income {PAYER_A} Total")
        self.assertNotIn(PAYER_A, out)
        self.assertIn("[PAYER-01]", out)

    def test_pseudonymises_mixed_case_payer(self):
        """Matching only ALL-CAPS runs let mixed-case company names through."""
        out = extract_tis.mask("SFT  Dividend income  SomeCement India Limited")
        self.assertNotIn("SomeCement India Limited", out)
        self.assertIn("[PAYER-01]", out)

    def test_column_label_alone_is_not_a_payer(self):
        """"Total Dividend" is a column value; masking it would be wrong."""
        self.assertEqual(extract_tis.mask("Total Dividend"), "Total Dividend")

    def test_label_adjacent_to_payer_is_absorbed(self):
        """Known limitation, locked so it stays known: a capitalised column
        label sitting immediately after a payer name is swallowed into the
        pseudonym. That over-masks - it never leaks - so it is acceptable."""
        out = extract_tis.mask("SomeCo India Limited  Total Dividend  59,500")
        self.assertNotIn("SomeCo", out)
        self.assertNotIn("Total Dividend", out)
        self.assertIn("59,500", out)

    def test_column_headings_not_pseudonymised(self):
        """Headings are upper-case too; mangling them makes output unreadable."""
        heading = "SR. NO. INFORMATION CATEGORY PROCESSED BY ACCEPTED BY"
        self.assertEqual(extract_tis.mask(heading), heading)

    def test_category_rows_are_whitelisted(self):
        self.assertTrue(extract_tis.is_wanted("1  Dividend  13,61,758"))
        self.assertTrue(extract_tis.is_wanted("2  Interest from savings bank  71,080"))

    def test_identity_lines_not_whitelisted(self):
        self.assertFalse(extract_tis.is_wanted("Address: 12 Some Road"))
        self.assertFalse(extract_tis.is_wanted("Mobile: 9876543210"))

    def test_usage_without_args(self):
        _, _, rc = run("extract_tis.py")
        self.assertEqual(rc, 2)

    def test_single_token_payer_masked(self):
        """Regression lock (fixed): a one-word payer after lowercase text
        escaped the two-word-minimum run matcher and leaked verbatim."""
        out = extract_tis.mask("1  Interest from savings bank  HDFC  71,080")
        self.assertNotIn("HDFC", out)
        self.assertIn("[PAYER-", out)
        self.assertIn("71,080", out)

    def test_leading_label_survives_payer_mask(self):
        """Regression lock (fixed): masking a payer swallowed the category
        label before it, leaving the figure unclassifiable."""
        out = extract_tis.mask("SFT-015  Dividend  RELIANCE INDUSTRIES LTD  1361758")
        self.assertIn("Dividend", out)
        self.assertNotIn("RELIANCE", out)
        self.assertIn("1361758", out)

    def test_pseudonyms_not_remasked(self):
        out = extract_tis.mask("interest paid  ICICI  and  AXIS BANK LIMITED  5,000")
        self.assertNotIn("[[", out)
        self.assertNotIn("ICICI", out)
        self.assertNotIn("AXIS", out)

    def test_document_tokens_survive_single_pass(self):
        line = "Interest from NRO account for AY 2026-27  2,000"
        self.assertEqual(extract_tis.mask(line), line)


class TestParse26asShapeGuard(unittest.TestCase):

    def setUp(self):
        parse_26as._book.clear()
        parse_26as._shape_warned = False

    def test_mismatched_row_skipped_loudly(self):
        """A digit-first row whose width matches neither header shape was
        zipped against the summary header, shifting columns and double
        counting. It must be skipped, with a warning, not totalled."""
        doctored = FAKE_26AS + "\n9^999999.00^UNMATCHED"
        with tempfile.TemporaryDirectory() as tmp:
            p = write(tmp, "26as.txt", doctored)
            out, err, rc = run("parse_26as.py", p)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("999999", out)
        self.assertIn("WARNING", err)
        self.assertIn("150,000.00", out)   # real totals unchanged


if __name__ == "__main__":
    unittest.main()
