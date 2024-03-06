from flask import Flask, jsonify, request
import requests
import json
from flask_cors import CORS, cross_origin
from datetime import datetime, timedelta
import logging

app = Flask(__name__)

# Define allowed origins
allowed_origins = ["http://localhost:3000", " http://192.168.0.15:3000"]


# Initialize CORS with allowed origins
CORS(app, origins=allowed_origins)

logging.basicConfig(level=logging.DEBUG)


api_key = "ZBD3QIPITMQNSPPF"
base_url = "https://www.alphavantage.co/query?"

with open("stock_portfolio.json", "r") as file:
    portfolio = json.load(file)

with open("stock_portfolio_details.json", "r") as file:
    portfolio_details = json.load(file)

def get_stock_final_price(symbol):
    function = "TIME_SERIES_DAILY"
    url = f"{base_url}function={function}&symbol={symbol}&apikey={api_key}&outputsize=compact"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        time_series = data.get("Time Series (Daily)", {})
        if time_series:
            latest_date = max(time_series.keys())
            final_price = float(time_series[latest_date]["4. close"])
            return final_price
        else:
            return None
    else:
        return None
    
def get_historical_stock_prices(symbol, date):
    function = "TIME_SERIES_DAILY"
    url = f"{base_url}function={function}&symbol={symbol}&apikey={api_key}&outputsize=full"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        time_series = data.get("Time Series (Daily)", {})
        if date in time_series:  # Check if the purchase date is in the time series data
            return float(time_series[date]["4. close"])  # Return the closing price for the given date
        else:
            return None  # Or you could choose to return a default value or raise an exception
    else:
        # Handle errors, possibly by logging or retrying
        pass



def calculate_portfolio_value_and_roi(portfolio_details):
    total_invested = 0
    total_current_value = 0
    graph_data = {}

    for investment in portfolio_details['investments']:
        symbol = investment['symbol']
        for inv in investment['investments']:
            invested_amount = inv['invested']
            purchase_date = inv['date']

            # Fetch the historical stock price for the exact purchase date
            purchase_price = get_historical_stock_prices(symbol, purchase_date)
            
            if purchase_price is None:
                print(f"Missing historical price data for {symbol} on {purchase_date}. Skipping this investment.")
                continue

            # Calculate how many shares were bought
            shares_bought = invested_amount / purchase_price

            # Get the current price of the stock
            current_price = get_stock_final_price(symbol)
            if current_price is None:
                print(f"Current price for {symbol} is not available. Skipping this investment.")
                continue

            # Calculate current value of this investment
            current_value = shares_bought * current_price

            # Update totals
            total_invested += invested_amount
            total_current_value += current_value

            # Store data for this investment
            graph_data[symbol] = {
                "purchase_price": purchase_price,
                "current_price": current_price,
                "shares_bought": shares_bought,
                "current_value": current_value,
            }

    # Calculate ROI
    roi = ((total_current_value - total_invested) / total_invested) * 100 if total_invested > 0 else 0

    return total_current_value, roi, graph_data


# API endpoint for the portfolio summary
@app.route('/api/portfolio', methods=['GET'])
def get_portfolio_summary():
    total_value, roi, graph_data = calculate_portfolio_value_and_roi(portfolio_details)
    
    # Create a response object
    response = {
        "total_portfolio_value": total_value,
        "roi": roi,
        "graph_data": graph_data
    }
    
    return jsonify(response)

@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    stock_data = []
    for stock_info in portfolio['stocks']:
        symbol = stock_info['symbol']
        try:
            final_price = get_stock_final_price(symbol)
            if final_price is not None:
                stock_data.append({
                    'symbol': symbol,
                    'price': final_price
                })
            else:
                # Handle the case where final_price is None
                stock_data.append({
                    'symbol': symbol,
                    'error': 'Price data is not available'
                })
        except Exception as e:
            # Log the exception and return an error message for this stock
            app.logger.error(f"Error fetching price for {symbol}: {e}")
            stock_data.append({
                'symbol': symbol,
                'error': 'An error occurred while fetching the price data'
            })
    return jsonify(stock_data)

def calculate_total_amount(symbol):
    total_shares = 0
    current_value = 0
    current_price = get_stock_final_price(symbol)  # Get the current price only once for efficiency

    for investment in portfolio_details['investments']:
        if investment['symbol'] == symbol:
            for inv in investment['investments']:
                purchase_price = get_historical_stock_prices(symbol, inv['date'])
                if purchase_price is not None:
                    shares_bought = inv['invested'] / purchase_price
                    total_shares += shares_bought
                    current_value += shares_bought * current_price

    return total_shares, current_value

def get_last_12_months_closing_prices(symbol):
    function = "TIME_SERIES_MONTHLY"
    url = f"{base_url}function={function}&symbol={symbol}&apikey={api_key}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        # Extract the "Monthly Time Series" data
        time_series = data.get("Monthly Time Series", {})
        
        # Extract the closing prices and dates for the last 12 months
        closing_prices = []
        for date, data_point in sorted(time_series.items(), reverse=True)[:12]:
            closing_price = float(data_point["4. close"])
            closing_prices.append({"date": date, "price": closing_price})

        return closing_prices
    else:
        raise Exception(f"API request failed with status code {response.status_code}")


def calculate_stock_roi(symbol):
    # This example assumes you calculate the ROI based on some logic
    # Make sure to implement this based on your actual data and requirements
    total_investment = 0
    current_value = 0
    current_price = get_stock_final_price(symbol)
    
    for investment in portfolio_details['investments']:
        if investment['symbol'] == symbol:
            for inv in investment['investments']:
                purchase_price = get_historical_stock_prices(symbol, inv['date'])
                if purchase_price is not None:
                    shares_bought = inv['invested'] / purchase_price
                    total_investment += inv['invested']
                    current_value += shares_bought * current_price

    roi = ((current_value - total_investment) / total_investment) * 100 if total_investment > 0 else 0
    return roi


@app.route('/api/stock-details/<symbol>', methods=['GET'])
def get_stock_details(symbol):
    try:
        total_shares, current_value = calculate_total_amount(symbol)
        roi = calculate_stock_roi(symbol)
        closing_prices = get_last_12_months_closing_prices(symbol)
        
        response = {
            "symbol": symbol,
            "total_shares": total_shares,
            "current_value": current_value,
            "roi": roi,
            "closing_prices": closing_prices  # Updated to include the new data
        }
        
        return jsonify(response), 200
    except Exception as e:
        app.logger.error(f"Error getting stock details for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # This enables better error messages in development.
    app.config["DEBUG"] = True
    # Start the Flask app
    app.run()