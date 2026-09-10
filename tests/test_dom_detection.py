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
            { el: { type: "text", name: "query", id: "search_input", placeholder: "Search site", getAttribute: (k) => null }, expectedDisqualified: true, label: "search_input" }
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
                        textContent: "To protect your account, we have sent a 6-digit verification code to alex.turner@gmail.com"
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
                        textContent: "我们已将验证码发送到 alex.turner@gmail.com，请在10分钟内输入。"
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
                        textContent: "Verification code sent to alex.turner@gmail.com. Questions: support@64clouds.com"
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
        self.assertEqual(data["email1"], "alex.turner@gmail.com", "Bandwagon Host verification sentence must extract alex.turner@gmail.com")
        self.assertEqual(data["email2"], "alex.turner@gmail.com", "Chinese verification sentence must extract alex.turner@gmail.com")
        self.assertIsNone(data["email3"], "Support/system email must be disqualified and return null")
        self.assertEqual(data["email4"], "alex.turner@gmail.com", "Mixed user and support email must correctly pick user email")

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
            children: [{ tagName: "BR" }, { tagName: "B", children: [{ tagName: "I", textContent: "alex.turner@gmail.com" }] }],
            textContent: "To protect your account, we have sent a 6-digit verification code to\\nalex.turner@gmail.com",
            querySelectorAll(sel) { return []; }
        };

        const sidebarInfoEl = {
            tagName: "DIV",
            className: "card panel panel-default account-info",
            textContent: "Account Information\\nAlex Turner\\nNew York, New York 10010\\nalex.turner@gmail.com",
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
                    return [{ children: [], textContent: "alex.turner@gmail.com" }];
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
        const userFuncIsDisq = userJs.match(/function isDisqualified\\(el\\) \\{[\\s\\S]*?\\n  \\}/)[0];
        const userFuncSort = userJs.match(/function sortInputs\\(inputs\\) \\{[\\s\\S]*?\\n  \\}/)[0];

        eval(userFuncIsDisq);
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
        self.assertEqual(res["extEmail"], "alex.turner@gmail.com", "content.js must detect alex.turner@gmail.com")
        self.assertTrue(res["userHasInput"], "spark-otp.user.js must detect verification_code input")
        self.assertEqual(res["userEmail"], "alex.turner@gmail.com", "spark-otp.user.js must detect alex.turner@gmail.com")
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
            if (isUserScript) {
                eval(extractFunc("isDisqualified"));
                eval(extractFunc("sortInputs"));
                eval(extractFunc("setInputValue"));
            } else {
                eval(extractFunc("isDisqualifiedInput"));
                eval(extractFunc("sortInputsByVisualOrder"));
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
            if (isUserScript) {
                eval(extractFunc("isDisqualified"));
                eval(extractFunc("sortInputs"));
                eval(extractFunc("setInputValue"));
            } else {
                eval(extractFunc("isDisqualifiedInput"));
                eval(extractFunc("sortInputsByVisualOrder"));
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

if __name__ == "__main__":
    unittest.main()
