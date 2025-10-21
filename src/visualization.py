import plotly.graph_objects as go
import numpy as np
from typing import List, Optional
from game import HexCoordinate, BoardState

def hex_to_pixel(coord: HexCoordinate, size: float = 1.0):
    """Convert hex coordinate to pixel position for plotting."""
    x = size * (3/2 * coord.q)
    y = size * (np.sqrt(3)/2 * coord.q + np.sqrt(3) * coord.r)
    return x, y

def get_hexagon_vertices(x: float, y: float, size: float = 1.0):
    """Get vertices of a hexagon centered at (x, y)."""
    angles = np.linspace(0, 2*np.pi, 7)  # 7 points to close the hexagon
    vertices_x = x + size * np.cos(angles)
    vertices_y = y + size * np.sin(angles)
    return vertices_x, vertices_y

def visualize_game_board(board_state: BoardState, show_empty_hexes: Optional[List[HexCoordinate]] = None, show_coordinates: bool = True):
    """
    Visualize game pieces on hex coordinates
    """
    fig = go.Figure()
    
    hex_size = 0.95
    icon_size = int(25 * hex_size)
    
    # CUSTOMIZATION: Team colors mapping
    team_colors = {
        "black": "#1D1A1A",  # black team
        "white": "#FFFFFF",  # white team
    }
    
    team_border_colors = {
        "black": "#000000",  # black border
        "white": "#808080",  # white border for visibility
    }
    
    # Draw empty hexes if provided
    if show_empty_hexes:
        for coord in show_empty_hexes:
            center_x, center_y = hex_to_pixel(coord, size=1.0)
            hex_x, hex_y = get_hexagon_vertices(center_x, center_y, hex_size)
            
            fig.add_trace(go.Scatter(
                x=hex_x,
                y=hex_y,
                fill='toself',
                fillcolor='#F5F5F5',
                line=dict(color='lightgray', width=1),
                mode='lines',
                showlegend=False,
                name='',
                hovertemplate=f'Empty<br>q={coord.q}, r={coord.r}, s={coord.s}<extra></extra>',
            ))
            
            if show_coordinates:
                fig.add_trace(go.Scatter(
                    x=[center_x],
                    y=[center_y],
                    mode='text',
                    text=[f'({coord.q},{coord.r},{coord.s})'],
                    textfont=dict(size=10, color='darkgray'),
                    showlegend=False,
                    name='',
                    hoverinfo='skip'
                ))
        
    # Draw hexes with game pieces (only pieces that are on the board)
    for piece in board_state.pieces.values():
        # Skip pieces without coordinates (offboard pieces)
        if piece.hex_coordinates is None:
            continue
            
        # Skip pieces that are explicitly offboard
        if piece.location == 'offboard':
            continue
        
        coord = piece.hex_coordinates
        center_x, center_y = hex_to_pixel(coord, size=1.0)
        hex_x, hex_y = get_hexagon_vertices(center_x, center_y, hex_size)
        
        # Get team colors
        fill_color = team_colors.get(piece.team, 'lightgray')
        line_color = team_border_colors.get(piece.team, 'gray')
        
        # Draw hexagon
        fig.add_trace(go.Scatter(
            x=hex_x,
            y=hex_y,
            fill='toself',
            fillcolor=fill_color,
            line=dict(color=line_color, width=2),
            mode='lines',
            showlegend=False,
            name='',
            hovertemplate=f'{piece.__class__.__name__} ({piece.team})<br>Position: ({coord.q},{coord.r},{coord.s})<extra></extra>',
        ))
        
        # Add piece icon
        fig.add_trace(go.Scatter(
            x=[center_x],
            y=[center_y],
            mode='text',
            text=[piece.icon],
            textfont=dict(size=icon_size, color='black'),
            showlegend=False,
            name='',
            hoverinfo='skip'
        ))
        
        # Add coordinate labels (optional)
        if show_coordinates:
            fig.add_trace(go.Scatter(
                x=[center_x],
                y=[center_y - 0.3],
                mode='text',
                text=[f'({coord.q},{coord.r},{coord.s})'],
                textfont=dict(size=8, color='gray'),
                showlegend=False,
                name='',
                hoverinfo='skip'
            ))

    fig.update_layout(
        title='Hive - digitally made by Dan',
        hovermode='closest',
        xaxis=dict(
            scaleanchor='y',
            scaleratio=1,
            showgrid=True,
            zeroline=True,
            gridcolor='lightgray'
        ),
        yaxis=dict(
            showgrid=True,
            zeroline=True,
            gridcolor='lightgray'
        ),
        plot_bgcolor='white',
        width=800,
        height=800,
    )
    
    fig.show()