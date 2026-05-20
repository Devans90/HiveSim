"""
Interactive browser GUI to play Hive against an AI opponent.

This example demonstrates:
- Plotly Dash interactive board (click to select, click to move/place)
- Live board rendering reusing the existing Plotly hex drawing helpers
- Pluggable AI via --ai MODULE.CLASS (defaults to RandomBot)

Usage:
    python play_vs_ai.py                         # Human (white) vs RandomBot
    python play_vs_ai.py --human-color black     # Human plays black
    python play_vs_ai.py --ai mymodule.MyBot     # Use a custom AI
    python play_vs_ai.py --port 8080             # Change server port
    python play_vs_ai.py --delay 0.3             # Pause (s) before AI moves

Open http://localhost:8050 (or the --port value) in your browser.
"""

from __future__ import annotations

import argparse
import importlib
import json
import time
from typing import List, Optional

import plotly.graph_objects as go
from dash import ALL, Dash, Input, Output, State, callback_context, dcc, html
from dash.exceptions import PreventUpdate

from hivesim.game import (
    Game,
    GameState,
    HexCoordinate,
    MovementHelper,
    Turn,
)
from hivesim.robots import RandomBot
from hivesim.visualization import get_hexagon_vertices, hex_to_pixel

# ---------------------------------------------------------------------------
# Visual constants
# ---------------------------------------------------------------------------
_HEX_SIZE = 0.95
_TEAM_FILL = {"black": "#1D1A1A", "white": "#FFFFFF"}
_TEAM_BORDER = {"black": "#000000", "white": "#808080"}

_SEL_FILL = "#FFD700"           # gold – selected piece
_SEL_BORDER = "#FF8C00"
_VALID_FILL = "rgba(0,200,80,0.35)"  # green – valid targets
_VALID_BORDER = "#00AA44"
_MOVABLE_BORDER = "#4169E1"     # royal-blue – human piece that can act

PIECE_ICONS = {
    "ant": "🐜",
    "grasshopper": "🦗",
    "spider": "🕷️",
    "beetle": "🪲",
    "queenbee": "🐝",
    "ladybug": "🐞",
    "mosquito": "🦟",
}

_STYLE_CANCEL_HIDDEN = {"display": "none"}
_STYLE_CANCEL_SHOWN = {
    "display": "block",
    "width": "100%",
    "marginTop": "10px",
    "padding": "8px",
    "cursor": "pointer",
    "border": "2px solid #cc0000",
    "borderRadius": "6px",
    "background": "#fff0f0",
    "color": "#cc0000",
    "fontSize": "14px",
}

# ---------------------------------------------------------------------------
# Module-level game state (single-user local app)
# ---------------------------------------------------------------------------


class _AppState:
    """Mutable singleton that holds the live game and UI selection state."""

    def __init__(self) -> None:
        self.game: Optional[Game] = None
        self.human_color: str = "white"
        self.ai_bot = None
        self.ai_delay: float = 0.5

        # UI selection state
        self.action_mode: str = "idle"  # 'idle' | 'move_target' | 'place_target'
        self.selected_piece_id: Optional[str] = None
        self.selected_piece_type: Optional[str] = None
        self.valid_targets: List[HexCoordinate] = []

        # Outcome
        self.winner: Optional[str] = None
        self.status_msg: str = ""
        self.last_move_arrow: Optional[tuple] = None  # (origin, dest, team)

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


_state = _AppState()


# ---------------------------------------------------------------------------
# Game-logic helpers
# ---------------------------------------------------------------------------


def _valid_placement_targets(piece_type: str, game_state: GameState) -> List[HexCoordinate]:
    """Return all board positions where *piece_type* may legally be placed."""
    result: List[HexCoordinate] = []
    for space in game_state.get_available_spaces():
        t = Turn(
            player=game_state.current_team,
            piece_type=piece_type,
            action_type="place",
            target_coordinates=space,
        )
        try:
            Turn.validate_placement(t, game_state)
            result.append(space)
        except ValueError:
            pass
    return result


def _valid_move_targets(piece_id: str, game_state: GameState) -> List[HexCoordinate]:
    """Return all positions a board piece can legally move to."""
    if not MovementHelper.hive_stays_connected(piece_id, game_state):
        return []
    piece = game_state.all_pieces.get(piece_id)
    return piece.get_valid_moves(game_state) if piece else []


