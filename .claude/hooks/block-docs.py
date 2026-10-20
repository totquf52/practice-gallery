# 01_docs 를 지키는 훅 (block-docs)
# AI가 파일을 새로 쓰거나 고치기 직전, 그리고 명령 창에 명령을 넣기 직전에 돌아간다.
# 고치려는 파일이 01_docs 폴더 아래에 있거나, 명령이 01_docs 아래 파일을 바꾸는 명령이면
# 막고, 경고창을 띄우고, AI에게 이유를 돌려보낸다.
# 다른 자리의 파일이거나, 01_docs 를 읽기만 하는 명령이거나,
# 01_docs 를 읽어서 다른 자리(02_output 같은 곳)에 쓰는 명령이면 아무 말 없이 끝내서 그대로 지나가게 한다.
#
# 명령은 글자 모양을 보고 가려낸다. 그래서 01_docs 라는 이름이 명령에 그대로 적혀 있을 때만 잡는다.
# 이름을 다른 곳에 담아 두고 쓰거나(변수), 따로 만든 프로그램 파일 안에서 바꾸는 것은 잡지 못한다.

# 윈도우 창을 띄우는 데 쓰는 도구를 가져온다
import ctypes
# 훅이 주고받는 글(JSON)을 읽고 쓰는 도구를 가져온다
import json
# 윈도우 경로에서 파일 이름을 떼어 내는 도구를 가져온다
import ntpath
# 글자 모양을 찾는 도구(정규식)를 가져온다
import re
# 다른 프로그램을 따로 띄우는 도구를 가져온다
import subprocess
# 이 프로그램이 받은 값과 들어오는 글을 다루는 도구를 가져온다
import sys

# 지킬 폴더 이름
LOCKED_FOLDER = "01_docs"
# 경고창 맨 위에 적히는 제목
BOX_TITLE = "원본 자물쇠"
# 경고창 안에 적히는 글
BOX_TEXT = "01_docs 는 원본이라 고칠 수 없습니다"
# 막았을 때 AI에게 돌려보내는 이유
REASON = "01_docs 는 원본이라 고치지 말고, 정리한 결과는 02_output 에 새로 써라"

# 윈도우 알림창에 붙이는 표시들
# [확인] 버튼 하나만 둔다
MB_OK = 0x0
# 느낌표 그림을 붙인다
MB_ICONWARNING = 0x30
# 다른 창을 누르기 전에 이 창부터 보게 한다
MB_SYSTEMMODAL = 0x1000
# 창을 맨 앞으로 가져온다
MB_SETFOREGROUND = 0x10000
# 늘 다른 창 위에 있게 한다
MB_TOPMOST = 0x40000

# 창을 따로 띄울 때 쓰는 표시들
# 새 창을 이 훅의 명령 창에서 떼어 낸다
DETACHED_PROCESS = 0x8
# 새 창을 따로 된 묶음으로 띄운다
CREATE_NEW_PROCESS_GROUP = 0x200
# 훅이 끝나도 같이 닫히지 않게 훅 묶음에서 떼어 낸다
CREATE_BREAKAWAY_FROM_JOB = 0x1000000

# 명령 안에 01_docs 라는 이름이 적혀 있는지 본다. 01_docs_old, my-01_docs 같은 다른 이름은 빼고 본다.
DOCS_IN_TEXT = re.compile(r"(?<![\w.-])01_docs(?![\w.-])", re.IGNORECASE)
# C: 처럼 드라이브 글자로 시작하는 경로
DRIVE = re.compile(r"^[A-Za-z]:")

# 화살표(>, >>) 뒤에 오는 파일 이름. 화살표는 결과를 그 파일에 적으라는 뜻이다.
ARROW_TARGET = re.compile(r">\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s<>|;&\"']+))")

