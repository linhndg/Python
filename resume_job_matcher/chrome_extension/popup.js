// Tab switching
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");
  });
});

// Load profile on popup open
const PROFILE_FIELDS = [
  "full_name", "email", "phone", "address", "city", "state",
  "zip_code", "linkedin", "website", "summary",
];

function loadProfile() {
  chrome.storage.local.get("profile", (data) => {
    const profile = data.profile;
    if (!profile) return;

    const contact = profile.contact || {};
    PROFILE_FIELDS.forEach((field) => {
      const el = document.getElementById(field);
      if (el) {
        el.value = contact[field] || profile[field] || "";
      }
    });

    // Show skills
    if (profile.skills && profile.skills.length > 0) {
      const container = document.getElementById("skills-list");
      container.innerHTML = profile.skills
        .map((s) => `<span class="skill-chip">${s}</span>`)
        .join("");
    }
  });
}

loadProfile();

// Save profile
document.getElementById("btn-save").addEventListener("click", () => {
  const contact = {};
  PROFILE_FIELDS.forEach((field) => {
    const el = document.getElementById(field);
    if (el) contact[field] = el.value;
  });

  chrome.storage.local.get("profile", (data) => {
    const profile = data.profile || {};
    profile.contact = contact;
    if (contact.summary) profile.summary = contact.summary;

    chrome.storage.local.set({ profile }, () => {
      const status = document.getElementById("save-status");
      status.textContent = "Profile saved!";
      status.className = "status success";
      setTimeout(() => { status.textContent = ""; }, 2000);
    });
  });
});

// Auto-fill button
document.getElementById("btn-fill").addEventListener("click", () => {
  const status = document.getElementById("fill-status");
  status.textContent = "Filling...";
  status.className = "status";

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    chrome.tabs.sendMessage(tabs[0].id, { action: "autoFill" }, (response) => {
      if (chrome.runtime.lastError) {
        status.textContent = "Error: Refresh the page and try again.";
        status.className = "status error";
        return;
      }
      if (response && response.success) {
        status.textContent = response.message;
        status.className = "status success";

        // Show details
        if (response.details) {
          const details = document.getElementById("detected-fields");
          details.innerHTML = Object.entries(response.details)
            .map(([key, val]) => {
              const cls = val === "filled" ? "found" : "missing";
              return `<span class="${cls}">${key}: ${val}</span>`;
            })
            .join(" | ");
        }
      } else {
        status.textContent = response ? response.message : "Failed to fill.";
        status.className = "status error";
      }
    });
  });
});

// Detect fields button
document.getElementById("btn-detect").addEventListener("click", () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    chrome.tabs.sendMessage(tabs[0].id, { action: "detectFields" }, (response) => {
      if (chrome.runtime.lastError) {
        document.getElementById("fill-status").textContent = "Error: Refresh the page and try again.";
        document.getElementById("fill-status").className = "status error";
        return;
      }
      const container = document.getElementById("detected-fields");
      if (!response) {
        container.innerHTML = '<span class="missing">No response from page</span>';
        return;
      }
      container.innerHTML = Object.entries(response)
        .map(([key, info]) => {
          if (info.found) {
            return `<span class="found">${key} (${info.tag}${info.hasValue ? ", has value" : ""})</span>`;
          }
          return `<span class="missing">${key} (not found)</span>`;
        })
        .join(" | ");
    });
  });
});

// Fetch from server
document.getElementById("btn-fetch").addEventListener("click", async () => {
  const status = document.getElementById("import-status");
  const url = document.getElementById("server-url").value.trim();

  if (!url) {
    status.textContent = "Enter server URL";
    status.className = "status error";
    return;
  }

  status.textContent = "Fetching...";
  status.className = "status";

  try {
    const resp = await fetch(`${url}/api/profile`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const profile = await resp.json();

    chrome.storage.local.set({ profile }, () => {
      status.textContent = "Profile imported successfully!";
      status.className = "status success";
      loadProfile();
    });
  } catch (e) {
    status.textContent = `Error: ${e.message}. Is the server running?`;
    status.className = "status error";
  }
});

// JSON import
document.getElementById("btn-json-import").addEventListener("click", () => {
  const status = document.getElementById("import-status");
  const jsonText = document.getElementById("json-import").value.trim();

  if (!jsonText) {
    status.textContent = "Paste JSON profile data first";
    status.className = "status error";
    return;
  }

  try {
    const profile = JSON.parse(jsonText);
    chrome.storage.local.set({ profile }, () => {
      status.textContent = "Profile imported from JSON!";
      status.className = "status success";
      loadProfile();
    });
  } catch (e) {
    status.textContent = "Invalid JSON format";
    status.className = "status error";
  }
});
