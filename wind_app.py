#!/usr/bin/env python3
"""
Jericho Wind Monitor — interactive web dashboard for wind speed and direction.

Run with:
    python3 wind_app.py
Then open http://localhost:8050 in your browser.
"""

import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from pathlib import Path

DATA_FILE = Path(__file__).parent / 'wind_data.csv'
WINDOW_OPTIONS = [1, 2, 5, 10, 30]  # minutes
REFRESH_INTERVAL_MS = 60_000        # auto-reload data every minute

# Compass tick marks for direction y-axis
COMPASS_VALS = [0, 22.5, 45, 67.5, 90, 112.5, 135, 157.5,
                180, 202.5, 225, 247.5, 270, 292.5, 315, 337.5, 360]
COMPASS_LABELS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                  'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW', 'N']


def load_data() -> pd.DataFrame:
    """Load wind CSV and return sorted DataFrame with parsed timestamps."""
    df = pd.read_csv(DATA_FILE)
    df['Date'] = pd.to_datetime(df['Date'])
    return df.sort_values('Date').reset_index(drop=True)


def compute_rolling_stats(df: pd.DataFrame, window_min: int) -> pd.DataFrame:
    """
    Compute trailing rolling statistics over a time-based window.

    Uses a time-based window (e.g. '5min') so data gaps don't inflate the
    effective window size the way a row-count window would.

    Args:
        df: DataFrame with Date, Speed (kts), Direction (deg).
        window_min: Window duration in minutes.

    Returns:
        Copy of df with extra columns: speed_avg, speed_gust, speed_lull, dir_avg.
    """
    df = df.copy().set_index('Date')
    window = f'{window_min}min'

    # Speed: mean, max (gust), min (lull)
    speed_roll = df['Speed (kts)'].rolling(window, min_periods=1)
    df['speed_avg']  = speed_roll.mean()
    df['speed_gust'] = speed_roll.max()
    df['speed_lull'] = speed_roll.min()

    # Direction: circular mean to handle 0/360 wrap-around correctly.
    # (Naively averaging 350° and 10° gives 180°; circular mean gives 0°.)
    rad = np.deg2rad(df['Direction (deg)'].values)
    sin_roll = pd.Series(np.sin(rad), index=df.index).rolling(window, min_periods=1).mean()
    cos_roll = pd.Series(np.cos(rad), index=df.index).rolling(window, min_periods=1).mean()
    df['dir_avg'] = np.rad2deg(np.arctan2(sin_roll, cos_roll)) % 360

    return df.reset_index()


def build_figure(df: pd.DataFrame, window_min: int) -> go.Figure:
    """
    Build the two-subplot Plotly figure.

    Top subplot: wind speed with rolling avg, gust/lull band, and raw scatter.
    Bottom subplot: wind direction with circular rolling avg and raw scatter.

    Args:
        df: Filtered DataFrame.
        window_min: Rolling window size in minutes (used in legend labels).

    Returns:
        Plotly Figure object.
    """
    stats = compute_rolling_stats(df, window_min)
    dates = stats['Date']

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=('Wind Speed', 'Wind Direction'),
        vertical_spacing=0.1,
    )

    # ── Speed subplot ──────────────────────────────────────────────────────────

    # Gust/lull shaded band: invisible lull trace first, then gust fills to it.
    fig.add_trace(go.Scatter(
        x=dates, y=stats['speed_lull'],
        mode='lines',
        line=dict(color='rgba(0,0,0,0)'),
        showlegend=False,
        hoverinfo='skip',
        name='_lull_bound',
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=dates, y=stats['speed_gust'],
        fill='tonexty',
        fillcolor='rgba(30,120,220,0.15)',
        mode='lines',
        line=dict(color='rgba(0,0,0,0)'),
        hoverinfo='skip',
        name='Gust/lull band',
        showlegend=True,
    ), row=1, col=1)

    # Raw 1-minute readings (faint scatter)
    fig.add_trace(go.Scatter(
        x=dates, y=df['Speed (kts)'],
        mode='markers',
        marker=dict(size=4, color='rgba(30,120,220,0.4)'),
        name='Raw speed',
    ), row=1, col=1)

    # Rolling average
    fig.add_trace(go.Scatter(
        x=dates, y=stats['speed_avg'],
        mode='lines',
        line=dict(color='royalblue', width=2.5),
        name=f'{window_min}-min avg',
    ), row=1, col=1)

    # Gust line
    fig.add_trace(go.Scatter(
        x=dates, y=stats['speed_gust'],
        mode='lines',
        line=dict(color='crimson', width=1.5, dash='dot'),
        name='Gust (max)',
    ), row=1, col=1)

    # Lull line
    fig.add_trace(go.Scatter(
        x=dates, y=stats['speed_lull'],
        mode='lines',
        line=dict(color='seagreen', width=1.5, dash='dot'),
        name='Lull (min)',
    ), row=1, col=1)

    # ── Direction subplot ──────────────────────────────────────────────────────

    fig.add_trace(go.Scatter(
        x=dates, y=df['Direction (deg)'],
        mode='markers',
        marker=dict(size=4, color='rgba(230,120,20,0.4)'),
        name='Raw direction',
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=dates, y=stats['dir_avg'],
        mode='lines',
        line=dict(color='darkorange', width=2.5),
        name=f'{window_min}-min avg direction',
    ), row=2, col=1)

    # ── Layout ─────────────────────────────────────────────────────────────────

    fig.update_layout(
        height=680,
        hovermode='x unified',
        dragmode='zoom',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.03,
            xanchor='right',
            x=1,
        ),
        margin=dict(l=70, r=20, t=80, b=50),
        paper_bgcolor='white',
        plot_bgcolor='#f8f9fa',
    )

    fig.update_yaxes(
        title_text='Speed (kts)',
        gridcolor='#e0e0e0',
        zeroline=False,
        row=1, col=1,
    )
    fig.update_yaxes(
        title_text='Direction',
        tickvals=COMPASS_VALS,
        ticktext=COMPASS_LABELS,
        range=[0, 360],
        gridcolor='#e0e0e0',
        zeroline=False,
        row=2, col=1,
    )
    fig.update_xaxes(gridcolor='#e0e0e0')
    fig.update_xaxes(title_text='Time', row=2, col=1)

    return fig