# 뒤에 적힌 파일을 모두 바꾸는 명령들 (지우기, 옮기기, 이름 바꾸기, 비우기, 새로 만들기)
ALL_ARGS = {
    # 지우는 명령들과 옮기는 명령들
    "rm", "rmdir", "rd", "del", "erase", "ri", "remove-item", "mv", "move", "mi", "move-item",
    # 이름을 바꾸는 명령들, 그리고 지우기·비우기·새로 만들기·받아 적기 명령들
    "ren", "rename", "rni", "rename-item", "unlink", "shred", "truncate", "touch", "tee",
    # 폴더를 만드는 명령들과 내용을 비우는 명령들
    "mkdir", "md", "clc", "clear-content",
# 묶음 끝
}
# 파일 하나에 내용을 적는 명령들. 적힐 파일 하나만 본다 (적을 내용은 01_docs 에서 읽어 와도 된다).
FIRST_ARG = {
    # 내용을 새로 적기·덧붙이기·파일에 내보내기·새로 만들기 명령들
    "sc", "set-content", "ac", "add-content", "out-file", "ni", "new-item",
    # 받아 적기와 표로 내보내기 명령들
    "tee-object", "export-csv", "epcsv",
# 묶음 끝
}
# 적힐 파일을 알려 주는 표시들
PATH_FLAGS = {"-path", "-literalpath", "-filepath"}
# 바로 뒤에 파일이 아닌 값이 오는 표시들. 그 값은 파일로 치지 않는다.
VALUE_FLAGS = {
    # 값·글자 방식·너비·나눔 글자·종류·이름을 알리는 표시들
    "-value", "-inputobject", "-encoding", "-width", "-delimiter", "-itemtype", "-type", "-name",
# 묶음 끝
}
# 베끼는 명령들. 01_docs 에서 베껴 가는 것은 읽기이고, 01_docs 안으로 베껴 넣을 때만 막는다.
COPIERS = {"cp", "cpi", "copy", "copy-item", "xcopy", "robocopy"}
# 받는 쪽을 알리는 표시(-Destination)를 찾는 모양
COPY_FLAG = re.compile(r"^-dest", re.IGNORECASE)
# dd 명령에서 적힐 파일(of=)을 찾는 모양
DD_TARGET = re.compile(r"\bof=[\"']?([^\s\"']+)", re.IGNORECASE)
# 자리를 옮기는 명령들. 01_docs 안으로 들어가면 그 뒤 명령은 이름 없이도 01_docs 를 바꿀 수 있다.
MOVERS = {"cd", "chdir", "pushd", "sl", "set-location"}
# 파일을 그 자리에서 바로 고치는 표시(-i, -pi 같은 것)가 붙으면 막는 명령들
INPLACE_TOOLS = {"sed", "gsed", "perl", "ruby"}
# 그 자리에서 고치라는 표시(-i, -pi, --in-place)를 찾는 모양
INPLACE_FLAG = re.compile(r"^(-(?![-MI])[A-Za-z0-9]*i|--in-place)")
# 한 줄짜리 프로그램을 돌리는 명령들. 그 안에서 01_docs 파일에 쓰는 모양이 보이면 막는다.
SCRIPT_TOOLS = {"python", "python3", "py", "node", "perl", "ruby", "php"}
# 한 줄짜리 프로그램 안에서 01_docs 에 쓰는 모양을 찾는다
SCRIPT_WRITE = re.compile(
    # open('01_docs/…', 'w') 처럼 쓰기로 여는 모양
    r"open\(\s*r?['\"][^'\"]*01_docs[^'\"]*['\"]\s*,\s*(mode\s*=\s*)?['\"][wax]"
    # '01_docs/…' 경로 바로 뒤에 점을 찍고 부르는 모양
    r"|['\"][^'\"]*01_docs[^'\"]*['\"]\s*\)\s*\.\s*"
    # 그 점 뒤에 오는 쓰기·지우기·이름 바꾸기·만들기 말들
    r"(write_text|write_bytes|unlink|rename|replace|touch|mkdir|rmdir)"
    # 괄호 안에 01_docs 를 넣어 부르는 내보내기·지우기·옮기기 말들
    r"|(to_csv|to_excel|to_json|to_parquet|remove|unlink|rmtree|rename|move|writefile\w*"
    # 이어서 덧붙이기·지우기·그림 저장 말들과, 그 괄호 안의 01_docs
    r"|appendfile\w*|unlinksync|rmsync|renamesync|savefig)\(\s*[^)]*01_docs",
    # 대소문자를 가리지 않는다
    re.IGNORECASE,
# 묶음 끝
)
# 파워셸에서 프로그램 말로 파일을 바꾸는 모양
DOTNET_WRITE = re.compile(
    # 파일에 쓰기·덧붙이기·지우기·옮기기 말들
    r"(writealltext|writealllines|writeallbytes|appendalltext|appendalllines|::delete|::move)"
    # 그 괄호 안 첫 자리에 01_docs 가 있는 모양
    r"\(\s*[^,)]*01_docs"
    # 옮기기·베끼기에서 받는 쪽(쉼표 뒤)에 01_docs 가 있는 모양
    r"|::(move|copy)\([^)]*,\s*[^)]*01_docs",
    # 대소문자를 가리지 않는다
    re.IGNORECASE,
# 묶음 끝
)
# git 명령 가운데 파일을 바꾸는 것들
GIT_WRITERS = {"checkout", "restore", "rm", "mv", "apply", "clean"}
# 다른 명령 창을 한 번 더 여는 명령들. 그 안에 든 명령을 다시 살핀다.
SHELLS = {"bash", "sh", "zsh", "cmd", "powershell", "pwsh", "wsl", "iex", "invoke-expression"}
# 명령 창을 열 때 붙는 표시(-c, /c 같은 것)를 찾는 모양
SHELL_FLAG = re.compile(r"^(-\w+|/\w)$")
# 명령 앞에 붙는 군말들. 건너뛰고 그 뒤의 진짜 명령을 본다.
SKIP_WORDS = {"sudo", "&", ".", "!", "command", "env", "time", "exec", "nohup", "if", "then", "do", "else"}
# 이름=값 꼴(명령 앞에 값을 정해 두는 말)을 찾는 모양
ASSIGN = re.compile(r"^\w+=\S*$")
# 명령 안의 명령을 몇 겹까지 살필지 정한 수
MAX_DEPTH = 3


