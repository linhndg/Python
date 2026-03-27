/**
 * Content script for Job Application Auto-Fill.
 * Detects form fields on job application pages and fills them with profile data.
 *
 * Supports common ATS platforms: Workday, Greenhouse, Lever, iCIMS,
 * SmartRecruiters, BambooHR, and generic HTML forms.
 */

// Field mapping: maps profile keys to common form field identifiers
const FIELD_PATTERNS = {
  full_name: {
    names: ["name", "full_name", "fullname", "full-name", "applicant_name", "candidate_name"],
    labels: ["full name", "your name", "name", "candidate name", "applicant name"],
    ids: ["name", "full_name", "fullName", "input-name"],
    autoComplete: ["name"],
  },
  first_name: {
    names: ["first_name", "firstname", "first-name", "fname", "given_name"],
    labels: ["first name", "given name", "first"],
    ids: ["firstName", "first_name", "fname"],
    autoComplete: ["given-name"],
  },
  last_name: {
    names: ["last_name", "lastname", "last-name", "lname", "family_name", "surname"],
    labels: ["last name", "family name", "surname", "last"],
    ids: ["lastName", "last_name", "lname"],
    autoComplete: ["family-name"],
  },
  email: {
    names: ["email", "email_address", "emailAddress", "e-mail", "mail"],
    labels: ["email", "e-mail", "email address"],
    ids: ["email", "emailAddress", "input-email"],
    autoComplete: ["email"],
    type: "email",
  },
  phone: {
    names: ["phone", "phone_number", "phoneNumber", "telephone", "tel", "mobile", "cell"],
    labels: ["phone", "telephone", "mobile", "cell", "phone number"],
    ids: ["phone", "phoneNumber", "telephone"],
    autoComplete: ["tel"],
    type: "tel",
  },
  address: {
    names: ["address", "street_address", "streetAddress", "address1", "street", "address_line_1"],
    labels: ["address", "street address", "address line 1"],
    ids: ["address", "streetAddress", "address1"],
    autoComplete: ["street-address", "address-line1"],
  },
  city: {
    names: ["city", "town", "locality"],
    labels: ["city", "town"],
    ids: ["city", "locality"],
    autoComplete: ["address-level2"],
  },
  state: {
    names: ["state", "province", "region", "administrative_area"],
    labels: ["state", "province", "region"],
    ids: ["state", "province", "region"],
    autoComplete: ["address-level1"],
  },
  zip_code: {
    names: ["zip", "zipcode", "zip_code", "postal_code", "postalCode", "postal"],
    labels: ["zip", "zip code", "postal code", "postcode"],
    ids: ["zip", "zipCode", "postalCode"],
    autoComplete: ["postal-code"],
  },
  linkedin: {
    names: ["linkedin", "linkedin_url", "linkedinUrl", "linkedin_profile"],
    labels: ["linkedin", "linkedin url", "linkedin profile"],
    ids: ["linkedin", "linkedinUrl"],
  },
  website: {
    names: ["website", "portfolio", "personal_website", "url", "web"],
    labels: ["website", "portfolio", "personal website", "url", "personal url"],
    ids: ["website", "portfolio", "personalWebsite"],
    type: "url",
  },
  summary: {
    names: ["summary", "cover_letter", "about", "bio", "introduction", "message", "additional_info"],
    labels: ["summary", "cover letter", "about you", "tell us about yourself", "additional information", "message"],
    ids: ["summary", "coverLetter", "about"],
  },
};

// Get profile from storage
function getProfile() {
  return new Promise((resolve) => {
    chrome.storage.local.get("profile", (data) => {
      resolve(data.profile || null);
    });
  });
}

// Find a form field by trying multiple matching strategies
function findField(patterns) {
  // Strategy 1: Match by name attribute
  for (const name of patterns.names || []) {
    const el = document.querySelector(
      `input[name*="${name}" i], textarea[name*="${name}" i], select[name*="${name}" i]`
    );
    if (el) return el;
  }

  // Strategy 2: Match by id
  for (const id of patterns.ids || []) {
    const el = document.getElementById(id) || document.querySelector(`[id*="${id}" i]`);
    if (el && isFormField(el)) return el;
  }

  // Strategy 3: Match by autocomplete attribute
  for (const ac of patterns.autoComplete || []) {
    const el = document.querySelector(`[autocomplete="${ac}"]`);
    if (el) return el;
  }

  // Strategy 4: Match by input type
  if (patterns.type) {
    const els = document.querySelectorAll(`input[type="${patterns.type}"]`);
    if (els.length === 1) return els[0];
  }

  // Strategy 5: Match by associated label text
  for (const labelText of patterns.labels || []) {
    const el = findByLabel(labelText);
    if (el) return el;
  }

  // Strategy 6: Match by placeholder
  for (const label of patterns.labels || []) {
    const el = document.querySelector(
      `input[placeholder*="${label}" i], textarea[placeholder*="${label}" i]`
    );
    if (el) return el;
  }

  // Strategy 7: Match by aria-label
  for (const label of patterns.labels || []) {
    const el = document.querySelector(`[aria-label*="${label}" i]`);
    if (el && isFormField(el)) return el;
  }

  return null;
}

