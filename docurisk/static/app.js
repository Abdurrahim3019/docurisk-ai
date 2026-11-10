(function () {
  "use strict";

  const MAX_FILE_SIZE = 10 * 1024 * 1024;

  // ---------- Navigation ----------
  const navButtons = document.querySelectorAll(".nav-btn");
  const views = document.querySelectorAll(".view");

  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      navButtons.forEach((b) => b.classList.remove("active"));
      views.forEach((v) => v.classList.remove("active"));

      btn.classList.add("active");
      document.getElementById(btn.dataset.view).classList.add("active");

      if (btn.dataset.view === "history-view") {
        loadHistory();
      }
    });
  });

  // ---------- Upload / Dropzone ----------
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const fileChip = document.getElementById("file-chip");
  const fileChipName = document.getElementById("file-chip-name");
  const fileChipRemove = document.getElementById("file-chip-remove");
  const analyzeBtn = document.getElementById("analyze-btn");
  const uploadError = document.getElementById("upload-error");

  const uploadCard = document.getElementById("upload-card");
  const loadingCard = document.getElementById("loading-card");
  const resultsSection = document.getElementById("results");

  let selectedFile = null;

  function showUploadError(message) {
    uploadError.textContent = message;
    uploadError.classList.remove("hidden");
  }

  function clearUploadError() {
    uploadError.textContent = "";
    uploadError.classList.add("hidden");
  }

  function setSelectedFile(file) {
    clearUploadError();

    if (!file) return;

    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      showUploadError("Yalnız PDF sənədləri qəbul edilir.");
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      showUploadError("PDF faylı 10 MB-dan böyük olmamalıdır.");
      return;
    }

    selectedFile = file;
    fileChipName.textContent = file.name;
    fileChip.classList.remove("hidden");
    analyzeBtn.disabled = false;
  }

  function resetFile() {
    selectedFile = null;
    fileInput.value = "";
    fileChip.classList.add("hidden");
    analyzeBtn.disabled = true;
  }

  dropzone.addEventListener("click", (e) => {
    if (e.target === fileChipRemove) return;
    fileInput.click();
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  });

  ["dragenter", "dragover"].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files && files[0]) {
      setSelectedFile(files[0]);
    }
  });

  fileChipRemove.addEventListener("click", (e) => {
    e.stopPropagation();
    resetFile();
  });

  // ---------- Analyze ----------
  function riskLevelClass(level) {
    if (!level) return "";
    const normalized = level.trim().toLowerCase();
    if (normalized.includes("aşağı") || normalized.includes("asagi")) return "level-low";
    if (normalized.includes("orta")) return "level-medium";
    if (normalized.includes("yüksək") || normalized.includes("yuksek")) return "level-high";
    if (normalized.includes("kritik")) return "level-critical";
    return "";
  }

  analyzeBtn.addEventListener("click", async () => {
    if (!selectedFile) return;

    clearUploadError();
    uploadCard.classList.add("hidden");
    resultsSection.classList.add("hidden");
    loadingCard.classList.remove("hidden");

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Analiz zamanı xəta baş verdi.");
      }

      renderResults(data);
    } catch (err) {
      uploadCard.classList.remove("hidden");
      showUploadError(err.message || "Gözlənilməz xəta baş verdi.");
    } finally {
      loadingCard.classList.add("hidden");
    }
  });

  function renderResults(data) {
    document.getElementById("risk-score").textContent = data.risk_score;
    document.getElementById("benefit-score").textContent = data.benefit_score;

    const levelBadge = document.getElementById("risk-level");
    levelBadge.textContent = data.risk_level;
    levelBadge.className = "score-badge " + riskLevelClass(data.risk_level);

    document.getElementById("report-filename").textContent = data.file_name;
    document.getElementById("report-text").textContent = data.full_report;

    // reset chat window for new document
    chatWindow.innerHTML =
      '<div class="chat-msg chat-msg-assistant">Salam! Yüklədiyiniz sənədlə bağlı istənilən sualı verə bilərsiniz.</div>';

    resultsSection.classList.remove("hidden");
    uploadCard.classList.remove("hidden");
    resetFile();

    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---------- Chat ----------
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatWindow = document.getElementById("chat-window");
  const chatSend = document.getElementById("chat-send");

  function appendChatMessage(text, role, pending) {
    const msg = document.createElement("div");
    msg.className = "chat-msg chat-msg-" + role + (pending ? " chat-msg-pending" : "");
    msg.textContent = text;
    chatWindow.appendChild(msg);
    chatWindow.scrollTop = chatWindow.scrollHeight;
    return msg;
  }

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const question = chatInput.value.trim();
    if (!question) return;

    appendChatMessage(question, "user");
    chatInput.value = "";
    chatSend.disabled = true;

    const pendingMsg = appendChatMessage("Cavab hazırlanır...", "assistant", true);

    try {
      const formData = new FormData();
      formData.append("question", question);

      const response = await fetch("/api/question", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Sual cavablandırılarkən xəta baş verdi.");
      }

      pendingMsg.textContent = data.answer;
      pendingMsg.classList.remove("chat-msg-pending");
    } catch (err) {
      pendingMsg.textContent = err.message || "Gözlənilməz xəta baş verdi.";
      pendingMsg.classList.remove("chat-msg-pending");
    } finally {
      chatSend.disabled = false;
    }
  });

  // ---------- History ----------
  const historyList = document.getElementById("history-list");
  const historyRefresh = document.getElementById("history-refresh");

  async function loadHistory() {
    historyList.innerHTML = '<p class="muted">Yüklənir...</p>';

    try {
      const response = await fetch("/api/history");
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Tarixçə yüklənərkən xəta baş verdi.");
      }

      if (!data.items || data.items.length === 0) {
        historyList.innerHTML = '<p class="muted">Hələ heç bir analiz aparılmayıb.</p>';
        return;
      }

      historyList.innerHTML = "";

      data.items.forEach((item) => {
        const row = document.createElement("div");
        row.className = "history-item";

        const date = new Date(item.created_at);
        const dateLabel = isNaN(date.getTime()) ? item.created_at : date.toLocaleString("az-AZ");

        row.innerHTML = `
          <div class="history-item-main">
            <span class="history-file">${escapeHtml(item.file_name)}</span>
            <span class="history-date">${escapeHtml(dateLabel)}</span>
          </div>
          <div class="history-scores">
            <span class="history-pill">Risk: ${item.risk_score}</span>
            <span class="history-pill">Fayda: ${item.benefit_score}</span>
            <span class="history-pill">${escapeHtml(item.risk_level)}</span>
          </div>
        `;

        historyList.appendChild(row);
      });
    } catch (err) {
      historyList.innerHTML =
        '<p class="error-text">' + escapeHtml(err.message || "Xəta baş verdi.") + "</p>";
    }
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = String(str);
    return div.innerHTML;
  }

  historyRefresh.addEventListener("click", loadHistory);
})();