# 경고창을 띄우는 일
def show_box():
    """경고창을 다른 창보다 맨 앞에 띄운다. [확인]을 누를 때까지 기다린다."""
    # 창에 붙일 표시를 모두 합친다
    flags = MB_OK | MB_ICONWARNING | MB_SYSTEMMODAL | MB_SETFOREGROUND | MB_TOPMOST
    # 윈도우에 경고창을 띄워 달라고 한다
    ctypes.windll.user32.MessageBoxW(None, BOX_TEXT, BOX_TITLE, flags)


# 경고창을 따로 띄우는 일
def open_box_apart():
    """경고창을 따로 띄운다. 훅이 [확인]을 기다리다 멈추지 않게 하려는 것이다."""
    # 새 창을 떼어 내는 표시를 합친다
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    # 훅이 끝날 때 창까지 같이 닫히지 않도록, 먼저 훅 묶음에서 떼어 내어 띄워 본다.
    # 떼어 내기가 허락되지 않으면 그냥 띄운다.
    for extra in (CREATE_BREAKAWAY_FROM_JOB, 0):
        # 띄우기를 해 본다
        try:
            # 다른 프로그램을 띄운다
            subprocess.Popen(
                # 이 스크립트를 --popup 을 붙여 다시 돌린다 (그러면 경고창만 띄운다)
                [sys.executable, __file__, "--popup"],
                # 들어오는 글은 받지 않는다
                stdin=subprocess.DEVNULL,
                # 나오는 글은 버린다
                stdout=subprocess.DEVNULL,
                # 잘못 알림도 버린다
                stderr=subprocess.DEVNULL,
                # 떼어 내는 표시를 붙인다
                creationflags=flags | extra,
                # 훅이 쓰던 통로를 물려주지 않는다
                close_fds=True,
            # 묶음 끝
            )
            # 띄웠으면 끝낸다
            return
        # 띄우지 못했으면
        except OSError:
            # 다음 방법으로 다시 해 본다
            continue


# 경로가 01_docs 아래인지 보는 일
def in_docs(word):
    """경로 가운데 01_docs 라는 폴더가 들어 있는지 본다. 대소문자는 가리지 않는다."""
    # 앞뒤 따옴표를 뗀다
    word = word.strip("\"'")
    # 괄호로 묶어 경로를 만들어 내는 자리는 01_docs 가 적혀 있기만 해도 그렇다고 본다
    if word.startswith(("(", "$(")):
        # 01_docs 가 적혀 있으면 그렇다고 답한다
        return bool(DOCS_IN_TEXT.search(word))
    # 빗금(/ 와 \)에서 경로를 토막 낸다 (끝에 붙은 괄호와 쉼표는 뗀다)
    parts = re.split(r"[\\/]+", word.rstrip("),"))
    # 토막 가운데 01_docs 가 있으면 그렇다고 답한다
    return any(part.lower() == LOCKED_FOLDER for part in parts)


