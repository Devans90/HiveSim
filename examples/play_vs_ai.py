"""
Interactive pygame GUI to play Hive against an AI opponent.

This example demonstrates:
- pygame-based board rendering with flat-top hexagons
- Click to select a piece or placement hex; valid moves highlighted in green
- Sidebar with off-board piece inventory for placement
- AI auto-plays in a background thread so the window stays responsive
- Pluggable AI via --ai MODULE.CLASS (defaults to RandomBot)

Usage:
    python play_vs_ai.py                         # Human (white) vs RandomBot
    python play_vs_ai.py --human-color black     # Human plays black
    python play_vs_ai.py --ai mymodule.MyBot     # Use a custom AI
    python play_vs_ai.py --delay 0.5             # Pause (s) before AI moves
"""

from __future__ import annotations

import argparse
import importlib
import math
import threading
import time
from typing import List, Optional, Tuple

import pygame

from hivesim.game import (
    Game,
    GameState,
    HexCoordinate,
    MovementHelper,
    Turn,
)
from hivesim.robots import RandomBot

# ---------------------------------------------------------------------------
# Window / layout constants
# ---------------------------------------------------------------------------
WIN_W, WIN_H = 1100, 750
BOARD_W = 800          # pixels wide for the hex board
PANEL_X = BOARD_W      # left edge of the side panel
PANEL_W = WIN_W - BOARD_W

HEX_SIZE = 56          # pixels from centre to vertex (flat-top)

# Colours (R, G, B)
BG_COLOR = (240, 240, 240)
BOARD_BG = (255, 255, 255)
GRID_COLOR = (200, 200, 200)
WHITE_FILL = (255, 255, 255)
WHITE_BORDER = (130, 130, 130)
BLACK_FILL = (30, 28, 28)
BLACK_BORDER = (0, 0, 0)
SEL_FILL = (255, 215, 0)        # gold – selected piece
SEL_BORDER = (220, 120, 0)
VALID_FILL = (0, 200, 80, 100)  # semi-transparent green (RGBA surface)
VALID_BORDER = (0, 160, 60)
MOVABLE_BORDER = (65, 105, 225)  # royal-blue – pieces the human can move
EMPTY_HEX_FILL = (248, 248, 248)
EMPTY_HEX_BORDER = (190, 190, 190)
PANEL_BG = (248, 248, 252)
PANEL_TEXT = (40, 40, 40)
BTN_NORMAL = (225, 225, 235)
BTN_HOVER = (200, 215, 255)
BTN_ACTIVE = (170, 220, 170)
BTN_DISABLED = (210, 210, 210)
BTN_TEXT = (30, 30, 30)
BTN_TEXT_DISABLED = (150, 150, 150)
AI_BTN_BG = (220, 235, 255)
WARN_COLOR = (200, 0, 0)
STATUS_COLOR = (80, 80, 80)

# Piece display text (fallback when emoji font unavailable)
PIECE_LABELS = {
    "ant": "ANT",
    "grasshopper": "GRS",
    "spider": "SPD",
    "beetle": "BTL",
    "queenbee": "QBE",
    "ladybug": "LDY",
    "mosquito": "MOS",
}

# Custom pygame event fired when the AI finishes its turn
AI_DONE = pygame.USEREVENT + 1

# ---------------------------------------------------------------------------
# Hex ↔ pixel helpers   (flat-top orientation, matching visualization.py)
# ---------------------------------------------------------------------------

def hex_to_screen(q: int, r: int, size: float, ox: float, oy: float) -> Tuple[float, float]:
    """Flat-top hex: convert cube coords to screen pixels."""
    x = size * (3 / 2 * q)
    y = size * (math.sqrt(3) / 2 * q + math.sqrt(3) * r)
    return ox + x, oy + y


def screen_to_hex(sx: float, sy: float, size: float, ox: float, oy: float) -> HexCoordinate:
    """Convert screen pixels to the nearest flat-top hex cube coordinate.

    Formulae are the inverse of ``hex_to_screen`` (flat-top orientation).
    Reference: https://www.redblobgames.com/grids/hexagons/#pixel-to-hex
    """
    x = (sx - ox) / size
    y = (sy - oy) / size
    q = 2 / 3 * x
    r = -1 / 3 * x + math.sqrt(3) / 3 * y
    s = -q - r
    # Cube-coordinate rounding
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    else:
        rs = -rq - rr
    return HexCoordinate(q=rq, r=rr, s=rs)


