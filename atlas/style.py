"""Shared visual system, independent of analytics and data contracts."""

from pathlib import Path
from typing import Any

import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

PALETTE = ["#286c60", "#59675f", "#89968b", "#3d5147", "#abb4a7", "#243e35"]
MAP_SCALE = [[0, "#edf0df"], [0.25, "#ccd8b7"], [0.5, "#90b394"], [0.75, "#508d7a"], [1, "#195c52"]]


def apply_style() -> None:
    st.html(f"<style>{Path(__file__).with_name('styles.css').read_text()}</style>")
    pio.templates["atlas"] = go.layout.Template(
        layout={
            "font": {"family": "Arial, sans-serif", "size": 12, "color": "#4e605b"},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "colorway": PALETTE,
            "margin": {"l": 10, "r": 10, "t": 45, "b": 20},
            "xaxis": {
                "showgrid": False,
                "zeroline": False,
                "tickfont": {"size": 11},
                "title": {"font": {"size": 11}},
                "automargin": True,
            },
            "yaxis": {
                "gridcolor": "#edf0e9",
                "zeroline": False,
                "tickfont": {"size": 11},
                "title": {"font": {"size": 11}},
                "automargin": True,
            },
            "legend": {"orientation": "h", "y": 1.15, "x": 0, "title": {"text": ""}, "font": {"size": 10}},
            "hoverlabel": {"bgcolor": "#fff", "bordercolor": "#dce3d8", "font": {"size": 12}},
        }
    )
    px.defaults.template = "atlas"
    px.defaults.color_discrete_sequence = PALETTE
    px.defaults.color_continuous_scale = MAP_SCALE


def chart(figure: go.Figure, **kwargs: Any) -> Any:
    figure.update_layout(template="atlas", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return st.plotly_chart(figure, theme=None, config={"displaylogo": False}, **kwargs)


def section(number: str, title: str) -> None:
    st.markdown(f'<div class="atlas-section">{number} / {title}</div>', unsafe_allow_html=True)
