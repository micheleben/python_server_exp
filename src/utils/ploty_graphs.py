import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Create a pandas DataFrame with a datetime index
start_date = datetime(2023, 1, 1)
dates = [start_date + timedelta(days=i) for i in range(100)]

# Sample data with datetime index
df = pd.DataFrame({
    'date': dates,
    'value': np.random.normal(0, 1, 100).cumsum(),
    'category': np.random.choice(['A', 'B', 'C'], 100)
})

# Create interactive time series plot
fig = px.line(df, x='date', y='value', color='category',
              title='Interactive Time Series Plot',
              hover_data=['date', 'value', 'category'])

# Improve the date formatting in the hover tooltip
fig.update_xaxes(
    tickformat="%b %d, %Y",
    title_text="Date"
)

# Display the figure
fig.show()


import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Create date range
start_date = datetime(2023, 1, 1)
dates = [start_date + timedelta(days=i) for i in range(100)]

# Create data
series1 = np.random.normal(0, 1, 100).cumsum()
series2 = np.random.normal(2, 1.5, 100).cumsum()
series3 = np.sin(np.linspace(0, 10, 100)) * 10

# Create figure
fig = go.Figure()

# Add traces one by one (similar to matplotlib's ax.plot)
fig.add_trace(go.Scatter(x=dates, y=series1, mode='lines', name='Series 1'))
fig.add_trace(go.Scatter(x=dates, y=series2, mode='lines', name='Series 2'))
fig.add_trace(go.Scatter(x=dates, y=series3, mode='lines', name='Series 3'))

# Update layout
fig.update_layout(
    title='Multiple Time Series Using Graph Objects',
    xaxis_title='Date',
    yaxis_title='Value',
    legend_title='Series'
)

fig.show()