def hex_vertices(cx: float, cy: float, size: float) -> List[Tuple[float, float]]:
    """Return the 6 screen vertices of a flat-top hex centred at (cx, cy)."""
    pts = []
    for i in range(6):
        angle = math.radians(60 * i)
        pts.append((cx + size * math.cos(angle), cy + size * math.sin(angle)))
    return pts


# ---------------------------------------------------------------------------
# Game-logic helpers
# ---------------------------------------------------------------------------

def _valid_placement_targets(piece_type: str, gs: GameState) -> List[HexCoordinate]:
    result: List[HexCoordinate] = []
    for space in gs.get_available_spaces():
        t = Turn(
            player=gs.current_team,
            piece_type=piece_type,
            action_type="place",
            target_coordinates=space,
        )
        try:
            Turn.validate_placement(t, gs)
            result.append(space)
        except ValueError:
            pass
    return result


def _valid_move_targets(piece_id: str, gs: GameState) -> List[HexCoordinate]:
    if not MovementHelper.hive_stays_connected(piece_id, gs):
        return []
    piece = gs.all_pieces.get(piece_id)
    return piece.get_valid_moves(gs) if piece else []


def _available_pieces(gs: GameState, team: str) -> dict:
    """Map piece_type → count for off-board pieces of *team*."""
    player = gs.white_player if team == "white" else gs.black_player
    counts: dict = {}
    for p in player.pieces:
        if p.location == "offboard":
            pt = p.__class__.__name__.lower()
            counts[pt] = counts.get(pt, 0) + 1
    return counts


def _movable_piece_ids(gs: GameState, team: str) -> set:
    player = gs.white_player if team == "white" else gs.black_player
    return {
        p.piece_id
        for p in player.pieces
        if p.location == "board" and _valid_move_targets(p.piece_id, gs)
    }


def _must_place_queen(gs: GameState, team: str) -> bool:
    queen = gs.get_queen(team)
    player_turn = gs.turn // 2 if team == "white" else (gs.turn - 1) // 2
    return bool(queen and queen.location == "offboard" and player_turn >= 3)


def _get_top_piece_id(coord: HexCoordinate, gs: GameState) -> Optional[str]:
    stack = gs.board_state.stacks.get((coord.q, coord.r, coord.s))
    return stack[-1] if stack else None


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

class AppState:
    """Single mutable object holding all game + UI state."""

    def __init__(self) -> None:
        self.game: Optional[Game] = None
        self.human_color: str = "white"
        self.ai_bot = None
        self.ai_delay: float = 0.5

        # UI selection
        self.action_mode: str = "idle"          # 'idle' | 'move_target' | 'place_target'
        self.selected_piece_id: Optional[str] = None
        self.selected_piece_type: Optional[str] = None
        self.valid_targets: List[HexCoordinate] = []

        # Outcome
        self.winner: Optional[str] = None
        self.status_msg: str = ""
        self.last_move_arrow: Optional[Tuple] = None  # (origin, dest, team)

        # AI thread guard
        self.ai_thinking: bool = False

        # Board viewport (offset so hexes are centred)
        self.board_offset: Tuple[float, float] = (BOARD_W / 2, WIN_H / 2)

    def reset(self, human_color: str, ai_bot) -> None:
        self.game = Game(game_state=GameState(verbose=False))
        self.human_color = human_color
        self.ai_bot = ai_bot
        self.action_mode = "idle"
        self.selected_piece_id = None
        self.selected_piece_type = None
        self.valid_targets = []
        self.winner = None
        self.status_msg = ""
        self.last_move_arrow = None
        self.ai_thinking = False
        self.board_offset = (BOARD_W / 2, WIN_H / 2)


# ---------------------------------------------------------------------------
# AI threading
# ---------------------------------------------------------------------------