# 지금 자리에서 벗어나지 않는 경로인지 보는 일
def stays_inside(word):
    """지금 있는 자리에서 벗어나지 않는 경로인지 본다 (.. 이나 맨 위부터 적은 경로가 아닌지)."""
    # 앞뒤 따옴표를 뗀다
    word = word.strip("\"'")
    # 비었거나, 위로 올라가거나(..), 맨 위부터 적었거나, 표시(-)이면
    if not word or word.startswith(("..", "/", "\\", "~", "$", "&", "-")):
        # 아니라고 답한다
        return False
    # 드라이브 글자(C:)로 시작하지 않으면 그렇다고 답한다
    return not DRIVE.match(word)


# 경로가 01_docs 아래를 가리키는지 보는 일
def hits(word, inside):
    """이 경로가 01_docs 아래를 가리키는지 본다. inside 는 지금 01_docs 안에 들어와 있다는 뜻이다."""
    # 01_docs 가 적혀 있거나, 01_docs 안에 있으면서 벗어나지 않는 경로이면 그렇다고 답한다
    return in_docs(word) or (inside and stays_inside(word))


# 따옴표 밖에서만 글을 자르는 일
def split_outside_quotes(text, breakers):
    """따옴표 밖에 있는 끊는 글자에서만 글을 자른다."""
    # 자른 조각들, 지금 모으는 글자들, 열려 있는 따옴표를 비워 둔다
    parts, now, quote = [], [], None
    # 글자를 하나씩 본다
    for ch in text:
        # 따옴표 안이면
        if quote:
            # 같은 따옴표를 다시 만났을 때
            if ch == quote:
                # 따옴표를 닫는다
                quote = None
        # 따옴표를 만나면
        elif ch in "\"'":
            # 따옴표를 연다
            quote = ch
        # 끊는 글자를 만나면
        elif ch in breakers:
            # 지금까지 모은 글자를 한 조각으로 담는다
            parts.append("".join(now))
            # 모으던 글자를 비운다
            now = []
            # 끊는 글자는 버리고 다음 글자로 간다
            continue
        # 글자를 모은다
        now.append(ch)
    # 마지막 조각을 담는다
    parts.append("".join(now))
    # 조각들을 돌려준다
    return parts


# 빈칸에서 낱말로 자르는 일
def split_words(text):
    """빈칸에서 낱말로 자른다. 따옴표 안과 괄호 안의 빈칸에서는 자르지 않는다."""
    # 낱말들, 지금 모으는 글자들, 열려 있는 따옴표, 괄호 깊이를 비워 둔다
    words, now, quote, depth = [], [], None, 0
    # 글자를 하나씩 본다
    for ch in text:
        # 따옴표 안이면
        if quote:
            # 같은 따옴표를 다시 만났을 때
            if ch == quote:
                # 따옴표를 닫는다
                quote = None
        # 따옴표를 만나면
        elif ch in "\"'":
            # 따옴표를 연다
            quote = ch
        # 여는 괄호를 만나면
        elif ch == "(":
            # 괄호 깊이를 하나 늘린다
            depth += 1
        # 닫는 괄호를 만나면
        elif ch == ")":
            # 괄호 깊이를 하나 줄인다 (0 아래로는 내려가지 않는다)
            depth = max(0, depth - 1)
        # 괄호 밖에서 빈칸을 만나면
        elif ch.isspace() and depth == 0:
            # 모은 글자가 있을 때
            if now:
                # 낱말 하나로 담는다
                words.append("".join(now))
                # 모으던 글자를 비운다
                now = []
            # 빈칸은 버리고 다음 글자로 간다
            continue
        # 글자를 모은다
        now.append(ch)
    # 남은 글자가 있으면
    if now:
        # 마지막 낱말로 담는다
        words.append("".join(now))
    # 낱말들을 돌려준다
    return words


