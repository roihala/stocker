import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc

import uvicorn
import dash
from starlette.middleware.wsgi import WSGIMiddleware

import plotly.express as px
from fastapi import FastAPI

from src.factory import Factory
from src.alert.tickers import alerters
from runnable import Runnable
from src.read import readers


class Rest(Runnable):
    def run(self):
        update_dash()
        app.mount("/dilution", WSGIMiddleware(dash_app.server))
        uvicorn.run(app)


rest = Rest()
app = FastAPI()
dash_app = dash.Dash(__name__, requests_pathname_prefix="/dilution/")


def update_dash():
    ticker = 'SOAN'
    securities_df = readers.Securities(mongo_db=rest._mongo_db, ticker=ticker) \
        .get_sorted_history(filter_rows=True, filter_cols=True).replace('', 0)

    keys_translation = {key: translation for key, translation in alerters.Securities.get_keys_translation().items() if
                        key in securities_df.columns}
    securities_df = securities_df.rename(columns=keys_translation)

    fig = px.line(securities_df, x="date",
                  y=list(keys_translation.values()),
                  title=ticker)
    fig.update_traces(mode="markers+lines", hovertemplate=None)
    fig.update_layout(clickmode='event+select', hovermode='x')

    styles = {
        'pre': {
            'border': 'thin lightgrey solid',
            'overflowX': 'scroll'
        }
    }

    dash_app.layout = html.Div([
        dcc.Graph(figure=fig),

        html.Div([
            dcc.Markdown("""
                        **Hover Data**

                        Mouse over values in the graph.
                    """),
            html.Pre(id='hover-data', style=styles['pre'])
        ], className='three columns')
    ],
        [
            html.Div([
                # represents the URL bar, doesn't render anything
                dcc.Location(id='url', refresh=False),

                dcc.Link('Navigate to "/"', href='/'),
                html.Br(),
                dcc.Link('Navigate to "/page-2"', href='/page-2'),

                # content will be rendered in this element
                html.Div(id='page-content')
            ])
        ]
    )

    # app.layout = html.Div([
    #     # represents the URL bar, doesn't render anything
    #     dcc.Location(id='url', refresh=False),
    #
    #     dcc.Link('Navigate to "/"', href='/'),
    #     html.Br(),
    #     dcc.Link('Navigate to "/page-2"', href='/page-2'),
    #
    #     # content will be rendered in this element
    #     html.Div(id='page-content')
    # ])

    return dash_app


@dash_app.callback(dash.dependencies.Output('page-content', 'children'),
                   [dash.dependencies.Input('url', 'pathname')])
def display_page(pathname):
    if pathname == '/kaki':
        return html.Div([
            dbc.Alert("This is a danger alert. Scary!", color="danger", dismissable=True, is_open=True)
        ])

    return html.Div([
        html.H3('You are on page {}'.format(pathname))
    ])

@app.get('/')
def root():
    return {'kaki': 'pipi'}


if __name__ == "__main__":
    rest.run()
