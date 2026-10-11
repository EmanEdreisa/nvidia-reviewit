"""Launch the Video Lecture Transcriber."""

from transcriber.web_ui import TranscriberApp


def main() -> None:
    app = TranscriberApp()
    app.run()


if __name__ == "__main__":
    main()
