from __future__ import print_function

import random
import logging

import grpc

import inventory_pb2, inventory_pb2_grpc
import cost_pb2, cost_pb2_grpc
import user_pb2, user_pb2_grpc
import order_pb2, order_pb2_grpc

from flask import Flask, render_template, request, make_response, session, url_for, redirect
from protobuf_to_dict import protobuf_to_dict
from functools import wraps


app = Flask(__name__)
app.secret_key='\xee\xf1-\xc4\xec\x98\x9b\xc2\xba\xe2\x8e\xa0\x91o\x93M\xec\xd8`\xf6\t/\xff\xad'

def requires_login(f):
        @wraps(f)
        def decorated(*args, **kwargs):
                status = session.get('logged_in', False)
                if not status:
                        return redirect(url_for('home'))
                return f(*args, **kwargs)
        return decorated

def requires_admin(f):
        @wraps(f)
        def decorated(*args, **kwargs):
                status = session.get('access_level', user_pb2.AccessLevel.ADMIN)
                if not status:
                        return redirect(url_for('home'))
                return f(*args, **kwargs)
        return decorated



@app.route('/')
def home():
    if session.get('logged_in') is None:
        return render_template('login.html')
    with grpc.insecure_channel(target='localhost:9092',
            options=[('grpc.lb_policy_name', 'pick_first'),
            ('grpc.enable_retries', 0),
            ('grpc.keepalive_timeout_ms', 10000)
            ]) as channel:
        invStub = inventory_pb2_grpc.InventoryStub(channel)
        costStub = cost_pb2_grpc.CostStub(channel)
        loc = session.get('location')
        response = invStub.GetStore(inventory_pb2.ShortRequest(Location=str(loc)),
                                 timeout=10)
        if response == None:
            return redirect(url_for('home'))
        xys = protobuf_to_dict(response, use_enum_labels=True)
        xy = xys['SList']
        storeItems = []
        for item in xy:
            response = costStub.GetUnitCost(cost_pb2.CostRequest(ID=str(item['ID'])),
                                     timeout=10)
            item['PPU'] = response.Price
            storeItems.append(item)
    return render_template('home.html', items=storeItems), 200

@app.route('/login', methods=['POST'])
def login():
    username = str(request.form['username'])
    pw = str(request.form['password'])
    with grpc.insecure_channel(target='localhost:9092',options=[('grpc.lb_policy_name', 'pick_first'),('grpc.enable_retries', 0),('grpc.keepalive_timeout_ms', 10000)]) as channel:
        userStub = user_pb2_grpc.UserStub(channel)
        response = userStub.Login(user_pb2.AuthsRequest(Username= username, Pass= pw), timeout=10)
        #print(response)
        if (response.AccessLevel != user_pb2.AccessLevel.DEFAULT):
            session['logged_in'] = True
            session['name'] = username
            session['location'] = response.Location
            session['access_level'] = response.AccessLevel
            return redirect(url_for('home'))
        else:
            session['logged_in'] = False
            return render_template('login.html')

@app.route('/logout')
@requires_login
def logout():
    [session.pop(key) for key in list(session.keys())]
    return render_template('login.html')

@app.route('/review')
@requires_login
def result():
    with grpc.insecure_channel(target='localhost:9092',
            options=[('grpc.lb_policy_name', 'pick_first'),
            ('grpc.enable_retries', 0),
            ('grpc.keepalive_timeout_ms', 10000)
            ]) as channel:
        invStub = inventory_pb2_grpc.InventoryStub(channel)
        response = invStub.CheckShort(inventory_pb2.ShortRequest(Location=session.get('location')),
                                 timeout=10)

        xy = protobuf_to_dict(response, use_enum_labels=True)['SList']
    return render_template('review.html', items=xy, loc=session.get('location')), 200

@app.route('/disc/<id>')
def itemDisc(id):
    with grpc.insecure_channel(target='localhost:9092',
                               options=[('grpc.lb_policy_name', 'pick_first'),
                                        ('grpc.enable_retries', 0),
                                        ('grpc.keepalive_timeout_ms', 10000)
                                       ]) as channel:
        invStub = inventory_pb2_grpc.InventoryStub(channel)
        costStub = cost_pb2_grpc.CostStub(channel)
        respStock = invStub.GetStock(inventory_pb2.LevelRequest(ID=str(id), Location = session.get('location')), timeout=10)
        xy = protobuf_to_dict(respStock, use_enum_labels=True)
        respCost = costStub.GetUnitCost(cost_pb2.CostRequest(ID=str(xy['ID'])),timeout=10)
        xy['Price'] = respCost.Price
    return render_template('itemdisc.html', item=xy), 200

@app.route('/run')
@requires_admin
def run():
    with grpc.insecure_channel(target='localhost:9092',
                               options=[('grpc.lb_policy_name', 'pick_first'),
                                        ('grpc.enable_retries', 0),
                                        ('grpc.keepalive_timeout_ms', 10000)
                                       ]) as channel:
        stub = inventory_pb2_grpc.InventoryStub(channel)
        response = stub.GetStock(inventory_pb2.LevelRequest(ID='44', Location = "Beef City"),
                                 timeout=10)
        xy = protobuf_to_dict(response, use_enum_labels=True)
    return xy, 200

if __name__ == '__main__':
    logging.basicConfig()
    #Hard Coding of Location
    #session['logged_in'] = False
    app.run(host='0.0.0.0', port=80, debug=False)
