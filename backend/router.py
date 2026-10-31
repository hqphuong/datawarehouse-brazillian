from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv
# Init
load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configurations


# Import service & repo layers
import service
from schema import StdError

# Standard API routes

@app.route('/health', methods=['GET'])
def hello_world():
    return service.health_check().to_dict()

@app.route('/order-count', methods=['GET'])
def count_orders():
    if request.method == 'GET':
        res = service.count_orders().to_dict()
        # app.logger.info('--------------')
        # app.logger.info(type(res))
        # app.logger.info(res)
        # app.logger.info('--------------')
        return res
    return StdError(500, "Can't count number of orders due to unexpected error").to_dict()

@app.route('/sales-count-date/<string:product_id>', methods=['GET'])
def count_orders_by_date(product_id):
    if request.method == 'GET':
        return service.count_orders_by_date(product_id).to_dict()
    return StdError(500, "Unexpected error").to_dict()

'''
Get query param: request.args.get()
Get '''