# ── Initial data load to seed the layout ──────────────────────────────────────

_df_init = load_data()
_min_date = _df_init['Date'].min().date()
_max_date = _df_init['Date'].max().date()

# ── App layout ────────────────────────────────────────────────────────────────

app = dash.Dash(__name__, title='Jericho Wind Monitor')

app.layout = html.Div([

    html.H1('Jericho Wind Monitor', style={
        'textAlign': 'center',
        'margin': '16px 0 8px',
        'color': '#1a3a5c',
    }),

    # Controls bar
    html.Div([

        html.Div([
            html.Label('Date Range', style={'fontWeight': 'bold', 'marginBottom': '4px'}),
            dcc.DatePickerRange(
                id='date-range',
                min_date_allowed=_min_date,
                max_date_allowed=_max_date,
                start_date=_min_date,
                end_date=_max_date,
                display_format='YYYY-MM-DD',
            ),
        ], style={'display': 'flex', 'flexDirection': 'column'}),

        html.Div(style={'width': '1px', 'background': '#ccc', 'margin': '0 16px', 'alignSelf': 'stretch'}),

        html.Div([
            html.Label('Averaging Window', style={'fontWeight': 'bold', 'marginBottom': '6px'}),
            dcc.RadioItems(
                id='window-size',
                options=[{'label': f' {w} min ', 'value': w} for w in WINDOW_OPTIONS],
                value=5,
                inline=True,
                inputStyle={'marginRight': '4px'},
                labelStyle={'marginRight': '12px'},
            ),
        ], style={'display': 'flex', 'flexDirection': 'column'}),

        html.Div(style={'flex': '1'}),

        html.Span(id='last-updated', style={
            'color': '#666',
            'fontSize': '13px',
            'alignSelf': 'flex-end',
            'paddingBottom': '2px',
        }),

    ], style={
        'display': 'flex',
        'alignItems': 'center',
        'padding': '12px 20px',
        'background': '#eef2f7',
        'borderRadius': '8px',
        'margin': '0 16px 12px',
        'flexWrap': 'wrap',
        'gap': '8px',
    }),

    dcc.Graph(
        id='wind-graph',
        config={'scrollZoom': True, 'displayModeBar': True, 'modeBarButtonsToRemove': ['select2d', 'lasso2d']},
        style={'margin': '0 16px'},
    ),

    # Reload data every minute to pick up new readings
    dcc.Interval(id='auto-refresh', interval=REFRESH_INTERVAL_MS, n_intervals=0),

], style={
    'maxWidth': '1400px',
    'margin': '0 auto',
    'fontFamily': 'system-ui, -apple-system, sans-serif',
})


# ── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output('date-range', 'min_date_allowed'),
    Output('date-range', 'max_date_allowed'),
    Input('auto-refresh', 'n_intervals'),
    prevent_initial_call=True,  # Layout already seeds the initial values
)
def refresh_date_bounds(_n):
    """Expand date picker bounds when new data arrives, without resetting selection."""
    df = load_data()
    return df['Date'].min().date(), df['Date'].max().date()


@app.callback(
    Output('wind-graph', 'figure'),
    Output('last-updated', 'children'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date'),
    Input('window-size', 'value'),
    Input('auto-refresh', 'n_intervals'),
)
def update_graph(start_date, end_date, window, _n):
    """Reload CSV, apply date filter, and rebuild both subplots."""
    df = load_data()

    if start_date and end_date:
        start = pd.to_datetime(start_date).date()
        end   = pd.to_datetime(end_date).date()
        mask  = (df['Date'].dt.date >= start) & (df['Date'].dt.date <= end)
        df    = df[mask].reset_index(drop=True)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text='No data for selected date range',
            xref='paper', yref='paper',
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=18, color='grey'),
        )
        return fig, 'No data'

    fig = build_figure(df, window or 5)
    last_time = df['Date'].max().strftime('%Y-%m-%d %H:%M')
    return fig, f'Last reading: {last_time}'


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)
