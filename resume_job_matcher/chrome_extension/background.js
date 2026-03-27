// Background service worker for Job Application Auto-Fill extension

// Listen for messages from popup or content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "getProfile") {
    chrome.storage.local.get("profile", (data) => {
      sendResponse(data.profile || null);
    });
    return true; // async response
  }

  if (message.action === "saveProfile") {
    chrome.storage.local.set({ profile: message.profile }, () => {
      sendResponse({ ok: true });
    });
    return true;
  }

  if (message.action === "triggerAutoFill") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { action: "autoFill" }, (response) => {
          sendResponse(response);
        });
      }
    });
    return true;
  }
});