def _run_ai(state: AppState) -> None:
    """Background thread: let AI pick and apply its move, then post AI_DONE."""
    gs = state.game.game_state

    ql = gs.check_queen_placement_loss()
    if ql:
        state.winner = ql
        pygame.event.post(pygame.event.Event(AI_DONE))
        return

    if state.ai_delay > 0:
        time.sleep(state.ai_delay)

    ai_color = "black" if state.human_color == "white" else "white"
    ai_turn = state.ai_bot.get_move(gs)

    origin_coord = None
    if ai_turn.action_type == "move" and ai_turn.piece_id:
        piece = gs.all_pieces.get(ai_turn.piece_id)
        if piece and piece.hex_coordinates:
            origin_coord = piece.hex_coordinates

    try:
        state.game.apply_turn(ai_turn)
    except Exception as exc:
        state.status_msg = f"AI error: {exc}"
        state.ai_thinking = False
        pygame.event.post(pygame.event.Event(AI_DONE))
        return

    state.last_move_arrow = (
        (origin_coord, ai_turn.target_coordinates, ai_color)
        if ai_turn.action_type == "move" and origin_coord and ai_turn.target_coordinates
        else None
    )

    winner = gs.check_win_condition()
    if winner:
        state.winner = winner

    state.ai_thinking = False
    pygame.event.post(pygame.event.Event(AI_DONE))


def trigger_ai(state: AppState) -> None:
    """Start the AI background thread if it's the AI's turn and it isn't already running."""
    if state.ai_thinking or state.winner:
        return
    gs = state.game.game_state
    ai_color = "black" if state.human_color == "white" else "white"
    if gs.current_team != ai_color:
        return
    state.ai_thinking = True
    threading.Thread(target=_run_ai, args=(state,), daemon=True).start()


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _compute_board_offset(state: AppState) -> Tuple[float, float]:
    """Auto-centre the hex board based on which hexes are visible."""
    gs = state.game.game_state
    all_coords: List[HexCoordinate] = []
    for piece in gs.board_state.pieces.values():
        if piece.location == "board" and piece.hex_coordinates:
            all_coords.append(piece.hex_coordinates)
    for coord in gs.get_available_spaces():
        all_coords.append(coord)

    if not all_coords:
        return BOARD_W / 2, WIN_H / 2

    # Use hex_to_screen with a zero origin to get raw pixel positions
    pixels = [hex_to_screen(c.q, c.r, HEX_SIZE, 0, 0) for c in all_coords]
    xs = [p[0] for p in pixels]
    ys = [p[1] for p in pixels]
    cx = (max(xs) + min(xs)) / 2
    cy = (max(ys) + min(ys)) / 2
    return BOARD_W / 2 - cx, WIN_H / 2 - cy


def draw_hex_filled(surface: pygame.Surface, pts: List, fill: Tuple,
                    border: Tuple, width: int = 2) -> None:
    pygame.draw.polygon(surface, fill, pts)
    pygame.draw.polygon(surface, border, pts, width)


