/* In-page diagnosis for the hero panel.
 *
 * This is a port of `sam_doctor.diagnostics.diagnose` and
 * `sam_doctor.redaction.redact` onto the generated catalog in
 * rule-catalog.js. It runs entirely in the page: no fetch, no upload, no
 * telemetry. If anything here fails to initialise, the static worked example
 * already in the markup stays visible and the hero still reads correctly.
 */
(function () {
  "use strict";

  var catalog = window.SAM_DOCTOR_CATALOG;
  if (!catalog || !catalog.rules || !catalog.rules.length) {
    return;
  }

  /* ---------------------------------------------------------------- engine */

  function compile(entry) {
    return new RegExp(entry.source, entry.flags);
  }

  function compileAll(entries) {
    return (entries || []).map(compile);
  }

  var engine;
  try {
    engine = {
      ansi: compile(catalog.ansi_escape),
      redaction: catalog.redaction.map(function (pass) {
        return {
          name: pass.name,
          pattern: compile(pass),
          replacement: pass.replacement
        };
      }),
      denial: {
        action: compile(catalog.denial_context.action),
        principal: compile(catalog.denial_context.principal),
        resource: compile(catalog.denial_context.resource),
        explicitDenyScp: compile(catalog.denial_context.explicit_deny_scp),
        explicitDeny: compile(catalog.denial_context.explicit_deny),
        implicitDenyLayer: compile(catalog.denial_context.implicit_deny_layer)
      },
      stabilization: {
        handlerMessage: compile(catalog.stabilization_context.handler_message),
        resourceType: compile(catalog.stabilization_context.resource_type),
        slowResourceHints: catalog.stabilization_context.slow_resource_hints
      },
      rules: catalog.rules.map(function (rule) {
        return {
          id: rule.id,
          title: rule.title,
          confidence: rule.confidence,
          explanation: rule.explanation,
          verification: rule.verification,
          documentationUrl: rule.documentation_url,
          parseDenialContext: rule.parse_denial_context,
          parseStabilizationContext: rule.parse_stabilization_context,
          patterns: compileAll(rule.patterns),
          suppressedBy: compileAll(rule.suppressed_by),
          excludedLinePatterns: compileAll(rule.excluded_line_patterns)
        };
      })
    };

    /* One alternation over every rule pattern, used to skip the overwhelming
     * majority of log lines that no rule can match. Semantically transparent:
     * a line that matches a rule always matches the union. */
    var union = [];
    catalog.rules.forEach(function (rule) {
      rule.patterns.forEach(function (pattern) {
        union.push("(?:" + pattern.source + ")");
      });
    });
    engine.candidate = new RegExp(union.join("|"), "i");
  } catch (error) {
    /* A catalog the browser cannot compile means no demo. The static example
     * below stays in place, so the hero is unchanged rather than broken. */
    return;
  }

  function stripAnsi(text) {
    return text.replace(engine.ansi, "");
  }

  /* Python's str.splitlines() breaks on more than \n, and CI logs really do
   * contain lone carriage returns from progress bars. Matching its set keeps
   * reported line numbers identical to the CLI's. */
  var LINE_BREAK = new RegExp("\\r\\n|[\\n\\r\\v\\f\\x1c-\\x1e\\x85\\u2028\\u2029]");

  function splitLines(text) {
    var lines = text.split(LINE_BREAK);
    if (lines.length && lines[lines.length - 1] === "") {
      lines.pop();
    }
    return lines;
  }

  function redactUrlCredentials(match, scheme, user, password) {
    /* With a password present the username is usually a harmless placeholder
     * and keeping it identifies which credential failed. With no password the
     * single value is itself the credential. */
    if (password) {
      return scheme + user + ":[REDACTED_URL_CREDENTIAL]@";
    }
    return scheme + "[REDACTED_URL_CREDENTIAL]@";
  }

  function redact(text) {
    engine.redaction.forEach(function (pass) {
      if (pass.replacement === "@url-credentials") {
        text = text.replace(pass.pattern, redactUrlCredentials);
      } else {
        text = text.replace(pass.pattern, pass.replacement);
      }
    });
    return text;
  }

  function compactEvidence(line) {
    var collapsed = line.split(/\s+/).filter(Boolean).join(" ");
    var limit = catalog.max_evidence_length;
    if (collapsed.length <= limit) {
      return collapsed;
    }
    var half = Math.floor((limit - 9) / 2);
    return collapsed.slice(0, half) + " ... " + collapsed.slice(-half);
  }

  function matchingEvidence(candidates, patterns, excluded) {
    var matches = [];
    var seen = Object.create(null);
    for (var index = 0; index < candidates.length; index += 1) {
      var line = candidates[index].text;
      var hit = patterns.some(function (pattern) {
        return pattern.test(line);
      });
      var blocked =
        hit &&
        excluded.some(function (pattern) {
          return pattern.test(line);
        });
      if (hit && !blocked) {
        var compacted = compactEvidence(redact(line.trim()));
        if (!seen[compacted]) {
          seen[compacted] = true;
          matches.push({ lineNumber: candidates[index].lineNumber, text: compacted });
        }
      }
      if (matches.length >= catalog.max_evidence_lines) {
        break;
      }
    }
    return matches;
  }

  function denialContextNote(evidence) {
    for (var index = 0; index < evidence.length; index += 1) {
      var line = evidence[index];
      var action = engine.denial.action.exec(line);
      var scp = engine.denial.explicitDenyScp.test(line);
      var explicit = scp || engine.denial.explicitDeny.test(line);
      var implicit = engine.denial.implicitDenyLayer.exec(line);
      if (!action && !explicit && !implicit) {
        continue;
      }
      var parts = [];
      if (action) {
        parts.push("denied action `" + action[1] + "`");
      }
      if (engine.denial.principal.test(line)) {
        parts.push("for the caller identity shown (redacted) in the evidence");
      }
      var resource = engine.denial.resource.exec(line);
      if (resource) {
        parts.push(
          "on " +
            (resource[1] === "*"
              ? "all resources (`*`)"
              : "the specific resource shown (redacted) in the evidence")
        );
      }
      if (scp) {
        parts.push(
          "blocked by an explicit deny in a service control policy " +
            "(set at the AWS Organizations level, not in this account)"
        );
      } else if (explicit) {
        parts.push("blocked by an explicit deny statement");
      } else if (implicit) {
        parts.push("an implicit deny: no " + implicit[1].trim() + " policy allows it");
      }
      return "Denial context parsed from the evidence: " + parts.join("; ") + ".";
    }
    return "";
  }

  function stabilizationContextNote(evidence) {
    for (var index = 0; index < evidence.length; index += 1) {
      var line = evidence[index];
      var message = engine.stabilization.handlerMessage.exec(line);
      var type = engine.stabilization.resourceType.exec(line);
      if (!message && !type) {
        continue;
      }
      var parts = [];
      if (message) {
        parts.push(
          'the service handler reported: "' +
            message[1].trim() +
            '" - inspect that reason before the stabilization timeout itself'
        );
      }
      if (type) {
        var resourceType = type[1];
        parts.push("resource type `" + resourceType + "`");
        for (var hint = 0; hint < engine.stabilization.slowResourceHints.length; hint += 1) {
          var entry = engine.stabilization.slowResourceHints[hint];
          if (resourceType.indexOf(entry[0]) === 0) {
            parts.push(entry[1]);
            break;
          }
        }
      }
      return "Underlying status reason parsed from the evidence: " + parts.join("; ") + ".";
    }
    return "";
  }

  function diagnose(rawText) {
    var text = stripAnsi(rawText);
    var candidates = [];
    splitLines(text).forEach(function (line, index) {
      if (engine.candidate.test(line)) {
        candidates.push({ lineNumber: index + 1, text: line });
      }
    });

    var matched = [];
    engine.rules.forEach(function (rule, ruleIndex) {
      var lineMatches = matchingEvidence(
        candidates,
        rule.patterns,
        rule.excludedLinePatterns
      );
      if (!lineMatches.length) {
        return;
      }
      var suppressed = rule.suppressedBy.some(function (pattern) {
        return pattern.test(text);
      });
      if (suppressed) {
        return;
      }
      var evidence = lineMatches.map(function (match) {
        return match.text;
      });
      var explanation = rule.explanation;
      if (rule.parseDenialContext) {
        var denial = denialContextNote(evidence);
        if (denial) {
          explanation = explanation + "\n\n" + denial;
        }
      }
      if (rule.parseStabilizationContext) {
        var stabilization = stabilizationContextNote(evidence);
        if (stabilization) {
          explanation = stabilization + "\n\n" + explanation;
        }
      }
      matched.push({
        sortLine: lineMatches[0].lineNumber,
        sortRule: ruleIndex,
        finding: {
          ruleId: rule.id,
          title: rule.title,
          confidence: rule.confidence,
          explanation: explanation,
          verification: rule.verification,
          documentationUrl: rule.documentationUrl,
          evidence: evidence,
          lineNumber: lineMatches[0].lineNumber
        }
      });
    });

    matched.sort(function (left, right) {
      return left.sortLine - right.sortLine || left.sortRule - right.sortRule;
    });
    return matched.map(function (entry) {
      return entry.finding;
    });
  }

  /* Exposed so the repository's own test can drive this exact code under Node
   * and compare it against the Python implementation, rather than a copy. */
  window.SAM_DOCTOR_DEMO = {
    diagnose: diagnose,
    redact: redact,
    stripAnsi: stripAnsi
  };

  /* -------------------------------------------------------------------- ui */

  var root = document.getElementById("hero-demo");
  var form = document.getElementById("hero-demo-form");
  var input = document.getElementById("hero-demo-input");
  var sampleButton = document.getElementById("hero-demo-sample");
  var results = document.getElementById("hero-demo-results");
  var status = document.getElementById("hero-demo-status");
  var staticExample = document.getElementById("hero-demo-example");
  var footerNote = document.getElementById("hero-demo-footer-note");
  if (!root || !form || !input || !sampleButton || !results || !status) {
    return;
  }

  var samples = catalog.samples || [];
  var nextSample = 0;

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = text;
    }
    return node;
  }

  /* Explanations carry inline `code` spans and paragraph breaks from the rule
   * source. Rendered as text nodes and elements, never as innerHTML: the input
   * is the visitor's own log, and it is never treated as markup. */
  function appendRichText(parent, value) {
    value.split(/\n\n+/).forEach(function (paragraph) {
      var node = element("p");
      paragraph.split(/`([^`]+)`/).forEach(function (chunk, index) {
        if (index % 2 === 1) {
          node.appendChild(element("code", null, chunk));
        } else if (chunk) {
          node.appendChild(document.createTextNode(chunk.replace(/\n/g, " ")));
        }
      });
      parent.appendChild(node);
    });
  }

  function renderFinding(finding, index) {
    var article = element("article", "demo-finding");

    var meta = element("div", "finding-meta");
    meta.appendChild(
      element(
        "span",
        "finding-number",
        "Finding " + (index + 1 < 10 ? "0" : "") + (index + 1)
      )
    );
    meta.appendChild(element("span", "confidence", finding.confidence + " confidence"));
    article.appendChild(meta);

    article.appendChild(element("h2", "demo-finding-title", finding.title));

    var explanation = element("div", "demo-explanation");
    appendRichText(explanation, finding.explanation);
    article.appendChild(explanation);

    var details = element("dl", "finding-details");

    var evidenceRow = element("div");
    evidenceRow.appendChild(element("dt", null, "Evidence"));
    var evidenceValue = element("dd");
    finding.evidence.forEach(function (line) {
      evidenceValue.appendChild(element("p", "demo-evidence", line));
    });
    evidenceRow.appendChild(evidenceValue);
    details.appendChild(evidenceRow);

    var checkRow = element("div");
    checkRow.appendChild(element("dt", null, "Check next"));
    var checkValue = element("dd");
    var steps = element("ol", "demo-steps");
    finding.verification.forEach(function (step) {
      var item = element("li");
      appendRichText(item, step);
      steps.appendChild(item);
    });
    checkValue.appendChild(steps);
    var docs = element("a", "demo-docs", "AWS documentation for this failure");
    docs.href = finding.documentationUrl;
    docs.rel = "noopener noreferrer";
    docs.target = "_blank";
    checkValue.appendChild(docs);
    checkRow.appendChild(checkValue);
    details.appendChild(checkRow);

    var ruleRow = element("div");
    ruleRow.appendChild(element("dt", null, "Rule"));
    var ruleValue = element("dd");
    ruleValue.appendChild(element("code", "demo-rule-id", finding.ruleId));
    ruleValue.appendChild(
      element("span", "demo-line", " · matched line " + finding.lineNumber)
    );
    ruleRow.appendChild(ruleValue);
    details.appendChild(ruleRow);

    article.appendChild(details);
    return article;
  }

  function renderNote(heading, body) {
    var note = element("div", "demo-note-block");
    note.appendChild(element("h2", "demo-finding-title", heading));
    appendRichText(note, body);
    return note;
  }

  function clear(node) {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function setFooter(text) {
    if (footerNote) {
      footerNote.textContent = text;
    }
  }

  function run() {
    var text = input.value;
    clear(results);
    results.hidden = false;

    if (!text.trim()) {
      status.textContent = "Nothing to diagnose yet.";
      results.appendChild(
        renderNote(
          "Nothing to diagnose",
          "The box is empty, so there was nothing to read. Paste a failed " +
            "deploy log, or load one of the sample failures."
        )
      );
      setFooter("Nothing read");
      return;
    }

    var findings = diagnose(text);
    if (!findings.length) {
      status.textContent = "No supported pattern found.";
      results.appendChild(
        renderNote(
          "No supported pattern found",
          "This log did not match any of the " +
            catalog.rules.length +
            " current rules. That is the honest answer rather than a guess. " +
            "Run `sam-doctor request-packet deployment.log` locally to write a " +
            "short sanitized excerpt, review it, then open a rule request."
        )
      );
      setFooter("0 findings · nothing left this page");
      return;
    }

    status.textContent =
      findings.length +
      (findings.length === 1 ? " finding" : " findings") +
      ", highest confidence " +
      findings[0].confidence +
      ".";
    findings.forEach(function (finding, index) {
      results.appendChild(renderFinding(finding, index));
    });
    setFooter(
      findings.length +
        (findings.length === 1 ? " finding" : " findings") +
        " · identifiers redacted · nothing left this page"
    );
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    run();
  });

  sampleButton.addEventListener("click", function () {
    if (!samples.length) {
      return;
    }
    var sample = samples[nextSample % samples.length];
    nextSample += 1;
    input.value = sample.log;
    sampleButton.textContent =
      samples.length > 1 ? "Try another sample failure" : "Try a sample failure";
    run();
  });

  /* Enhance only now that everything above is wired: until this point the
   * static worked example is what a visitor sees, including with JS disabled. */
  if (staticExample) {
    staticExample.hidden = true;
  }
  form.hidden = false;
  root.classList.add("is-interactive");
  status.textContent = "Ready. Nothing has been read yet.";
  if (samples.length) {
    sampleButton.hidden = false;
  }
  setFooter("Runs in this page · nothing is uploaded");
})();
