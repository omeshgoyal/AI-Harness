#!/usr/bin/env python3
"""A basic terminal Snake game. Zero dependencies (stdlib curses only).

Controls:
    Arrow keys / WASD  - move
    P                  - pause / unpause
    Q                  - quit
"""

import curses
import random
import sys
from collections import deque

TICK_MS = 110          # starting speed (lower = faster)
MIN_TICK_MS = 55       # fastest speed the game will ramp to
TICK_STEP = 3          # ms shaved off per food eaten
MIN_HEIGHT = 5         # smallest playfield we consider playable
MIN_WIDTH = 10

# (dy, dx) keyed by direction name
DIRECTIONS = {
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1),
}

OPPOSITE = {
    "up": "down",
    "down": "up",
    "left": "right",
    "right": "left",
}

# key -> direction name
KEYMAP = {
    curses.KEY_UP: "up", curses.KEY_DOWN: "down",
    curses.KEY_LEFT: "left", curses.KEY_RIGHT: "right",
    ord("w"): "up", ord("s"): "down", ord("a"): "left", ord("d"): "right",
}


class Snake:
    def __init__(self, height, width):
        self.height = height
        self.width = width
        self.reset()

    def reset(self):
        cy, cx = self.height // 2, self.width // 2
        # body[0] is the head; start with length 3, heading right
        self.body = deque([(cy, cx), (cy, cx - 1), (cy, cx - 2)])
        self.direction = "right"
        self.pending = "right"   # buffered turn applied on next tick
        self.score = 0
        self.alive = True
        self.place_food()

    def occupied(self):
        return set(self.body)

    def place_food(self):
        free = [
            (y, x)
            for y in range(self.height)
            for x in range(self.width)
            if (y, x) not in self.occupied()
        ]
        self.food = random.choice(free) if free else None

    def turn(self, direction):
        # Ignore a reversal of the direction we're already committed to.
        if direction != OPPOSITE[self.direction]:
            self.pending = direction

    def step(self):
        self.direction = self.pending
        dy, dx = DIRECTIONS[self.direction]
        hy, hx = self.body[0]
        new_head = (hy + dy, hx + dx)
        ny, nx = new_head

        # Wall collision
        if not (0 <= ny < self.height and 0 <= nx < self.width):
            self.alive = False
            return

        # Self collision. The tail square frees up this tick unless we grow,
        # so ignore it for the collision check.
        will_grow = new_head == self.food
        body_set = self.occupied()
        if not will_grow:
            body_set.discard(self.body[-1])
        if new_head in body_set:
            self.alive = False
            return

        self.body.appendleft(new_head)
        if will_grow:
            self.score += 1
            self.place_food()
        else:
            self.body.pop()
        return will_grow


def fit(text, limit):
    """Truncate text so it never overflows `limit` columns."""
    return text[:limit] if limit > 0 else ""


def draw(stdscr, snake, paused, tick_ms):
    stdscr.erase()
    height, width = snake.height, snake.width

    # Border
    stdscr.addstr(0, 0, "+" + "-" * width + "+")
    for y in range(height):
        stdscr.addstr(y + 1, 0, "|")
        stdscr.addstr(y + 1, width + 1, "|")
    stdscr.addstr(height + 1, 0, "+" + "-" * width + "+")

    # Food
    if snake.food is not None:
        fy, fx = snake.food
        stdscr.addstr(fy + 1, fx + 1, "*", curses.A_BOLD)

    # Snake
    hy, hx = snake.body[0]
    stdscr.addstr(hy + 1, hx + 1, "@", curses.A_BOLD)
    for (by, bx) in list(snake.body)[1:]:
        stdscr.addstr(by + 1, bx + 1, "o")

    # Status line, shrunk to fit narrow terminals.
    avail = width + 2
    speed = max(1, round(1000 / tick_ms))
    full = f" Score: {snake.score}   Speed: {speed}   P: pause   Q: quit "
    compact = f" {snake.score} | P:pause Q:quit "
    status = full if len(full) <= avail else compact
    stdscr.addstr(height + 2, 0, fit(status, avail))

    if paused:
        msg = fit(" PAUSED ", avail)
        stdscr.addstr(height // 2 + 1, max(0, (width - len(msg)) // 2), msg, curses.A_REVERSE)

    stdscr.refresh()


def game_over(stdscr, snake, height, width):
    lines = [
        " GAME OVER ",
        f" Final score: {snake.score} ",
        "",
        " Press R to play again, Q to quit ",
    ]
    top = height // 2
    avail = width + 2
    for i, line in enumerate(lines):
        line = fit(line, avail)
        col = max(0, (width - len(line)) // 2)
        attr = curses.A_REVERSE if i in (0, 3) else curses.A_NORMAL
        stdscr.addstr(top + i, col, line, attr)
    stdscr.refresh()

    while True:
        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            return False
        if key in (ord("r"), ord("R")):
            return True


def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.nodelay(True)
    curses.use_default_colors()

    # Size the playfield to the terminal. The frame needs `height + 3` rows
    # (top border, playfield, bottom border, status) and `width + 2` columns.
    term_h, term_w = stdscr.getmaxyx()
    height = term_h - 4
    width = term_w - 3
    if height < MIN_HEIGHT or width < MIN_WIDTH:
        stdscr.erase()
        msg = f" Terminal too small: need at least {MIN_WIDTH + 2}x{MIN_HEIGHT + 3}. "
        stdscr.addstr(0, 0, fit(msg, term_w - 1))
        stdscr.addstr(1, 0, " Press any key to exit. ")
        stdscr.nodelay(False)
        stdscr.getch()
        return

    snake = Snake(height, width)
    tick_ms = TICK_MS
    paused = False
    last_move = 0
    now = 0

    while True:
        key = stdscr.getch()

        if key in (ord("q"), ord("Q")):
            return
        if key in (ord("p"), ord("P")):
            paused = not paused
            last_move = now  # don't instantly move on unpause

        if key in KEYMAP:
            snake.turn(KEYMAP[key])

        if not paused:
            if now - last_move >= tick_ms:
                last_move = now
                if snake.step():
                    tick_ms = max(MIN_TICK_MS, tick_ms - TICK_STEP)

        draw(stdscr, snake, paused, tick_ms)

        if not snake.alive:
            if game_over(stdscr, snake, height, width):
                snake.reset()
                tick_ms = TICK_MS
                paused = False
                last_move = now
            else:
                return

        curses.napms(8)
        now += 8


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        sys.exit(0)
