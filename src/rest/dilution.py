import plotly.express as px


import dash


import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc

from src import alerters_factory
from src.alert.tickers import alerters
from src.read import readers


def init_dash(mongo_db):
    dash_app = dash.Dash(__name__, requests_pathname_prefix="/dilution/")

    ticker = 'SOAN'
    securities_df = readers.Securities(mongo_db=mongo_db, ticker=ticker) \
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
    ]
    )

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

    return dash_app
