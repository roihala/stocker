import plotly.express as px
import streamlit as st
import pandas as pd
import requests
import json


def main():

    # ### Configuration
    st.set_page_config(
        page_title="Stocker Alerts - Toolkit",
        page_icon="🧊",
        layout="wide",
        initial_sidebar_state="expanded")

    hide_streamlit_style = """
                <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                </style>
                """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

    ticker = ""
    query = st.experimental_get_query_params()
    if query and "symbol" in query:
        ticker = query["symbol"][0].upper()

    # ### Layout
    ph_header = st.empty()
    ph_form = st.empty()

    c1, c2, c3 = ph_header.columns((1, 4, 1))
    c2.markdown(
        """
        # Stocker Alerts - Toolkit
        **[StockerAlerts](https://www.stocker.watch/)**
        
        `
        The Stocker Alerts toolkit offers a lot of functions to track and see your favorite companies.
        `
        
        """
    )
    c2.header('')

    symbols = get_symbols()["symbols"]
    ddl_default_ix = 0
    is_query = False

    if ticker in symbols:
        ddl_default_ix = symbols.index(ticker)
        is_query = True

    c1, c2, c3 = ph_form.columns((1, 4, 1))
    ph_graph = c2.empty()

    form = c2.form(key='graph-form')
    ticker = form.selectbox('Company', symbols, index=ddl_default_ix)
    submit = form.form_submit_button('Submit')

    if submit or is_query:
        chart = draw_graph(ticker)

        if chart:
            config = {'displayModeBar': False,
                      'scrollZoom': False,
                      'modeBarButtonsToAdd': []
                      }
            ph_graph.plotly_chart(chart, config=config)
        else:
            c2.error('No data for this specific company.')


def draw_graph(ticker: str):
    graph_data = rest("dilution_json/" + ticker)

    try:
        jg = json.loads(graph_data)
        df = pd.DataFrame.from_dict(jg["dataframe"])

        fig = px.line(df, x="date",
                      y=jg["keys_translation"],
                      title=ticker,
                      labels={
                        "date": "",
                        "value": "",
                        "variable": "Component"
                      },
                      width=1000)
        fig.update_traces(mode="markers+lines", hovertemplate=None)
        fig.update_layout(clickmode='event+select', hovermode='x')

    except Exception as e:
        return None

    return fig


def get_symbols():
    return json.loads(rest("companies"))


def rest(url: str):
    req = requests.get("http://127.0.0.1:8000/" + url)
    return req.content.decode('utf-8')


if __name__ == '__main__':
    main()
