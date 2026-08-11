/* Run the website's in-page matcher outside a browser, so the repository's own
 * tests can compare it against the Python rules it was generated from.
 *
 * Reads a JSON array of log strings on stdin and writes a JSON array of
 * finding lists on stdout, in the field names `sam_doctor.diagnostics` uses.
 * The two site scripts are loaded and executed unmodified - the point is to
 * exercise the shipped file, not a copy of it.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const siteAssets = path.join(__dirname, "..", "site", "assets");

function readStdin() {
  return fs.readFileSync(0, "utf8");
}

const sandbox = {
  window: {},
  /* The demo script wires up UI only when these elements exist. Returning null
   * for every lookup leaves the matcher built and exported, and skips the DOM
   * half entirely. */
  document: { getElementById: () => null },
  RegExp,
  Object,
  Math,
  JSON,
  console
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

for (const file of ["rule-catalog.js", "hero-demo.js"]) {
  const source = fs.readFileSync(path.join(siteAssets, file), "utf8");
  vm.runInContext(source, sandbox, { filename: file });
}

const demo = sandbox.window.SAM_DOCTOR_DEMO;
if (!demo) {
  console.error("hero-demo.js did not expose SAM_DOCTOR_DEMO");
  process.exit(2);
}

const request = JSON.parse(readStdin());
const mode = request.mode || "diagnose";
const output = request.inputs.map((text) => {
  if (mode === "redact") {
    return demo.redact(text);
  }
  return demo.diagnose(text).map((finding) => ({
    rule_id: finding.ruleId,
    title: finding.title,
    confidence: finding.confidence,
    explanation: finding.explanation,
    evidence: finding.evidence,
    verification: finding.verification,
    documentation_url: finding.documentationUrl,
    line_number: finding.lineNumber
  }));
});

process.stdout.write(JSON.stringify(output));
