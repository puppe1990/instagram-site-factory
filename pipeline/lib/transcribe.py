from __future__ import annotations

import json
import mimetypes
import subprocess
import time
import uuid
from pathlib import Path
from urllib import error, request

BASE_URL = "https://api.assemblyai.com"


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _video_sort_key(path: Path) -> tuple:
    meta_path = path.with_suffix(path.suffix + ".json")
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            likes = int(meta.get("likes") or 0)
            date = str(meta.get("date") or meta.get("post_date") or "")
            return (likes, date)
        except (json.JSONDecodeError, ValueError):
            pass
    return (0, path.name)


def convert_videos_to_mp3(
    video_dir: Path,
    audio_dir: Path,
    limit: int | None = None,
    sort_by: str = "likes",
) -> list[Path]:
    audio_dir.mkdir(parents=True, exist_ok=True)
    video_files = list(video_dir.glob("*.mp4"))
    if sort_by == "likes":
        video_files.sort(key=_video_sort_key, reverse=True)
    else:
        video_files.sort(key=lambda path: path.name, reverse=True)
    if limit:
        video_files = video_files[:limit]

    mp3_files: list[Path] = []
    for i, video in enumerate(video_files, 1):
        mp3_file = audio_dir / f"{video.stem}.mp3"
        if mp3_file.exists() and mp3_file.stat().st_size > 0:
            print(f"[{i}/{len(video_files)}] [PULADO] {mp3_file.name}")
            mp3_files.append(mp3_file)
            continue

        print(f"[{i}/{len(video_files)}] [MP3] {video.name}")
        run_cmd(
            ["ffmpeg", "-i", str(video), "-vn", "-ab", "192k", "-ar", "44100", "-y", str(mp3_file)],
        )
        if mp3_file.exists() and mp3_file.stat().st_size > 0:
            mp3_files.append(mp3_file)

    return mp3_files


def api_request(url: str, method: str = "GET", headers=None, data=None) -> dict:
    req = request.Request(url, method=method, headers=headers or {}, data=data)
    try:
        with request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with {exc.code}: {body}") from exc


def upload_file(file_path: Path, api_key: str) -> str:
    boundary = f"----AssemblyAIBoundary{uuid.uuid4().hex}"
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode(),
            f"Content-Type: {mime_type}\r\n\r\n".encode(),
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    headers = {
        "authorization": api_key,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
    }
    response = api_request(f"{BASE_URL}/v2/upload", method="POST", headers=headers, data=body)
    return response["upload_url"]


def start_transcript(audio_url: str, api_key: str) -> str:
    config = {
        "audio_url": audio_url,
        "speech_models": ["universal-3-pro", "universal-2"],
        "speaker_labels": True,
        "language_detection": True,
        "temperature": 0,
    }
    headers = {
        "authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    response = api_request(
        f"{BASE_URL}/v2/transcript",
        method="POST",
        headers=headers,
        data=json.dumps(config).encode("utf-8"),
    )
    return response["id"]


def poll_transcript(transcript_id: str, api_key: str) -> dict:
    headers = {"authorization": api_key, "Accept": "application/json"}
    polling_url = f"{BASE_URL}/v2/transcript/{transcript_id}"
    while True:
        result = api_request(polling_url, headers=headers)
        status = result["status"]
        if status == "completed":
            return result
        if status == "error":
            raise RuntimeError(result.get("error", "unknown transcription error"))
        time.sleep(3)


def format_transcript(result: dict) -> str:
    utterances = result.get("utterances") or []
    if utterances:
        return " ".join(
            utterance.get("text", "").strip() for utterance in utterances if utterance.get("text")
        ).strip()
    return (result.get("text") or "").strip()


def transcribe_mp3_files(
    mp3_files: list[Path], transcript_dir: Path, api_key: str
) -> dict[str, str]:
    transcript_dir.mkdir(parents=True, exist_ok=True)
    transcripts: dict[str, str] = {}

    for i, mp3_file in enumerate(mp3_files, 1):
        out_file = transcript_dir / f"{mp3_file.stem}.txt"
        if out_file.exists() and out_file.stat().st_size > 0:
            text = out_file.read_text(encoding="utf-8").strip()
            transcripts[mp3_file.stem] = text
            print(f"[{i}/{len(mp3_files)}] [CACHE] {out_file.name}")
            continue

        print(f"[{i}/{len(mp3_files)}] [UPLOAD] {mp3_file.name}")
        upload_url = upload_file(mp3_file, api_key)
        print(f"[{i}/{len(mp3_files)}] [TRANSCRIBE] {mp3_file.name}")
        transcript_id = start_transcript(upload_url, api_key)
        result = poll_transcript(transcript_id, api_key)
        text = format_transcript(result)
        out_file.write_text(text + "\n", encoding="utf-8")
        transcripts[mp3_file.stem] = text
        print(f"[{i}/{len(mp3_files)}] [OK] {len(text)} chars")

    return transcripts
