# PRD.md 를 지키는 훅
# AI가 파일을 새로 쓰거나 고치기 직전, 그리고 명령 창에 명령을 넣기 직전에 돌아간다.
# 고치려는 파일이 PRD.md 이거나, 명령이 PRD.md 를 바꾸는 명령이면
# 막고, 경고창을 띄우고, AI에게 이유를 돌려보낸다.
# 다른 파일이거나 PRD.md 를 읽기만 하는 명령이면 아무 말 없이 끝내서 그대로 지나가게 한다.
#
# 명령은 글자 모양을 보고 가려낸다. 그래서 PRD.md 라는 이름이 명령에 그대로 적혀 있을 때만 잡는다.
# 이름을 다른 곳에 담아 두고 쓰거나(변수), *.md 처럼 뭉뚱그려 쓰거나,
# 따로 만든 프로그램 파일 안에서 바꾸는 것은 잡지 못한다.

import ctypes
import json
import ntpath
import re
import subprocess
import sys

LOCKED_NAME = "prd.md"
BOX_TITLE = "PRD 자물쇠"
BOX_TEXT = "PRD.md 는 잠겨 있습니다"
REASON = "PRD.md 는 잠겨 있으니 고치지 말고 바꿀 내용을 제안만 하라"

# 윈도우 알림창에 붙이는 표시들
MB_OK = 0x0
MB_ICONWARNING = 0x30
MB_SYSTEMMODAL = 0x1000
MB_SETFOREGROUND = 0x10000
MB_TOPMOST = 0x40000

# 창을 따로 띄울 때 쓰는 표시들
DETACHED_PROCESS = 0x8
CREATE_NEW_PROCESS_GROUP = 0x200
CREATE_BREAKAWAY_FROM_JOB = 0x1000000

# 명령 안에 PRD.md 라는 이름이 적혀 있는지 본다. PRD.md.bak, my-prd.md 같은 다른 파일은 빼고 본다.
PRD_IN_TEXT = re.compile(r"(?<![\w.-])prd\.md(?![\w-]|\.\w)", re.IGNORECASE)

# 화살표(>, >>) 뒤에 오는 파일 이름. 화살표는 결과를 그 파일에 적으라는 뜻이다.
ARROW_TARGET = re.compile(r">\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s<>|;&\"']+))")

# 이름만 봐도 파일을 바꾸는 명령들. 조각 어디에 있어도 잡는다.
LONG_WRITERS = re.compile(
    r"(?<![\w-])(set-content|add-content|clear-content|out-file|remove-item|move-item"
    r"|rename-item|new-item|tee-object|export-csv|writealltext|writealllines"
    r"|writeallbytes|appendalltext|appendalllines)(?![\w-])"
    r"|::(delete|move|replace)\b",
    re.IGNORECASE,
)

# 짧은 이름으로 파일을 바꾸는 명령들. 흔한 글자라서 명령 자리(맨 앞)에 있을 때만 잡는다.
SHORT_WRITERS = {
    "sc", "ac", "clc", "ri", "rm", "rmdir", "rd", "del", "erase", "mi", "mv", "move",
    "rni", "ren", "rename", "ni", "tee", "truncate", "touch", "unlink", "shred",
}
# 베끼는 명령들. PRD.md 를 베껴 가는 것은 읽기이고, PRD.md 위에 덮어쓸 때만 막는다.
COPIERS = {"cp", "cpi", "copy", "copy-item", "xcopy"}
COPY_TARGET = re.compile(r"-dest\w*[:\s]+[\"']?([^\s\"']+)", re.IGNORECASE)
DD_TARGET = re.compile(r"\bof=[\"']?([^\s\"']+)", re.IGNORECASE)
# 파일을 그 자리에서 바로 고치는 표시(-i, -pi 같은 것)가 붙으면 막는 명령들
INPLACE_TOOLS = {"sed", "gsed", "perl", "ruby"}
INPLACE_FLAG = re.compile(r"^(-(?![-MI])[A-Za-z0-9]*i|--in-place)")
# 한 줄짜리 프로그램을 돌리는 명령들. 그 안에 쓰기 표시가 있으면 막는다.
SCRIPT_TOOLS = {"python", "python3", "py", "node", "perl", "ruby", "php"}
SCRIPT_WRITE = re.compile(
    r"['\"][wax][bt+]*['\"]|write|append|unlink|remove|rename|truncate|rmtree",
    re.IGNORECASE,
)
GIT_WRITERS = {"checkout", "restore", "rm", "mv", "apply"}
# 다른 명령 창을 한 번 더 여는 명령들. 그 안에 든 명령을 다시 살핀다.
SHELLS = {"bash", "sh", "zsh", "cmd", "powershell", "pwsh", "wsl", "iex", "invoke-expression"}
SHELL_FLAG = re.compile(r"^(-\w+|/\w)$")
# 명령 앞에 붙는 군말들. 건너뛰고 그 뒤의 진짜 명령을 본다.
SKIP_WORDS = {"sudo", "&", ".", "!", "command", "env", "time", "exec", "nohup", "if", "then", "do", "else"}
ASSIGN = re.compile(r"^\w+=\S*$")
MAX_DEPTH = 3


def show_box():
    """경고창을 다른 창보다 맨 앞에 띄운다. [확인]을 누를 때까지 기다린다."""
    flags = MB_OK | MB_ICONWARNING | MB_SYSTEMMODAL | MB_SETFOREGROUND | MB_TOPMOST
    ctypes.windll.user32.MessageBoxW(None, BOX_TEXT, BOX_TITLE, flags)