def _available_pieces(game_state: GameState, team: str) -> dict:
    """Map piece_type → count for off-board pieces belonging to *team*."""
    player = game_state.white_player if team == "white" else game_state.black_player
    counts: dict = {}
    for p in player.pieces:
        if p.location == "offboard":
            pt = p.__class__.__name__.lower()
            counts[pt] = counts.get(pt, 0) + 1
    return counts


def _movable_piece_ids(game_state: GameState, team: str) -> set:
    """IDs of board pieces that have at least one valid move."""
    player = game_state.white_player if team == "white" else game_state.black_player
    return {
        p.piece_id
        for p in player.pieces
        if p.location == "board" and _valid_move_targets(p.piece_id, game_state)
    }


def _get_piece_id_at(coord: HexCoordinate, game_state: GameState) -> Optional[str]:
    """Return the top piece_id at *coord*, or None."""
    stack = game_state.board_state.stacks.get((coord.q, coord.r, coord.s))
    return stack[-1] if stack else None


def _must_place_queen(game_state: GameState, team: str) -> bool:
    """Return True if *team* is forced to place their queen this turn."""
    queen = game_state.get_queen(team)
    player_turn = game_state.turn // 2 if team == "white" else (game_state.turn - 1) // 2
    return bool(queen and queen.location == "offboard" and player_turn >= 3)


# ---------------------------------------------------------------------------
# Figure builder
# ---------------------------------------------------------------------------