// Find form field by label text
function findByLabel(text) {
  const labels = document.querySelectorAll("label");
  for (const label of labels) {
    if (label.textContent.toLowerCase().trim().includes(text.toLowerCase())) {
      // Try for= attribute
      if (label.htmlFor) {
        const el = document.getElementById(label.htmlFor);
        if (el) return el;
      }
      // Try child input
      const child = label.querySelector("input, textarea, select");
      if (child) return child;
      // Try next sibling
      const next = label.nextElementSibling;
      if (next && isFormField(next)) return next;
    }
  }
  return null;
}

function isFormField(el) {
  const tag = el.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select";
}

// Set a value on a form field, triggering React/Angular change events
function setValue(el, value) {
  if (!el || !value) return false;

  const tag = el.tagName.toLowerCase();

  if (tag === "select") {
    // Try to find matching option
    const options = el.querySelectorAll("option");
    for (const opt of options) {
      if (opt.textContent.toLowerCase().includes(value.toLowerCase()) ||
          opt.value.toLowerCase().includes(value.toLowerCase())) {
        el.value = opt.value;
        triggerEvents(el);
        return true;
      }
    }
    return false;
  }

  // For input/textarea
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, "value"
  )?.set || Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype, "value"
  )?.set;

  if (nativeInputValueSetter) {
    nativeInputValueSetter.call(el, value);
  } else {
    el.value = value;
  }

  triggerEvents(el);
  return true;
}

// Trigger events to notify React/Angular/Vue frameworks
function triggerEvents(el) {
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  el.dispatchEvent(new Event("blur", { bubbles: true }));
}

// Split full name into first/last
function splitName(fullName) {
  const parts = fullName.trim().split(/\s+/);
  return {
    first: parts[0] || "",
    last: parts.slice(1).join(" ") || "",
  };
}

// Main auto-fill function
async function autoFill() {
  const profile = await getProfile();
  if (!profile || !profile.contact) {
    return { success: false, message: "No profile data. Import your profile in the extension popup." };
  }

  const contact = profile.contact;
  let filled = 0;
  let attempted = 0;
  const results = {};

  // Split name if needed
  const nameParts = splitName(contact.full_name || "");

  // Map profile data to field patterns
  const fieldData = {
    full_name: contact.full_name || "",
    first_name: nameParts.first,
    last_name: nameParts.last,
    email: contact.email || "",
    phone: contact.phone || "",
    address: contact.address || "",
    city: contact.city || "",
    state: contact.state || "",
    zip_code: contact.zip_code || "",
    linkedin: contact.linkedin || "",
    website: contact.website || "",
    summary: profile.summary || "",
  };

  for (const [key, value] of Object.entries(fieldData)) {
    if (!value) continue;
    attempted++;

    const patterns = FIELD_PATTERNS[key];
    if (!patterns) continue;

    const field = findField(patterns);
    if (field && !field.value) { // Only fill empty fields
      const success = setValue(field, value);
      if (success) {
        filled++;
        field.style.outline = "2px solid #28a745";
        setTimeout(() => { field.style.outline = ""; }, 2000);
      }
      results[key] = success ? "filled" : "failed";
    } else if (field && field.value) {
      results[key] = "skipped (already has value)";
    } else {
      results[key] = "field not found";
    }
  }

  return {
    success: true,
    filled,
    attempted,
    message: `Filled ${filled}/${attempted} fields`,
    details: results,
  };
}

// Listen for messages from popup/background
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "autoFill") {
    autoFill().then(sendResponse);
    return true; // async
  }

  if (message.action === "detectFields") {
    // Detect what fields are on this page
    const detected = {};
    for (const [key, patterns] of Object.entries(FIELD_PATTERNS)) {
      const field = findField(patterns);
      detected[key] = field ? {
        found: true,
        tag: field.tagName,
        name: field.name,
        id: field.id,
        hasValue: !!field.value,
      } : { found: false };
    }
    sendResponse(detected);
    return true;
  }
});

// Add auto-fill button to job application pages
function addAutoFillButton() {
  // Only show on pages that look like job applications
  const forms = document.querySelectorAll("form");
  let isApplicationPage = false;

  for (const form of forms) {
    const text = form.textContent.toLowerCase();
    if (text.includes("apply") || text.includes("application") ||
        text.includes("resume") || text.includes("candidate")) {
      isApplicationPage = true;
      break;
    }
  }

  // Also check for common ATS URL patterns
  const url = window.location.href.toLowerCase();
  const atsPatterns = [
    "greenhouse.io", "lever.co", "workday.com", "icims.com",
    "smartrecruiters.com", "bamboohr.com", "myworkdayjobs.com",
    "jobs.lever.co", "boards.greenhouse.io", "careers", "apply",
    "job-application", "application-form"
  ];
  if (atsPatterns.some(p => url.includes(p))) {
    isApplicationPage = true;
  }

  if (!isApplicationPage) return;

  // Create floating button
  const btn = document.createElement("div");
  btn.id = "jm-autofill-btn";
  btn.innerHTML = `<span style="font-size:14px;">Auto-Fill</span>`;
  btn.title = "Auto-fill this form with your profile data";
  document.body.appendChild(btn);

  btn.addEventListener("click", async () => {
    btn.innerHTML = `<span style="font-size:14px;">Filling...</span>`;
    const result = await autoFill();
    btn.innerHTML = `<span style="font-size:14px;">${result.filled} filled</span>`;
    setTimeout(() => {
      btn.innerHTML = `<span style="font-size:14px;">Auto-Fill</span>`;
    }, 3000);
  });
}

// Run on page load
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", addAutoFillButton);
} else {
  addAutoFillButton();
}