def open_box_apart():
    """경고창을 따로 띄운다. 훅이 [확인]을 기다리다 멈추지 않게 하려는 것이다."""
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    # 훅이 끝날 때 창까지 같이 닫히지 않도록, 먼저 훅 묶음에서 떼어 내어 띄워 본다.
    # 떼어 내기가 허락되지 않으면 그냥 띄운다.
    for extra in (CREATE_BREAKAWAY_FROM_JOB, 0):
        try:
            subprocess.Popen(
                [sys.executable, __file__, "--popup"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags | extra,
                close_fds=True,
            )
            return
        except OSError:
            continue


def is_locked(file_path):
    """경로 맨 끝 파일 이름이 PRD.md 인지 본다. 대소문자는 가리지 않는다."""
    return ntpath.basename(file_path).lower() == LOCKED_NAME


def split_outside_quotes(text, breakers):
    """따옴표 밖에 있는 끊는 글자에서만 글을 자른다."""
    parts, now, quote = [], [], None
    for ch in text:
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in breakers:
            parts.append("".join(now))
            now = []
            continue
        now.append(ch)
    parts.append("".join(now))
    return parts


def pull_quoted(text):
    """따옴표 안의 글을 따로 빼낸다. (따옴표 밖 글, 따옴표 안 글 목록)을 돌려준다."""
    plain, inside, now, quote = [], [], [], None
    for ch in text:
        if quote:
            if ch == quote:
                inside.append("".join(now))
                now, quote = [], None
                plain.append(" ")
            else:
                now.append(ch)
        elif ch in "\"'":
            quote = ch
        else:
            plain.append(ch)
    if quote:
        inside.append("".join(now))
    return "".join(plain), inside


def copy_lands_on_prd(piece):
    """베끼는 명령에서 받는 쪽(맨 뒤에 적힌 파일)이 PRD.md 인지 본다."""
    named = COPY_TARGET.search(piece)
    if named:
        return is_locked(named.group(1))
    words = [w.strip("\"'") for w in re.findall(r"\"[^\"]*\"|'[^']*'|\S+", piece)]
    paths = [w for w in words[1:] if not w.startswith("-")]
    return bool(paths) and is_locked(paths[-1].rstrip(")"))


def piece_changes_prd(piece, depth):
    """명령 한 조각이 PRD.md 를 바꾸는지 본다."""
    if not PRD_IN_TEXT.search(piece):
        return False

    for found in ARROW_TARGET.finditer(piece):
        target = found.group(1) or found.group(2) or found.group(3)
        if is_locked(target.rstrip(")")):
            return True

    if LONG_WRITERS.search(piece):
        return True

    plain, inside = pull_quoted(piece)
    # 괄호 안에 든 명령도 따로 본다
    for small in re.split(r"[()`]", plain):
        words = small.split()
        while words and (words[0].lower() in SKIP_WORDS or ASSIGN.match(words[0])):
            words.pop(0)
        if not words:
            continue
        name = ntpath.basename(words[0]).lower()
        if name.endswith(".exe"):
            name = name[:-4]
        rest = words[1:]

        if name in SHORT_WRITERS:
            return True
        if name in COPIERS and copy_lands_on_prd(piece):
            return True
        if name == "dd":
            out = DD_TARGET.search(piece)
            if out and is_locked(out.group(1)):
                return True
        if name in INPLACE_TOOLS and any(INPLACE_FLAG.match(w) for w in rest):
            return True
        if name in SCRIPT_TOOLS and SCRIPT_WRITE.search(piece):
            return True
        if name == "git" and any(w.lower() in GIT_WRITERS for w in rest):
            return True
        if name in SHELLS and depth < MAX_DEPTH:
            if any(command_changes_prd(q, depth + 1) for q in inside):
                return True
            inner = " ".join(w for w in rest if not SHELL_FLAG.match(w))
            if command_changes_prd(inner, depth + 1):
                return True
    return False


def command_changes_prd(command, depth=0):
    """명령이 PRD.md 를 바꾸는지 본다. 읽기만 하는 명령은 아니라고 답한다."""
    if not PRD_IN_TEXT.search(command):
        return False
    # 명령을 잇는 글자(; | & 줄바꿈 중괄호)에서 잘라 조각마다 따로 본다.
    # 그래야 PRD.md 를 읽어서 다른 파일에 적는 명령을 막지 않는다.
    pieces = split_outside_quotes(command, ";|&\n{}")
    return any(piece_changes_prd(piece, depth) for piece in pieces)


def main():
    if "--popup" in sys.argv:
        show_box()
        return

    try:
        # utf-8-sig : 글 맨 앞에 보이지 않는 표시(BOM)가 붙어 와도 읽는다
        data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        tool_input = data["tool_input"]
        # 파일을 고치는 도구는 file_path 를, 명령 창 도구는 command 를 넘겨준다
        file_path = tool_input.get("file_path")
        command = tool_input.get("command")
    except (ValueError, KeyError, TypeError, AttributeError):
        return

    if isinstance(file_path, str):
        if not is_locked(file_path):
            return
    elif not isinstance(command, str) or not command_changes_prd(command):
        return

    try:
        open_box_apart()
    except OSError:
        pass

    answer = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON,
        }
    }
    print(json.dumps(answer))


if __name__ == "__main__":
    main()