def build_figure() -> go.Figure:
    """Render the current game state as an interactive Plotly figure."""
    st = _state
    gs = st.game.game_state
    bs = gs.board_state

    fig = go.Figure()
    icon_size = int(25 * _HEX_SIZE)

    vt_set = {(t.q, t.r, t.s) for t in st.valid_targets}

    # Group board pieces by coordinate (handles beetle stacks)
    coord_to_stack: dict = {}
    for piece_id, piece in bs.pieces.items():
        if piece.location != "board" or piece.hex_coordinates is None:
            continue
        key = (piece.hex_coordinates.q, piece.hex_coordinates.r, piece.hex_coordinates.s)
        coord_to_stack.setdefault(key, []).append((piece.z_level, piece_id, piece))
    for key in coord_to_stack:
        coord_to_stack[key].sort(key=lambda x: x[0])

    occupied = set(coord_to_stack.keys())

    # Pieces the human can currently move (highlighted with blue border)
    movable_ids: set = set()
    if not st.winner and gs.current_team == st.human_color and st.action_mode == "idle":
        movable_ids = _movable_piece_ids(gs, st.human_color)

    # ---- Empty / target hexes ----
    available_spaces = gs.get_available_spaces()
    for coord in available_spaces:
        key = (coord.q, coord.r, coord.s)
        if key in occupied:
            continue
        x, y = hex_to_pixel(coord)
        hx, hy = get_hexagon_vertices(x, y, _HEX_SIZE)

        is_target = key in vt_set
        fig.add_trace(go.Scatter(
            x=hx, y=hy,
            fill="toself",
            fillcolor=_VALID_FILL if is_target else "#F5F5F5",
            line=dict(
                color=_VALID_BORDER if is_target else "lightgray",
                width=3 if is_target else 2,
                dash="solid" if is_target else "dot",
            ),
            mode="lines", showlegend=False,
            hovertemplate=f"({coord.q},{coord.r},{coord.s})<extra></extra>",
        ))

    # ---- Board pieces ----
    for key, stack in coord_to_stack.items():
        coord = HexCoordinate(q=key[0], r=key[1], s=key[2])
        x, y = hex_to_pixel(coord)

        for z_level, piece_id, piece in stack:
            ox, oy = x + z_level * 0.15, y + z_level * 0.15
            size = _HEX_SIZE * (0.95 - z_level * 0.05)
            hx, hy = get_hexagon_vertices(ox, oy, size)

            is_top = z_level == stack[-1][0]
            is_selected = piece_id == st.selected_piece_id
            is_target_hex = key in vt_set
            is_movable = piece_id in movable_ids

            if is_selected:
                fill_color, line_color, line_width = _SEL_FILL, _SEL_BORDER, 4
            elif is_target_hex:
                fill_color, line_color, line_width = _VALID_FILL, _VALID_BORDER, 3
            elif is_movable and is_top:
                fill_color = _TEAM_FILL.get(piece.team, "lightgray")
                line_color, line_width = _MOVABLE_BORDER, 3
            else:
                fill_color = _TEAM_FILL.get(piece.team, "lightgray")
                line_color = _TEAM_BORDER.get(piece.team, "gray")
                line_width = 3 if is_top else 2

            hover = (
                f"{piece.__class__.__name__} ({piece.team})<br>"
                f"pos: ({coord.q},{coord.r},{coord.s})  z={z_level}"
            )
            if len(stack) > 1:
                hover += f"<br>stack depth: {len(stack)}"

            fig.add_trace(go.Scatter(
                x=hx, y=hy, fill="toself", fillcolor=fill_color,
                line=dict(color=line_color, width=line_width),
                mode="lines", showlegend=False,
                hovertemplate=f"{hover}<extra></extra>",
            ))

            # Piece icon
            text_size = icon_size if is_top else int(icon_size * 0.6)
            piece_icon = getattr(piece, "icon", None) or PIECE_ICONS.get(
                piece.__class__.__name__.lower(), "?"
            )
            fig.add_trace(go.Scatter(
                x=[ox], y=[oy],
                mode="text", text=[piece_icon],
                textfont=dict(size=text_size, color="black" if is_top else "gray"),
                showlegend=False, hoverinfo="skip",
            ))

        # Coordinate label on top piece
        top_z, _, top_piece = stack[-1]
        ox, oy = x + top_z * 0.15, y + top_z * 0.15
        lbl_color = "black" if _TEAM_FILL.get(top_piece.team) == "#FFFFFF" else "white"
        coord_lbl = f"({coord.q},{coord.r},{coord.s})"
        if len(stack) > 1:
            coord_lbl += f" [z{top_z}]"
        fig.add_trace(go.Scatter(
            x=[ox], y=[oy - 0.38],
            mode="text", text=[coord_lbl],
            textfont=dict(size=10, color=lbl_color),
            showlegend=False, hoverinfo="skip",
        ))

    # ---- Last-move arrow ----
    if st.last_move_arrow:
        origin, dest, team = st.last_move_arrow
        xs, ys = hex_to_pixel(origin)
        xe, ye = hex_to_pixel(dest)
        fig.add_annotation(
            x=xe, y=ye, ax=xs, ay=ys,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=2, arrowsize=2, arrowwidth=4,
            arrowcolor=_TEAM_BORDER.get(team, "gray"), opacity=0.65,
        )

    # ---- Invisible click-target markers ----
    # One per hex centre; customdata=[q, r, s] lets the callback identify clicks.
    click_xs, click_ys, click_cd = [], [], []
    for key, _ in coord_to_stack.items():
        cx, cy = hex_to_pixel(HexCoordinate(q=key[0], r=key[1], s=key[2]))
        click_xs.append(cx)
        click_ys.append(cy)
        click_cd.append([key[0], key[1], key[2]])
    for coord in available_spaces:
        key = (coord.q, coord.r, coord.s)
        if key in occupied:
            continue
        cx, cy = hex_to_pixel(coord)
        click_xs.append(cx)
        click_ys.append(cy)
        click_cd.append([coord.q, coord.r, coord.s])

    if click_xs:
        fig.add_trace(go.Scatter(
            x=click_xs, y=click_ys,
            mode="markers",
            marker=dict(size=48, opacity=0, symbol="hexagon"),
            customdata=click_cd,
            hoverinfo="skip",
            showlegend=False,
            name="_click_targets",
        ))

    turn_label = (
        f"Turn {gs.turn} – "
        + ("Your turn" if gs.current_team == st.human_color else "AI's turn")
        + f"  ({gs.current_team.upper()})"
    )
    if st.winner:
        if st.winner == st.human_color:
            turn_label = "You WIN! 🎉"
        else:
            turn_label = f"AI wins ({st.winner.upper()})"

    fig.update_layout(
        title=dict(text=f"Hive – {turn_label}", font=dict(size=18)),
        showlegend=False,
        hovermode="closest",
        xaxis=dict(
            scaleanchor="y", scaleratio=1,
            showgrid=True, gridcolor="lightgray", zeroline=False,
        ),
        yaxis=dict(showgrid=True, gridcolor="lightgray", zeroline=False),
        plot_bgcolor="white",
        width=800, height=800,
        margin=dict(l=20, r=20, t=60, b=20),
        clickmode="event",
    )
    return fig


# ---------------------------------------------------------------------------
# Side-panel content builder
# ---------------------------------------------------------------------------