# 파일 자리인 낱말만 고르는 일
def path_words(rest):
    """명령 뒤에 적힌 낱말 가운데 파일 자리인 것만 고른다."""
    # 고른 낱말들과, 다음 낱말을 건너뛸지를 비워 둔다
    paths, skip = [], False
    # 낱말을 하나씩 본다
    for word in rest:
        # 건너뛸 차례이면
        if skip:
            # 건너뛰고 표시를 끈다
            skip = False
        # 표시(-로 시작하는 낱말)이면
        elif word.startswith("-"):
            # 뒤에 값이 오는 표시일 때만 다음 낱말을 건너뛰게 한다
            skip = word.lower() in VALUE_FLAGS
        # 그 밖의 낱말이면
        else:
            # 파일 자리로 담는다
            paths.append(word)
    # 고른 낱말들을 돌려준다
    return paths


# 적힐 파일을 찾는 일
def first_target(rest):
    """내용을 적는 명령에서 적힐 파일을 찾는다."""
    # 마지막 낱말을 뺀 낱말을 차례로 본다
    for i, word in enumerate(rest[:-1]):
        # 적힐 파일을 알리는 표시이면
        if word.lower() in PATH_FLAGS:
            # 바로 뒤 낱말을 돌려준다
            return rest[i + 1]
    # 표시가 없으면 파일 자리 낱말을 고른다
    paths = path_words(rest)
    # 그 가운데 맨 앞 것을 돌려준다 (없으면 없다고 답한다)
    return paths[0] if paths else None


# 베끼는 명령에서 받는 쪽을 찾는 일
def copy_target(rest):
    """베끼는 명령에서 받는 쪽(맨 뒤에 적힌 파일)을 찾는다."""
    # 마지막 낱말을 뺀 낱말을 차례로 본다
    for i, word in enumerate(rest[:-1]):
        # 받는 쪽을 알리는 표시이면
        if COPY_FLAG.match(word):
            # 바로 뒤 낱말을 돌려준다
            return rest[i + 1]
    # 표시가 없으면 파일 자리 낱말을 고른다
    paths = path_words(rest)
    # 둘 이상이면 맨 뒤 것을 돌려준다 (하나뿐이면 받는 쪽이 없다고 답한다)
    return paths[-1] if len(paths) > 1 else None