def draw_board(surface: pygame.Surface, state: AppState,
               font_sm: pygame.font.Font, font_md: pygame.font.Font) -> None:
    """Draw all hexes, pieces, and highlights onto *surface*."""
    gs = state.game.game_state
    ox, oy = state.board_offset
    vt_set = {(t.q, t.r, t.s) for t in state.valid_targets}

    # Group pieces by hex coord (stacks)
    coord_to_stack: dict = {}
    for pid, piece in gs.board_state.pieces.items():
        if piece.location != "board" or piece.hex_coordinates is None:
            continue
        key = (piece.hex_coordinates.q, piece.hex_coordinates.r, piece.hex_coordinates.s)
        coord_to_stack.setdefault(key, []).append((piece.z_level, pid, piece))
    for k in coord_to_stack:
        coord_to_stack[k].sort(key=lambda x: x[0])

    occupied = set(coord_to_stack.keys())

    # Movable pieces when it's the human's idle turn
    movable_ids: set = set()
    if (not state.winner and not state.ai_thinking
            and gs.current_team == state.human_color
            and state.action_mode == "idle"):
        movable_ids = _movable_piece_ids(gs, state.human_color)

    board_rect = pygame.Rect(0, 0, BOARD_W, WIN_H)

    # One shared SRCALPHA surface reused for all semi-transparent overlays
    overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)

    # ── Empty / target hexes ────────────────────────────────────────────────
    for coord in gs.get_available_spaces():
        key = (coord.q, coord.r, coord.s)
        if key in occupied:
            continue
        cx, cy = hex_to_screen(coord.q, coord.r, HEX_SIZE, ox, oy)
        if not board_rect.collidepoint(cx, cy):
            continue
        pts = hex_vertices(cx, cy, HEX_SIZE - 2)
        is_target = key in vt_set
        if is_target:
            overlay.fill((0, 0, 0, 0))
            pygame.draw.polygon(overlay, (0, 200, 80, 100), pts)
            surface.blit(overlay, (0, 0))
            pygame.draw.polygon(surface, VALID_BORDER, pts, 3)
        else:
            draw_hex_filled(surface, pts, EMPTY_HEX_FILL, EMPTY_HEX_BORDER, 1)

        # Coordinate label
        lbl = font_sm.render(f"{coord.q},{coord.r}", True, (160, 160, 160))
        surface.blit(lbl, (cx - lbl.get_width() // 2, cy - lbl.get_height() // 2))

    # ── Board pieces ────────────────────────────────────────────────────────
    for key, stack in coord_to_stack.items():
        coord = HexCoordinate(q=key[0], r=key[1], s=key[2])
        cx, cy = hex_to_screen(coord.q, coord.r, HEX_SIZE, ox, oy)
        if not board_rect.collidepoint(cx, cy):
            continue

        is_target_hex = key in vt_set

        for z, pid, piece in stack:
            ox2, oy2 = cx + z * 8, cy + z * 8  # stack offset
            size = HEX_SIZE - 2 - z * 3
            pts = hex_vertices(ox2, oy2, size)

            is_selected = pid == state.selected_piece_id
            is_top = z == stack[-1][0]
            is_movable = pid in movable_ids

            # Fill & border colours
            base_fill = WHITE_FILL if piece.team == "white" else BLACK_FILL
            base_border = WHITE_BORDER if piece.team == "white" else BLACK_BORDER

            if is_selected:
                fill, border, bw = SEL_FILL, SEL_BORDER, 4
            elif is_target_hex:
                overlay.fill((0, 0, 0, 0))
                pygame.draw.polygon(overlay, (0, 200, 80, 100), pts)
                surface.blit(overlay, (0, 0))
                fill, border, bw = base_fill, VALID_BORDER, 3
            elif is_movable and is_top:
                fill, border, bw = base_fill, MOVABLE_BORDER, 3
            else:
                fill, border, bw = base_fill, base_border, 2

            draw_hex_filled(surface, pts, fill, border, bw)

            # Piece label
            piece_type = piece.__class__.__name__.lower()
            lbl_str = PIECE_LABELS.get(piece_type, piece_type[:3].upper())
            lbl_color = (30, 30, 30) if piece.team == "white" else (220, 220, 220)
            if not is_top:
                lbl_color = (100, 100, 100) if piece.team == "white" else (140, 140, 140)
            fnt = font_md if is_top else font_sm
            lbl = fnt.render(lbl_str, True, lbl_color)
            surface.blit(lbl, (ox2 - lbl.get_width() // 2, oy2 - lbl.get_height() // 2))

        # Coordinate label (top piece)
        top_z, _, top_piece = stack[-1]
        ox2, oy2 = cx + top_z * 8, cy + top_z * 8
        coord_str = f"{coord.q},{coord.r}"
        if len(stack) > 1:
            coord_str += f"[z{top_z}]"
        lbl_color = (80, 80, 80) if top_piece.team == "white" else (180, 180, 180)
        lbl = font_sm.render(coord_str, True, lbl_color)
        surface.blit(lbl, (ox2 - lbl.get_width() // 2, oy2 + HEX_SIZE - 20))

    # ── Last-move arrow ─────────────────────────────────────────────────────
    if state.last_move_arrow:
        origin, dest, team = state.last_move_arrow
        sx, sy = hex_to_screen(origin.q, origin.r, HEX_SIZE, ox, oy)
        ex, ey = hex_to_screen(dest.q, dest.r, HEX_SIZE, ox, oy)
        arrow_col = (100, 100, 230) if team == "white" else (200, 100, 100)
        pygame.draw.line(surface, arrow_col, (int(sx), int(sy)), (int(ex), int(ey)), 3)
        # Arrowhead
        angle = math.atan2(ey - sy, ex - sx)
        for da in (0.5, -0.5):
            ax = ex - 18 * math.cos(angle + da)
            ay = ey - 18 * math.sin(angle + da)
            pygame.draw.line(surface, arrow_col, (int(ex), int(ey)), (int(ax), int(ay)), 3)


# ---------------------------------------------------------------------------
# Side-panel drawing + button hit-testing
# ---------------------------------------------------------------------------

class Button:
    """Simple rectangular button."""

    def __init__(self, rect: pygame.Rect, label: str,
                 data=None, disabled: bool = False, active: bool = False):
        self.rect = rect
        self.label = label
        self.data = data       # arbitrary payload (e.g. piece_type string)
        self.disabled = disabled
        self.active = active

    def draw(self, surface: pygame.Surface, font: pygame.font.Font,
             mouse_pos: Tuple[int, int]) -> None:
        hovered = self.rect.collidepoint(mouse_pos) and not self.disabled
        if self.disabled:
            bg = BTN_DISABLED
            tc = BTN_TEXT_DISABLED
        elif self.active:
            bg = BTN_ACTIVE
            tc = BTN_TEXT
        elif hovered:
            bg = BTN_HOVER
            tc = BTN_TEXT
        else:
            bg = BTN_NORMAL
            tc = BTN_TEXT
        pygame.draw.rect(surface, bg, self.rect, border_radius=6)
        pygame.draw.rect(surface, (160, 160, 180), self.rect, 2, border_radius=6)
        lbl = font.render(self.label, True, tc)
        surface.blit(lbl, (self.rect.x + 10, self.rect.centery - lbl.get_height() // 2))

    def hit(self, pos: Tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos) and not self.disabled


def build_panel_buttons(state: AppState, panel_y_start: int,
                        btn_w: int, btn_h: int) -> List[Button]:
    """Build the list of clickable buttons for the side panel."""
    if state.game is None:
        return []
    gs = state.game.game_state
    buttons: List[Button] = []
    y = panel_y_start
    px = PANEL_X + 12

    if not state.winner and not state.ai_thinking and gs.current_team == state.human_color:
        avail = _available_pieces(gs, state.human_color)
        must_q = _must_place_queen(gs, state.human_color)

        for pt, cnt in sorted(avail.items()):
            disabled = must_q and pt != "queenbee"
            is_active = (state.action_mode == "place_target"
                         and state.selected_piece_type == pt)
            label = f"{PIECE_LABELS.get(pt, pt.upper())}  x{cnt}"
            buttons.append(Button(
                rect=pygame.Rect(px, y, btn_w, btn_h),
                label=label,
                data=("place", pt),
                disabled=disabled,
                active=is_active,
            ))
            y += btn_h + 6

    # Cancel button
    if state.action_mode != "idle":
        y += 8
        buttons.append(Button(
            rect=pygame.Rect(px, y, btn_w, btn_h),
            label="✕  Cancel",
            data=("cancel", None),
            active=False,
        ))

    return buttons


def draw_panel(surface: pygame.Surface, state: AppState,
               buttons: List[Button], font_sm: pygame.font.Font,
               font_md: pygame.font.Font, font_lg: pygame.font.Font,
               mouse_pos: Tuple[int, int]) -> None:
    """Draw the right-side panel."""
    # Background
    panel_rect = pygame.Rect(PANEL_X, 0, PANEL_W, WIN_H)
    pygame.draw.rect(surface, PANEL_BG, panel_rect)
    pygame.draw.line(surface, (190, 190, 200), (PANEL_X, 0), (PANEL_X, WIN_H), 2)

    y = 16
    # Title
    title = font_lg.render("Hive", True, PANEL_TEXT)
    surface.blit(title, (PANEL_X + 12, y))
    y += title.get_height() + 6

    # Turn info
    gs = state.game.game_state
    if state.winner:
        if state.winner == state.human_color:
            info = "You WIN! 🎉"
            col = (0, 140, 0)
        else:
            info = f"AI wins ({state.winner.upper()})"
            col = WARN_COLOR
    elif state.ai_thinking:
        info = f"Turn {gs.turn}  –  AI thinking…"
        col = (100, 100, 180)
    elif gs.current_team == state.human_color:
        info = f"Turn {gs.turn}  –  Your turn ({state.human_color.upper()})"
        col = (0, 120, 0)
    else:
        info = f"Turn {gs.turn}  –  AI's turn ({gs.current_team.upper()})"
        col = (100, 100, 180)
    lbl = font_sm.render(info, True, col)
    surface.blit(lbl, (PANEL_X + 12, y))
    y += lbl.get_height() + 12

    # Must-place-queen warning
    if (not state.winner and not state.ai_thinking
            and gs.current_team == state.human_color
            and _must_place_queen(gs, state.human_color)):
        warn = font_sm.render("⚠ Must place Queen now!", True, WARN_COLOR)
        surface.blit(warn, (PANEL_X + 12, y))
        y += warn.get_height() + 8

    # Section heading: place piece
    if (not state.winner and not state.ai_thinking
            and gs.current_team == state.human_color):
        hdr = font_sm.render("Place a piece:", True, PANEL_TEXT)
        surface.blit(hdr, (PANEL_X + 12, y))
        y += hdr.get_height() + 6

    # Piece buttons
    for btn in buttons:
        btn.draw(surface, font_sm, mouse_pos)

    # Status message
    y_status = WIN_H - 110
    if state.status_msg:
        for line in state.status_msg.split("\n"):
            lbl = font_sm.render(line, True, STATUS_COLOR)
            surface.blit(lbl, (PANEL_X + 12, y_status))
            y_status += lbl.get_height() + 2

    # Hint text
    y_hint = WIN_H - 80
    if not state.winner:
        if state.ai_thinking:
            hint = "AI is calculating…"
        elif gs.current_team == state.human_color:
            if state.action_mode == "idle":
                hint = "Click a blue-bordered piece to move"
                hint2 = "or pick a type above to place."
            elif state.action_mode == "move_target":
                hint = "Click a green hex to move there."
                hint2 = ""
            else:
                hint = "Click a green hex to place."
                hint2 = ""
        else:
            hint, hint2 = "", ""

        if hint:
            h1 = font_sm.render(hint, True, (110, 110, 110))
            surface.blit(h1, (PANEL_X + 12, y_hint))
        if state.action_mode == "idle" and not state.ai_thinking:
            if gs.current_team == state.human_color:
                h2 = font_sm.render(hint2, True, (110, 110, 110))
                surface.blit(h2, (PANEL_X + 12, y_hint + h1.get_height() + 2))

    # Key legend
    y_leg = WIN_H - 30
    leg = font_sm.render("ESC / R-click: cancel selection", True, (150, 150, 150))
    surface.blit(leg, (PANEL_X + 12, y_leg))


# ---------------------------------------------------------------------------
# Human click handling
# ---------------------------------------------------------------------------

def handle_board_click(mx: int, my: int, state: AppState) -> None:
    """Process a left click at screen position (mx, my) on the board area."""
    gs = state.game.game_state
    if state.winner or state.ai_thinking or gs.current_team != state.human_color:
        return

    ox, oy = state.board_offset
    clicked = screen_to_hex(mx, my, HEX_SIZE, ox, oy)
    ckey = (clicked.q, clicked.r, clicked.s)
    vt_set = {(t.q, t.r, t.s) for t in state.valid_targets}

    # ── Move-target mode ─────────────────────────────────────────────────────
    if state.action_mode == "move_target":
        if ckey in vt_set:
            pid = state.selected_piece_id
            turn = Turn(
                player=state.human_color,
                piece_id=pid,
                action_type="move",
                target_coordinates=clicked,
            )
            try:
                state.game.apply_turn(turn)
            except Exception as exc:
                state.status_msg = f"Invalid move: {exc}"
                return
            state.action_mode = "idle"
            state.selected_piece_id = None
            state.valid_targets = []
            state.last_move_arrow = None
            state.status_msg = ""
            winner = gs.check_win_condition()
            if winner:
                state.winner = winner
            elif gs.check_queen_placement_loss():
                state.winner = gs.check_queen_placement_loss()
            else:
                trigger_ai(state)
        else:
            # Maybe clicking a different movable piece → re-select
            pid = _get_top_piece_id(clicked, gs)
            piece = gs.all_pieces.get(pid) if pid else None
            if piece and piece.team == state.human_color and piece.location == "board":
                targets = _valid_move_targets(pid, gs)
                if targets:
                    state.selected_piece_id = pid
                    state.valid_targets = targets
                    state.status_msg = (
                        f"Selected {piece.__class__.__name__} – "
                        f"{len(targets)} valid target(s)"
                    )
                    return
            # Cancel
            state.action_mode = "idle"
            state.selected_piece_id = None
            state.valid_targets = []
            state.status_msg = ""

    # ── Place-target mode ────────────────────────────────────────────────────
    elif state.action_mode == "place_target":
        if ckey in vt_set:
            player = gs.white_player if state.human_color == "white" else gs.black_player
            pt_cls = state.selected_piece_type
            pid = next(
                (p.piece_id for p in player.pieces
                 if p.__class__.__name__.lower() == pt_cls and p.location == "offboard"),
                None,
            )
            if pid is None:
                state.status_msg = "No piece of that type available."
                return
            turn = Turn(
                player=state.human_color,
                piece_id=pid,
                piece_type=state.selected_piece_type,
                action_type="place",
                target_coordinates=clicked,
            )
            try:
                state.game.apply_turn(turn)
            except Exception as exc:
                state.status_msg = f"Invalid placement: {exc}"
                return
            state.action_mode = "idle"
            state.selected_piece_type = None
            state.valid_targets = []
            state.last_move_arrow = None
            state.status_msg = ""
            winner = gs.check_win_condition()
            if winner:
                state.winner = winner
            elif gs.check_queen_placement_loss():
                state.winner = gs.check_queen_placement_loss()
            else:
                trigger_ai(state)
        else:
            # Cancel
            state.action_mode = "idle"
            state.selected_piece_type = None
            state.valid_targets = []
            state.status_msg = ""

    # ── Idle – try selecting a board piece to move ────────────────────────────
    else:
        pid = _get_top_piece_id(clicked, gs)
        piece = gs.all_pieces.get(pid) if pid else None
        if piece and piece.team == state.human_color and piece.location == "board":
            targets = _valid_move_targets(pid, gs)
            if targets:
                state.action_mode = "move_target"
                state.selected_piece_id = pid
                state.valid_targets = targets
                state.status_msg = (
                    f"Selected {piece.__class__.__name__} – "
                    f"{len(targets)} valid target(s)"
                )
            else:
                state.status_msg = "That piece has no valid moves right now."


def handle_panel_click(mx: int, my: int, state: AppState,
                       buttons: List[Button]) -> None:
    """Process a left click on the side panel area."""
    for btn in buttons:
        if btn.hit((mx, my)):
            kind, payload = btn.data
            if kind == "cancel":
                state.action_mode = "idle"
                state.selected_piece_id = None
                state.selected_piece_type = None
                state.valid_targets = []
                state.status_msg = ""
            elif kind == "place":
                pt = payload
                gs = state.game.game_state
                if _must_place_queen(gs, state.human_color):
                    pt = "queenbee"
                targets = _valid_placement_targets(pt, gs)
                if targets:
                    state.action_mode = "place_target"
                    state.selected_piece_type = pt
                    state.selected_piece_id = None
                    state.valid_targets = targets
                    state.status_msg = (
                        f"Placing {pt.capitalize()} – "
                        f"{len(targets)} valid hex(es)"
                    )
                else:
                    state.status_msg = f"No valid spots for {pt}."
            break


# ---------------------------------------------------------------------------
# Main game loop
# ---------------------------------------------------------------------------

def run(state: AppState) -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("HiveSim – Play vs AI")

    # Fonts (fallback to system default if no monospace found)
    font_sm = pygame.font.SysFont("monospace", 14)
    font_md = pygame.font.SysFont("monospace", 18, bold=True)
    font_lg = pygame.font.SysFont("monospace", 28, bold=True)

    clock = pygame.time.Clock()

    # If AI goes first (human plays black), trigger immediately
    trigger_ai(state)

    PANEL_BTN_W = PANEL_W - 24
    PANEL_BTN_H = 34
    PANEL_BTN_Y_START = 120  # approximate; recomputed each frame

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()

        # Recompute board offset so the board stays centred
        state.board_offset = _compute_board_offset(state)

        # Build side-panel buttons (recomputed each frame – cheap)
        buttons = build_panel_buttons(state, PANEL_BTN_Y_START, PANEL_BTN_W, PANEL_BTN_H)

        # ── Event handling ─────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == AI_DONE:
                # AI thread finished; just redraw (state already updated)
                pass

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    state.action_mode = "idle"
                    state.selected_piece_id = None
                    state.selected_piece_type = None
                    state.valid_targets = []
                    state.status_msg = ""

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 3:   # right-click → cancel
                    state.action_mode = "idle"
                    state.selected_piece_id = None
                    state.selected_piece_type = None
                    state.valid_targets = []
                    state.status_msg = ""

                elif event.button == 1:  # left-click
                    mx, my = event.pos
                    if mx < BOARD_W:
                        handle_board_click(mx, my, state)
                    else:
                        handle_panel_click(mx, my, state, buttons)

        # ── Drawing ────────────────────────────────────────────────────────
        screen.fill(BOARD_BG, (0, 0, BOARD_W, WIN_H))
        screen.fill(PANEL_BG, (PANEL_X, 0, PANEL_W, WIN_H))

        draw_board(screen, state, font_sm, font_md)
        draw_panel(screen, state, buttons, font_sm, font_md, font_lg, mouse_pos)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def load_bot_class(class_path: str):
    """Load a bot class from a dotted module path, e.g. 'mymodule.MyBot'."""
    if "." not in class_path:
        raise ValueError(f"Bot class path must be 'module.ClassName', got: {class_path}")
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Play Hive against an AI opponent in a pygame window",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python play_vs_ai.py
  python play_vs_ai.py --human-color black
  python play_vs_ai.py --ai mymodule.MyBot
  python play_vs_ai.py --delay 0.2
        """,
    )
    parser.add_argument(
        "--human-color", choices=["white", "black"], default="white",
        help="Color for the human player (default: white)",
    )
    parser.add_argument(
        "--ai", default=None, metavar="MODULE.CLASS",
        help=(
            "Dotted path to a custom AI bot class, e.g. 'mymodule.MyBot'. "
            "Must accept team= and name= keyword args. Default: RandomBot."
        ),
    )
    parser.add_argument(
        "--delay", type=float, default=0.5,
        help="Seconds to pause before the AI moves (default: 0.5)",
    )
    args = parser.parse_args()

    ai_color = "black" if args.human_color == "white" else "white"
    ai_bot = None

    if args.ai:
        try:
            BotClass = load_bot_class(args.ai)
            ai_bot = BotClass(team=ai_color, name=args.ai.split(".")[-1])
            print(f"Loaded custom AI: {args.ai}")
        except Exception as exc:
            print(f"Warning: could not load '{args.ai}': {exc}. Using RandomBot.")

    if ai_bot is None:
        ai_bot = RandomBot(team=ai_color, name="RandomBot")

    state = AppState()
    state.reset(human_color=args.human_color, ai_bot=ai_bot)
    state.ai_delay = args.delay

    print(f"HiveSim – Play vs AI")
    print(f"  You   : {args.human_color.upper()}")
    print(f"  AI    : {ai_bot.name} ({ai_color.upper()})")
    print(f"  Window: {WIN_W}×{WIN_H}  |  ESC or R-click to cancel selection")

    run(state)


if __name__ == "__main__":
    main()
