# 0002: OSC 52 tests

Tests for [0001](0001-osc52-clipboard-write.md). Kept separate so 0001 stays
a minimal change to PuTTY; drop this patch to build without it.

## What is tested

- Option round trip: `OSC52Write` is saved and loaded, default Deny.
- Allow mode: `BEL`, `ESC \` and C1 ST terminators, the accepted selection parameters,
  newline conversion, and that nothing is written in Deny mode.
- Rejected input, with nothing written: oversized, empty or malformed Base64,
  invalid UTF-8, embedded NUL, missing `;`, a clipboard query (`?`), and a
  sequence aborted before its terminator.
- Ask mode:
  - one prompt per request, with the size, line count and preview text;
  - Yes writes, No writes nothing;
  - after No, requests are dropped until the user types, pastes or changes
    the settings;
  - invalid requests never reach the prompt;
  - control and bidi characters in the preview are replaced.
- Allow mode never prompts.

The terminal test uses a mock window that records clipboard writes and prompts
and answers them on demand. The size limit is lowered for the size test, so
it needs only tiny payloads.

## Running

`test_terminal` is built by the Windows build (and by the Unix build when GTK
is found); run `test_terminal.exe` there. The expected newline in the output
depends on the platform: CRLF on Windows, LF on Unix.