def _build_piece_buttons() -> list:
    """Return Dash children for the 'Place a piece' section."""
    st = _state
    gs = st.game.game_state

    if st.winner or gs.current_team != st.human_color:
        return []

    avail = _available_pieces(gs, st.human_color)
    must_q = _must_place_queen(gs, st.human_color)

    if not avail:
        return []

    children = [html.H4("Place a piece", style={"marginBottom": "6px"})]
    for pt, cnt in sorted(avail.items()):
        icon = PIECE_ICONS.get(pt, "?")
        is_active = (
            st.action_mode == "place_target" and st.selected_piece_type == pt
        )
        # If must place queen, disable non-queen buttons
        disabled = must_q and pt != "queenbee"
        btn_style = {
            "display": "block",
            "width": "100%",
            "marginBottom": "6px",
            "padding": "8px",
            "cursor": "not-allowed" if disabled else "pointer",
            "border": "2px solid " + ("#00AA44" if is_active else "#ccc"),
            "borderRadius": "6px",
            "background": "#e8ffe8" if is_active else ("#f0f0f0" if disabled else "#f9f9f9"),
            "fontSize": "15px",
            "textAlign": "left",
            "opacity": "0.45" if disabled else "1",
        }
        children.append(html.Button(
            f"{icon} {pt.capitalize()} ×{cnt}",
            id={"type": "piece-btn", "piece_type": pt},
            style=btn_style,
            n_clicks=0,
            disabled=disabled,
        ))
    return children


def _build_status_section() -> list:
    """Return hint / status children for the side panel."""
    st = _state
    if st.game is None:
        return []

    gs = st.game.game_state
    children = []

    # Status message
    if st.status_msg:
        children.append(html.Div(
            st.status_msg,
            style={"marginBottom": "10px", "color": "#333", "fontStyle": "italic"},
        ))

    # Must-place-queen warning
    if not st.winner and gs.current_team == st.human_color:
        if _must_place_queen(gs, st.human_color):
            children.append(html.Div(
                "⚠ You must place your Queen this turn!",
                style={"color": "#cc0000", "fontWeight": "bold", "marginBottom": "10px"},
            ))

    # Hint text
    if not st.winner:
        if gs.current_team == st.human_color:
            if st.action_mode == "idle":
                hint = (
                    "Click a 🔵 bordered piece on the board to move it, "
                    "or choose a piece type above to place."
                )
            elif st.action_mode == "move_target":
                hint = "Click a green ✅ hex to move the selected piece there."
            else:
                hint = "Click a green ✅ hex to place the selected piece there."
        else:
            hint = "AI is thinking…"
        children.append(html.P(hint, style={"marginTop": "10px", "color": "#666",
                                             "fontSize": "13px"}))

    return children


# ---------------------------------------------------------------------------
# Dash application layout
# ---------------------------------------------------------------------------

app = Dash(__name__, title="HiveSim – Play vs AI")
app.layout = html.Div(
    style={
        "display": "flex",
        "flexDirection": "row",
        "fontFamily": "sans-serif",
        "padding": "16px",
        "gap": "24px",
    },
    children=[
        # Board graph (left)
        dcc.Graph(
            id="board-graph",
            figure=go.Figure(),
            config={"displayModeBar": False},
            style={"flex": "0 0 auto"},
        ),
        # Side panel (right) – static structure, dynamic children
        html.Div(
            style={
                "flex": "1 1 220px",
                "maxWidth": "260px",
                "borderLeft": "1px solid #ddd",
                "paddingLeft": "20px",
                "overflowY": "auto",
            },
            children=[
                html.H2("Hive", style={"marginTop": "0"}),
                # Piece placement buttons (dynamic)
                html.Div(id="piece-buttons"),
                # Cancel button – always in DOM, visibility controlled by callbacks
                html.Button(
                    "✕ Cancel selection",
                    id="cancel-btn",
                    n_clicks=0,
                    style=_STYLE_CANCEL_HIDDEN,
                ),
                # Status / hints (dynamic)
                html.Div(id="status-section"),
            ],
        ),
        # Hidden stores
        dcc.Store(id="trigger-store", data=0),
    ],
)


# ---------------------------------------------------------------------------
# Shared output refresh helper
# ---------------------------------------------------------------------------

def _refresh_outputs():
    """Return (figure, piece_buttons, cancel_style, status_section)."""
    st = _state
    if st.game is None:
        return go.Figure(), [], _STYLE_CANCEL_HIDDEN, []
    cancel_style = _STYLE_CANCEL_SHOWN if st.action_mode != "idle" else _STYLE_CANCEL_HIDDEN
    return (
        build_figure(),
        _build_piece_buttons(),
        cancel_style,
        _build_status_section(),
    )


