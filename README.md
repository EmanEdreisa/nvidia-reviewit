# Review It

**Don't just note it. Review it.**

Windows software with a modern local web interface. It transcribes lecture videos locally, adds context from the instructor's shared screen, and exports Word or PDF files.

## Processing

- Speech: faster-whisper, running locally.
- Screen text: RapidOCR, running locally.
- Optional visual understanding: Gemma 3 through Ollama on the same computer.
- Export: Word and PDF files generated locally.
- No paid API, account, or subscription is required.

## Install

1. Use 64-bit Python 3.10 through 3.13. The setup script automatically uses the Python interpreter registered with the Windows Python launcher.
2. If Python is missing, install it from https://www.python.org/downloads/windows/. During installation, select **Add python.exe to PATH**, then select **Install Now**.
3. Double-click `setup.bat` in this folder.
4. Wait for **Setup complete**, then press any key.

## Optional local vision AI

1. Download Ollama for Windows from https://ollama.com/download/windows.
2. Install and open Ollama.
3. Open Windows Terminal or Command Prompt.
4. Run `ollama pull gemma3:4b`.
5. Wait until the model download reaches 100%.

If Ollama is not installed, the application automatically continues with screen OCR.

## Use

1. Double-click `run.bat`.
2. Select **Browse** and choose a lecture video.
3. Leave **Speech model** set to `small` for the first run.
4. Leave **Language** set to `auto`, or enter a language code such as `en` or `fil`.
5. Leave **Screen interval** at `45` seconds for long videos.
6. Leave **Processing mode** on **Balanced**. Choose **Fast** when speed matters more than maximum accuracy.
7. Select **Detailed screen AI** only when detailed visual descriptions are required; it substantially increases processing time.
8. Select **Start transcription**.
9. On the first run, wait while the speech and OCR models download.
10. When processing finishes, choose a transcript tab, then select **Word** or **PDF**.
11. Choose a folder, enter a filename, and select **Save**.

## Optional reviewer

1. Finish the transcription first.
2. Select **Create Reviewer**.
3. The app immediately creates a simple demonstration reviewer.
4. If Ollama and `gemma3:4b` are installed, the app automatically uses them for a better reviewer.
5. Open the **Reviewer** tab and export it to Word or PDF if needed.

The reviewer is optional and does not change the original transcript. For very long
transcripts it uses selected sections and labels the result as a quick reviewer.

## Speed choices

- **Fast**: quickest decoding with a small accuracy tradeoff.
- **Balanced**: recommended for most lectures; faster than the former desktop version.
- **Accurate**: performs a wider wording search and takes longer.
- 1440p and 4K screen frames are automatically resized before OCR to reduce processing time.

## Model choices

- `tiny` or `base`: fastest, lowest accuracy.
- `small`: recommended starting point.
- `medium`: better accuracy, slower.
- `large-v3`: highest accuracy, requires substantially more memory and time.

## Developer checks

Run `python -m unittest discover -s tests -v` from the project environment.
