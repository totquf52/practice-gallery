# 첫 화면 큰 제목 뒤에 깔 배경 영상(static/hero.mp4)을 만든다
# PRD.md 의 "실습 게시판이 격자로 한 번에 깔린다"를 그림으로 옮겼다
#   - 강조 색 빛 덩어리 세 개가 천천히 맴돈다
#   - 5x4 게시판 칸 위로 불빛이 물결처럼 지나가고, 몇 칸은 눌린 것처럼 반짝인다
# 모든 움직임이 SECONDS 초에 딱 한 바퀴 돌게 맞춰서, 끝과 처음이 끊기지 않고 이어진다
# 글자는 넣지 않는다 (위에 큰 제목과 버튼을 올린다)
#
# 먼저 깔 것 : pip install imageio imageio-ffmpeg
# 만드는 법 : python make_hero.py

from pathlib import Path

import imageio.v2 as imageio
import numpy as np

WIDTH, HEIGHT = 1280, 720
FPS = 30
SECONDS = 8
OUT = Path(__file__).parent / "static" / "hero.mp4"

BACK = np.array([21, 13, 14]) / 255  # 배경 #150d0e
ACCENT = np.array([239, 85, 147]) / 255  # 강조 #ef5593
LIGHT = np.array([228, 202, 213]) / 255  # 글자 #e4cad5

COLS, ROWS = 5, 4
CELL_W, CELL_H, GAP, RADIUS = 176, 112, 22, 16

y, x = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)


def smooth(edge0, edge1, value):
    t = np.clip((value - edge0) / (edge1 - edge0), 0, 1)
    return t * t * (3 - 2 * t)


# 게시판 칸 모양은 움직이지 않으므로 한 번만 그려 둔다
# 화면의 점마다 "몇 번째 칸에 속하는지"와 "칸 안쪽·테두리에 얼마나 걸치는지"를 구해 둔다
grid_w = COLS * CELL_W + (COLS - 1) * GAP
grid_h = ROWS * CELL_H + (ROWS - 1) * GAP
left, top = (WIDTH - grid_w) / 2, (HEIGHT - grid_h) / 2 + 40
col = np.floor((x - left) / (CELL_W + GAP))
row = np.floor((y - top) / (CELL_H + GAP))
inside_grid = (col >= 0) & (col < COLS) & (row >= 0) & (row < ROWS)
local_x = x - left - col * (CELL_W + GAP) - CELL_W / 2
local_y = y - top - row * (CELL_H + GAP) - CELL_H / 2
qx = np.abs(local_x) - (CELL_W / 2 - RADIUS)
qy = np.abs(local_y) - (CELL_H / 2 - RADIUS)
distance = (
    np.hypot(np.maximum(qx, 0), np.maximum(qy, 0))
    + np.minimum(np.maximum(qx, qy), 0)
    - RADIUS
)
fill = np.where(inside_grid, 1 - smooth(-1.5, 1.5, distance), 0).astype(np.float32)
border = np.where(inside_grid, 1 - smooth(0, 1.6, np.abs(distance + 0.8)), 0).astype(np.float32)
cell_index = np.where(inside_grid, row * COLS + col, 0).astype(np.int32)

# 칸마다 물결이 지나가는 때(왼쪽 위에서 오른쪽 아래로)와 따로 반짝이는 때를 정해 둔다
cols_of = np.arange(COLS * ROWS) % COLS
rows_of = np.arange(COLS * ROWS) // COLS
wave_phase = (cols_of + rows_of * 0.8) / (COLS + ROWS * 0.8)
rng = np.random.default_rng(7)
blink_phase = rng.random(COLS * ROWS)
blink_on = rng.random(COLS * ROWS) < 0.3

# 가장자리를 어둡게 눌러 가운데 글자가 잘 보이게 한다
vignette = 1 - 0.65 * smooth(0.35, 1.05, np.hypot((x / WIDTH - 0.5) * 1.5, y / HEIGHT - 0.5) * 1.6)

# 빛 덩어리 : (가운데 x, 가운데 y, 맴도는 반지름 x, y, 크기, 세기, 한 바퀴에 도는 횟수, 시작 자리)
BLOBS = [
    (0.50, 0.30, 0.16, 0.08, 330, 0.55, 1, 0.0),
    (0.25, 0.65, 0.10, 0.12, 280, 0.35, 1, 0.4),
    (0.78, 0.62, 0.12, 0.10, 300, 0.35, 2, 0.7),
]


def frame(t):
    loop = t / SECONDS  # 0 에서 1 까지 한 바퀴
    turn = 2 * np.pi * loop

    glow = np.zeros((HEIGHT, WIDTH), np.float32)
    for cx, cy, rx, ry, size, power, laps, start in BLOBS:
        angle = turn * laps + 2 * np.pi * start
        bx = (cx + rx * np.cos(angle)) * WIDTH
        by = (cy + ry * np.sin(angle)) * HEIGHT
        glow += power * np.exp(-((x - bx) ** 2 + (y - by) ** 2) / (2 * size * size))

    wave = ((1 + np.cos(2 * np.pi * (loop - wave_phase))) / 2) ** 4
    blink = np.where(blink_on, ((1 + np.cos(2 * np.pi * (2 * loop - blink_phase))) / 2) ** 12, 0)
    light = np.clip(wave + blink, 0, 1)[cell_index]

    image = np.broadcast_to(BACK, (HEIGHT, WIDTH, 3)).copy()
    image += ACCENT * (glow * 0.45)[..., None]
    image += ACCENT * (fill * (0.025 + 0.12 * light))[..., None]
    edge_color = ACCENT * (1 - 0.35 * light[..., None]) + LIGHT * (0.35 * light[..., None])
    image += edge_color * (border * (0.10 + 0.45 * light))[..., None]
    image *= vignette[..., None]
    return (np.clip(image, 0, 1) * 255).astype(np.uint8)


def main():
    OUT.parent.mkdir(exist_ok=True)
    total = FPS * SECONDS
    # 마지막 장면 다음이 곧 첫 장면이 되도록, SECONDS 초 자리(=0초와 같은 장면)는 넣지 않는다
    with imageio.get_writer(
        OUT,
        fps=FPS,
        codec="libx264",
        quality=None,
        pixelformat="yuv420p",
        output_params=["-crf", "20", "-preset", "slow", "-movflags", "+faststart"],
    ) as writer:
        for number in range(total):
            writer.append_data(frame(number / FPS))
            if number % FPS == 0:
                print(f"{number // FPS + 1}/{SECONDS}초 그리는 중")
    print(f"다 만들었습니다 : {OUT}")


if __name__ == "__main__":
    main()