# ---------------------------------------------------------------------------
# Turn helpers
# ---------------------------------------------------------------------------

def _apply_turn(turn: Turn) -> Optional[str]:
    """Apply *turn* to the global game. Returns winner or None."""
    try:
        _state.game.apply_turn(turn)
    except Exception as exc:
        _state.status_msg = f"Invalid move: {exc}"
        return None
    return _state.game.game_state.check_win_condition()


def _do_ai_turn() -> None:
    """Make the AI play one turn."""
    st = _state
    gs = st.game.game_state

    ql = gs.check_queen_placement_loss()
    if ql:
        st.winner = ql
        return

    if st.ai_delay > 0:
        time.sleep(st.ai_delay)

    ai_color = "black" if st.human_color == "white" else "white"
    ai_turn = st.ai_bot.get_move(gs)

    origin_coord = None
    if ai_turn.action_type == "move" and ai_turn.piece_id:
        piece = gs.all_pieces.get(ai_turn.piece_id)
        if piece and piece.hex_coordinates:
            origin_coord = piece.hex_coordinates

    winner = _apply_turn(ai_turn)

    st.last_move_arrow = (
        (origin_coord, ai_turn.target_coordinates, ai_color)
        if ai_turn.action_type == "move" and origin_coord and ai_turn.target_coordinates
        else None
    )

    if winner:
        st.winner = winner


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@app.callback(
    Output("board-graph", "figure"),
    Output("piece-buttons", "children"),
    Output("cancel-btn", "style"),
    Output("status-section", "children"),
    Input("board-graph", "clickData"),
    Input("trigger-store", "data"),
    prevent_initial_call=False,
)
def on_board_click_or_trigger(click_data, _trigger):
    """Handle board clicks and page-load / side-panel triggers."""
    st = _state
    ctx = callback_context

    if not ctx.triggered or "trigger-store" in ctx.triggered[0]["prop_id"]:
        return _refresh_outputs()

    if click_data is None:
        raise PreventUpdate

    # Parse clicked hex coordinate
    point = click_data["points"][0]
    cd = point.get("customdata")
    if cd is None:
        raise PreventUpdate
    try:
        q, r, s = int(cd[0]), int(cd[1]), int(cd[2])
    except (TypeError, IndexError, ValueError):
        raise PreventUpdate
    clicked = HexCoordinate(q=q, r=r, s=s)

    gs = st.game.game_state

    if st.winner:
        raise PreventUpdate

    # Only process clicks on the human's turn
    if gs.current_team != st.human_color:
        raise PreventUpdate

    ckey = (clicked.q, clicked.r, clicked.s)
    vt_set = {(t.q, t.r, t.s) for t in st.valid_targets}

    # ── Move-target mode ──────────────────────────────────────────────────
    if st.action_mode == "move_target":
        if ckey in vt_set:
            turn = Turn(
                player=st.human_color,
                piece_id=st.selected_piece_id,
                action_type="move",
                target_coordinates=clicked,
            )
            winner = _apply_turn(turn)
            st.action_mode = "idle"
            st.selected_piece_id = None
            st.valid_targets = []
            st.last_move_arrow = None
            st.status_msg = ""
            if winner:
                st.winner = winner
            else:
                ql = gs.check_queen_placement_loss()
                if ql:
                    st.winner = ql
                else:
                    _do_ai_turn()
        else:
            # Clicking a different movable human piece → re-select
            pid = _get_piece_id_at(clicked, gs)
            piece = gs.all_pieces.get(pid) if pid else None
            if piece and piece.team == st.human_color and piece.location == "board":
                targets = _valid_move_targets(pid, gs)
                if targets:
                    st.selected_piece_id = pid
                    st.valid_targets = targets
                    st.status_msg = (
                        f"Selected {piece.__class__.__name__} – "
                        f"{len(targets)} valid target(s)"
                    )
                else:
                    st.action_mode = "idle"
                    st.selected_piece_id = None
                    st.valid_targets = []
                    st.status_msg = "That piece has no valid moves right now."
            else:
                # Clicked empty/opponent hex → cancel
                st.action_mode = "idle"
                st.selected_piece_id = None
                st.valid_targets = []
                st.status_msg = ""

    # ── Place-target mode ─────────────────────────────────────────────────
    elif st.action_mode == "place_target":
        if ckey in vt_set:
            player = gs.white_player if st.human_color == "white" else gs.black_player
            pt_cls = st.selected_piece_type
            pid = next(
                (p.piece_id for p in player.pieces
                 if p.__class__.__name__.lower() == pt_cls and p.location == "offboard"),
                None,
            )
            if pid is None:
                st.status_msg = "No piece available of that type."
                return _refresh_outputs()

            turn = Turn(
                player=st.human_color,
                piece_id=pid,
                piece_type=st.selected_piece_type,
                action_type="place",
                target_coordinates=clicked,
            )
            winner = _apply_turn(turn)
            st.action_mode = "idle"
            st.selected_piece_type = None
            st.valid_targets = []
            st.last_move_arrow = None
            st.status_msg = ""
            if winner:
                st.winner = winner
            else:
                ql = gs.check_queen_placement_loss()
                if ql:
                    st.winner = ql
                else:
                    _do_ai_turn()
        else:
            # Clicked outside valid targets → cancel placement
            st.action_mode = "idle"
            st.selected_piece_type = None
            st.valid_targets = []
            st.status_msg = ""

    # ── Idle – try selecting a board piece to move ─────────────────────────
    else:
        pid = _get_piece_id_at(clicked, gs)
        piece = gs.all_pieces.get(pid) if pid else None
        if piece and piece.team == st.human_color and piece.location == "board":
            targets = _valid_move_targets(pid, gs)
            if targets:
                st.action_mode = "move_target"
                st.selected_piece_id = pid
                st.valid_targets = targets
                st.status_msg = (
                    f"Selected {piece.__class__.__name__} – "
                    f"{len(targets)} valid target(s)"
                )
            else:
                st.status_msg = "That piece has no valid moves right now."

    return _refresh_outputs()


