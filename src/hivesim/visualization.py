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

def visualize_game_board(board_state: BoardState, show_empty_hexes: Optional[List[HexCoordinate]] = None, 
                        show_coordinates: bool = True, delay: float = 0.5, turn_number: int = 0,
                        last_move: Optional[tuple[HexCoordinate, HexCoordinate, str]] = None):
    """Render and refresh a persistent game board in the browser."""
    fig = go.Figure()
    hex_size = 0.95
    icon_size = int(25 * hex_size)

    team_colors = {"black": "#1D1A1A", "white": "#FFFFFF"}
    team_border_colors = {"black": "#000000", "white": "#808080"}

    # Group pieces by their base coordinates to handle stacks (ONLY ONCE!)
    coord_to_pieces = {}
    for piece_id, piece in board_state.pieces.items():
        if not piece.hex_coordinates or piece.location != 'board':
            continue
        coord_tuple = (piece.hex_coordinates.q, piece.hex_coordinates.r, piece.hex_coordinates.s)
        if coord_tuple not in coord_to_pieces:
            coord_to_pieces[coord_tuple] = []
        coord_to_pieces[coord_tuple].append((piece.z_level, piece_id, piece))
    
    # Sort each stack by z_level
    for coord_tuple in coord_to_pieces:
        coord_to_pieces[coord_tuple].sort(key=lambda x: x[0])

    # Create set of occupied coordinates for filtering
    occupied_coords = set(coord_to_pieces.keys())
    
    # Draw empty hexes FIRST, but only for truly empty spaces
    if show_empty_hexes:
        empty_count = 0
        for coord in show_empty_hexes:
            coord_tuple = (coord.q, coord.r, coord.s)
            
            # DEBUG: Check each coordinate
            if coord_tuple in occupied_coords:
                print(f"DEBUG: Skipping occupied {coord_tuple}")
                continue
            
            empty_count += 1
            x, y = hex_to_pixel(coord)
            hx, hy = get_hexagon_vertices(x, y, hex_size)
            fig.add_trace(go.Scatter(x=hx, y=hy, fill='toself', fillcolor='#F5F5F5',
                                     line=dict(color='lightgray', width=2, dash='dot'),
                                     mode='lines', showlegend=False,
                                     hovertemplate=f'Empty<br>{coord}<extra></extra>'))
            coord_text = f'({coord.q},{coord.r},{coord.s})'
            fig.add_trace(go.Scatter(
                x=[x],
                y=[y - 0.35],  # Below center
                mode='text',
                text=[coord_text],
                textfont=dict(size=10, color='gray'),  # Gray color for empty hexes
                showlegend=False,
                hoverinfo='skip'
            ))
        
    # Draw pieces (handling stacks)
    for coord_tuple, stack in coord_to_pieces.items():
        coord = HexCoordinate(q=coord_tuple[0], r=coord_tuple[1], s=coord_tuple[2])
        x, y = hex_to_pixel(coord)
        
        # Draw each piece in the stack with a slight offset for visibility
        for z_level, piece_id, piece in stack:
            # Offset for stacked pieces (shift slightly to show stacking)
            offset_x = z_level * 0.15
            offset_y = z_level * 0.15
            
            hx, hy = get_hexagon_vertices(x + offset_x, y + offset_y, hex_size * (0.95 - z_level * 0.05))

            fill_color = team_colors.get(piece.team, 'lightgray')
            line_color = team_border_colors.get(piece.team, 'gray')
            
            # Make the border thicker for top piece
            border_width = 3 if z_level == stack[-1][0] else 2

            # Hover info showing stack details
            stack_info = f'{piece.__class__.__name__} ({piece.team})<br>'
            stack_info += f'Position: {coord}<br>'
            stack_info += f'Z-level: {z_level}<br>'
            if len(stack) > 1:
                stack_info += f'Stack size: {len(stack)}<br>'
                stack_pieces = [p[2].__class__.__name__ for p in stack]
                stack_info += f'Stack: {" → ".join(stack_pieces)}'

            # Draw hexagon
            fig.add_trace(go.Scatter(
                x=hx, y=hy, fill='toself', fillcolor=fill_color,
                line=dict(color=line_color, width=border_width),
                mode='lines', showlegend=False,
                hovertemplate=f'{stack_info}<extra></extra>'
            ))

            # Draw piece icon (only show top piece icon prominently)
            icon_offset_y = 0
            if z_level == stack[-1][0]:  # Top piece
                fig.add_trace(go.Scatter(
                    x=[x + offset_x], y=[y + offset_y + icon_offset_y], 
                    mode='text', text=[piece.icon],
                    textfont=dict(size=icon_size, color='black'),
                    showlegend=False, hoverinfo='skip'
                ))
            else:  # Lower pieces in stack - show smaller
                fig.add_trace(go.Scatter(
                    x=[x + offset_x], y=[y + offset_y + icon_offset_y], 
                    mode='text', text=[piece.icon],
                    textfont=dict(size=int(icon_size * 0.6), color='gray'),
                    showlegend=False, hoverinfo='skip'
                ))

        # Draw coordinates on top piece only
        if show_coordinates:
            top_z_level = stack[-1][0]
            top_piece = stack[-1][2]
            offset_x = top_z_level * 0.15
            offset_y = top_z_level * 0.15
            
            fill_color = team_colors.get(top_piece.team, 'lightgray')
            label_color = 'black' if fill_color == '#FFFFFF' else 'white'
            
            coord_text = f'({coord.q},{coord.r},{coord.s})'
            if len(stack) > 1:
                coord_text += f' [z{top_z_level}]'
            
            fig.add_trace(go.Scatter(
                x=[x + offset_x],
                y=[y + offset_y - 0.35],  # Below the icon
                mode='text',
                text=[coord_text],
                textfont=dict(size=10, color=label_color),
                showlegend=False,
                hoverinfo='skip'
            ))

        # Draw arrow for last move

    # Draw arrow for last move
    if last_move:
        origin, destination, team = last_move
        x_start, y_start = hex_to_pixel(origin)
        x_end, y_end = hex_to_pixel(destination)
        
        arrow_color = team_border_colors.get(team, 'gray')
        
        # Draw the arrow line
        fig.add_annotation(
            x=x_end,
            y=y_end,
            ax=x_start,
            ay=y_start,
            xref='x',
            yref='y',
            axref='x',
            ayref='y',
            showarrow=True,
            arrowhead=2,
            arrowsize=2,
            arrowwidth=4,
            arrowcolor=arrow_color,
            opacity=0.7
        )

    fig.update_layout(
        title=f'Hive - Game Board (Turn {turn_number})',
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