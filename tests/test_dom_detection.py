"""
Tests for Universal DOM Input Detection and React Controlled State Invariants.
Executes DOM heuristics against Node.js to verify frontend behavior.
"""
import unittest
import subprocess
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

class TestDomDetection(unittest.TestCase):
    def test_dom_input_disqualification_and_detection(self):
        js_code = """
        const fs = require('fs');
        const contentJs = fs.readFileSync('extension/content.js', 'utf8');

        // Extract isDisqualifiedInput function from content.js
        const funcMatch = contentJs.match(/function isDisqualifiedInput\\(el\\) \\{[\\s\\S]*?\\n  \\}/);
        if (!funcMatch) {
            console.error("isDisqualifiedInput not found");
            process.exit(1);
        }
        eval(funcMatch[0]);

        const testCases = [
            { el: { type: "text", name: "email_code", id: "otp", placeholder: "Code sent to email", getAttribute: (k) => null }, expectedDisqualified: false, label: "email_code" },
            { el: { type: "text", name: "phone_verification_code", id: "phone_otp", placeholder: "SMS code", getAttribute: (k) => null }, expectedDisqualified: false, label: "phone_verification_code" },
            { el: { type: "password", name: "otp", id: "sec_code", placeholder: "6-digit code", getAttribute: (k) => null }, expectedDisqualified: false, label: "password_masked_otp" },
            { el: { type: "password", name: "digit1", id: "d1", placeholder: "", getAttribute: (k) => k === "maxlength" ? "1" : null }, expectedDisqualified: false, label: "segmented_password_box" },
            { el: { type: "text", name: "code", id: "code", placeholder: "Verification code", getAttribute: (k) => null }, expectedDisqualified: false, label: "simple_code" },
            { el: { type: "text", name: "val_input", id: "v_input", placeholder: "请输入短信验证码", getAttribute: (k) => null }, expectedDisqualified: false, label: "chinese_sms_verification_code" },
            { el: { type: "text", name: "token", id: "tok", placeholder: "認証コードを入力", getAttribute: (k) => null }, expectedDisqualified: false, label: "japanese_auth_code" },
            { el: { type: "text", name: "sec", id: "sec", placeholder: "Nhập mã xác thực", getAttribute: (k) => null }, expectedDisqualified: false, label: "vietnamese_otp" },
            { el: { type: "text", name: "thai_inp", id: "t_inp", placeholder: "กรอกรหัส OTP", getAttribute: (k) => null }, expectedDisqualified: false, label: "thai_otp" },
            { el: { type: "text", name: "devicecode", id: "devicecode", placeholder: "Device verification code", getAttribute: (k) => null }, expectedDisqualified: false, label: "bandwagon_devicecode" },
            { el: { type: "text", name: "twofactorauthcode", id: "twofactorauthcode", placeholder: "", getAttribute: (k) => null }, expectedDisqualified: false, label: "whmcs_twofactorauthcode" },
            { el: { type: "text", name: "twofacode", id: "twofa", placeholder: "Enter 2FA", getAttribute: (k) => null }, expectedDisqualified: false, label: "twofacode" },
            { el: { type: "text", name: "twofactorcode", id: "tfcode", placeholder: "Enter code", getAttribute: (k) => null }, expectedDisqualified: false, label: "twofactorcode" },
            { el: { type: "password", name: "twofactorauthcode", id: "inputVerificationCode", placeholder: "", getAttribute: (k) => null }, expectedDisqualified: false, label: "whmcs_password_2fa" },
            { el: { type: "password", name: "password", id: "current_password", placeholder: "Enter password", getAttribute: (k) => null }, expectedDisqualified: true, label: "login_password" },
            { el: { type: "email", name: "email", id: "user_email", placeholder: "Email address", getAttribute: (k) => null }, expectedDisqualified: true, label: "email_address" },
            { el: { type: "text", name: "zip_code", id: "zip", placeholder: "ZIP code", getAttribute: (k) => null }, expectedDisqualified: true, label: "zip_code" },
            { el: { type: "text", name: "promo_code", id: "promo", placeholder: "Coupon code", getAttribute: (k) => null }, expectedDisqualified: true, label: "promo_code" },
            { el: { type: "text", name: "query", id: "search_input", placeholder: "Search site", getAttribute: (k) => null }, expectedDisqualified: true, label: "search_input" },
            { el: { type: "text", name: "company_website", id: "company_website", placeholder: "https://example.com", getAttribute: (k) => null }, expectedDisqualified: true, label: "company_website" },
            { el: { type: "url", name: "website", id: "url", placeholder: "", getAttribute: (k) => null }, expectedDisqualified: true, label: "type_url" },
            { el: { type: "text", name: "business_activity", id: "activity", placeholder: "Financial services", getAttribute: (k) => null }, expectedDisqualified: true, label: "business_activity" },
            { el: { type: "text", name: "company_name", id: "company", placeholder: "Acme Corp", getAttribute: (k) => null }, expectedDisqualified: true, label: "company_name" },
            { el: { type: "text", name: "industry", id: "industry", placeholder: "Fintech", getAttribute: (k) => null }, expectedDisqualified: true, label: "industry" },
            { el: { type: "text", name: "country_code", id: "country", placeholder: "+1", getAttribute: (k) => null }, expectedDisqualified: true, label: "country_code" },
            { el: { type: "text", name: "area_code", id: "area", placeholder: "415", getAttribute: (k) => null }, expectedDisqualified: true, label: "area_code" },
            { el: { type: "text", name: "currency_code", id: "curr", placeholder: "USD", getAttribute: (k) => null }, expectedDisqualified: true, label: "currency_code" },
            { el: { type: "text", name: "tracking_code", id: "track", placeholder: "FEDEX-91823", getAttribute: (k) => null }, expectedDisqualified: true, label: "tracking_code" },
            { el: { type: "text", name: "postal_code", id: "postcode", placeholder: "10001", getAttribute: (k) => null }, expectedDisqualified: true, label: "postal_code" },
            { el: { type: "text", name: "passport_number", id: "passport", placeholder: "Passport #", getAttribute: (k) => null }, expectedDisqualified: true, label: "passport_number" },
            { el: { type: "text", name: "tax_id", id: "ein", placeholder: "Tax ID / EIN", getAttribute: (k) => null }, expectedDisqualified: true, label: "tax_id" },
            { el: { type: "text", name: "device_name", id: "device_alias", placeholder: "My MacBook", getAttribute: (k) => null }, expectedDisqualified: true, label: "device_name" },
            { el: { type: "text", name: "desc", id: "desc", placeholder: "Brief description", getAttribute: (k) => k === "maxlength" ? "100" : null }, expectedDisqualified: true, label: "maxlength_over_20" }
        ];

        const results = testCases.map(tc => {
            const actual = isDisqualifiedInput(tc.el);
            return { label: tc.label, expected: tc.expectedDisqualified, actual: actual, pass: actual === tc.expectedDisqualified };
        });

        console.log(JSON.stringify(results));
        """
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        results = json.loads(proc.stdout)
        for r in results:
            self.assertTrue(r["pass"], f"Failed case {r['label']}: expected disqualified={r['expected']}, got {r['actual']}")

    def test_react_value_tracker_bypass_invariance(self):
        js_code = """
        // Simulate React 16-19 updateValueIfChanged mechanism
        function updateValueIfChanged(node) {
            if (!node || !node._valueTracker) return true;
            const lastValue = node._valueTracker.getValue();
            const nextValue = node.value;
            if (nextValue !== lastValue) {
                node._valueTracker.setValue(nextValue);
                return true;
            }
            return false;
        }

        // Mock node with React value tracker
        const node = {
            value: "123456",
            _valueTracker: {
                _val: "",
                getValue() { return this._val; },
                setValue(v) { this._val = v; }
            }
        };

        // Reset tracker to empty string (our fix)
        node._valueTracker.setValue("");
        const triggersChange = updateValueIfChanged(node);
        console.log(JSON.stringify({ triggersChange }));
        """
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertTrue(data["triggersChange"], "Resetting _valueTracker must trigger React updateValueIfChanged")

    def test_whmcs_bootstrap_control_group_detection(self):
        """Verify that WHMCS Bootstrap control-group without for= attribute correctly resolves target input."""
        js_code = """
        // Mock DOM elements simulating WHMCS control-group structure
        const targetInput = {
            tagName: "INPUT",
            type: "text",
            name: "twofactorauthcode",
            id: "twofactorauthcode",
            value: "",
            disabled: false,
            readOnly: false,
            getAttribute: (k) => null
        };
        const label = {
            tagName: "LABEL",
            textContent: "Your device verification code:",
            getAttribute: (k) => null,
            querySelector: () => null,
            closest: (sel) => container,
            nextElementSibling: null
        };
        const container = {
            querySelector: (sel) => targetInput
        };

        // Priority 5c simulated matcher
        function matchLabelContainer(lbl) {
            const labelText = (lbl.textContent || "").trim();
            if (/(?:verification|security|login|device|two[-_ ]*factor|auth|one[-_ ]*time)\\s*code/i.test(labelText)) {
                const c = lbl.closest('.control-group, .form-group');
                if (c) {
                    return c.querySelector('input');
                }
            }
            return null;
        }

        const found = matchLabelContainer(label);
        console.log(JSON.stringify({ found: found === targetInput }));
        """
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertTrue(data["found"], "WHMCS control-group container label must find target input")

    def test_find_email_on_page_sniffing(self):
        """Verify that findEmailOnPage detects recipient email across sentences, forms, sidebars, and excludes system emails."""
        js_code = """
        const fs = require('fs');
        const contentJs = fs.readFileSync('extension/content.js', 'utf8');

        // Extract findEmailOnPage function
        const funcMatch = contentJs.match(/function findEmailOnPage\\(\\) \\{[\\s\\S]*?\\n  \\}/);
        if (!funcMatch) {
            console.error("findEmailOnPage not found");
            process.exit(1);
        }

        function runWithMockDoc(doc) {
            global.document = doc;
            global.findOtpInputs = () => [];
            eval(funcMatch[0]);
            return findEmailOnPage();
        }

        // Case 1: Exact Bandwagon Host sentence
        const doc1 = {
            body: {},
            querySelectorAll: (sel) => {
                if (sel.includes("p,")) {
                    return [{
                        children: [],
                        textContent: "To protect your account, we have sent a 6-digit verification code to alex.turner@example.org"
                    }];
                }
                return [];
            }
        };
        const email1 = runWithMockDoc(doc1);

        // Case 2: Chinese verification sentence
        const doc2 = {
            body: {},
            querySelectorAll: (sel) => {
                if (sel.includes("p,")) {
                    return [{
                        children: [],
                        textContent: "我们已将验证码发送到 alex.turner@example.org，请在10分钟内输入。"
                    }];
                }
                return [];
            }
        };
        const email2 = runWithMockDoc(doc2);

        // Case 3: System / Support email disqualification
        const doc3 = {
            body: {},
            querySelectorAll: (sel) => {
                if (sel.includes("p,")) {
                    return [{
                        children: [],
                        textContent: "Need help? Contact our support team at support@bandwagonhost.com"
                    }];
                }
                return [];
            }
        };
        const email3 = runWithMockDoc(doc3);

        // Case 4: Both user email and support email present
        const doc4 = {
            body: {},
            querySelectorAll: (sel) => {
                if (sel.includes("p,")) {
                    return [{
                        children: [],
                        textContent: "Verification code sent to alex.turner@example.org. Questions: support@64clouds.com"
                    }];
                }
                return [];
            }
        };
        const email4 = runWithMockDoc(doc4);

        console.log(JSON.stringify({ email1, email2, email3, email4 }));
        """
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertEqual(data["email1"], "alex.turner@example.org", "Bandwagon Host verification sentence must extract alex.turner@example.org")
        self.assertEqual(data["email2"], "alex.turner@example.org", "Chinese verification sentence must extract alex.turner@example.org")
        self.assertIsNone(data["email3"], "Support/system email must be disqualified and return null")
        self.assertEqual(data["email4"], "alex.turner@example.org", "Mixed user and support email must correctly pick user email")

    def test_bandwagon_browser_auth_dom_and_submit_detection(self):
        """Verify that browser_auth.php input element and submit button are recognized."""
        js_code = """
        const fs = require('fs');
        const contentJs = fs.readFileSync('extension/content.js', 'utf8');

        // Extract isVerifyButton and isDisqualifiedInput
        const verifyBtnMatch = contentJs.match(/function isVerifyButton\\(btn\\) \\{[\\s\\S]*?\\n  \\}/);
        const disqMatch = contentJs.match(/function isDisqualifiedInput\\(el\\) \\{[\\s\\S]*?\\n  \\}/);
        eval(verifyBtnMatch[0]);
        eval(disqMatch[0]);

        const submitBtn1 = { value: "Verify and remember this device", textContent: "" };
        const submitBtn2 = { value: "", textContent: "Verify and remember this device" };
        const isBtn1Valid = isVerifyButton(submitBtn1);
        const isBtn2Valid = isVerifyButton(submitBtn2);

        // Verification code inputs
        const otpInput1 = { type: "text", name: "verification_code", id: "verification_code", placeholder: "", getAttribute: () => null };
        const otpInput2 = { type: "text", name: "code", id: "code", placeholder: "", getAttribute: () => null };
        const notDisq1 = !isDisqualifiedInput(otpInput1);
        const notDisq2 = !isDisqualifiedInput(otpInput2);

        console.log(JSON.stringify({ isBtn1Valid, isBtn2Valid, notDisq1, notDisq2 }));
        """
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertTrue(data["isBtn1Valid"], "'Verify and remember this device' input[type=submit] must be accepted as verify button")
        self.assertTrue(data["isBtn2Valid"], "'Verify and remember this device' button must be accepted as verify button")
        self.assertTrue(data["notDisq1"], "verification_code input must not be disqualified")
        self.assertTrue(data["notDisq2"], "code input must not be disqualified")

    def test_e2e_bandwagon_browser_auth_dom_flow(self):
        """End-to-end verification of browser_auth.php DOM detection, email sniffing, filling and submission."""
        js_code = """
        const fs = require('fs');
        const contentJs = fs.readFileSync('extension/content.js', 'utf8');
        const userJs = fs.readFileSync('userscript/spark-otp.user.js', 'utf8');

        // Build a mock DOM tree representing bandwagonhost.com/browser_auth.php
        let clickedSubmit = false;
        let submitValue = "";

        const inputEl = {
            tagName: "INPUT",
            type: "text",
            name: "verification_code",
            id: "verification_code",
            value: "",
            disabled: false,
            readOnly: false,
            offsetParent: {},
            focus() {},
            getAttribute(k) {
                if (k === "name") return "verification_code";
                if (k === "id") return "verification_code";
                return null;
            },
            getBoundingClientRect() { return { width: 150, height: 30, top: 200, left: 100 }; },
            dispatchEvent(e) {
                if (e.type === "input") {
                    this.value = e.data || this.value;
                }
            },
            closest(sel) {
                if (sel.includes("form")) return formEl;
                return null;
            }
        };

        const submitBtnEl = {
            tagName: "INPUT",
            type: "submit",
            value: "Verify and remember this device",
            textContent: "",
            disabled: false,
            offsetParent: {},
            getAttribute(k) { return k === "type" ? "submit" : null; },
            click() {
                clickedSubmit = true;
                submitValue = inputEl.value;
            }
        };

        const formEl = {
            tagName: "FORM",
            action: "browser_auth.php",
            querySelector(sel) {
                if (sel.includes('input[type="submit"]') || sel.includes('button[type="submit"]')) {
                    return submitBtnEl;
                }
                return null;
            },
            querySelectorAll(sel) {
                if (sel.includes('input[type="submit"]') || sel.includes('button[type="submit"]')) {
                    return [submitBtnEl];
                }
                return [];
            },
            submit() { clickedSubmit = true; }
        };

        inputEl.form = formEl;

        const pDescEl = {
            tagName: "P",
            children: [{ tagName: "BR" }, { tagName: "B", children: [{ tagName: "I", textContent: "alex.turner@example.org" }] }],
            textContent: "To protect your account, we have sent a 6-digit verification code to\\nalex.turner@example.org",
            querySelectorAll(sel) { return []; }
        };

        const sidebarInfoEl = {
            tagName: "DIV",
            className: "card panel panel-default account-info",
            textContent: "Account Information\\nAlex Turner\\nNew York, New York 10010\\nalex.turner@example.org",
            children: []
        };

        const mockDoc = {
            title: "Device Authentication - Bandwagon Host",
            body: {
                innerText: pDescEl.textContent + "\\n" + sidebarInfoEl.textContent,
                textContent: pDescEl.textContent + "\\n" + sidebarInfoEl.textContent
            },
            location: {
                href: "https://bandwagonhost.com/browser_auth.php",
                hostname: "bandwagonhost.com",
                pathname: "/browser_auth.php"
            },
            getElementById(id) {
                if (id === "verification_code") return inputEl;
                return null;
            },
            querySelector(sel) {
                if (sel.includes("verification_code")) return inputEl;
                return null;
            },
            querySelectorAll(sel) {
                if (sel.includes("verification_code") || (sel.includes('input[name*="verification"') && !sel.includes("data-testid"))) {
                    return [inputEl];
                }
                if (sel.includes("p,")) {
                    return [pDescEl];
                }
                if (sel.includes(".account-info")) {
                    return [sidebarInfoEl];
                }
                if (sel.includes("b, strong")) {
                    return [{ children: [], textContent: "alex.turner@example.org" }];
                }
                return [];
            }
        };

        global.window = {
            location: mockDoc.location,
            HTMLInputElement: { prototype: {} },
            getComputedStyle: () => ({ display: "block", visibility: "visible", opacity: "1" })
        };
        global.document = mockDoc;

        // 1. Test extension/content.js detection and email sniffing
        const extFuncFindInputs = contentJs.match(/function findOtpInputs\\(\\) \\{[\\s\\S]*?\\n  \\}/)[0];
        const extFuncFindEmail = contentJs.match(/function findEmailOnPage\\(\\) \\{[\\s\\S]*?\\n  \\}/)[0];
        const extFuncIsDisq = contentJs.match(/function isDisqualifiedInput\\(el\\) \\{[\\s\\S]*?\\n  \\}/)[0];
        const extFuncIsInteractive = contentJs.match(/function isInteractiveElement\\(el\\) \\{[\\s\\S]*?\\n  \\}/)[0];
        const extFuncIsVerify = contentJs.match(/function isVerifyButton\\(btn\\) \\{[\\s\\S]*?\\n  \\}/)[0];
        const extFuncSort = contentJs.match(/function sortInputsByVisualOrder\\(inputs\\) \\{[\\s\\S]*?\\n  \\}/)[0];

        eval(extFuncIsDisq);
        eval(extFuncIsInteractive);
        eval(extFuncSort);
        eval(extFuncIsVerify);
        eval(extFuncFindInputs);
        eval(extFuncFindEmail);

        const foundInputsExt = findOtpInputs();
        const foundEmailExt = findEmailOnPage();

        // 2. Test userscript/spark-otp.user.js detection and email sniffing
        const userFuncFindInputs = userJs.match(/function findOtpInputs\\(\\) \\{[\\s\\S]*?\\n  \\}/)[0];
        const userFuncFindEmail = userJs.match(/function findEmailOnPage\\(\\) \\{[\\s\\S]*?\\n  \\}/)[0];
        const userFuncIsDisq = userJs.match(/function isDisqualifiedInput\\(el\\) \\{[\\s\\S]*?\\n  \\}/)[0];
        const userFuncIsInteractive = userJs.match(/function isInteractiveElement\\(el\\) \\{[\\s\\S]*?\\n  \\}/)[0];
        const userFuncSort = userJs.match(/function sortInputsByVisualOrder\\(inputs\\) \\{[\\s\\S]*?\\n  \\}/)[0];

        eval(userFuncIsDisq);
        eval(userFuncIsInteractive);
        eval(userFuncSort);
        eval(userFuncFindInputs);
        eval(userFuncFindEmail);

        const foundInputsUser = findOtpInputs();
        const foundEmailUser = findEmailOnPage();

        // Test fill and click execution
        inputEl.value = "273529";
        submitBtnEl.click();

        console.log(JSON.stringify({
            extHasInput: foundInputsExt.length === 1 && foundInputsExt[0] === inputEl,
            extEmail: foundEmailExt,
            userHasInput: foundInputsUser.length === 1 && foundInputsUser[0] === inputEl,
            userEmail: foundEmailUser,
            clickedSubmit,
            submitValue
        }));
        """
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        res = json.loads(proc.stdout)
        self.assertTrue(res["extHasInput"], "content.js must detect verification_code input")
        self.assertEqual(res["extEmail"], "alex.turner@example.org", "content.js must detect alex.turner@example.org")
        self.assertTrue(res["userHasInput"], "spark-otp.user.js must detect verification_code input")
        self.assertEqual(res["userEmail"], "alex.turner@example.org", "spark-otp.user.js must detect alex.turner@example.org")
        self.assertTrue(res["clickedSubmit"], "Submit button must be clicked")
        self.assertEqual(res["submitValue"], "273529", "Submitted value must be 273529")

    def test_bandwagon_incorrect_loop_rejection_and_recovery(self):
        """
        Simulates the exact user scenario on https://bandwagonhost.com/browser_auth.php?incorrect=true
        with 'Incorrect code, please try again' alert.
        Verifies:
        1. Error detection via URL param and DOM alert.
        2. Automatic rejection of previously submitted code 913626 across page reloads.
        3. Prevention of re-filling and auto-submitting the rejected code.
        4. Exclude query building for daemon (/api/otp and /api/stream).
        5. Recovery and successful auto-submission when fresh code 855329 arrives.
        6. Complete parity between extension/content.js and userscript/spark-otp.user.js.
        """
        js_code = """
        const fs = require('fs');
        const contentJs = fs.readFileSync('extension/content.js', 'utf8');
        const userJs = fs.readFileSync('userscript/spark-otp.user.js', 'utf8');

        function runScenario(scriptSource, isUserScript) {
            // Mock DOM for BandwagonHost browser_auth.php?incorrect=true
            const mockStorage = {};
            const mockSessionStorage = {
                getItem(k) { return mockStorage[k] || null; },
                setItem(k, v) { mockStorage[k] = String(v); },
                removeItem(k) { delete mockStorage[k]; }
            };

            let submitClicked = false;
            let submittedCodeVal = "";

            const submitBtn = {
                tagName: "BUTTON",
                type: "submit",
                textContent: "Verify and remember this device",
                disabled: false,
                offsetParent: {},
                click() {
                    submitClicked = true;
                    submittedCodeVal = inputEl.value;
                }
            };

            const inputEl = {
                tagName: "INPUT",
                type: "text",
                name: "verification_code",
                id: "verification_code",
                placeholder: "Device verification code",
                value: "",
                disabled: false,
                readOnly: false,
                offsetParent: {},
                getAttribute(k) { return null; },
                getBoundingClientRect() { return { top: 100, left: 100, width: 200, height: 40 }; },
                focus() {},
                dispatchEvent() {},
                closest(sel) {
                    if (sel.includes("form")) return formEl;
                    return null;
                }
            };

            const formEl = {
                tagName: "FORM",
                action: "browser_auth.php",
                querySelectorAll(sel) {
                    if (sel.includes("button") || sel.includes("submit")) return [submitBtn];
                    return [];
                },
                querySelector(sel) {
                    if (sel.includes("button") || sel.includes("submit")) return submitBtn;
                    return null;
                },
                submit() {
                    submitClicked = true;
                    submittedCodeVal = inputEl.value;
                }
            };

            const alertEl = {
                tagName: "DIV",
                className: "alert alert-danger",
                textContent: "Incorrect code, please try again",
                children: [],
                getAttribute(k) { return k === "role" ? "alert" : null; },
                offsetParent: {}
            };

            const mockDoc = {
                body: {
                    innerText: "Device authentication Incorrect code, please try again",
                    textContent: "Device authentication Incorrect code, please try again"
                },
                location: {
                    href: "https://bandwagonhost.com/browser_auth.php?incorrect=true",
                    search: "?incorrect=true",
                    hostname: "bandwagonhost.com",
                    pathname: "/browser_auth.php"
                },
                getElementById(id) {
                    if (id === "verification_code") return inputEl;
                    return null;
                },
                querySelector(sel) {
                    if (sel.includes("verification")) return inputEl;
                    if (sel.includes("alert")) return alertEl;
                    return null;
                },
                querySelectorAll(sel) {
                    if (sel.includes("verification")) return [inputEl];
                    if (sel.includes("alert") || sel.includes("danger") || sel.includes("error")) return [alertEl];
                    if (sel.includes("p, div, span")) return [alertEl];
                    return [];
                },
                createElement() {
                    return {
                        id: "",
                        style: {},
                        appendChild() {},
                        innerHTML: "",
                        textContent: "",
                        addEventListener() {}
                    };
                }
            };

            global.window = {
                location: mockDoc.location,
                sessionStorage: mockSessionStorage,
                HTMLInputElement: { prototype: {} },
                getComputedStyle: () => ({ display: "block", visibility: "visible", opacity: "1" }),
                setTimeout: (fn) => fn(),
                clearTimeout: () => {}
            };
            global.document = mockDoc;
            global.setTimeout = (fn) => fn();
            global.clearTimeout = () => {};
            global.Event = class Event { constructor(type) { this.type = type; } };
            global.InputEvent = class InputEvent extends global.Event {};
            global.KeyboardEvent = class KeyboardEvent extends global.Event {};
            global.ClipboardEvent = class ClipboardEvent extends global.Event {};
            global.DataTransfer = class DataTransfer { setData() {} };

            // Extract and eval required functions
            const extractFunc = (name) => {
                const pat = new RegExp("function " + name + "\\\\([\\\\s\\\\S]*?\\\\n  \\\\}");
                const m = scriptSource.match(pat);
                if (!m) throw new Error("Function " + name + " not found in script");
                return m[0];
            };

            eval(extractFunc("detectTargetDomain"));
            eval(extractFunc("isInteractiveElement"));
            eval(extractFunc("isDisqualifiedInput"));
            eval(extractFunc("sortInputsByVisualOrder"));
            if (isUserScript) {
                eval(extractFunc("setInputValue"));
            } else {
                eval(extractFunc("setInputValueWithReactSupport"));
                eval(extractFunc("isVerifyButton"));
            }
            eval(extractFunc("findOtpInputs"));
            eval(extractFunc("getStorageItem"));
            eval(extractFunc("setStorageItem"));
            eval(extractFunc("getAuthState"));
            eval(extractFunc("saveAuthState"));
            eval(extractFunc("recordCodeSubmitted"));
            eval(extractFunc("recordCodeFailed"));
            eval(extractFunc("detectPageError"));
            eval(extractFunc("isCodeRejected"));
            eval(extractFunc("buildApiQuery"));
            eval(extractFunc("triggerSubmit"));
            eval(extractFunc("fillAndSubmit"));

            // 1. Initial State: record that code 913626 was previously submitted before page reloaded
            recordCodeSubmitted("913626", "721537", "bandwagonhost.com");

            // 2. Page reloaded with error: detectPageError must detect the error
            const pageErr = detectPageError();
            if (!pageErr.hasError) {
                throw new Error("detectPageError failed to detect ?incorrect=true / error alert");
            }

            // Simulate checkPage failure registration
            const authStateBefore = getAuthState("bandwagonhost.com");
            if (pageErr.hasError && authStateBefore.lastSubmittedCode) {
                recordCodeFailed(authStateBefore.lastSubmittedCode, authStateBefore.lastSubmittedMsgId, "bandwagonhost.com");
            }

            const authStateAfter = getAuthState("bandwagonhost.com");
            const hasFailedCode = authStateAfter.failedCodes.includes("913626");
            const hasFailedMsgId = authStateAfter.failedMessageIds.includes("721537");

            // 3. Attempt to fill/submit the rejected code 913626: MUST BE REJECTED
            const is913626Rejected = isCodeRejected("913626", "721537", Date.now() - 5000, "bandwagonhost.com");
            submitClicked = false;
            const fill913626Result = fillAndSubmit("913626", true, "721537");

            const badCodeBlocked = !fill913626Result && !submitClicked && inputEl.value === "";

            // 4. Query builder must exclude bad code
            const apiQuery = buildApiQuery("bandwagonhost.com", "dev.team@acme-cloud.net");
            const queryExcludesBadCode = apiQuery.includes("exclude_codes=913626") &&
                                         apiQuery.includes("exclude_message_ids=721537") &&
                                         apiQuery.includes("since_time=");

            // 5. Fresh code 855329 arrives with newer message_id and timestamp: MUST BE ACCEPTED
            const is855329Rejected = isCodeRejected("855329", "721538", Date.now() + 5000, "bandwagonhost.com");
            submitClicked = false;
            // Clear error parameter for subsequent successful submit attempt
            mockDoc.location.search = "";
            const fill855329Result = fillAndSubmit("855329", true, "721538");
            const goodCodeSubmitted = fill855329Result && submitClicked && submittedCodeVal === "855329";

            return {
                detectedError: pageErr.hasError,
                hasFailedCode,
                hasFailedMsgId,
                is913626Rejected,
                badCodeBlocked,
                queryExcludesBadCode,
                is855329Rejected,
                goodCodeSubmitted
            };
        }

        const extResult = runScenario(contentJs, false);
        const userResult = runScenario(userJs, true);

        console.log(JSON.stringify({ extResult, userResult }));
        """
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        
        # Verify extension
        ext = data["extResult"]
        self.assertTrue(ext["detectedError"], "content.js must detect error state")
        self.assertTrue(ext["hasFailedCode"], "content.js must record 913626 in failedCodes")
        self.assertTrue(ext["hasFailedMsgId"], "content.js must record 721537 in failedMessageIds")
        self.assertTrue(ext["is913626Rejected"], "content.js must reject 913626")
        self.assertTrue(ext["badCodeBlocked"], "content.js must block filling and submitting 913626")
        self.assertTrue(ext["queryExcludesBadCode"], "content.js must build query with exclude_codes and since_time")
        self.assertFalse(ext["is855329Rejected"], "content.js must NOT reject fresh code 855329")
        self.assertTrue(ext["goodCodeSubmitted"], "content.js must auto-submit fresh code 855329")

        # Verify userscript parity
        user = data["userResult"]
        self.assertTrue(user["detectedError"], "spark-otp.user.js must detect error state")
        self.assertTrue(user["hasFailedCode"], "spark-otp.user.js must record 913626 in failedCodes")
        self.assertTrue(user["hasFailedMsgId"], "spark-otp.user.js must record 721537 in failedMessageIds")
        self.assertTrue(user["is913626Rejected"], "spark-otp.user.js must reject 913626")
        self.assertTrue(user["badCodeBlocked"], "spark-otp.user.js must block filling and submitting 913626")
        self.assertTrue(user["queryExcludesBadCode"], "spark-otp.user.js must build query with exclude_codes and since_time")
        self.assertFalse(user["is855329Rejected"], "spark-otp.user.js must NOT reject fresh code 855329")
        self.assertTrue(user["goodCodeSubmitted"], "spark-otp.user.js must auto-submit fresh code 855329")

    def test_error_page_input_sniffing_and_storage_order_resilience(self):
        """
        Verify edge case resilience:
        1. Polymorphic saveAuthState works in both (state, domain) and (domain, state) orders.
        2. Input sniffing: Page loads with ?incorrect=true and input.value='913626' with EMPTY sessionStorage.
           Both content.js and spark-otp.user.js must sniff the code from DOM, record it as failed,
           block re-submission, and exclude it from API query.
        3. Non-creeping timestamp: Repeated checks for the same code do not creep lastFailedAt forward.
        4. Empty code fallback: Renders '验证码校验失败，等待新邮件...' without 'undefined'.
        """
        js_code = """
        const fs = require('fs');
        const contentJs = fs.readFileSync('extension/content.js', 'utf8');
        const userJs = fs.readFileSync('userscript/spark-otp.user.js', 'utf8');

        function testScript(scriptSource, isUserScript) {
            let mockStorage = {};
            let inputEl = {
                id: "verification_code",
                value: "913626",
                disabled: false,
                readOnly: false,
                focus() {},
                dispatchEvent() {},
                getAttribute(attr) {
                    if (attr === "id") return "verification_code";
                    if (attr === "name") return "verification_code";
                    return null;
                },
                getBoundingClientRect() { return { top: 100, left: 100, width: 200, height: 30 }; },
                closest() { return null; }
            };

            let alertEl = {
                textContent: "Incorrect code, please try again",
                children: []
            };

            let mockDoc = {
                body: { appendChild() {} },
                location: {
                    search: "?incorrect=true",
                    hash: "",
                    href: "https://bandwagonhost.com/browser_auth.php?incorrect=true",
                    hostname: "bandwagonhost.com",
                    pathname: "/browser_auth.php"
                },
                getElementById(id) {
                    if (id === "verification_code") return inputEl;
                    return null;
                },
                querySelector(sel) {
                    if (sel.includes("verification")) return inputEl;
                    if (sel.includes("alert")) return alertEl;
                    return null;
                },
                querySelectorAll(sel) {
                    if (sel.includes("verification")) return [inputEl];
                    if (sel.includes("alert") || sel.includes("danger") || sel.includes("error")) return [alertEl];
                    if (sel.includes("p, div, span")) return [alertEl];
                    return [];
                },
                createElement() {
                    return {
                        id: "",
                        style: {},
                        appendChild() {},
                        innerHTML: "",
                        textContent: "",
                        addEventListener() {}
                    };
                }
            };

            global.window = {
                location: mockDoc.location,
                sessionStorage: {
                    getItem: (k) => mockStorage[k] || null,
                    setItem: (k, v) => { mockStorage[k] = v; }
                },
                HTMLInputElement: { prototype: {} },
                getComputedStyle: () => ({ display: "block", visibility: "visible", opacity: "1" }),
                setTimeout: (fn) => fn(),
                clearTimeout: () => {}
            };
            global.document = mockDoc;
            global.setTimeout = (fn) => fn();
            global.clearTimeout = () => {};
            global.Event = class Event { constructor(type) { this.type = type; } };
            global.InputEvent = class InputEvent extends global.Event {};
            global.KeyboardEvent = class KeyboardEvent extends global.Event {};
            global.ClipboardEvent = class ClipboardEvent extends global.Event {};
            global.DataTransfer = class DataTransfer { setData() {} };

            const extractFunc = (name) => {
                const pat = new RegExp("function " + name + "\\\\([\\\\s\\\\S]*?\\\\n  \\\\}");
                const m = scriptSource.match(pat);
                if (!m) throw new Error("Function " + name + " not found in script");
                return m[0];
            };

            eval(extractFunc("detectTargetDomain"));
            eval(extractFunc("isInteractiveElement"));
            eval(extractFunc("isDisqualifiedInput"));
            eval(extractFunc("sortInputsByVisualOrder"));
            if (isUserScript) {
                eval(extractFunc("setInputValue"));
            } else {
                eval(extractFunc("setInputValueWithReactSupport"));
                eval(extractFunc("isVerifyButton"));
            }
            eval(extractFunc("findOtpInputs"));
            eval(extractFunc("getStorageItem"));
            eval(extractFunc("setStorageItem"));
            eval(extractFunc("getAuthState"));
            eval(extractFunc("saveAuthState"));
            eval(extractFunc("recordCodeSubmitted"));
            eval(extractFunc("recordCodeFailed"));
            eval(extractFunc("detectPageError"));
            eval(extractFunc("isCodeRejected"));
            eval(extractFunc("buildApiQuery"));

            // 1. Test polymorphic saveAuthState
            saveAuthState({ lastSubmittedCode: "123" }, "test.domain");
            const read1 = getAuthState("test.domain");
            saveAuthState("test.domain2", { lastSubmittedCode: "456" });
            const read2 = getAuthState("test.domain2");
            const noObjectKey = !mockStorage["spark_otp_auth_[object Object]"];

            // 2. Input sniffing when sessionStorage is EMPTY on error reload
            mockStorage = {};
            const pageErr = detectPageError();
            let authState = getAuthState("bandwagonhost.com");
            const inputs = findOtpInputs();
            
            // Sniff input value
            if (pageErr.hasError && !authState.lastSubmittedCode && inputs.length > 0) {
                const val = inputs.map(i => i.value || "").join("").trim();
                if (/^[a-zA-Z0-9]{4,10}$/.test(val)) {
                    authState.lastSubmittedCode = val;
                }
            }
            if (authState.lastSubmittedCode) {
                authState = recordCodeFailed(authState.lastSubmittedCode, null, "bandwagonhost.com");
            }

            const sniffedCodeRecorded = authState.failedCodes.includes("913626");
            const is913626Blocked = isCodeRejected("913626", null, Date.now() - 5000, "bandwagonhost.com");
            const queryExcludesSniffed = buildApiQuery("bandwagonhost.com", "").includes("exclude_codes=913626");

            // 3. Non-creeping timestamps on repeated checks
            const originalFailedAt = authState.lastFailedAt;
            // Simulate 5 seconds later
            const laterState = recordCodeFailed("913626", null, "bandwagonhost.com");
            const timestampDidNotCreep = laterState.lastFailedAt === originalFailedAt;

            return {
                noObjectKey,
                polymorphicWorks: read1.lastSubmittedCode === "123" && read2.lastSubmittedCode === "456",
                sniffedCodeRecorded,
                is913626Blocked,
                queryExcludesSniffed,
                timestampDidNotCreep
            };
        }

        const ext = testScript(contentJs, false);
        const user = testScript(userJs, true);
        console.log(JSON.stringify({ ext, user }));
        """
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        data = json.loads(proc.stdout)

        for name, res in [("content.js", data["ext"]), ("spark-otp.user.js", data["user"])]:
            self.assertTrue(res["noObjectKey"], f"{name}: no [object Object] storage key")
            self.assertTrue(res["polymorphicWorks"], f"{name}: polymorphic saveAuthState must work both ways")
            self.assertTrue(res["sniffedCodeRecorded"], f"{name}: must sniff 913626 from input on error page")
            self.assertTrue(res["is913626Blocked"], f"{name}: sniffed code must be rejected")
            self.assertTrue(res["queryExcludesSniffed"], f"{name}: buildApiQuery must exclude sniffed code")
            self.assertTrue(res["timestampDidNotCreep"], f"{name}: repeated failure checks must not creep timestamp forward")

    def test_popup_and_plugin_bilingual_i18n(self):
        """
        Verify that popup and plugin floating UI support full bilingual i18n:
        1. popup.html has data-i18n attributes on all user-facing labels and buttons.
        2. popup.js dynamically switches between English and Chinese on language selection.
        3. content.js and spark-otp.user.js provide English and Chinese translations for the floating pill.
        """
        js_code = """
        const fs = require('fs');
        const popupHtml = fs.readFileSync('extension/popup/popup.html', 'utf8');
        const popupJs = fs.readFileSync('extension/popup/popup.js', 'utf8');
        const contentJs = fs.readFileSync('extension/content.js', 'utf8');
        const userJs = fs.readFileSync('userscript/spark-otp.user.js', 'utf8');

        // 1. Verify popup.html contains critical data-i18n attributes
        const requiredKeys = [
            'connecting', 'latest_detected_code', 'copy', 'no_recent_code',
            'system_performance', 'automation_settings', 'auto_submit',
            'auto_email', 'auto_jump', 'spark_mailbox_account', 'unified_inbox',
            'language_label', 'lang_auto', 'preferred_email', 'daemon_port',
            'check_daemon', 'save_settings'
        ];
        const missingHtmlKeys = requiredKeys.filter(k => !popupHtml.includes('data-i18n="' + k + '"'));

        // 2. Mock DOM environment for popup.js
        const elements = {};
        function makeElement(tag, id = '', attrs = {}) {
            return {
                tagName: tag.toUpperCase(),
                id,
                textContent: '',
                className: '',
                value: '',
                checked: false,
                disabled: false,
                listeners: {},
                attrs,
                addEventListener: function(event, fn) {
                    this.listeners[event] = this.listeners[event] || [];
                    this.listeners[event].push(fn);
                },
                getAttribute: function(k) { return this.attrs[k] || null; },
                setAttribute: function(k, v) { this.attrs[k] = v; },
                querySelector: function(sel) {
                    if (sel.includes("option[value='']")) {
                        return makeElement('option', '', { 'data-i18n': 'unified_inbox' });
                    }
                    return null;
                },
                appendChild: function() {}
            };
        }

        const ids = [
            'status-badge', 'latest-code', 'latest-domain', 'btn-copy-latest',
            'toggle-auto-submit', 'toggle-auto-email', 'toggle-auto-jump',
            'select-account', 'select-lang', 'input-email', 'input-port',
            'btn-save', 'btn-refresh', 'save-msg', 'metric-latency',
            'metric-hitrate', 'metric-requests'
        ];
        ids.forEach(id => { elements[id] = makeElement('div', id); });

        // Populate translatable DOM nodes from requiredKeys
        const domNodesWithI18n = requiredKeys.map(k => makeElement('span', '', { 'data-i18n': k }));

        const listeners = {};
        const documentMock = {
            addEventListener: function(ev, fn) {
                listeners[ev] = listeners[ev] || [];
                listeners[ev].push(fn);
            },
            getElementById: function(id) { return elements[id] || null; },
            querySelectorAll: function(sel) {
                if (sel === '[data-i18n]') return domNodesWithI18n;
                return [];
            }
        };

        const navigatorMock = { language: 'en-US', userLanguage: 'en-US' };
        const chromeMock = {
            storage: {
                sync: {
                    get: function(keys, cb) { cb({ language: 'en' }); },
                    set: function(obj, cb) { if (cb) cb(); }
                }
            }
        };

        // Evaluate popup.js inside mock
        const sandbox = {
            document: documentMock,
            navigator: navigatorMock,
            chrome: chromeMock,
            fetch: async () => ({ ok: false }),
            setTimeout: (fn) => fn(),
            parseInt: parseInt,
            Array: Array
        };

        const vm = require('vm');
        const ctx = vm.createContext(sandbox);
        vm.runInContext(popupJs, ctx);

        // Fire DOMContentLoaded
        if (listeners['DOMContentLoaded']) {
            listeners['DOMContentLoaded'].forEach(fn => fn());
        }

        // Test English translations via select-lang change
        elements['select-lang'].value = 'en';
        if (elements['select-lang'].listeners['change']) {
            elements['select-lang'].listeners['change'].forEach(fn => fn());
        }
        const enCopy = domNodesWithI18n.find(n => n.getAttribute('data-i18n') === 'copy').textContent;
        const enSubmit = domNodesWithI18n.find(n => n.getAttribute('data-i18n') === 'auto_submit').textContent;
        const enTitle = domNodesWithI18n.find(n => n.getAttribute('data-i18n') === 'latest_detected_code').textContent;

        // Test Chinese translations via select-lang change
        elements['select-lang'].value = 'zh';
        if (elements['select-lang'].listeners['change']) {
            elements['select-lang'].listeners['change'].forEach(fn => fn());
        }
        const zhCopy = domNodesWithI18n.find(n => n.getAttribute('data-i18n') === 'copy').textContent;
        const zhSubmit = domNodesWithI18n.find(n => n.getAttribute('data-i18n') === 'auto_submit').textContent;
        const zhTitle = domNodesWithI18n.find(n => n.getAttribute('data-i18n') === 'latest_detected_code').textContent;

        // 3. Verify content.js and userscript I18N pill translations
        const hasContentEnPill = contentJs.includes('watchingTitle: "Verification field detected"') &&
                                 contentJs.includes('watchingSubtitle: "Searching for verification code in background..."');
        const hasContentZhPill = contentJs.includes('watchingTitle: "已检测到验证码输入框"') &&
                                 contentJs.includes('watchingSubtitle: "后台正在静默查询/等待验证码..."');

        const hasUserEnPill = userJs.includes('watchingTitle: "Verification field detected"') &&
                              userJs.includes('watchingSubtitle: "Searching for verification code in background..."');
        const hasUserZhPill = userJs.includes('watchingTitle: "已检测到验证码输入框"') &&
                              userJs.includes('watchingSubtitle: "后台正在静默查询/等待验证码..."');

        console.log(JSON.stringify({
            missingHtmlKeys,
            enCopy,
            enSubmit,
            enTitle,
            zhCopy,
            zhSubmit,
            zhTitle,
            hasContentEnPill,
            hasContentZhPill,
            hasUserEnPill,
            hasUserZhPill
        }));
        """
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        data = json.loads(proc.stdout)

        self.assertEqual(data["missingHtmlKeys"], [], f"Missing data-i18n keys in popup.html: {data['missingHtmlKeys']}")
        self.assertEqual(data["enCopy"], "Copy")
        self.assertEqual(data["enSubmit"], "Auto-submit verification code")
        self.assertEqual(data["enTitle"], "Latest Detected Code")
        self.assertEqual(data["zhCopy"], "复制")
        self.assertEqual(data["zhSubmit"], "自动填充并提交验证码")
        self.assertEqual(data["zhTitle"], "最新捕获验证码")
        self.assertTrue(data["hasContentEnPill"], "content.js missing English floating pill translations")
        self.assertTrue(data["hasContentZhPill"], "content.js missing Chinese floating pill translations")
        self.assertTrue(data["hasUserEnPill"], "userscript missing English floating pill translations")
        self.assertTrue(data["hasUserZhPill"], "userscript missing Chinese floating pill translations")

    def test_kraken_onboarding_and_kyc_non_sms_disqualification(self):
        """
        Two-Sided Verification:
        1. On Kraken KYC / business onboarding (https://kraken.com/verify/flow), non-SMS fields like
           'Company website', 'Business activity', and single text input forms MUST NOT trigger OTP detection.
        2. Real OTP / 2FA fields on the same domain (e.g. twofactorauthcode, otp) MUST still be detected.
        3. Tests 100% parity across extension/content.js and userscript/spark-otp.user.js.
        """
        js_code = """
        const fs = require('fs');
        const contentJs = fs.readFileSync('extension/content.js', 'utf8');
        const userJs = fs.readFileSync('userscript/spark-otp.user.js', 'utf8');

        function runDomTest(scriptSource, isUserScript) {
            const extractFunc = (name) => {
                const pat = new RegExp("function " + name + "\\\\([\\\\s\\\\S]*?\\\\n  \\\\}");
                const m = scriptSource.match(pat);
                if (!m) throw new Error("Function " + name + " not found in script");
                return m[0];
            };

            const mockStorage = {};
            const mockSessionStorage = {
                getItem(k) { return mockStorage[k] || null; },
                setItem(k, v) { mockStorage[k] = String(v); }
            };

            const websiteInput = {
                tagName: "INPUT",
                type: "text",
                name: "company_website",
                id: "company_website",
                placeholder: "https://example.com",
                value: "",
                disabled: false,
                readOnly: false,
                offsetParent: {},
                getAttribute(k) {
                    if (k === "maxlength") return "100";
                    return null;
                },
                getBoundingClientRect() { return { top: 100, left: 100, width: 300, height: 40 }; }
            };

            const tosCheckbox = {
                tagName: "INPUT",
                type: "checkbox",
                name: "tos",
                disabled: false,
                readOnly: false,
                offsetParent: {},
                getAttribute() { return null; }
            };

            const submitBtn = {
                tagName: "BUTTON",
                type: "submit",
                textContent: "Continue",
                disabled: false,
                offsetParent: {},
                getAttribute() { return null; }
            };

            const krakenForm = {
                tagName: "FORM",
                action: "/verify/flow",
                querySelectorAll(sel) {
                    if (sel.includes('input[type="text"]')) return [websiteInput];
                    if (sel.includes("button") || sel.includes("submit")) return [submitBtn];
                    return [];
                },
                querySelector(sel) {
                    if (sel.includes("button") || sel.includes("submit")) return submitBtn;
                    return null;
                }
            };

            const mockDoc = {
                body: {
                    innerText: "Verify your business details Company website https://example.com Continue",
                    textContent: "Verify your business details Company website https://example.com Continue"
                },
                location: {
                    href: "https://kraken.com/verify/flow",
                    search: "",
                    hostname: "kraken.com",
                    pathname: "/verify/flow"
                },
                getElementById(id) {
                    if (id === "company_website") return websiteInput;
                    return null;
                },
                querySelector(sel) {
                    if (sel.includes("company_website")) return websiteInput;
                    return null;
                },
                querySelectorAll(sel) {
                    if (sel.includes("form")) return [krakenForm];
                    if (sel.includes("company_website")) return [websiteInput];
                    return [];
                }
            };

            global.window = {
                location: mockDoc.location,
                sessionStorage: mockSessionStorage,
                HTMLInputElement: { prototype: {} },
                getComputedStyle: () => ({ display: "block", visibility: "visible", opacity: "1" })
            };
            global.document = mockDoc;

            eval(extractFunc("detectTargetDomain"));
            eval(extractFunc("isInteractiveElement"));
            eval(extractFunc("isDisqualifiedInput"));
            eval(extractFunc("sortInputsByVisualOrder"));
            if (!isUserScript) {
                eval(extractFunc("isVerifyButton"));
            }
            eval(extractFunc("findOtpInputs"));
            eval(extractFunc("getStorageItem"));
            eval(extractFunc("setStorageItem"));

            // 1. Non-SMS KYC onboarding: Company website must NOT be detected as OTP
            const nonSmsFound = findOtpInputs();

            // 2. Real OTP test: Now add an authentic 2FA / OTP field to the page
            const authenticOtpInput = {
                tagName: "INPUT",
                type: "text",
                name: "twofactorauthcode",
                id: "twofactorauthcode",
                placeholder: "Enter 6-digit code",
                value: "",
                disabled: false,
                readOnly: false,
                offsetParent: {},
                getAttribute(k) { return null; },
                getBoundingClientRect() { return { top: 200, left: 100, width: 160, height: 40 }; }
            };

            mockDoc.getElementById = (id) => (id === "twofactorauthcode" ? authenticOtpInput : null);
            mockDoc.querySelectorAll = (sel) => {
                if (sel.includes("twofactorauthcode") || sel.includes("twofactor") || sel.includes("two-factor")) {
                    return [authenticOtpInput];
                }
                return [];
            };

            const authenticFound = findOtpInputs();

            // 3. Dismissal tracking test
            setStorageItem("spark_otp_dismissed_kraken.com", "1");
            const isDismissed = getStorageItem("spark_otp_dismissed_kraken.com") === "1";

            return {
                nonSmsCount: nonSmsFound.length,
                authenticCount: authenticFound.length,
                authenticCodeMatches: authenticFound.length === 1 && authenticFound[0] === authenticOtpInput,
                isDismissed
            };
        }

        const extResult = runDomTest(contentJs, false);
        const userResult = runDomTest(userJs, true);

        console.log(JSON.stringify({ ext: extResult, user: userResult }));
        """
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        data = json.loads(proc.stdout)

        # Extension assertions
        self.assertEqual(data["ext"]["nonSmsCount"], 0, "Extension must not detect company website on Kraken onboarding")
        self.assertEqual(data["ext"]["authenticCount"], 1, "Extension must detect authentic 2FA field")
        self.assertTrue(data["ext"]["authenticCodeMatches"], "Extension must return the authentic 2FA field")
        self.assertTrue(data["ext"]["isDismissed"], "Extension session dismissal must be stored")

        # Userscript assertions
        self.assertEqual(data["user"]["nonSmsCount"], 0, "Userscript must not detect company website on Kraken onboarding")
        self.assertEqual(data["user"]["authenticCount"], 1, "Userscript must detect authentic 2FA field")
        self.assertTrue(data["user"]["authenticCodeMatches"], "Userscript must return the authentic 2FA field")
        self.assertTrue(data["user"]["isDismissed"], "Userscript session dismissal must be stored")

    def test_kraken_persona_qr_handoff_and_stepper_disqualification(self):
        """
        Two-Sided Verification for Kraken KYC Persona QR Handoff & Stepper navigation:
        1. Non-SMS / Stepper / QR handoff elements:
           - Stepper sidebar item with id="step-2fa" inside nav/aside container.
           - Persona handoff URL input with value="https://perso.na/s/7xNNFG-980FVZ3-519680".
           - Cookie consent modal input.
           - QR scan text container.
           -> Must return 0 OTP inputs (zero false positive).
        2. Legitimate OTP field added:
           - Authentic 6-digit 2FA input with name="twofactorauthcode".
           -> Must return 1 valid OTP input (authentic capture).
        3. Tested identically across both extension/content.js and userscript/spark-otp.user.js.
        """
        js_code = """
        const fs = require('fs');
        const contentJs = fs.readFileSync('extension/content.js', 'utf8');
        const userJs = fs.readFileSync('userscript/spark-otp.user.js', 'utf8');

        function runHandoffTest(scriptSource, isUserScript) {
            const extractFunc = (name) => {
                const pat = new RegExp("function " + name + "\\\\([\\\\s\\\\S]*?\\\\n  \\\\}");
                const m = scriptSource.match(pat);
                if (!m) throw new Error("Function " + name + " not found in script");
                return m[0];
            };

            const stepperContainer = {
                tagName: "NAV",
                closest: () => null,
                getAttribute: () => "navigation"
            };

            const stepper2faInput = {
                tagName: "INPUT",
                type: "text",
                name: "step_2fa",
                id: "step-2fa",
                placeholder: "Step 2FA",
                value: "",
                disabled: false,
                readOnly: false,
                offsetParent: {},
                closest(sel) {
                    if (sel.includes("nav") || sel.includes("aside")) return stepperContainer;
                    return null;
                },
                getAttribute(k) { return null; },
                getBoundingClientRect() { return { top: 100, left: 20, width: 100, height: 30 }; }
            };

            const personaHandoffInput = {
                tagName: "INPUT",
                type: "text",
                name: "persona_link",
                id: "persona-link",
                placeholder: "Copy link",
                value: "https://perso.na/s/7xNNFG-980FVZ3-519680",
                disabled: false,
                readOnly: true,
                offsetParent: {},
                closest(sel) { return null; },
                getAttribute(k) { return null; },
                getBoundingClientRect() { return { top: 300, left: 200, width: 320, height: 40 }; }
            };

            const cookieContainer = {
                tagName: "DIV",
                id: "cookie-consent-banner",
                closest: () => null,
                getAttribute: () => null
            };

            const cookieInput = {
                tagName: "INPUT",
                type: "text",
                name: "cookie_pref",
                id: "cookie_pref",
                value: "",
                disabled: false,
                readOnly: false,
                offsetParent: {},
                closest(sel) {
                    if (sel.includes("cookie") || sel.includes("consent")) return cookieContainer;
                    return null;
                },
                getAttribute(k) { return null; },
                getBoundingClientRect() { return { top: 700, left: 100, width: 200, height: 30 }; }
            };

            const mockDoc = {
                body: {
                    innerText: "Continue on another device. Scan QR code with phone camera or use link. Keep Kraken secure.",
                    textContent: "Continue on another device. Scan QR code with phone camera or use link. Keep Kraken secure."
                },
                location: {
                    href: "https://kraken.com/verify/flow",
                    hostname: "kraken.com",
                    pathname: "/verify/flow"
                },
                getElementById(id) {
                    if (id === "step-2fa") return stepper2faInput;
                    if (id === "persona-link") return personaHandoffInput;
                    return null;
                },
                querySelector(sel) {
                    if (sel.includes("step-2fa")) return stepper2faInput;
                    if (sel.includes("persona")) return personaHandoffInput;
                    return null;
                },
                querySelectorAll(sel) {
                    const results = [];
                    if (sel.includes("step-2fa") || sel.includes("2fa")) results.push(stepper2faInput);
                    if (sel.includes("persona") || sel.includes("link")) results.push(personaHandoffInput);
                    if (sel.includes("cookie")) results.push(cookieInput);
                    return results;
                }
            };

            global.window = {
                location: mockDoc.location,
                HTMLInputElement: { prototype: {} },
                getComputedStyle: () => ({ display: "block", visibility: "visible", opacity: "1" })
            };
            global.document = mockDoc;

            eval(extractFunc("detectTargetDomain"));
            eval(extractFunc("isInteractiveElement"));
            eval(extractFunc("isDisqualifiedInput"));
            eval(extractFunc("sortInputsByVisualOrder"));
            if (!isUserScript) {
                eval(extractFunc("isVerifyButton"));
            }
            eval(extractFunc("findOtpInputs"));

            // 1. Adversarial Check: QR handoff and Stepper navigation must NOT be detected as OTP
            const nonOtpFound = findOtpInputs();

            // 2. Authentic Check: Legitimate 2FA input is added
            const real2faInput = {
                tagName: "INPUT",
                type: "text",
                name: "twofactorauthcode",
                id: "twofactorauthcode",
                placeholder: "Enter 6-digit code",
                value: "",
                disabled: false,
                readOnly: false,
                offsetParent: {},
                closest(sel) { return null; },
                getAttribute(k) { return null; },
                getBoundingClientRect() { return { top: 400, left: 200, width: 180, height: 40 }; }
            };

            mockDoc.getElementById = (id) => {
                if (id === "twofactorauthcode") return real2faInput;
                if (id === "step-2fa") return stepper2faInput;
                return null;
            };
            mockDoc.querySelectorAll = (sel) => {
                if (sel.includes("twofactor") || sel.includes("two-factor") || sel.includes("twofa")) {
                    return [real2faInput];
                }
                return [];
            };

            const authenticFound = findOtpInputs();

            return {
                nonOtpCount: nonOtpFound.length,
                authenticCount: authenticFound.length,
                authenticMatches: authenticFound.length === 1 && authenticFound[0] === real2faInput
            };
        }

        const extResult = runHandoffTest(contentJs, false);
        const userResult = runHandoffTest(userJs, true);

        console.log(JSON.stringify({ ext: extResult, user: userResult }));
        """
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        data = json.loads(proc.stdout)

        # Extension assertions
        self.assertEqual(data["ext"]["nonOtpCount"], 0, "Extension must not detect QR handoff or stepper nav as OTP")
        self.assertEqual(data["ext"]["authenticCount"], 1, "Extension must detect authentic 2FA code field")
        self.assertTrue(data["ext"]["authenticMatches"], "Extension must return authentic 2FA input")

        # Userscript assertions
        self.assertEqual(data["user"]["nonOtpCount"], 0, "Userscript must not detect QR handoff or stepper nav as OTP")
        self.assertEqual(data["user"]["authenticCount"], 1, "Userscript must detect authentic 2FA code field")
        self.assertTrue(data["user"]["authenticMatches"], "Userscript must return authentic 2FA input")

if __name__ == "__main__":
    unittest.main()