@app.callback(
    Output("trigger-store", "data"),
    Input({"type": "piece-btn", "piece_type": ALL}, "n_clicks"),
    Input("cancel-btn", "n_clicks"),
    State("trigger-store", "data"),
    prevent_initial_call=True,
)
def on_piece_or_cancel(piece_btn_clicks, _cancel_clicks, trigger):
    """Handle piece-type selection buttons and the Cancel button."""
    st = _state
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    prop_id = ctx.triggered[0]["prop_id"]

    # ── Cancel ────────────────────────────────────────────────────────────
    if "cancel-btn" in prop_id:
        st.action_mode = "idle"
        st.selected_piece_id = None
        st.selected_piece_type = None
        st.valid_targets = []
        st.status_msg = ""
        return trigger + 1

    # ── Piece button ──────────────────────────────────────────────────────
    try:
        btn_id = json.loads(prop_id.split(".")[0])
        pt = btn_id.get("piece_type")
    except Exception:
        raise PreventUpdate

    if pt is None:
        raise PreventUpdate

    gs = st.game.game_state
    if gs.current_team != st.human_color or st.winner:
        raise PreventUpdate

    # Must-place-queen rule overrides user choice
    effective_pt = "queenbee" if _must_place_queen(gs, st.human_color) else pt

    targets = _valid_placement_targets(effective_pt, gs)
    if targets:
        st.action_mode = "place_target"
        st.selected_piece_type = effective_pt
        st.selected_piece_id = None
        st.valid_targets = targets
        st.status_msg = (
            f"Placing {effective_pt.capitalize()} – "
            f"{len(targets)} valid hex(es)"
        )
    else:
        st.action_mode = "idle"
        st.selected_piece_type = None
        st.valid_targets = []
        st.status_msg = f"No valid placement spots for {effective_pt}."

    return trigger + 1


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
        description="Play Hive against an AI opponent in your browser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python play_vs_ai.py
  python play_vs_ai.py --human-color black
  python play_vs_ai.py --ai mymodule.MyBot
  python play_vs_ai.py --port 8080 --delay 0.2
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
        "--port", type=int, default=8050,
        help="Port for the Dash web server (default: 8050)",
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

    _state.reset(human_color=args.human_color, ai_bot=ai_bot)
    _state.ai_delay = args.delay

    print("\nHiveSim – Play vs AI")
    print(f"  You   : {args.human_color.upper()}")
    print(f"  AI    : {ai_bot.name} ({ai_color.upper()})")
    print(f"  Open  : http://localhost:{args.port}")
    print("  Press Ctrl-C to quit.\n")

    app.run(debug=False, port=args.port)


if __name__ == "__main__":
    main()
