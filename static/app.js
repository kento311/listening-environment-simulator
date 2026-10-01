const fileInput = document.getElementById("fileInput");
const selectButton = document.getElementById("selectButton");
const processButton = document.getElementById("processButton");
const dropZone = document.getElementById("dropZone");
const selectedFile = document.getElementById("selectedFile");
const resultPanel = document.getElementById("resultPanel");
const originalAudio = document.getElementById("originalAudio");
const processedAudio = document.getElementById("processedAudio");
const downloadLink = document.getElementById("downloadLink");
const status = document.getElementById("status");

const maxFileSizeBytes =
    Number(document.body.dataset.maxFileSizeMb) * 1024 * 1024;
const acceptedExtensions = new Set(["mp3", "wav"]);

let currentFile = null;
let originalUrl = null;
let processedUrl = null;

selectButton.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => selectFile(fileInput.files[0]));
processButton.addEventListener("click", processSelectedFile);

["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.add("is-dragging");
    });
});

["dragleave", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.remove("is-dragging");
    });
});

dropZone.addEventListener("drop", (event) => {
    selectFile(event.dataTransfer.files[0]);
});

function showStatus(message, isError = false) {
    status.textContent = message;
    status.classList.toggle("status-error", isError);
    status.hidden = false;
}

function clearStatus() {
    status.hidden = true;
    status.textContent = "";
    status.classList.remove("status-error");
}

function revokeUrl(url) {
    if (url) URL.revokeObjectURL(url);
}

function selectFile(file) {
    clearStatus();
    resultPanel.hidden = true;
    currentFile = null;
    processButton.disabled = true;

    if (!file) {
        selectedFile.textContent = "ファイルは未選択です";
        return;
    }

    const extension = file.name.toLowerCase().split(".").pop();
    if (!acceptedExtensions.has(extension)) {
        selectedFile.textContent = "ファイルは未選択です";
        showStatus("対応形式はMP3とWAVです。", true);
        return;
    }
    if (file.size > maxFileSizeBytes) {
        selectedFile.textContent = "ファイルは未選択です";
        showStatus("ファイルサイズは25 MB以下にしてください。", true);
        return;
    }

    currentFile = file;
    selectedFile.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
    processButton.disabled = false;
}

async function processSelectedFile() {
    if (!currentFile) return;

    clearStatus();
    processButton.disabled = true;
    processButton.textContent = "音響を処理しています…";

    const body = new FormData();
    body.append("file", currentFile);

    try {
        const response = await fetch("/api/process", { method: "POST", body });
        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.error || "音声の変換に失敗しました。");
        }

        const processedBlob = await response.blob();
        revokeUrl(originalUrl);
        revokeUrl(processedUrl);
        originalUrl = URL.createObjectURL(currentFile);
        processedUrl = URL.createObjectURL(processedBlob);

        originalAudio.src = originalUrl;
        processedAudio.src = processedUrl;
        downloadLink.href = processedUrl;
        downloadLink.download = `${currentFile.name.replace(/\.[^.]+$/, "")}_exam-room.wav`;
        resultPanel.hidden = false;
        resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
        showStatus(error.message || "音声の変換に失敗しました。", true);
    } finally {
        processButton.disabled = currentFile === null;
        processButton.textContent = "試験会場プリセットを適用";
    }
}

window.addEventListener("beforeunload", () => {
    revokeUrl(originalUrl);
    revokeUrl(processedUrl);
});