# 명령 한 조각을 살피는 일
def piece_changes_docs(piece, inside, depth):
    """명령 한 조각이 01_docs 를 바꾸는지 본다. (바꾸는지, 그 뒤에 01_docs 안에 있는지)를 돌려준다."""
    # 01_docs 안도 아니고 01_docs 라는 이름도 없으면
    if not inside and not DOCS_IN_TEXT.search(piece):
        # 바꾸지 않는다고 답한다
        return False, inside

    # 화살표 뒤의 파일 이름을 모두 찾는다
    for found in ARROW_TARGET.finditer(piece):
        # 따옴표가 있든 없든 그 파일 이름을 꺼낸다
        target = found.group(1) or found.group(2) or found.group(3)
        # 그 파일이 01_docs 아래이면
        if hits(target, inside):
            # 바꾼다고 답한다
            return True, inside

    # 프로그램 말로 01_docs 에 쓰는 모양이 있으면
    if DOTNET_WRITE.search(piece):
        # 바꾼다고 답한다
        return True, inside

    # 조각을 낱말로 자른다
    words = split_words(piece)
    # 괄호 안에 든 명령도 따로 본다
    if depth < MAX_DEPTH:
        # 낱말을 하나씩 본다
        for word in words:
            # 괄호로 시작하는 낱말이면
            if word.startswith(("(", "$(")):
                # 괄호를 벗겨 안의 명령을 꺼낸다
                inner = word.lstrip("$(").rstrip(")")
                # 안의 명령이 01_docs 를 바꾸면
                if command_changes_docs(inner, inside, depth + 1):
                    # 바꾼다고 답한다
                    return True, inside

    # 맨 앞이 군말이거나 이름=값 꼴인 동안
    while words and (words[0].lower() in SKIP_WORDS or ASSIGN.match(words[0])):
        # 그 낱말을 떼어 낸다
        words.pop(0)
    # $이름 = 명령 꼴이면 그 뒤의 명령을 본다
    if len(words) >= 2 and words[0].startswith("$") and words[1] == "=":
        # 앞의 두 낱말을 떼어 낸다
        words = words[2:]
    # 남은 낱말이 없으면
    if not words:
        # 바꾸지 않는다고 답한다
        return False, inside

    # 맨 앞 낱말에서 명령 이름만 떼어 소문자로 바꾼다
    name = ntpath.basename(words[0].strip("\"'")).lower()
    # 이름이 .exe 로 끝나면
    if name.endswith(".exe"):
        # .exe 를 뗀다
        name = name[:-4]
    # 명령 이름 뒤의 낱말들
    rest = words[1:]
    # 그 가운데 파일 자리 낱말들
    paths = path_words(rest)

    # 자리를 옮기는 명령이면
    if name in MOVERS:
        # 옮길 자리가 적혀 있을 때
        if paths:
            # 그 자리가 01_docs 안인지 적어 둔다
            inside = in_docs(paths[0]) or (inside and stays_inside(paths[0]))
        # 옮기기만 한 것이니 바꾸지 않는다고 답한다
        return False, inside

    # 뒤의 파일을 모두 바꾸는 명령이고 그 가운데 01_docs 아래 파일이 있으면
    if name in ALL_ARGS and any(hits(w, inside) for w in paths):
        # 바꾼다고 답한다
        return True, inside
    # 파일 하나에 내용을 적는 명령이면
    if name in FIRST_ARG:
        # 적힐 파일을 찾는다
        target = first_target(rest)
        # 그 파일이 01_docs 아래이면
        if target and hits(target, inside):
            # 바꾼다고 답한다
            return True, inside
    # 베끼는 명령이면
    if name in COPIERS:
        # 받는 쪽을 찾는다
        target = copy_target(rest)
        # 받는 쪽이 01_docs 아래이면
        if target and hits(target, inside):
            # 바꾼다고 답한다
            return True, inside
    # dd 명령이면
    if name == "dd":
        # 적힐 파일(of=)을 찾는다
        out = DD_TARGET.search(piece)
        # 그 파일이 01_docs 아래이면
        if out and hits(out.group(1), inside):
            # 바꾼다고 답한다
            return True, inside
    # 그 자리에서 고치는 표시가 붙은 명령이면
    if name in INPLACE_TOOLS and any(INPLACE_FLAG.match(w) for w in rest):
        # 뒤의 파일 가운데 01_docs 아래 파일이 있을 때
        if any(hits(w, inside) for w in paths):
            # 바꾼다고 답한다
            return True, inside
    # 한 줄짜리 프로그램이 01_docs 에 쓰는 모양이면
    if name in SCRIPT_TOOLS and SCRIPT_WRITE.search(piece):
        # 바꾼다고 답한다
        return True, inside
    # 01_docs 안에서 파일을 찾는 find 명령이면
    if name == "find" and (inside or any(in_docs(w) for w in paths)):
        # 뒤의 낱말을 소문자로 바꾼다
        lowered = [w.lower() for w in rest]
        # 찾은 것을 지우라는 표시가 있으면
        if "-delete" in lowered:
            # 바꾼다고 답한다
            return True, inside
        # 낱말을 차례로 본다
        for i, word in enumerate(lowered[:-1]):
            # 찾은 것마다 지우거나 고치는 명령을 돌리라는 표시이면
            if word in ("-exec", "-execdir") and lowered[i + 1] in ALL_ARGS | INPLACE_TOOLS:
                # 바꾼다고 답한다
                return True, inside
    # 파일을 바꾸는 git 명령이면
    if name == "git" and any(w.lower() in GIT_WRITERS for w in rest):
        # 뒤의 파일 가운데 01_docs 아래 파일이 있을 때
        if any(hits(w, inside) for w in paths):
            # 바꾼다고 답한다
            return True, inside
    # 다른 명령 창을 여는 명령이면 (너무 깊지 않을 때만)
    if name in SHELLS and depth < MAX_DEPTH:
        # 따옴표 없는 낱말을 모을 자리
        loose = []
        # 뒤의 낱말을 하나씩 본다
        for word in rest:
            # 따옴표로 시작하는 낱말이면
            if word[:1] in "\"'":
                # 따옴표 안의 명령이 01_docs 를 바꾸는지 다시 살핀다
                if command_changes_docs(word.strip("\"'"), inside, depth + 1):
                    # 바꾼다고 답한다
                    return True, inside
            # 명령 창 표시가 아닌 낱말이면
            elif not SHELL_FLAG.match(word):
                # 모아 둔다
                loose.append(word)
        # 모은 낱말을 이어 붙인 명령이 01_docs 를 바꾸는지 다시 살핀다
        if command_changes_docs(" ".join(loose), inside, depth + 1):
            # 바꾼다고 답한다
            return True, inside
    # 아무것에도 걸리지 않았으니 바꾸지 않는다고 답한다
    return False, inside


