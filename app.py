import io
import logging
import os
import tempfile
from pathlib import Path

import soundfile as sf
from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from services.audio_processing import AudioProcessingError, process_audio_file


MAX_AUDIO_FILE_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".mp3", ".wav"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_AUDIO_FILE_BYTES + 1024 * 1024


def _allowed_filename(filename):
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@app.get("/")
def index():
    return render_template("index.html", max_file_size_mb=25)


@app.errorhandler(RequestEntityTooLarge)
def handle_oversized_request(_error):
    return jsonify({"error": "ファイルサイズは25 MB以下にしてください。"}), 413


@app.post("/api/process")
def process_audio():
    uploaded_file = request.files.get("file")
    if uploaded_file is None or not uploaded_file.filename:
        return jsonify({"error": "音声ファイルを選択してください。"}), 400
    if not _allowed_filename(uploaded_file.filename):
        return jsonify({"error": "対応形式はMP3とWAVです。"}), 400

    safe_name = secure_filename(uploaded_file.filename)
    suffix = Path(safe_name).suffix.lower()
    output_stem = Path(safe_name).stem or "processed-audio"

    try:
        with tempfile.TemporaryDirectory(prefix="listening-simulator-") as temp_dir:
            input_path = Path(temp_dir) / f"input{suffix}"
            uploaded_file.save(input_path)
            if input_path.stat().st_size > MAX_AUDIO_FILE_BYTES:
                return jsonify({"error": "ファイルサイズは25 MB以下にしてください。"}), 413

            processed = process_audio_file(input_path)

        output = io.BytesIO()
        sf.write(
            output,
            processed.samples,
            processed.sample_rate,
            format="WAV",
            subtype="PCM_16",
        )
        output.seek(0)
        return send_file(
            output,
            mimetype="audio/wav",
            as_attachment=False,
            download_name=f"{output_stem}_exam-room.wav",
        )
    except AudioProcessingError as error:
        return jsonify({"error": str(error)}), 422
    except Exception:
        app.logger.exception("Audio processing failed")
        return jsonify({"error": "音声の変換に失敗しました。"}), 500


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("PORT", 8000))
    app.run(host="127.0.0.1", port=port)
