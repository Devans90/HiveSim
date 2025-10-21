import plotly.graph_objects as go
import numpy as np
from typing import List, Optional
import tempfile, webbrowser, os, time
from game import HexCoordinate, BoardState

_html_path = os.path.join(tempfile.gettempdir(), "hive_live.html")

def hex_to_pixel(coord: HexCoordinate, size: float = 1.0):
    x = size * (3/2 * coord.q)
    y = size * (np.sqrt(3)/2 * coord.q + np.sqrt(3) * coord.r)
    return x, y

def get_hexagon_vertices(x: float, y: float, size: float = 1.0):
    angles = np.linspace(0, 2*np.pi, 7)
    return x + size * np.cos(angles), y + size * np.sin(angles)

def visualize_game_board(board_state: BoardState, show_empty_hexes: Optional[List[HexCoordinate]] = None, show_coordinates: bool = True, delay: float = 0.5):
    """Render and refresh a persistent game board in the browser."""
    fig = go.Figure()
    hex_size = 0.95
    icon_size = int(25 * hex_size)

    team_colors = {"black": "#1D1A1A", "white": "#FFFFFF"}
    team_border_colors = {"black": "#000000", "white": "#808080"}

    # Draw empty hexes
    if show_empty_hexes:
        for coord in show_empty_hexes:
            x, y = hex_to_pixel(coord)
            hx, hy = get_hexagon_vertices(x, y, hex_size)
            fig.add_trace(go.Scatter(x=hx, y=hy, fill='toself', fillcolor='#F5F5F5',
                                     line=dict(color='lightgray', width=1),
                                     mode='lines', showlegend=False,
                                     hovertemplate=f'Empty<br>{coord}<extra></extra>'))

    # Draw pieces
    for piece in board_state.pieces.values():
        if not piece.hex_coordinates or piece.location == 'offboard':
            continue
        coord = piece.hex_coordinates
        x, y = hex_to_pixel(coord)
        hx, hy = get_hexagon_vertices(x, y, hex_size)

        fill_color = team_colors.get(piece.team, 'lightgray')
        line_color = team_border_colors.get(piece.team, 'gray')

        # Draw hexagon
        fig.add_trace(go.Scatter(
            x=hx, y=hy, fill='toself', fillcolor=fill_color,
            line=dict(color=line_color, width=2),
            mode='lines', showlegend=False,
            hovertemplate=f'{piece.__class__.__name__} ({piece.team})<br>{coord}<extra></extra>'
        ))

        # Draw piece icon
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode='text', text=[piece.icon],
            textfont=dict(size=icon_size, color='black'),
            showlegend=False, hoverinfo='skip'
        ))

        # Draw coordinates on top of the piece
        if show_coordinates:
            label_color = 'black' if fill_color == '#FFFFFF' else 'white'
            fig.add_trace(go.Scatter(
            x=[x],
            y=[y + 0.1],  # slight vertical offset to avoid overlapping icon
            mode='text',
            text=[f'({coord.q},{coord.r},{coord.s})'],
            textfont=dict(size=10, color=label_color),
            showlegend=False,
            hoverinfo='skip'
        ))

    fig.update_layout(
        title=f'Hive - Game Board Turn : TODO add this',
        showlegend=False,
        hovermode='closest',
        xaxis=dict(scaleanchor='y', scaleratio=1, showgrid=True, gridcolor='lightgray'),
        yaxis=dict(showgrid=True, gridcolor='lightgray'),
        plot_bgcolor='white',
        width=800,
        height=800,
    )

    # Export to temp HTML and refresh the browser tab
    fig.write_html(_html_path, auto_open=False)
    if not getattr(visualize_game_board, "_opened", False):
        webbrowser.open(f"file://{_html_path}", new=1)
        visualize_game_board._opened = True
    time.sleep(delay)