# 명령 전체를 살피는 일
def command_changes_docs(command, inside=False, depth=0):
    """명령이 01_docs 를 바꾸는지 본다. 읽기만 하는 명령은 아니라고 답한다."""
    # 01_docs 안도 아니고 01_docs 라는 이름도 없으면
    if not inside and not DOCS_IN_TEXT.search(command):
        # 바꾸지 않는다고 답한다
        return False
    # 명령을 잇는 글자(; | & 줄바꿈 중괄호)에서 잘라 조각마다 따로 본다.
    # 그래야 01_docs 를 읽어서 다른 자리에 적는 명령을 막지 않는다.
    for piece in split_outside_quotes(command, ";|&\n{}"):
        # 조각 하나를 살피고, 01_docs 안에 있는지도 이어받는다
        changed, inside = piece_changes_docs(piece, inside, depth)
        # 조각이 01_docs 를 바꾸면
        if changed:
            # 바꾼다고 답한다
            return True
    # 어느 조각도 바꾸지 않으면 아니라고 답한다
    return False


# 훅이 돌 때 맨 먼저 하는 일
def main():
    # --popup 이 붙어 왔으면
    if "--popup" in sys.argv:
        # 경고창만 띄우고
        show_box()
        # 끝낸다
        return

    # 넘어온 글을 읽어 본다
    try:
        # utf-8-sig : 글 맨 앞에 보이지 않는 표시(BOM)가 붙어 와도 읽는다
        data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        # 도구가 넘겨준 값을 꺼낸다
        tool_input = data["tool_input"]
        # 파일을 고치는 도구는 file_path(공책 파일은 notebook_path)를, 명령 창 도구는 command 를 넘겨준다
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
        # 명령 창 도구가 넘겨준 명령을 꺼낸다
        command = tool_input.get("command")
        # 명령을 넣는 자리가 이미 01_docs 안인지도 본다
        cwd = data.get("cwd")
    # 읽지 못했거나 모양이 다르면
    except (ValueError, KeyError, TypeError, AttributeError):
        # 아무 말 없이 끝낸다 (그대로 지나가게 한다)
        return

    # 파일 경로가 넘어왔으면
    if isinstance(file_path, str):
        # 그 파일이 01_docs 아래가 아닐 때
        if not in_docs(file_path):
            # 그대로 지나가게 한다
            return
    # 파일 경로가 없으면 (명령 창 도구이면)
    else:
        # 명령을 넣는 자리가 01_docs 안인지 본다
        inside = isinstance(cwd, str) and in_docs(cwd)
        # 명령이 없거나 01_docs 를 바꾸지 않으면
        if not isinstance(command, str) or not command_changes_docs(command, inside):
            # 그대로 지나가게 한다
            return

    # 경고창 띄우기를 해 본다
    try:
        # 경고창을 따로 띄운다
        open_box_apart()
    # 띄우지 못해도
    except OSError:
        # 그냥 넘어간다 (막는 일은 그대로 한다)
        pass

    # AI에게 돌려보낼 답을 만든다
    answer = {
        # 훅이 내는 답 묶음
        "hookSpecificOutput": {
            # 도구를 쓰기 직전에 낸 답이라는 표시
            "hookEventName": "PreToolUse",
            # 막는다는 결정
            "permissionDecision": "deny",
            # 막은 이유
            "permissionDecisionReason": REASON,
        # 답 묶음 끝
        }
    # 답 끝
    }
    # 답을 글로 바꿔 내보낸다
    print(json.dumps(answer))


# 이 파일을 바로 돌렸을 때만
if __name__ == "__main__":
    # main 을 돌린다
    main()
