"""Klien LLM dengan fallback model dan penanganan rate limit."""

import time

from openai import OpenAI

from .config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_HEADERS,
    LLM_MODEL,
    LLM_PROVIDER,
    _env,
)

_client_kwargs = {"api_key": LLM_API_KEY, "base_url": LLM_BASE_URL}
if LLM_HEADERS:
    _client_kwargs["default_headers"] = LLM_HEADERS
client = OpenAI(**_client_kwargs)

OPENROUTER_FALLBACK_MODELS = [
    "NVIDIA: Nemotron 3 Nano 30B A3B/free",
    "openrouter/free",
]

SYSTEM_PROMPT_DEFAULT = (
    "Kamu adalah asisten akademik universitas tingkat tinggi. "
    "Tugasmu adalah menyelesaikan tugas kuliah yang diberikan oleh user. "
    "Berikan jawaban yang sangat mendalam, analitis, terstruktur dengan baik, "
    "dan gunakan bahasa Indonesia yang natural, cerdas, layaknya mahasiswa asli. "
    "HINDARI gaya bahasa kaku khas AI seperti 'Dalam era digital ini' atau 'Signifikan'."
)


def daftar_model_llm():
    utama = LLM_MODEL
    custom = _env("LLM_FALLBACK_MODELS", "")
    cadangan = (
        [m.strip() for m in custom.split(",") if m.strip()]
        if custom
        else (OPENROUTER_FALLBACK_MODELS if LLM_PROVIDER == "openrouter" else [])
    )
    urutan, seen = [], set()
    for model in [utama] + cadangan:
        if model and model not in seen:
            seen.add(model)
            urutan.append(model)
    return urutan


def _is_rate_limit_error(err):
    teks = str(err).lower()
    return "429" in teks or "rate" in teks or "rate-limited" in teks


def _panggil_llm(model, messages):
    for percobaan in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.4,
                max_tokens=4096,
            )
            return response.choices[0].message.content, None
        except Exception as e:
            if _is_rate_limit_error(e) and percobaan < 2:
                tunggu = 25 * (percobaan + 1)
                print(f"[AI] Rate limit pada {model}, tunggu {tunggu}s lalu coba lagi...")
                time.sleep(tunggu)
                continue
            return None, e
    return None, None


def minta_jawaban(soal_tugas, system_prompt=None):
    """Kembalikan (jawaban, model) — model diisi nama model yang berhasil dipakai."""
    if not LLM_API_KEY:
        return "API key belum diatur di file .env", ""

    if len(soal_tugas) > 12000:
        soal_tugas = soal_tugas[:12000] + "\n\n[...teks dipotong...]"

    messages = [
        {"role": "system", "content": system_prompt or SYSTEM_PROMPT_DEFAULT},
        {"role": "user", "content": f"Selesaikan tugas kuliah ini dengan kualitas terbaik:\n\n{soal_tugas}"},
    ]

    for model in daftar_model_llm():
        print(f"[AI] Mencoba model: {model}")
        jawaban, err = _panggil_llm(model, messages)
        if jawaban:
            return jawaban, model
        print(f"[AI Error] {model}: {err}")

    return "Semua model AI sibuk atau kuota habis. Silakan coba lagi nanti.", ""
